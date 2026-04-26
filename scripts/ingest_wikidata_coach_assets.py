from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

import psycopg2
import requests
from PIL import Image, ImageOps


ROOT_DIR = Path(__file__).resolve().parents[1]
VISUAL_ASSETS_ROOT = ROOT_DIR / "data" / "visual_assets"
COACH_ASSETS_DIR = VISUAL_ASSETS_ROOT / "coaches"
MANIFEST_PATH = VISUAL_ASSETS_ROOT / "manifests" / "coaches.json"

WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
COMMONS_FILEPATH_URL = "https://commons.wikimedia.org/wiki/Special:FilePath/{file_name}?width=512"
WIKIPEDIA_API_URL = "https://{lang}.wikipedia.org/w/api.php"
TARGET_SIZE = 512
REQUEST_TIMEOUT_SECONDS = 30
USER_AGENT = "football-analytics/coach-assets-ingest (+local)"
MAX_DOWNLOAD_RETRIES = 5
REQUEST_PAUSE_SECONDS = 0.6


@dataclass
class CoachRow:
    coach_identity_id: int
    provider: str
    provider_coach_id: int
    coach_name: str
    wikidata_qid: str | None = None


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def safe_text(value: str) -> str:
    return value.encode("cp1252", errors="replace").decode("cp1252")


def resolve_db_dsn() -> str:
    env_dsn = (os.getenv("FOOTBALL_PG_DSN") or os.getenv("DATABASE_URL") or "").strip()
    if env_dsn:
        return env_dsn.replace("postgresql+psycopg2://", "postgresql://")

    return "postgresql://football:football@127.0.0.1:5432/football_dw"


def fetch_missing_coaches(conn: Any, limit: int | None) -> list[CoachRow]:
    query = """
        select
            coach_identity_id,
            provider,
            provider_coach_id,
            coalesce(nullif(trim(display_name), ''), nullif(trim(canonical_name), ''), concat('Coach ', coach_identity_id::text)) as coach_name
        from mart.coach_identity
        where provider = 'wikidata'
          and nullif(trim(image_url), '') is null
        order by coach_identity_id
    """
    params: tuple[Any, ...] = ()
    if limit is not None:
        query += " limit %s"
        params = (limit,)

    with conn.cursor() as cur:
        cur.execute(query, params)
        return [CoachRow(*row) for row in cur.fetchall()]


def fetch_sportmonks_placeholder_coaches_with_wikidata_ref(conn: Any, limit: int | None) -> list[CoachRow]:
    query = """
        with linked as (
            select
                ci.coach_identity_id,
                ci.provider,
                ci.provider_coach_id,
                coalesce(nullif(trim(ci.display_name), ''), nullif(trim(ci.canonical_name), ''), concat('Coach ', ci.coach_identity_id::text)) as coach_name,
                min(ref.external_person_id) as wikidata_qid
            from mart.coach_identity ci
            join mart.coach_identity_source_ref ref
              on ref.coach_identity_id = ci.coach_identity_id
            where ci.provider = 'sportmonks'
              and ci.image_url ilike '%%placeholder%%'
              and ref.source in ('wikidata', 'wikidata_P286_team_to_person', 'wikidata_P6087_person_to_team')
              and ref.external_person_id ~ '^Q[0-9]+$'
            group by ci.coach_identity_id, ci.provider, ci.provider_coach_id, coach_name
        )
        select coach_identity_id, provider, provider_coach_id, coach_name, wikidata_qid
        from linked
        order by coach_identity_id
    """
    if limit is not None:
        query += " limit %s"

    with conn.cursor() as cur:
        if limit is None:
            cur.execute(query)
        else:
            cur.execute(query, (limit,))
        return [CoachRow(*row) for row in cur.fetchall()]


def sync_database_from_existing_files(conn: Any) -> int:
    updated = 0
    with conn.cursor() as cur:
        for asset_path in sorted(COACH_ASSETS_DIR.glob("*.png")):
            try:
                coach_identity_id = int(asset_path.stem)
            except ValueError:
                continue

            cur.execute(
                """
                update mart.coach_identity
                   set image_url = %s,
                       updated_at = now()
                 where coach_identity_id = %s
                   and nullif(trim(image_url), '') is null
                """,
                (f"/api/visual-assets/coaches/{coach_identity_id}", coach_identity_id),
            )
            updated += cur.rowcount
    return updated


def prune_orphaned_database_urls(conn: Any) -> int:
    existing_ids = {int(asset_path.stem) for asset_path in COACH_ASSETS_DIR.glob("*.png") if asset_path.stem.isdigit()}
    pruned = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            select coach_identity_id
              from mart.coach_identity
             where image_url like '/api/visual-assets/coaches/%'
            """
        )
        coach_ids = [int(row[0]) for row in cur.fetchall()]

        for coach_identity_id in coach_ids:
            if coach_identity_id in existing_ids:
                continue
            cur.execute(
                """
                update mart.coach_identity
                   set image_url = null,
                       updated_at = now()
                 where coach_identity_id = %s
                   and image_url = %s
                """,
                (coach_identity_id, f"/api/visual-assets/coaches/{coach_identity_id}"),
            )
            pruned += cur.rowcount
    return pruned


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {
            "category": "coaches",
            "generated_at": utc_now_iso(),
            "summary": {
                "category": "coaches",
                "targets_total": 0,
                "cached_local_total": 0,
                "downloaded_total": 0,
                "download_failed_total": 0,
                "missing_source_url_total": 0,
                "assets_present_total": 0,
                "assets_missing_total": 0,
                "manifest_path": "data/visual_assets/manifests/coaches.json",
                "category_dir": "data/visual_assets/coaches",
            },
            "entries": [],
        }

    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def ensure_manifest_category(manifest: dict[str, Any]) -> None:
    if manifest.get("category") == "coaches":
        return
    manifest["category"] = "coaches"
    manifest.setdefault("entries", [])


def write_manifest(manifest: dict[str, Any]) -> None:
    entries = manifest.get("entries", [])
    present_total = sum(1 for entry in entries if entry.get("local_path") and not entry.get("error"))
    manifest["generated_at"] = utc_now_iso()
    manifest["summary"] = {
        "category": "coaches",
        "targets_total": len(entries),
        "cached_local_total": sum(1 for entry in entries if entry.get("status") == "cached_local"),
        "downloaded_total": sum(1 for entry in entries if entry.get("status") == "downloaded"),
        "download_failed_total": sum(1 for entry in entries if entry.get("status") == "download_failed"),
        "missing_source_url_total": sum(1 for entry in entries if entry.get("status") == "missing_source_url"),
        "assets_present_total": present_total,
        "assets_missing_total": max(len(entries) - present_total, 0),
        "manifest_path": "data/visual_assets/manifests/coaches.json",
        "category_dir": "data/visual_assets/coaches",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reconcile_manifest_with_files(manifest: dict[str, Any]) -> int:
    reconciled = 0
    for entry in manifest.get("entries", []):
        entity_id = entry.get("entity_id")
        if entity_id is None:
            continue

        asset_path = COACH_ASSETS_DIR / f"{entity_id}.png"
        if not asset_path.exists():
            continue

        if entry.get("status") != "downloaded" or not entry.get("local_path"):
            entry["status"] = "cached_local"
            entry["local_path"] = f"data/visual_assets/coaches/{entity_id}.png"
            entry["content_type"] = "image/png"
            entry["file_size_bytes"] = asset_path.stat().st_size
            entry["last_synced_at"] = utc_now_iso()
            entry["error"] = None
            reconciled += 1

    return reconciled


def export_missing_csv(manifest: dict[str, Any], output_path: Path) -> int:
    rows = [
        entry
        for entry in manifest.get("entries", [])
        if entry.get("status") in {"missing_source_url", "download_failed"}
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "entity_id",
                "entity_name",
                "status",
                "source_ref",
                "source_file_name",
                "source_url",
                "error",
            ],
        )
        writer.writeheader()
        for entry in rows:
            writer.writerow(
                {
                    "entity_id": entry.get("entity_id"),
                    "entity_name": entry.get("entity_name"),
                    "status": entry.get("status"),
                    "source_ref": entry.get("source_ref"),
                    "source_file_name": entry.get("source_file_name"),
                    "source_url": entry.get("source_url"),
                    "error": entry.get("error"),
                }
            )
    return len(rows)


def export_missing_real_photo_csv(conn: Any, manifest: dict[str, Any], output_path: Path) -> int:
    manifest_entries = {int(entry.get("entity_id")): entry for entry in manifest.get("entries", []) if entry.get("entity_id") is not None}
    with conn.cursor() as cur:
        cur.execute(
            """
            select
                coach_identity_id,
                provider,
                provider_coach_id,
                coalesce(nullif(trim(display_name), ''), nullif(trim(canonical_name), ''), concat('Coach ', coach_identity_id::text)) as coach_name,
                image_url
            from mart.coach_identity
            where nullif(trim(image_url), '') is null
               or image_url ilike '%%placeholder%%'
            order by coach_identity_id
            """
        )
        rows = cur.fetchall()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "coach_identity_id",
                "provider",
                "provider_coach_id",
                "coach_name",
                "missing_reason",
                "current_image_url",
                "source_ref",
                "source_status",
                "source_file_name",
                "source_url",
                "source_error",
            ],
        )
        writer.writeheader()

        for coach_identity_id, provider, provider_coach_id, coach_name, image_url in rows:
            manifest_entry = manifest_entries.get(int(coach_identity_id))
            missing_reason = "placeholder_image_url" if image_url and "placeholder" in image_url.lower() else "missing_image_url"
            writer.writerow(
                {
                    "coach_identity_id": coach_identity_id,
                    "provider": provider,
                    "provider_coach_id": provider_coach_id,
                    "coach_name": coach_name,
                    "missing_reason": missing_reason,
                    "current_image_url": image_url,
                    "source_ref": manifest_entry.get("source_ref") if manifest_entry else None,
                    "source_status": manifest_entry.get("status") if manifest_entry else None,
                    "source_file_name": manifest_entry.get("source_file_name") if manifest_entry else None,
                    "source_url": manifest_entry.get("source_url") if manifest_entry else None,
                    "source_error": manifest_entry.get("error") if manifest_entry else None,
                }
            )

    return len(rows)


def fetch_wikidata_image_filename(session: requests.Session, wikidata_numeric_id: int) -> str | None:
    entity_id = f"Q{wikidata_numeric_id}"
    response = session.get(
        WIKIDATA_ENTITY_URL.format(entity_id=entity_id),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    entity = payload.get("entities", {}).get(entity_id, {})
    claims = entity.get("claims", {})
    p18_claims = claims.get("P18", [])
    for claim in p18_claims:
        datavalue = (((claim or {}).get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(datavalue, str) and datavalue.strip():
            return datavalue.strip()
    return None


def fetch_wikidata_image_filename_from_qid(session: requests.Session, wikidata_qid: str) -> str | None:
    response = session.get(
        WIKIDATA_ENTITY_URL.format(entity_id=wikidata_qid),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    entity = payload.get("entities", {}).get(wikidata_qid, {})
    claims = entity.get("claims", {})
    p18_claims = claims.get("P18", [])
    for claim in p18_claims:
        datavalue = (((claim or {}).get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(datavalue, str) and datavalue.strip():
            return datavalue.strip()
    return None


def fetch_wikidata_entity(session: requests.Session, wikidata_qid: str) -> dict[str, Any]:
    response = session.get(
        WIKIDATA_ENTITY_URL.format(entity_id=wikidata_qid),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("entities", {}).get(wikidata_qid, {})


def fetch_wikipedia_thumbnail_url(session: requests.Session, wikidata_qid: str) -> str | None:
    entity = fetch_wikidata_entity(session, wikidata_qid)
    sitelinks = entity.get("sitelinks", {})
    for site_key in ("enwiki", "ptwiki", "eswiki", "frwiki", "dewiki", "itwiki"):
        site_entry = sitelinks.get(site_key)
        title = site_entry.get("title") if isinstance(site_entry, dict) else None
        if not title:
            continue

        lang = site_key.removesuffix("wiki")
        response = session.get(
            WIKIPEDIA_API_URL.format(lang=lang),
            params={
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "prop": "pageimages",
                "titles": title,
                "pithumbsize": 800,
            },
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        pages = payload.get("query", {}).get("pages", [])
        for page in pages:
            thumb = page.get("thumbnail") if isinstance(page, dict) else None
            source = thumb.get("source") if isinstance(thumb, dict) else None
            if isinstance(source, str) and source.strip():
                return source.strip()
    return None


def download_and_convert_png(session: requests.Session, file_name: str, target_path: Path) -> int:
    response = None
    last_error: Exception | None = None
    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            response = session.get(
                COMMONS_FILEPATH_URL.format(file_name=quote(file_name, safe="")),
                headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"},
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
            response.raise_for_status()
            break
        except requests.HTTPError as exc:
            last_error = exc
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code != 429 or attempt == MAX_DOWNLOAD_RETRIES:
                raise

            retry_after_header = (exc.response.headers.get("Retry-After") or "").strip() if exc.response is not None else ""
            retry_after_seconds = float(retry_after_header) if retry_after_header.isdigit() else min(5.0 * attempt, 30.0)
            time.sleep(retry_after_seconds)
        except Exception as exc:
            last_error = exc
            if attempt == MAX_DOWNLOAD_RETRIES:
                raise
            time.sleep(min(2.0 * attempt, 10.0))

    if response is None:
        assert last_error is not None
        raise last_error

    with Image.open(BytesIO(response.content)) as image:
        normalized = ImageOps.exif_transpose(image).convert("RGBA")
        squared = ImageOps.pad(
            normalized,
            (TARGET_SIZE, TARGET_SIZE),
            method=Image.Resampling.LANCZOS,
            color=(0, 0, 0, 0),
            centering=(0.5, 0.35),
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        squared.save(target_path, format="PNG", optimize=True)

    return target_path.stat().st_size


def download_raster_png(session: requests.Session, source_url: str, target_path: Path) -> int:
    response = None
    last_error: Exception | None = None
    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            response = session.get(
                source_url,
                headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"},
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
            response.raise_for_status()
            break
        except requests.HTTPError as exc:
            last_error = exc
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code != 429 or attempt == MAX_DOWNLOAD_RETRIES:
                raise
            retry_after_header = (exc.response.headers.get("Retry-After") or "").strip() if exc.response is not None else ""
            retry_after_seconds = float(retry_after_header) if retry_after_header.isdigit() else min(5.0 * attempt, 30.0)
            time.sleep(retry_after_seconds)
        except Exception as exc:
            last_error = exc
            if attempt == MAX_DOWNLOAD_RETRIES:
                raise
            time.sleep(min(2.0 * attempt, 10.0))

    if response is None:
        assert last_error is not None
        raise last_error

    with Image.open(BytesIO(response.content)) as image:
        normalized = ImageOps.exif_transpose(image).convert("RGBA")
        squared = ImageOps.pad(
            normalized,
            (TARGET_SIZE, TARGET_SIZE),
            method=Image.Resampling.LANCZOS,
            color=(0, 0, 0, 0),
            centering=(0.5, 0.35),
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        squared.save(target_path, format="PNG", optimize=True)

    return target_path.stat().st_size


def upsert_manifest_entry(manifest: dict[str, Any], entry: dict[str, Any]) -> None:
    entries = manifest.setdefault("entries", [])
    for index, existing in enumerate(entries):
        if str(existing.get("entity_id")) == str(entry.get("entity_id")):
            entries[index] = entry
            break
    else:
        entries.append(entry)
    entries.sort(key=lambda item: int(item.get("entity_id", 0)))


def update_coach_image_url(conn: Any, coach_identity_id: int) -> None:
    image_url = f"/api/visual-assets/coaches/{coach_identity_id}"
    with conn.cursor() as cur:
        cur.execute(
            """
            update mart.coach_identity
               set image_url = %s,
                   updated_at = now()
             where coach_identity_id = %s
               and (
                   nullif(trim(image_url), '') is null
                   or image_url ilike '%%placeholder%%'
               )
            """,
            (image_url, coach_identity_id),
        )


def build_success_entry(coach: CoachRow, file_name: str, file_size_bytes: int, status: str) -> dict[str, Any]:
    return {
        "entity_id": coach.coach_identity_id,
        "entity_name": coach.coach_name,
        "status": status,
        "source_kind": "wikimedia_commons_p18",
        "source_ref": coach.wikidata_qid or f"Q{coach.provider_coach_id}",
        "provider": coach.provider,
        "provider_coach_id": coach.provider_coach_id,
        "source_file_name": file_name,
        "source_url": COMMONS_FILEPATH_URL.format(file_name=quote(file_name, safe="")),
        "local_path": f"data/visual_assets/coaches/{coach.coach_identity_id}.png",
        "content_type": "image/png",
        "file_size_bytes": file_size_bytes,
        "last_synced_at": utc_now_iso(),
        "error": None,
    }


def build_error_entry(coach: CoachRow, status: str, error: str) -> dict[str, Any]:
    return {
        "entity_id": coach.coach_identity_id,
        "entity_name": coach.coach_name,
        "status": status,
        "source_kind": "wikimedia_commons_p18",
        "source_ref": coach.wikidata_qid or f"Q{coach.provider_coach_id}",
        "provider": coach.provider,
        "provider_coach_id": coach.provider_coach_id,
        "source_file_name": None,
        "source_url": None,
        "local_path": None,
        "content_type": "image/png",
        "file_size_bytes": None,
        "last_synced_at": utc_now_iso(),
        "error": error,
    }


def process_coach(session: requests.Session, manifest: dict[str, Any], conn: Any, coach: CoachRow) -> tuple[str, str | None]:
    target_path = COACH_ASSETS_DIR / f"{coach.coach_identity_id}.png"
    try:
        file_name = (
            fetch_wikidata_image_filename_from_qid(session, coach.wikidata_qid)
            if coach.wikidata_qid
            else fetch_wikidata_image_filename(session, coach.provider_coach_id)
        )
        source_url: str | None = None
        source_file_name: str | None = None
        source_kind = "wikimedia_commons_p18"

        if file_name:
            source_file_name = file_name
            source_url = COMMONS_FILEPATH_URL.format(file_name=quote(file_name, safe=""))
        elif coach.wikidata_qid:
            source_url = fetch_wikipedia_thumbnail_url(session, coach.wikidata_qid)
            source_kind = "wikipedia_pageimage"

        if not source_url:
            upsert_manifest_entry(manifest, build_error_entry(coach, "missing_source_url", "wikidata entity has no P18 image or wikipedia thumbnail"))
            return "missing_source_url", None

        status = "cached_local" if target_path.exists() else "downloaded"
        if not target_path.exists():
            file_size_bytes = (
                download_and_convert_png(session, source_file_name, target_path)
                if source_file_name
                else download_raster_png(session, source_url, target_path)
            )
        else:
            file_size_bytes = target_path.stat().st_size

        entry = build_success_entry(coach, source_file_name or coach.wikidata_qid or str(coach.provider_coach_id), file_size_bytes, status)
        entry["source_kind"] = source_kind
        entry["source_url"] = source_url
        entry["source_file_name"] = source_file_name
        upsert_manifest_entry(manifest, entry)
        update_coach_image_url(conn, coach.coach_identity_id)
        time.sleep(REQUEST_PAUSE_SECONDS)
        return status, None
    except Exception as exc:
        upsert_manifest_entry(manifest, build_error_entry(coach, "download_failed", str(exc)))
        time.sleep(REQUEST_PAUSE_SECONDS)
        return "download_failed", str(exc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill coach profile PNGs from Wikidata/Wikimedia Commons")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of missing coaches to process")
    parser.add_argument("--dry-run", action="store_true", help="Only list the coaches that would be processed")
    parser.add_argument("--sync-db-from-files", action="store_true", help="Populate image_url for existing local coach PNGs")
    parser.add_argument("--prune-orphaned-db-urls", action="store_true", help="Clear coach image_url entries that have no local PNG")
    parser.add_argument("--reconcile-manifest", action="store_true", help="Refresh manifest statuses from local coach PNG files")
    parser.add_argument("--export-missing-csv", type=Path, default=None, help="Write missing coach asset cases to CSV")
    parser.add_argument("--export-missing-real-photo-csv", type=Path, default=None, help="Write coaches without real non-placeholder photos to CSV")
    parser.add_argument("--sportmonks-placeholder-with-wikidata", action="store_true", help="Backfill Sportmonks placeholder coaches that already have Wikidata refs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    COACH_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    ensure_manifest_category(manifest)

    conn = psycopg2.connect(resolve_db_dsn())
    conn.autocommit = False

    try:
        if args.sync_db_from_files:
            updated = sync_database_from_existing_files(conn)
            conn.commit()
            print(json.dumps({"synced_from_files": updated}, ensure_ascii=False, indent=2))
            return 0

        if args.prune_orphaned_db_urls:
            pruned = prune_orphaned_database_urls(conn)
            conn.commit()
            print(json.dumps({"pruned_orphaned_urls": pruned}, ensure_ascii=False, indent=2))
            return 0

        if args.reconcile_manifest:
            reconciled = reconcile_manifest_with_files(manifest)
            write_manifest(manifest)
            conn.rollback()
            print(json.dumps({"reconciled_manifest_entries": reconciled}, ensure_ascii=False, indent=2))
            return 0

        if args.export_missing_csv is not None:
            exported = export_missing_csv(manifest, args.export_missing_csv)
            conn.rollback()
            print(json.dumps({"exported_missing_rows": exported, "output_path": str(args.export_missing_csv)}, ensure_ascii=False, indent=2))
            return 0

        if args.export_missing_real_photo_csv is not None:
            exported = export_missing_real_photo_csv(conn, manifest, args.export_missing_real_photo_csv)
            conn.rollback()
            print(
                json.dumps(
                    {"exported_missing_real_photo_rows": exported, "output_path": str(args.export_missing_real_photo_csv)},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        coaches = (
            fetch_sportmonks_placeholder_coaches_with_wikidata_ref(conn, args.limit)
            if args.sportmonks_placeholder_with_wikidata
            else fetch_missing_coaches(conn, args.limit)
        )
        if args.dry_run:
            print(json.dumps([coach.__dict__ for coach in coaches], ensure_ascii=False, indent=2))
            conn.rollback()
            return 0

        session = requests.Session()
        stats = {
            "targets": len(coaches),
            "downloaded": 0,
            "cached_local": 0,
            "missing_source_url": 0,
            "download_failed": 0,
        }

        for coach in coaches:
            try:
                status, error = process_coach(session, manifest, conn, coach)
                write_manifest(manifest)
                conn.commit()
            except Exception:
                conn.rollback()
                raise

            stats[status] = stats.get(status, 0) + 1
            if error:
                print(
                    safe_text(f"[warn] {coach.coach_identity_id} {coach.coach_name}: {error}"),
                    file=sys.stderr,
                )
            else:
                print(safe_text(f"[ok] {coach.coach_identity_id} {coach.coach_name}: {status}"))

        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
