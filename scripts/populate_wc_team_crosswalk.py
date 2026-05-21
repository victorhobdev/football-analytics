from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.src.db.client import db_client


def _to_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value

    normalized = str(value).strip()
    if normalized == "":
        return None
    return int(normalized)


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    if normalized == "":
        return None
    return normalized


def _load_rows(json_path: Path) -> list[tuple[int, str | None, int | None, str, str]]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") or []
    if not isinstance(entries, list):
        raise ValueError("JSON payload must contain an 'entries' list.")

    rows: list[tuple[int, str | None, int | None, str, str]] = []
    seen_wc_team_ids: set[int] = set()

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        wc_team_id = _to_optional_int(entry.get("wc_team_id"))
        confidence = _normalize_text(entry.get("confidence"))
        status = _normalize_text(entry.get("status"))
        if wc_team_id is None or confidence is None or status is None:
            raise ValueError(f"Entry missing required fields: {entry}")

        if wc_team_id in seen_wc_team_ids:
            raise ValueError(f"Duplicate wc_team_id in JSON payload: {wc_team_id}")
        seen_wc_team_ids.add(wc_team_id)

        rows.append(
            (
                wc_team_id,
                _normalize_text(entry.get("wc_display_slug")),
                _to_optional_int(entry.get("sportmonks_team_id")),
                confidence,
                status,
            )
        )

    return rows


def run(json_path: Path) -> int:
    rows = _load_rows(json_path)
    if not rows:
        print("No rows found in wc_team_crosswalk.json.")
        return 0

    upsert_sql = """
        insert into raw.wc_team_identity_map (
            wc_team_id,
            wc_display_slug,
            sportmonks_team_id,
            confidence,
            status
        )
        values (%s, %s, %s, %s, %s)
        on conflict (wc_team_id) do update
        set wc_display_slug = excluded.wc_display_slug,
            sportmonks_team_id = excluded.sportmonks_team_id,
            confidence = excluded.confidence,
            status = excluded.status,
            updated_at = now();
    """

    with db_client._connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(upsert_sql, rows)
        conn.commit()

    distribution: dict[str, int] = {}
    for _, _, sportmonks_team_id, confidence, status in rows:
        bucket = f"{confidence}/{status}"
        distribution[bucket] = distribution.get(bucket, 0) + 1

        if confidence == "confirmed" and sportmonks_team_id is None:
            raise ValueError("Confirmed row without sportmonks_team_id in JSON payload.")
        if confidence == "none" and sportmonks_team_id is not None:
            raise ValueError("None row with sportmonks_team_id in JSON payload.")

    print(f"Inserted/updated {len(rows)} rows in raw.wc_team_identity_map")
    print(json.dumps(distribution, ensure_ascii=True, sort_keys=True))
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate raw.wc_team_identity_map from wc_team_crosswalk.json.",
    )
    parser.add_argument(
        "--json-path",
        default="data/visual_assets/wc_pipeline/wc_team_crosswalk.json",
        help="Path to wc_team_crosswalk.json",
    )
    args = parser.parse_args()

    json_path = Path(args.json_path).resolve()
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    run(json_path)


if __name__ == "__main__":
    main()
