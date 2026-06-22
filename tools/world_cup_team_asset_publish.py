from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parent.parent
RECONCILIATION_PATH = REPO_ROOT / "data" / "visual_assets" / "wc_pipeline" / "wc_reconciliation_map.json"
OUTPUT_DIR = REPO_ROOT / "data" / "visual_assets" / "wc_overlay" / "clubs"
MANIFEST_PATH = REPO_ROOT / "data" / "visual_assets" / "wc_pipeline" / "wc_team_asset_manifest.json"
REQUEST_TIMEOUT_SECONDS = 30
MAX_DOWNLOAD_DIMENSION = 1024
USER_AGENT = "football-analytics/1.0 (world-cup-team-assets)"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


TEAM_SOURCE_MAP: dict[str, dict[str, object]] = {
    "world-cup-algeria": {"kind": "flagcdn", "code": "dz", "confidence": 0.98},
    "world-cup-angola": {"kind": "flagcdn", "code": "ao", "confidence": 0.98},
    "world-cup-argentina": {"kind": "flagcdn", "code": "ar", "confidence": 0.98},
    "world-cup-australia": {"kind": "flagcdn", "code": "au", "confidence": 0.98},
    "world-cup-austria": {"kind": "flagcdn", "code": "at", "confidence": 0.98},
    "world-cup-bolivia": {"kind": "flagcdn", "code": "bo", "confidence": 0.98},
    "world-cup-bosnia-and-herzegovina": {"kind": "flagcdn", "code": "ba", "confidence": 0.98},
    "world-cup-bulgaria": {"kind": "flagcdn", "code": "bg", "confidence": 0.98},
    "world-cup-cameroon": {"kind": "flagcdn", "code": "cm", "confidence": 0.98},
    "world-cup-canada": {"kind": "flagcdn", "code": "ca", "confidence": 0.98},
    "world-cup-chile": {"kind": "flagcdn", "code": "cl", "confidence": 0.98},
    "world-cup-china": {"kind": "flagcdn", "code": "cn", "confidence": 0.98},
    "world-cup-colombia": {"kind": "flagcdn", "code": "co", "confidence": 0.98},
    "world-cup-costa-rica": {"kind": "flagcdn", "code": "cr", "confidence": 0.98},
    "world-cup-croatia": {"kind": "flagcdn", "code": "hr", "confidence": 0.98},
    "world-cup-cuba": {"kind": "flagcdn", "code": "cu", "confidence": 0.98},
    "world-cup-czech-republic": {"kind": "flagcdn", "code": "cz", "confidence": 0.98},
    "world-cup-czechoslovakia": {
        "kind": "wikimedia_file",
        "filename": "Flag of Czechoslovakia.svg",
        "confidence": 0.9,
    },
    "world-cup-denmark": {"kind": "flagcdn", "code": "dk", "confidence": 0.98},
    "world-cup-east-germany": {
        "kind": "wikimedia_file",
        "filename": "Flag of East Germany.svg",
        "confidence": 0.9,
    },
    "world-cup-ecuador": {"kind": "flagcdn", "code": "ec", "confidence": 0.98},
    "world-cup-el-salvador": {"kind": "flagcdn", "code": "sv", "confidence": 0.98},
    "world-cup-england": {"kind": "flagcdn", "code": "gb-eng", "confidence": 0.96},
    "world-cup-france": {"kind": "flagcdn", "code": "fr", "confidence": 0.98},
    "world-cup-germany": {"kind": "flagcdn", "code": "de", "confidence": 0.98},
    "world-cup-ghana": {"kind": "flagcdn", "code": "gh", "confidence": 0.98},
    "world-cup-haiti": {"kind": "flagcdn", "code": "ht", "confidence": 0.98},
    "world-cup-hungary": {"kind": "flagcdn", "code": "hu", "confidence": 0.98},
    "world-cup-iceland": {"kind": "flagcdn", "code": "is", "confidence": 0.98},
    "world-cup-iran": {"kind": "flagcdn", "code": "ir", "confidence": 0.98},
    "world-cup-iraq": {"kind": "flagcdn", "code": "iq", "confidence": 0.98},
    "world-cup-israel": {"kind": "flagcdn", "code": "il", "confidence": 0.98},
    "world-cup-italy": {"kind": "flagcdn", "code": "it", "confidence": 0.98},
    "world-cup-ivory-coast": {"kind": "flagcdn", "code": "ci", "confidence": 0.98},
    "world-cup-jamaica": {"kind": "flagcdn", "code": "jm", "confidence": 0.98},
    "world-cup-japan": {"kind": "flagcdn", "code": "jp", "confidence": 0.98},
    "world-cup-kuwait": {"kind": "flagcdn", "code": "kw", "confidence": 0.98},
    "world-cup-mexico": {"kind": "flagcdn", "code": "mx", "confidence": 0.98},
    "world-cup-morocco": {"kind": "flagcdn", "code": "ma", "confidence": 0.98},
    "world-cup-netherlands": {"kind": "flagcdn", "code": "nl", "confidence": 0.98},
    "world-cup-new-zealand": {"kind": "flagcdn", "code": "nz", "confidence": 0.98},
    "world-cup-nigeria": {"kind": "flagcdn", "code": "ng", "confidence": 0.98},
    "world-cup-north-korea": {"kind": "flagcdn", "code": "kp", "confidence": 0.98},
    "world-cup-northern-ireland": {"kind": "flagcdn", "code": "gb-nir", "confidence": 0.9},
    "world-cup-norway": {"kind": "flagcdn", "code": "no", "confidence": 0.98},
    "world-cup-panama": {"kind": "flagcdn", "code": "pa", "confidence": 0.98},
    "world-cup-paraguay": {"kind": "flagcdn", "code": "py", "confidence": 0.98},
    "world-cup-peru": {"kind": "flagcdn", "code": "pe", "confidence": 0.98},
    "world-cup-poland": {"kind": "flagcdn", "code": "pl", "confidence": 0.98},
    "world-cup-portugal": {"kind": "flagcdn", "code": "pt", "confidence": 0.98},
    "world-cup-qatar": {"kind": "flagcdn", "code": "qa", "confidence": 0.98},
    "world-cup-republic-of-ireland": {"kind": "flagcdn", "code": "ie", "confidence": 0.98},
    "world-cup-romania": {"kind": "flagcdn", "code": "ro", "confidence": 0.98},
    "world-cup-russia": {"kind": "flagcdn", "code": "ru", "confidence": 0.98},
    "world-cup-saudi-arabia": {"kind": "flagcdn", "code": "sa", "confidence": 0.98},
    "world-cup-scotland": {"kind": "flagcdn", "code": "gb-sct", "confidence": 0.96},
    "world-cup-senegal": {"kind": "flagcdn", "code": "sn", "confidence": 0.98},
    "world-cup-serbia": {"kind": "flagcdn", "code": "rs", "confidence": 0.98},
    "world-cup-serbia-and-montenegro": {
        "kind": "wikimedia_file",
        "filename": "Flag of Serbia and Montenegro.svg",
        "confidence": 0.9,
    },
    "world-cup-slovakia": {"kind": "flagcdn", "code": "sk", "confidence": 0.98},
    "world-cup-slovenia": {"kind": "flagcdn", "code": "si", "confidence": 0.98},
    "world-cup-south-africa": {"kind": "flagcdn", "code": "za", "confidence": 0.98},
    "world-cup-south-korea": {"kind": "flagcdn", "code": "kr", "confidence": 0.98},
    "world-cup-soviet-union": {
        "kind": "wikimedia_file",
        "filename": "Flag of the Soviet Union.svg",
        "confidence": 0.9,
    },
    "world-cup-spain": {"kind": "flagcdn", "code": "es", "confidence": 0.98},
    "world-cup-sweden": {"kind": "flagcdn", "code": "se", "confidence": 0.98},
    "world-cup-switzerland": {"kind": "flagcdn", "code": "ch", "confidence": 0.98},
    "world-cup-togo": {"kind": "flagcdn", "code": "tg", "confidence": 0.98},
    "world-cup-trinidad-and-tobago": {"kind": "flagcdn", "code": "tt", "confidence": 0.98},
    "world-cup-tunisia": {"kind": "flagcdn", "code": "tn", "confidence": 0.98},
    "world-cup-turkey": {"kind": "flagcdn", "code": "tr", "confidence": 0.98},
    "world-cup-ukraine": {"kind": "flagcdn", "code": "ua", "confidence": 0.98},
    "world-cup-united-arab-emirates": {"kind": "flagcdn", "code": "ae", "confidence": 0.98},
    "world-cup-uruguay": {"kind": "flagcdn", "code": "uy", "confidence": 0.98},
    "world-cup-wales": {"kind": "flagcdn", "code": "gb-wls", "confidence": 0.96},
    "world-cup-yugoslavia": {
        "kind": "wikimedia_file",
        "filename": "Flag of Yugoslavia.svg",
        "confidence": 0.9,
    },
    "world-cup-zaire": {
        "kind": "wikimedia_file",
        "filename": "Flag of Zaire.svg",
        "confidence": 0.88,
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_repo_relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def build_source_url(source_config: dict[str, object]) -> str:
    kind = source_config["kind"]
    if kind == "flagcdn":
        return f"https://flagcdn.com/w640/{source_config['code']}.png"
    if kind == "wikimedia_file":
        filename = str(source_config["filename"])
        return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(filename)}?width=640"
    raise ValueError(f"Unsupported source kind: {kind}")


def fetch_bytes(session: requests.Session, url: str) -> bytes:
    delay_seconds = 1.0
    last_error: Exception | None = None
    for _ in range(4):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code in RETRYABLE_STATUS_CODES:
                time.sleep(delay_seconds)
                delay_seconds *= 2
                continue
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            last_error = error
            time.sleep(delay_seconds)
            delay_seconds *= 2
    if last_error is None:
        raise RuntimeError(f"Unable to fetch asset: {url}")
    raise last_error


def save_png(image_bytes: bytes, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(image_bytes)) as image:
        image = image.convert("RGBA")
        if max(image.size) > MAX_DOWNLOAD_DIMENSION:
            image.thumbnail((MAX_DOWNLOAD_DIMENSION, MAX_DOWNLOAD_DIMENSION))
        image.save(output_path, format="PNG")


def main() -> None:
    reconciliation = json.loads(RECONCILIATION_PATH.read_text(encoding="utf-8"))
    teams = reconciliation["teams"]
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"})

    manifest_entries: list[dict[str, object]] = []
    published = 0
    unresolved = 0

    for team in teams:
        team_slug = team["wc_team_id"]
        output_path = OUTPUT_DIR / f"{team_slug}.png"
        source_config = TEAM_SOURCE_MAP.get(team_slug)
        if output_path.exists():
            manifest_entries.append(
                {
                    "team_slug": team_slug,
                    "display_name": team["display_name"],
                    "asset_path": to_repo_relative(output_path),
                    "source": source_config["kind"] if source_config else "preexisting_overlay",
                    "source_url": build_source_url(source_config) if source_config else None,
                    "status": "published",
                    "confidence": source_config.get("confidence", 1.0) if source_config else 1.0,
                    "surface_priority": team["surface_priority"],
                    "published_at": utc_now(),
                }
            )
            continue

        if source_config is None:
            manifest_entries.append(
                {
                    "team_slug": team_slug,
                    "display_name": team["display_name"],
                    "asset_path": None,
                    "source": None,
                    "source_url": None,
                    "status": "no_approved_source",
                    "confidence": 0.0,
                    "surface_priority": team["surface_priority"],
                    "published_at": None,
                }
            )
            unresolved += 1
            continue

        source_url = build_source_url(source_config)
        try:
            image_bytes = fetch_bytes(session, source_url)
            save_png(image_bytes, output_path)
            manifest_entries.append(
                {
                    "team_slug": team_slug,
                    "display_name": team["display_name"],
                    "asset_path": to_repo_relative(output_path),
                    "source": source_config["kind"],
                    "source_url": source_url,
                    "status": "published",
                    "confidence": source_config["confidence"],
                    "surface_priority": team["surface_priority"],
                    "published_at": utc_now(),
                }
            )
            published += 1
        except Exception as error:  # noqa: BLE001
            manifest_entries.append(
                {
                    "team_slug": team_slug,
                    "display_name": team["display_name"],
                    "asset_path": None,
                    "source": source_config["kind"],
                    "source_url": source_url,
                    "status": "download_failed",
                    "confidence": source_config["confidence"],
                    "surface_priority": team["surface_priority"],
                    "published_at": None,
                    "error": str(error),
                }
            )
            unresolved += 1

    manifest_entries.sort(key=lambda entry: str(entry["team_slug"]))
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "generated_at": utc_now(),
                "published_count": sum(1 for entry in manifest_entries if entry["status"] == "published"),
                "unresolved_count": sum(1 for entry in manifest_entries if entry["status"] != "published"),
                "entries": manifest_entries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "published_new": published,
                "published_total": sum(1 for entry in manifest_entries if entry["status"] == "published"),
                "unresolved": unresolved,
                "manifest_path": to_repo_relative(MANIFEST_PATH),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
