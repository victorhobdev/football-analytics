from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import ssl
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

import psycopg
from psycopg.rows import dict_row


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = REPO_ROOT / ".env"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "data" / "visual_assets"
DEFAULT_BATCH_SIZE = 50
DEFAULT_DOWNLOAD_WORKERS = 12
DEFAULT_TIMEOUT_SECONDS = 45
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


COMPETITIONS_SQL = """
select
    league_id as entity_id,
    league_name as entity_name,
    nullif(trim(payload ->> 'image_path'), '') as source_url
from raw.competition_leagues
where league_id is not null
order by league_id
"""


CLUBS_SQL = """
with standings_assets as (
    select distinct on (team_id)
        team_id,
        nullif(trim(payload -> 'participant' ->> 'image_path'), '') as source_url
    from raw.standings_snapshots
    where payload -> 'participant' ->> 'image_path' is not null
    order by team_id, updated_at desc, season_id desc, round_id desc
)
select
    team_id as entity_id,
    team_name as entity_name,
    standings_assets.source_url as source_url
from mart.dim_team
left join standings_assets using (team_id)
where team_id is not null
order by team_id
"""


PLAYERS_SQL = """
select
    player_id as entity_id,
    player_name as entity_name,
    cast(null as text) as source_url
from mart.dim_player
where player_id is not null
order by player_id
"""


@dataclass(frozen=True)
class CategoryConfig:
    name: str
    sql: str
    collection_endpoint: str | None
    single_endpoint_template: str
    id_filter_name: str | None
    select_fields: tuple[str, ...]
    display_name_field: str


@dataclass(frozen=True)
class TargetEntity:
    entity_id: int
    entity_name: str
    source_url: str | None


@dataclass(frozen=True)
class ApiImageMetadata:
    entity_id: int
    entity_name: str | None
    image_path: str | None


@dataclass(frozen=True)
class DownloadPlan:
    entity_id: int
    entity_name: str
    source_url: str
    source_kind: str


@dataclass(frozen=True)
class DownloadResult:
    entity_id: int
    ok: bool
    local_path: str | None
    content_type: str | None
    file_size_bytes: int | None
    error: str | None


CATEGORY_CONFIGS = {
    "competitions": CategoryConfig(
        name="competitions",
        sql=COMPETITIONS_SQL,
        collection_endpoint=None,
        single_endpoint_template="/leagues/{entity_id}",
        id_filter_name=None,
        select_fields=("id", "name", "image_path"),
        display_name_field="name",
    ),
    "clubs": CategoryConfig(
        name="clubs",
        sql=CLUBS_SQL,
        collection_endpoint="/teams",
        single_endpoint_template="/teams/{entity_id}",
        id_filter_name="teamIds",
        select_fields=("id", "name", "image_path"),
        display_name_field="name",
    ),
    "players": CategoryConfig(
        name="players",
        sql=PLAYERS_SQL,
        collection_endpoint="/players",
        single_endpoint_template="/players/{entity_id}",
        id_filter_name="playerIds",
        select_fields=("id", "name", "display_name", "image_path"),
        display_name_field="display_name",
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sincroniza assets visuais locais apenas para entidades ja existentes no banco, "
            "reaproveitando URLs materializadas e minimizando requests a SportMonks."
        )
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=sorted(CATEGORY_CONFIGS.keys()),
        default=["competitions", "clubs", "players"],
        help="Categorias de assets para sincronizar.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Diretorio raiz do cache local de assets.",
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_PATH),
        help="Arquivo .env usado como fallback para credenciais locais.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nao faz chamadas HTTP nem downloads. Apenas calcula escopo e requests estimados.",
    )
    parser.add_argument(
        "--api-batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Quantidade maxima de IDs por request batch na SportMonks.",
    )
    parser.add_argument(
        "--download-workers",
        type=int,
        default=DEFAULT_DOWNLOAD_WORKERS,
        help="Numero de downloads paralelos de assets.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Timeout de requests HTTP.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Numero maximo de retries para chamadas HTTP.",
    )
    return parser.parse_args()


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def resolve_setting(name: str, env_file_values: dict[str, str], default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is not None and value != "":
        return value
    value = env_file_values.get(name)
    if value is not None and value != "":
        return value
    return default


def build_pg_dsn(env_file_values: dict[str, str]) -> str:
    user = resolve_setting("POSTGRES_USER", env_file_values, "football")
    password = resolve_setting("POSTGRES_PASSWORD", env_file_values, "football")
    database = resolve_setting("POSTGRES_DB", env_file_values, "football_dw")
    host = resolve_setting("POSTGRES_HOST", env_file_values, "localhost")
    port = resolve_setting("POSTGRES_PORT", env_file_values, "5432")
    if user and password and database:
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    dsn = resolve_setting("FOOTBALL_PG_DSN", env_file_values) or resolve_setting("DATABASE_URL", env_file_values)
    if not dsn:
        return f"postgresql://football:football@localhost:5432/football_dw"

    normalized = dsn.replace("postgresql+psycopg2://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")
    parsed = urlparse(normalized)
    hostname = parsed.hostname or "localhost"
    if hostname in {"postgres", "football-postgres"}:
        hostname = "localhost"
    netloc = hostname
    if parsed.username:
        credentials = parsed.username
        if parsed.password:
            credentials = f"{credentials}:{parsed.password}"
        netloc = f"{credentials}@{netloc}"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse((parsed.scheme or "postgresql", netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))


def relpath(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def chunked(values: list[int], size: int) -> Iterable[list[int]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def load_manifest(manifest_path: Path) -> dict[int, dict[str, Any]]:
    if not manifest_path.exists():
        return {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") or []
    by_id: dict[int, dict[str, Any]] = {}
    for entry in entries:
        entity_id = entry.get("entity_id")
        if isinstance(entity_id, int):
            by_id[entity_id] = entry
    return by_id


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_existing_asset(category_dir: Path, entity_id: int) -> Path | None:
    matches = sorted(category_dir.glob(f"{entity_id}.*"))
    for match in matches:
        if match.is_file() and match.stat().st_size > 0:
            return match
    return None


def infer_extension(*, source_url: str, content_type: str | None) -> str:
    if content_type:
        normalized = content_type.split(";", 1)[0].strip().lower()
        extension = CONTENT_TYPE_EXTENSIONS.get(normalized)
        if extension:
            return extension
    parsed = urlparse(source_url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix:
        return suffix
    return ".bin"


def fetch_targets(conn: psycopg.Connection[Any], config: CategoryConfig) -> list[TargetEntity]:
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(config.sql)
        rows = cursor.fetchall()
    targets: list[TargetEntity] = []
    for row in rows:
        entity_id = row["entity_id"]
        if entity_id is None:
            continue
        entity_name = row.get("entity_name") or f"{config.name[:-1].title()} #{entity_id}"
        targets.append(
            TargetEntity(
                entity_id=int(entity_id),
                entity_name=str(entity_name),
                source_url=row.get("source_url"),
            )
        )
    return targets


class SportMonksClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_token: str,
        timeout_seconds: int,
        max_retries: int,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.ssl_context = ssl.create_default_context()
        self.request_counts = Counter()

    def _request_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}?{urlencode(params, doseq=True)}"
        request_obj = Request(url, headers={"User-Agent": "football-analytics-visual-assets/1.0"})
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self.request_counts["total"] += 1
            self.request_counts[f"endpoint:{endpoint}"] += 1
            try:
                with urlopen(request_obj, timeout=self.timeout_seconds, context=self.ssl_context) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    return payload
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    time.sleep(2**attempt)
                    last_error = RuntimeError(f"status={exc.code} body={body[:300]}")
                    continue
                raise RuntimeError(f"SportMonks endpoint={endpoint} status={exc.code} body={body[:300]}") from exc
            except URLError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError(f"SportMonks endpoint={endpoint} erro_rede={exc}") from exc
        raise RuntimeError(f"SportMonks endpoint={endpoint} retries_excedidos error={last_error}")

    def fetch_metadata(
        self,
        *,
        config: CategoryConfig,
        entity_ids: list[int],
        batch_size: int,
    ) -> tuple[dict[int, ApiImageMetadata], dict[int, str]]:
        metadata: dict[int, ApiImageMetadata] = {}
        errors: dict[int, str] = {}

        if not entity_ids:
            return metadata, errors

        if config.collection_endpoint and config.id_filter_name:
            for batch in chunked(entity_ids, batch_size):
                try:
                    batch_rows = self._fetch_batch(config=config, entity_ids=batch)
                except Exception as exc:
                    batch_error = str(exc)
                    for entity_id in batch:
                        single_meta, single_error = self._fetch_single_with_error(config=config, entity_id=entity_id)
                        if single_meta is not None:
                            metadata[entity_id] = single_meta
                        elif single_error is not None:
                            errors[entity_id] = f"{batch_error} | fallback={single_error}"
                    continue
                metadata.update(batch_rows)
        else:
            for entity_id in entity_ids:
                single_meta, single_error = self._fetch_single_with_error(config=config, entity_id=entity_id)
                if single_meta is not None:
                    metadata[entity_id] = single_meta
                elif single_error is not None:
                    errors[entity_id] = single_error

        return metadata, errors

    def _fetch_batch(self, *, config: CategoryConfig, entity_ids: list[int]) -> dict[int, ApiImageMetadata]:
        params = {
            "api_token": self.api_token,
            "filters": f"{config.id_filter_name}:{','.join(str(entity_id) for entity_id in entity_ids)}",
            "select": ",".join(config.select_fields),
            "per_page": str(len(entity_ids)),
        }
        payload = self._request_json(config.collection_endpoint or "", params)
        data = payload.get("data") or []
        if isinstance(data, dict):
            data = [data]
        output: dict[int, ApiImageMetadata] = {}
        for row in data:
            entity_id = row.get("id")
            if entity_id is None:
                continue
            output[int(entity_id)] = ApiImageMetadata(
                entity_id=int(entity_id),
                entity_name=row.get(config.display_name_field) or row.get("name"),
                image_path=row.get("image_path"),
            )
        return output

    def _fetch_single_with_error(
        self,
        *,
        config: CategoryConfig,
        entity_id: int,
    ) -> tuple[ApiImageMetadata | None, str | None]:
        endpoint = config.single_endpoint_template.format(entity_id=entity_id)
        try:
            payload = self._request_json(endpoint, {"api_token": self.api_token})
        except Exception as exc:
            return None, str(exc)
        row = payload.get("data") or {}
        if not isinstance(row, dict) or not row:
            return None, "SportMonks response sem data"
        return (
            ApiImageMetadata(
                entity_id=entity_id,
                entity_name=row.get(config.display_name_field) or row.get("name"),
                image_path=row.get("image_path"),
            ),
            None,
        )


class AssetDownloader:
    def __init__(self, *, timeout_seconds: int, max_retries: int):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.ssl_context = ssl.create_default_context()
        self.request_counts = Counter()

    def download(self, *, category_dir: Path, plan: DownloadPlan) -> DownloadResult:
        request_obj = Request(plan.source_url, headers={"User-Agent": "football-analytics-visual-assets/1.0"})
        last_error: Exception | None = None
        temp_path: Path | None = None
        for attempt in range(self.max_retries + 1):
            self.request_counts["total"] += 1
            try:
                with urlopen(request_obj, timeout=self.timeout_seconds, context=self.ssl_context) as response:
                    content_type = response.headers.get_content_type()
                    extension = infer_extension(source_url=plan.source_url, content_type=content_type)
                    final_path = category_dir / f"{plan.entity_id}{extension}"
                    temp_path = final_path.with_suffix(final_path.suffix + ".tmp")
                    with temp_path.open("wb") as handle:
                        shutil.copyfileobj(response, handle)
                    temp_path.replace(final_path)
                    temp_path = None
                    return DownloadResult(
                        entity_id=plan.entity_id,
                        ok=True,
                        local_path=relpath(final_path),
                        content_type=content_type,
                        file_size_bytes=final_path.stat().st_size,
                        error=None,
                    )
            except HTTPError as exc:
                if temp_path and temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    last_error = RuntimeError(f"status={exc.code} body={body[:200]}")
                    time.sleep(2**attempt)
                    continue
                return DownloadResult(
                    entity_id=plan.entity_id,
                    ok=False,
                    local_path=None,
                    content_type=None,
                    file_size_bytes=None,
                    error=f"download status={exc.code} body={body[:200]}",
                )
            except URLError as exc:
                if temp_path and temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                return DownloadResult(
                    entity_id=plan.entity_id,
                    ok=False,
                    local_path=None,
                    content_type=None,
                    file_size_bytes=None,
                    error=f"download erro_rede={exc}",
                )
            except Exception as exc:
                if temp_path and temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                last_error = exc
                break
        return DownloadResult(
            entity_id=plan.entity_id,
            ok=False,
            local_path=None,
            content_type=None,
            file_size_bytes=None,
            error=str(last_error) if last_error else "erro_desconhecido",
        )


def build_category_paths(output_root: Path, category_name: str) -> tuple[Path, Path]:
    category_dir = output_root / category_name
    manifest_path = output_root / "manifests" / f"{category_name}.json"
    category_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    return category_dir, manifest_path


def sync_category(
    *,
    conn: psycopg.Connection[Any],
    config: CategoryConfig,
    output_root: Path,
    env_file_values: dict[str, str],
    dry_run: bool,
    api_batch_size: int,
    download_workers: int,
    timeout_seconds: int,
    max_retries: int,
) -> dict[str, Any]:
    category_dir, manifest_path = build_category_paths(output_root, config.name)
    existing_manifest = load_manifest(manifest_path)
    targets = fetch_targets(conn, config)

    entries_by_id: dict[int, dict[str, Any]] = {}
    api_lookup_ids: list[int] = []
    download_plans: list[DownloadPlan] = []

    db_source_urls_total = 0
    manifest_source_urls_total = 0
    cached_local_total = 0

    for target in targets:
        existing_file = find_existing_asset(category_dir, target.entity_id)
        existing_manifest_entry = existing_manifest.get(target.entity_id, {})
        manifest_source_url = existing_manifest_entry.get("source_url")
        resolved_source_url = target.source_url or manifest_source_url
        if target.source_url:
            db_source_urls_total += 1
        elif manifest_source_url:
            manifest_source_urls_total += 1

        if existing_file is not None:
            cached_local_total += 1
            entries_by_id[target.entity_id] = {
                "entity_id": target.entity_id,
                "entity_name": target.entity_name,
                "status": "cached_local",
                "source_kind": (
                    "raw_db" if target.source_url else existing_manifest_entry.get("source_kind") or "local_cache"
                ),
                "source_url": resolved_source_url,
                "local_path": relpath(existing_file),
                "content_type": existing_manifest_entry.get("content_type"),
                "file_size_bytes": existing_file.stat().st_size,
                "last_synced_at": utc_now(),
                "error": None,
            }
            continue

        if resolved_source_url:
            download_plans.append(
                DownloadPlan(
                    entity_id=target.entity_id,
                    entity_name=target.entity_name,
                    source_url=resolved_source_url,
                    source_kind="raw_db" if target.source_url else "manifest_cache",
                )
            )
            continue

        api_lookup_ids.append(target.entity_id)

    if dry_run:
        estimated_api_requests = 0
        if config.collection_endpoint and config.id_filter_name:
            estimated_api_requests = math.ceil(len(api_lookup_ids) / api_batch_size)
        else:
            estimated_api_requests = len(api_lookup_ids)
        summary = {
            "category": config.name,
            "targets_total": len(targets),
            "cached_local_total": cached_local_total,
            "db_source_urls_total": db_source_urls_total,
            "manifest_source_urls_total": manifest_source_urls_total,
            "download_ready_without_api_total": len(download_plans),
            "api_lookup_needed_total": len(api_lookup_ids),
            "estimated_api_requests_total": estimated_api_requests,
            "planned_downloads_upper_bound_total": len(download_plans) + len(api_lookup_ids),
            "manifest_path": relpath(manifest_path),
            "category_dir": relpath(category_dir),
        }
        return {
            "summary": summary,
            "entries": [],
        }

    sportmonks: SportMonksClient | None = None
    api_metadata: dict[int, ApiImageMetadata] = {}
    api_errors: dict[int, str] = {}
    if api_lookup_ids:
        api_base_url = resolve_setting("SPORTMONKS_BASE_URL", env_file_values, "https://api.sportmonks.com/v3/football")
        api_token = resolve_setting("API_KEY_SPORTMONKS", env_file_values)
        if not api_token:
            raise RuntimeError("API_KEY_SPORTMONKS nao encontrada no ambiente nem no .env.")
        sportmonks = SportMonksClient(
            base_url=api_base_url or "",
            api_token=api_token,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        api_metadata, api_errors = sportmonks.fetch_metadata(
            config=config,
            entity_ids=api_lookup_ids,
            batch_size=api_batch_size,
        )

    unresolved_after_api = []
    target_index = {target.entity_id: target for target in targets}

    for entity_id in api_lookup_ids:
        target = target_index[entity_id]
        meta = api_metadata.get(entity_id)
        if meta and meta.image_path:
            download_plans.append(
                DownloadPlan(
                    entity_id=entity_id,
                    entity_name=meta.entity_name or target.entity_name,
                    source_url=meta.image_path,
                    source_kind="sportmonks_api",
                )
            )
            continue

        error_message = api_errors.get(entity_id)
        status = "api_lookup_failed" if error_message else "missing_source_url"
        entries_by_id[entity_id] = {
            "entity_id": entity_id,
            "entity_name": target.entity_name,
            "status": status,
            "source_kind": "sportmonks_api",
            "source_url": meta.image_path if meta else None,
            "local_path": None,
            "content_type": None,
            "file_size_bytes": None,
            "last_synced_at": utc_now(),
            "error": error_message,
        }
        unresolved_after_api.append(entity_id)

    downloader = AssetDownloader(timeout_seconds=timeout_seconds, max_retries=max_retries)
    download_results: dict[int, DownloadResult] = {}
    if download_plans:
        with ThreadPoolExecutor(max_workers=max(1, download_workers)) as executor:
            future_map = {
                executor.submit(downloader.download, category_dir=category_dir, plan=plan): plan
                for plan in download_plans
            }
            for future in as_completed(future_map):
                plan = future_map[future]
                result = future.result()
                download_results[plan.entity_id] = result

    for plan in download_plans:
        result = download_results.get(plan.entity_id)
        if result is None:
            entries_by_id[plan.entity_id] = {
                "entity_id": plan.entity_id,
                "entity_name": plan.entity_name,
                "status": "download_failed",
                "source_kind": plan.source_kind,
                "source_url": plan.source_url,
                "local_path": None,
                "content_type": None,
                "file_size_bytes": None,
                "last_synced_at": utc_now(),
                "error": "resultado de download ausente",
            }
            continue
        entries_by_id[plan.entity_id] = {
            "entity_id": plan.entity_id,
            "entity_name": plan.entity_name,
            "status": "downloaded" if result.ok else "download_failed",
            "source_kind": plan.source_kind,
            "source_url": plan.source_url,
            "local_path": result.local_path,
            "content_type": result.content_type,
            "file_size_bytes": result.file_size_bytes,
            "last_synced_at": utc_now(),
            "error": result.error,
        }

    ordered_entries = [entries_by_id[target.entity_id] for target in targets if target.entity_id in entries_by_id]
    status_counts = Counter(entry["status"] for entry in ordered_entries)
    summary = {
        "category": config.name,
        "targets_total": len(targets),
        "cached_local_total": status_counts.get("cached_local", 0),
        "downloaded_total": status_counts.get("downloaded", 0),
        "download_failed_total": status_counts.get("download_failed", 0),
        "missing_source_url_total": status_counts.get("missing_source_url", 0),
        "api_lookup_failed_total": status_counts.get("api_lookup_failed", 0),
        "db_source_urls_total": db_source_urls_total,
        "manifest_source_urls_total": manifest_source_urls_total,
        "api_lookup_needed_total": len(api_lookup_ids),
        "api_requests_total": sportmonks.request_counts.get("total", 0) if sportmonks else 0,
        "api_requests_by_endpoint": {
            key.removeprefix("endpoint:"): value
            for key, value in (sportmonks.request_counts.items() if sportmonks else [])
            if key.startswith("endpoint:")
        },
        "asset_download_requests_total": downloader.request_counts.get("total", 0),
        "assets_present_total": status_counts.get("cached_local", 0) + status_counts.get("downloaded", 0),
        "assets_missing_total": (
            status_counts.get("missing_source_url", 0)
            + status_counts.get("api_lookup_failed", 0)
            + status_counts.get("download_failed", 0)
        ),
        "manifest_path": relpath(manifest_path),
        "category_dir": relpath(category_dir),
    }

    manifest_payload = {
        "category": config.name,
        "generated_at": utc_now(),
        "summary": summary,
        "entries": ordered_entries,
    }
    write_json(manifest_path, manifest_payload)
    return {
        "summary": summary,
        "entries": ordered_entries,
        "unresolved_after_api_ids": unresolved_after_api,
    }


def write_summary(output_root: Path, payload: dict[str, Any]) -> None:
    write_json(output_root / "manifests" / "summary.json", payload)


def main() -> int:
    args = parse_args()
    if args.api_batch_size <= 0 or args.api_batch_size > 50:
        raise SystemExit("--api-batch-size deve ficar entre 1 e 50 para garantir 1 pagina por batch.")

    output_root = Path(args.output_root).resolve()
    env_file_values = load_env_file(Path(args.env_file).resolve())
    pg_dsn = build_pg_dsn(env_file_values)

    started_at = time.perf_counter()
    category_results: dict[str, Any] = {}

    with psycopg.connect(pg_dsn) as conn:
        for category_name in args.categories:
            config = CATEGORY_CONFIGS[category_name]
            category_results[category_name] = sync_category(
                conn=conn,
                config=config,
                output_root=output_root,
                env_file_values=env_file_values,
                dry_run=args.dry_run,
                api_batch_size=args.api_batch_size,
                download_workers=args.download_workers,
                timeout_seconds=args.timeout_seconds,
                max_retries=args.max_retries,
            )

    total_seconds = round(time.perf_counter() - started_at, 2)
    summary_payload = {
        "generated_at": utc_now(),
        "dry_run": args.dry_run,
        "output_root": relpath(output_root),
        "categories": {name: result["summary"] for name, result in category_results.items()},
        "total_seconds": total_seconds,
    }
    write_summary(output_root, summary_payload)
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
