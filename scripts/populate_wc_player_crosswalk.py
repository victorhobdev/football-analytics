from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.src.db.client import db_client

LOAD_CONFIDENCE_MAP = {
    "USE_BASE": "confirmed",
    "NEEDS_REVIEW": "probable",
    "NO_MATCH": "none",
    "UNRESOLVABLE": "none",
}
SOURCE_RUN_ID = "wc_reconciliation_map_v2"
SIGNAL_WEIGHTS = {
    "exact_name_casefold": 40,
    "normalized_name_match": 30,
    "single_candidate_bonus": 15,
    "single_candidate_in_base": 15,
    "nationality_match": 20,
    "era_overlap": 15,
    "asset_quality_ok": 5,
    "multiple_candidates": -20,
    "era_mismatch": -40,
    "name_abbreviated": -10,
}


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


def _load_payload(json_path: Path) -> dict[int, dict[str, object]]:
    with json_path.open(encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    rows: dict[int, dict[str, object]] = {}
    for player in payload.get("players", []):
        wc_player_id = _to_optional_int(player.get("wc_player_id"))
        if wc_player_id is None:
            continue

        rows[wc_player_id] = player

    return rows


def _load_rows(json_path: Path) -> list[tuple[int, int | None, str, str, str]]:
    payload = _load_payload(json_path)
    rows: list[tuple[int, int | None, str, str, str]] = []
    for wc_player_id, player in sorted(payload.items()):
        rows.append(
            (
                wc_player_id,
                _to_optional_int(player.get("base_sportmonks_id")),
                LOAD_CONFIDENCE_MAP.get(str(player.get("decision") or "").strip(), "none"),
                json.dumps(player.get("match_signals_used") or []),
                SOURCE_RUN_ID,
            )
        )

    return rows


def _load_review_log(review_log_path: Path | None) -> dict[int, dict[str, str | None]]:
    if review_log_path is None or not review_log_path.exists():
        return {}

    with review_log_path.open(encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    tickets: dict[int, dict[str, str | None]] = {}
    for ticket in payload.get("tickets", []):
        if _normalize_text(ticket.get("entity_type")) != "player":
            continue

        wc_player_id = _to_optional_int(ticket.get("wc_player_id"))
        if wc_player_id is None:
            continue

        tickets[wc_player_id] = {
            "reviewer_decision": _normalize_text(ticket.get("reviewer_decision")),
            "reviewer_notes": _normalize_text(ticket.get("reviewer_notes")),
        }

    return tickets


def _compose_match_score(player: dict[str, object]) -> int | None:
    confidence_score = _to_optional_int(player.get("confidence_score"))
    if confidence_score is not None:
        return confidence_score

    signals = player.get("match_signals_used") or []
    if not isinstance(signals, list) or not signals:
        return None

    score = 0
    for signal in signals:
        score += SIGNAL_WEIGHTS.get(str(signal).strip(), 0)

    return max(0, min(100, score))


def _build_sanitized_row(
    player: dict[str, object],
    review_ticket: dict[str, str | None] | None,
) -> tuple[int, int | None, str, str, str, int | None, str | None, str | None, str | None, str | None]:
    wc_player_id = _to_optional_int(player.get("wc_player_id"))
    if wc_player_id is None:
        raise ValueError("Player row without wc_player_id cannot be sanitized.")

    decision = _normalize_text(player.get("decision")) or "NO_MATCH"
    decision_reason = _normalize_text(player.get("decision_reason"))
    reviewer_decision = (
        (review_ticket or {}).get("reviewer_decision")
        or _normalize_text(player.get("reviewer_decision"))
    )
    review_notes = (review_ticket or {}).get("reviewer_notes")
    human_audited = review_ticket is not None or reviewer_decision is not None
    base_sportmonks_id = _to_optional_int(player.get("base_sportmonks_id"))
    match_signals = json.dumps(player.get("match_signals_used") or [])
    match_score = _compose_match_score(player)
    auto_fallback = bool(player.get("auto_fallback"))

    match_confidence = "none"
    match_method: str | None = None
    blocked_reason: str | None = None

    if decision == "USE_BASE":
        match_confidence = "probable"
        match_method = "exact_name"
    elif decision == "UNRESOLVABLE" or auto_fallback:
        blocked_reason = "unresolvable_era"
        match_score = None
    elif decision == "NO_MATCH":
        if decision_reason == "candidate_found_without_usable_base_asset":
            match_confidence = "probable"
            match_method = "asset_rejected"
        elif reviewer_decision == "reject_to_overlay" or (
            decision_reason is not None and decision_reason.startswith("manual_review_reject")
        ):
            match_method = "manual"
            blocked_reason = "manual_rejection"
        else:
            blocked_reason = "no_candidate_found"
            match_score = None
    elif decision == "NEEDS_REVIEW":
        match_confidence = "probable"
        match_method = "needs_review"
    else:
        blocked_reason = "no_candidate_found"
        match_score = None

    if match_confidence == "probable" and match_score is None:
        raise ValueError(f"Probable row without match_score: wc_player_id={wc_player_id}")

    return (
        wc_player_id,
        base_sportmonks_id,
        match_confidence,
        match_signals,
        SOURCE_RUN_ID,
        match_score,
        match_method,
        "human" if human_audited else "script",
        review_notes,
        blocked_reason,
    )


def run_load(json_path: Path) -> int:
    rows = _load_rows(json_path)
    if not rows:
        print("No rows found in reconciliation map.")
        return 0

    insert_sql = """
        insert into raw.wc_player_identity_map (
            wc_player_id,
            sportmonks_player_id,
            match_confidence,
            match_signals,
            source_run_id
        )
        values (%s, %s, %s, %s::jsonb, %s)
        on conflict (wc_player_id) do update
        set sportmonks_player_id = excluded.sportmonks_player_id,
            match_confidence = excluded.match_confidence,
            match_signals = excluded.match_signals,
            source_run_id = excluded.source_run_id,
            updated_at = now();
    """

    with db_client._connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(insert_sql, rows)
        conn.commit()

    confidence_counts: dict[str, int] = {}
    for _, _, match_confidence, _, _ in rows:
        confidence_counts[match_confidence] = confidence_counts.get(match_confidence, 0) + 1

    print(f"Inserted/updated {len(rows)} rows in raw.wc_player_identity_map")
    print(json.dumps(confidence_counts, ensure_ascii=True, sort_keys=True))
    return len(rows)


def run_sanitize(json_path: Path, review_log_path: Path | None) -> int:
    payload = _load_payload(json_path)
    if not payload:
        print("No rows found in reconciliation map.")
        return 0

    existing_rows = db_client.fetch_all(
        """
        select wc_player_id
        from raw.wc_player_identity_map
        order by wc_player_id
        """
    )
    existing_ids = {int(row["wc_player_id"]) for row in existing_rows}
    payload_ids = set(payload.keys())
    if existing_ids != payload_ids:
        missing_in_db = sorted(payload_ids - existing_ids)
        missing_in_payload = sorted(existing_ids - payload_ids)
        raise RuntimeError(
            "Crosswalk cardinality mismatch. "
            f"missing_in_db={missing_in_db[:5]} "
            f"missing_in_payload={missing_in_payload[:5]}"
        )

    review_tickets = _load_review_log(review_log_path)
    rows = [
        _build_sanitized_row(payload[wc_player_id], review_tickets.get(wc_player_id))
        for wc_player_id in sorted(payload)
    ]

    update_sql = """
        update raw.wc_player_identity_map
        set sportmonks_player_id = %s,
            match_confidence = %s,
            match_signals = %s::jsonb,
            source_run_id = %s,
            match_score = %s,
            match_method = %s,
            audited_by = %s,
            audit_notes = %s,
            blocked_reason = %s,
            updated_at = now()
        where wc_player_id = %s;
    """

    with db_client._connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                update_sql,
                [
                    (
                        sportmonks_player_id,
                        match_confidence,
                        match_signals,
                        source_run_id,
                        match_score,
                        match_method,
                        audited_by,
                        audit_notes,
                        blocked_reason,
                        wc_player_id,
                    )
                    for (
                        wc_player_id,
                        sportmonks_player_id,
                        match_confidence,
                        match_signals,
                        source_run_id,
                        match_score,
                        match_method,
                        audited_by,
                        audit_notes,
                        blocked_reason,
                    ) in rows
                ],
            )
        conn.commit()

    confidence_counts: dict[str, int] = {}
    for _, _, match_confidence, _, _, _, _, _, _, _ in rows:
        confidence_counts[match_confidence] = confidence_counts.get(match_confidence, 0) + 1

    print(f"Sanitized {len(rows)} rows in raw.wc_player_identity_map")
    print(json.dumps(confidence_counts, ensure_ascii=True, sort_keys=True))
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate raw.wc_player_identity_map from wc_reconciliation_map.json.",
    )
    parser.add_argument(
        "--json-path",
        default="data/visual_assets/wc_pipeline/wc_reconciliation_map.json",
        help="Path to wc_reconciliation_map.json",
    )
    parser.add_argument(
        "--review-log-path",
        default="data/visual_assets/wc_pipeline/wc_review_log.json",
        help="Path to wc_review_log.json",
    )
    parser.add_argument(
        "--mode",
        choices=("load", "sanitize"),
        default="load",
        help="Execution mode: initial load or sanitize the existing crosswalk.",
    )
    args = parser.parse_args()

    json_path = Path(args.json_path).resolve()
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    review_log_path = Path(args.review_log_path).resolve()
    if args.mode == "sanitize":
        run_sanitize(
            json_path=json_path,
            review_log_path=review_log_path if review_log_path.exists() else None,
        )
        return

    run_load(json_path)


if __name__ == "__main__":
    main()
