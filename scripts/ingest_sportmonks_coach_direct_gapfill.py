from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.src.core.config import get_settings
from api.src.db.client import db_client
from scripts.ingest_sportmonks_reliability_pilot import (
    PROVIDER,
    SportMonksClient,
    _coach_name,
    _date,
    _execute_many,
    _json,
    _table_count,
)

REPORT_PATH = ROOT / "quality" / "sportmonks_coach_direct_gapfill_report.md"
JSON_PATH = ROOT / "quality" / "sportmonks_coach_direct_gapfill_report.json"
PROVIDER_YEARS = [2024, 2025]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preenche lacunas de tecnico por partida usando fixtures/coaches da SportMonks."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Executa as escritas em transacao e desfaz no final.")
    mode.add_argument("--execute", action="store_true", help="Grava o gapfill no banco.")
    return parser.parse_args()


def _missing_fixture_ids() -> list[dict[str, Any]]:
    placeholders = ", ".join(["%s"] * len(PROVIDER_YEARS))
    return db_client.fetch_all(
        f"""
        with match_teams as (
          select fm.match_id, fm.date_day, fm.competition_key, fm.season, fm.home_team_id as team_id
          from mart.fact_matches fm
          where fm.date_day <= %s
            and fm.season in ({placeholders})
          union all
          select fm.match_id, fm.date_day, fm.competition_key, fm.season, fm.away_team_id as team_id
          from mart.fact_matches fm
          where fm.date_day <= %s
            and fm.season in ({placeholders})
        ),
        missing as (
          select distinct mt.match_id, mt.date_day, mt.competition_key, mt.season
          from match_teams mt
          left join mart.fact_coach_match_assignment fcma
            on fcma.match_id = mt.match_id
           and fcma.team_id = mt.team_id
           and fcma.is_public_eligible
          where fcma.match_id is null
        )
        select *
        from missing
        order by date_day desc, match_id desc
        """,
        [get_settings().product_data_cutoff, *PROVIDER_YEARS, get_settings().product_data_cutoff, *PROVIDER_YEARS],
    )


def _provider_window_coverage() -> dict[str, Any]:
    placeholders = ", ".join(["%s"] * len(PROVIDER_YEARS))
    row = db_client.fetch_one(
        f"""
        with match_teams as (
          select match_id, home_team_id as team_id
          from mart.fact_matches
          where date_day <= %s
            and season in ({placeholders})
          union all
          select match_id, away_team_id as team_id
          from mart.fact_matches
          where date_day <= %s
            and season in ({placeholders})
        )
        select
          count(*) as total_match_teams,
          count(fcma.*) filter (where fcma.is_public_eligible) as public_assignments
        from match_teams mt
        left join mart.fact_coach_match_assignment fcma
          on fcma.match_id = mt.match_id
         and fcma.team_id = mt.team_id
        """,
        [get_settings().product_data_cutoff, *PROVIDER_YEARS, get_settings().product_data_cutoff, *PROVIDER_YEARS],
    ) or {}
    total = int(row.get("total_match_teams") or 0)
    assigned = int(row.get("public_assignments") or 0)
    return {
        "total_match_teams": total,
        "public_assignments": assigned,
        "coverage_pct": round((assigned / total * 100), 2) if total else 0.0,
    }


def _flamengo_coverage() -> dict[str, Any]:
    row = db_client.fetch_one(
        """
        with match_teams as (
          select match_id, home_team_id as team_id
          from mart.fact_matches
          where date_day <= %s
            and season in (2024, 2025)
          union all
          select match_id, away_team_id as team_id
          from mart.fact_matches
          where date_day <= %s
            and season in (2024, 2025)
        )
        select
          count(*) as total_match_teams,
          count(fcma.*) filter (where fcma.is_public_eligible) as public_assignments
        from match_teams mt
        left join mart.fact_coach_match_assignment fcma
          on fcma.match_id = mt.match_id
         and fcma.team_id = mt.team_id
        where mt.team_id = 1024
        """,
        [get_settings().product_data_cutoff, get_settings().product_data_cutoff],
    ) or {}
    total = int(row.get("total_match_teams") or 0)
    assigned = int(row.get("public_assignments") or 0)
    return {
        "total_match_teams": total,
        "public_assignments": assigned,
        "coverage_pct": round((assigned / total * 100), 2) if total else 0.0,
    }


def _upsert_fixture_payload(cursor: Any, fixture: dict[str, Any], run_id: str) -> tuple[int, int, int, int]:
    fixture_id = fixture.get("id")
    if fixture_id is None:
        return (0, 0, 0, 0)
    fixture_id_int = int(fixture_id)
    fixture_date = _date(fixture.get("starting_at"))
    coaches = fixture.get("coaches") if isinstance(fixture.get("coaches"), list) else []
    grouped: dict[int, dict[int, dict[str, Any]]] = defaultdict(dict)
    raw_rows: dict[tuple[int, int, int], tuple[Any, ...]] = {}
    stg_rows: dict[tuple[int, int, int], tuple[Any, ...]] = {}
    lineup_rows: dict[str, tuple[Any, ...]] = {}
    identity_rows: dict[int, tuple[Any, ...]] = {}
    identity_candidate_rows: dict[int, tuple[Any, ...]] = {}

    for coach in coaches:
        coach_id = coach.get("id")
        meta = coach.get("meta") if isinstance(coach.get("meta"), dict) else {}
        team_id = meta.get("participant_id")
        if coach_id is None or team_id is None:
            continue
        coach_id_int = int(coach_id)
        team_id_int = int(team_id)
        name = _coach_name(coach)
        source_record_id = f"fixture:{fixture_id_int}:team:{team_id_int}:coach:{coach_id_int}"
        payload = {"fixture": fixture, "coach": coach}
        row_key = (fixture_id_int, team_id_int, coach_id_int)

        identity_rows[coach_id_int] = (
            PROVIDER,
            coach_id_int,
            coach.get("name"),
            coach.get("display_name"),
            coach.get("common_name"),
            coach.get("firstname"),
            coach.get("lastname"),
            coach.get("image_path"),
            _json(coach),
            run_id,
        )
        identity_candidate_rows[coach_id_int] = (
            "sportmonks_fixture_coaches",
            f"coach:{coach_id_int}",
            PROVIDER,
            coach_id_int,
            coach.get("name"),
            coach.get("display_name") or coach.get("name") or coach.get("common_name"),
            _json([coach.get("common_name")] if coach.get("common_name") else []),
            coach.get("image_path"),
            0.95 if name else 0.0,
            _json(coach),
            run_id,
        )
        raw_rows[row_key] = (
            PROVIDER,
            fixture_id_int,
            team_id_int,
            coach_id_int,
            fixture_date,
            fixture.get("league_id"),
            fixture.get("season_id"),
            fixture.get("state_id"),
            _json(coach),
            _json(fixture),
            run_id,
        )
        stg_rows[row_key] = (
            PROVIDER,
            fixture_id_int,
            fixture_id_int,
            team_id_int,
            team_id_int,
            coach_id_int,
            name,
            coach.get("display_name"),
            fixture_date,
            "lineup_source",
            0.95 if name else 0.0,
            True,
            bool(fixture_date and fixture_date <= get_settings().product_data_cutoff),
            _json(payload),
            run_id,
        )
        lineup_rows[source_record_id] = (
            "sportmonks_fixture_coaches",
            source_record_id,
            fixture_id_int,
            team_id_int,
            PROVIDER,
            coach_id_int,
            "head_coach",
            "lineup_source",
            0.95 if name else 0.0,
            _json(payload),
            run_id,
        )
        grouped[team_id_int][coach_id_int] = {
            "coach_id": coach_id_int,
            "name": name,
            "source_record_id": source_record_id,
        }

    _execute_many(
        cursor,
        """
        insert into raw.sportmonks_coaches (
          provider, coach_id, coach_name, display_name, common_name, firstname, lastname, image_path, payload, ingested_run
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        on conflict (provider, coach_id) do update set
          coach_name = excluded.coach_name,
          display_name = excluded.display_name,
          common_name = excluded.common_name,
          firstname = excluded.firstname,
          lastname = excluded.lastname,
          image_path = excluded.image_path,
          payload = excluded.payload,
          ingested_run = excluded.ingested_run,
          updated_at = now()
        """,
        list(identity_rows.values()),
    )
    _execute_many(
        cursor,
        """
        insert into raw.sportmonks_fixture_coaches (
          provider, fixture_id, team_id, coach_id, fixture_date, league_id, season_id, state_id,
          coach_payload, fixture_payload, ingested_run
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
        on conflict (provider, fixture_id, team_id, coach_id) do update set
          fixture_date = excluded.fixture_date,
          league_id = excluded.league_id,
          season_id = excluded.season_id,
          state_id = excluded.state_id,
          coach_payload = excluded.coach_payload,
          fixture_payload = excluded.fixture_payload,
          ingested_run = excluded.ingested_run,
          updated_at = now()
        """,
        list(raw_rows.values()),
    )
    _execute_many(
        cursor,
        """
        insert into mart.stg_sportmonks_fixture_coach_assignments (
          provider, fixture_id, local_match_id, provider_team_id, team_id, provider_coach_id,
          coach_name, display_name, fixture_date, assignment_method, source_confidence,
          is_local_match, is_public_cutoff_eligible, source_payload, ingested_run
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        on conflict (provider, fixture_id, provider_team_id, provider_coach_id) do update set
          local_match_id = excluded.local_match_id,
          team_id = excluded.team_id,
          coach_name = excluded.coach_name,
          display_name = excluded.display_name,
          fixture_date = excluded.fixture_date,
          assignment_method = excluded.assignment_method,
          source_confidence = excluded.source_confidence,
          is_local_match = excluded.is_local_match,
          is_public_cutoff_eligible = excluded.is_public_cutoff_eligible,
          source_payload = excluded.source_payload,
          ingested_run = excluded.ingested_run,
          updated_at = now()
        """,
        list(stg_rows.values()),
    )
    _execute_many(
        cursor,
        """
        insert into mart.stg_coach_identity_candidates (
          source, source_record_id, provider, provider_coach_id, coach_name,
          display_name_candidate, aliases, image_url, source_confidence, source_payload, ingested_run
        )
        values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s)
        on conflict (source, source_record_id) do update set
          coach_name = excluded.coach_name,
          display_name_candidate = excluded.display_name_candidate,
          aliases = excluded.aliases,
          image_url = excluded.image_url,
          source_confidence = excluded.source_confidence,
          source_payload = excluded.source_payload,
          ingested_run = excluded.ingested_run,
          updated_at = now()
        """,
        list(identity_candidate_rows.values()),
    )
    cursor.execute(
        """
        insert into mart.coach_identity (
          provider, provider_coach_id, canonical_name, display_name, aliases,
          image_url, identity_confidence, source_refs
        )
        select
          provider,
          provider_coach_id,
          nullif(trim(coach_name), ''),
          nullif(trim(display_name_candidate), ''),
          aliases,
          image_url,
          source_confidence,
          jsonb_build_array(jsonb_build_object('source', source, 'source_record_id', source_record_id))
        from mart.stg_coach_identity_candidates
        where source = 'sportmonks_fixture_coaches'
          and provider = 'sportmonks'
          and provider_coach_id is not null
        on conflict (provider, provider_coach_id) do update set
          canonical_name = coalesce(excluded.canonical_name, mart.coach_identity.canonical_name),
          display_name = coalesce(excluded.display_name, mart.coach_identity.display_name),
          aliases = excluded.aliases,
          image_url = coalesce(excluded.image_url, mart.coach_identity.image_url),
          identity_confidence = greatest(coalesce(mart.coach_identity.identity_confidence, 0), coalesce(excluded.identity_confidence, 0)),
          source_refs = excluded.source_refs,
          updated_at = now()
        """
    )
    _execute_many(
        cursor,
        """
        insert into mart.stg_coach_lineup_assignments (
          source, source_record_id, match_id, team_id, provider, provider_coach_id,
          role, assignment_method, source_confidence, source_payload, ingested_run
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        on conflict (source, source_record_id) do update set
          match_id = excluded.match_id,
          team_id = excluded.team_id,
          provider = excluded.provider,
          provider_coach_id = excluded.provider_coach_id,
          role = excluded.role,
          assignment_method = excluded.assignment_method,
          source_confidence = excluded.source_confidence,
          source_payload = excluded.source_payload,
          ingested_run = excluded.ingested_run,
          updated_at = now()
        """,
        list(lineup_rows.values()),
    )

    public_assignments = 0
    blocked_conflicts = 0
    protected_existing_skipped = 0
    for team_id, candidates_by_coach in grouped.items():
        candidates = list(candidates_by_coach.values())
        cursor.execute(
            """
            select source
            from mart.fact_coach_match_assignment
            where match_id = %s
              and team_id = %s
            """,
            (fixture_id_int, team_id),
        )
        existing_assignment = cursor.fetchone()
        if existing_assignment and existing_assignment.get("source") != "sportmonks_fixture_coaches":
            protected_existing_skipped += 1
            continue

        if len(candidates) == 1 and candidates[0]["name"]:
            candidate = candidates[0]
            cursor.execute(
                """
                insert into mart.fact_coach_match_assignment (
                  match_id, team_id, coach_identity_id, coach_tenure_id,
                  assignment_method, assignment_confidence, conflict_reason,
                  is_public_eligible, source, source_record_id
                )
                select
                  %s, %s, ci.coach_identity_id, null,
                  'lineup_source', 0.95, null,
                  true, 'sportmonks_fixture_coaches', %s
                from mart.coach_identity ci
                where ci.provider = 'sportmonks'
                  and ci.provider_coach_id = %s
                on conflict (match_id, team_id) do update set
                  coach_identity_id = excluded.coach_identity_id,
                  coach_tenure_id = excluded.coach_tenure_id,
                  assignment_method = excluded.assignment_method,
                  assignment_confidence = excluded.assignment_confidence,
                  conflict_reason = excluded.conflict_reason,
                  is_public_eligible = excluded.is_public_eligible,
                  source = excluded.source,
                  source_record_id = excluded.source_record_id,
                  updated_at = now()
                where mart.fact_coach_match_assignment.source = 'sportmonks_fixture_coaches'
                returning 1
                """,
                (fixture_id_int, team_id, candidate["source_record_id"], candidate["coach_id"]),
            )
            if cursor.fetchone() is not None:
                public_assignments += 1
        elif candidates:
            cursor.execute(
                """
                insert into mart.fact_coach_match_assignment (
                  match_id, team_id, assignment_method, assignment_confidence,
                  conflict_reason, is_public_eligible, source, source_record_id
                )
                values (%s, %s, 'blocked_conflict', 0, %s, false, 'sportmonks_fixture_coaches', %s)
                on conflict (match_id, team_id) do update set
                  coach_identity_id = null,
                  coach_tenure_id = null,
                  assignment_method = excluded.assignment_method,
                  assignment_confidence = excluded.assignment_confidence,
                  conflict_reason = excluded.conflict_reason,
                  is_public_eligible = excluded.is_public_eligible,
                  source = excluded.source,
                  source_record_id = excluded.source_record_id,
                  updated_at = now()
                where mart.fact_coach_match_assignment.source = 'sportmonks_fixture_coaches'
                returning 1
                """,
                (
                    fixture_id_int,
                    team_id,
                    "multiple_or_invalid_coaches_in_fixture_payload",
                    f"fixture:{fixture_id_int}:team:{team_id}:blocked_conflict",
                ),
            )
            if cursor.fetchone() is not None:
                blocked_conflicts += 1

    return (len(coaches), public_assignments, blocked_conflicts, protected_existing_skipped)


def _write_report(summary: dict[str, Any]) -> None:
    JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    before = summary["coverage_before"]
    after = summary["coverage_after"]
    lines = [
        "# SportMonks coach direct gapfill report",
        "",
        f"- Mode: `{'EXECUCAO' if summary['executed'] else 'DRY-RUN'}`",
        f"- Run id: `{summary['run_id']}`",
        f"- Missing fixtures targeted: `{summary['fixtures_requested']}`",
        f"- Multi requests planned: `{summary['multi_requests_planned']}`",
        f"- Failed chunks: `{summary['failed_chunks']}`",
        f"- API requests: `{summary['api_requests']}`",
        f"- Fixtures returned by multi endpoint: `{summary['fixtures_seen_on_dates']}`",
        f"- Fixtures with payload: `{summary['fixtures_with_payload']}`",
        f"- Fixtures still missing after gapfill: `{summary['fixtures_without_payload']}`",
        f"- Coach rows seen: `{summary['coach_rows_seen']}`",
        f"- Public assignments inserted/refreshed: `{summary['public_assignments_upserted']}`",
        f"- Blocked conflicts upserted: `{summary['blocked_conflicts_upserted']}`",
        f"- Protected existing assignments skipped: `{summary['protected_existing_skipped']}`",
        "",
        "## Coverage",
        "",
        f"- Provider window before: `{before['public_assignments']}/{before['total_match_teams']}` ({before['coverage_pct']}%)",
        f"- Provider window after: `{after['public_assignments']}/{after['total_match_teams']}` ({after['coverage_pct']}%)",
        f"- Flamengo 2024-2025 after: `{summary['flamengo_after']['public_assignments']}/{summary['flamengo_after']['total_match_teams']}` ({summary['flamengo_after']['coverage_pct']}%)",
        "",
        "## Top messages",
        "",
    ]
    for message, count in summary["message_counts"].items():
        lines.append(f"- `{count}`: {message}")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _chunks(values: list[int], size: int) -> list[list[int]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def main() -> None:
    args = parse_args()
    execute = not args.dry_run
    run_id = f"sportmonks_coach_multi_gapfill_{int(time.time())}"
    client = SportMonksClient()
    missing = _missing_fixture_ids()
    missing_ids = sorted({int(row["match_id"]) for row in missing}, reverse=True)
    missing_id_set = set(missing_ids)
    before = _provider_window_coverage()
    before_counts = {
        "raw.sportmonks_coaches": _table_count("raw.sportmonks_coaches"),
        "raw.sportmonks_fixture_coaches": _table_count("raw.sportmonks_fixture_coaches"),
        "mart.fact_coach_match_assignment": _table_count("mart.fact_coach_match_assignment"),
    }

    fixtures_seen_on_dates = 0
    fixtures_matched = 0
    fixtures_without_payload = 0
    coach_rows_seen = 0
    public_assignments = 0
    blocked_conflicts = 0
    protected_existing_skipped = 0
    message_counts: dict[str, int] = defaultdict(int)

    chunks = _chunks(missing_ids, 20)
    failed_chunks = 0
    for fixture_ids in chunks:
        with db_client._connection() as conn:
            with conn.cursor() as cursor:
                try:
                    payload = client.get(
                        f"fixtures/multi/{','.join(str(fixture_id) for fixture_id in fixture_ids)}",
                        {"include": "coaches;participants;state"},
                    )
                except RuntimeError as exc:
                    failed_chunks += 1
                    message_counts[str(exc)[:240]] += 1
                    if execute:
                        conn.commit()
                    else:
                        conn.rollback()
                    continue
                rows = payload.get("data") if isinstance(payload.get("data"), list) else []
                if payload.get("message"):
                    message_counts[str(payload["message"])] += 1
                fixtures_seen_on_dates += len(rows)
                fixture_id_set = set(fixture_ids)
                for fixture in rows:
                    fixture_id = fixture.get("id")
                    if fixture_id is None or int(fixture_id) not in fixture_id_set:
                        continue
                    seen, assigned, blocked, protected_skipped = _upsert_fixture_payload(cursor, fixture, run_id)
                    fixtures_matched += 1
                    coach_rows_seen += seen
                    public_assignments += assigned
                    blocked_conflicts += blocked
                    protected_existing_skipped += protected_skipped
            if execute:
                conn.commit()
            else:
                conn.rollback()

    after = _provider_window_coverage()
    remaining_ids = {int(row["match_id"]) for row in _missing_fixture_ids()}
    fixtures_without_payload = len(missing_id_set & remaining_ids)
    after_counts = {
        "raw.sportmonks_coaches": _table_count("raw.sportmonks_coaches"),
        "raw.sportmonks_fixture_coaches": _table_count("raw.sportmonks_fixture_coaches"),
        "mart.fact_coach_match_assignment": _table_count("mart.fact_coach_match_assignment"),
    }
    summary = {
        "executed": execute,
        "run_id": run_id,
        "fixtures_requested": len(missing),
        "multi_requests_planned": len(chunks),
        "failed_chunks": failed_chunks,
        "api_requests": client.request_count,
        "fixtures_seen_on_dates": fixtures_seen_on_dates,
        "fixtures_with_payload": fixtures_matched,
        "fixtures_without_payload": fixtures_without_payload,
        "coach_rows_seen": coach_rows_seen,
        "public_assignments_upserted": public_assignments,
        "blocked_conflicts_upserted": blocked_conflicts,
        "protected_existing_skipped": protected_existing_skipped,
        "coverage_before": before,
        "coverage_after": after,
        "flamengo_after": _flamengo_coverage(),
        "table_counts_before": before_counts,
        "table_counts_after": after_counts,
        "message_counts": dict(message_counts),
    }
    _write_report(summary)
    print(json.dumps(summary, ensure_ascii=False))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
