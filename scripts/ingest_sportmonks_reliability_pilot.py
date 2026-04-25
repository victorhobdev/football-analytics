from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.src.core.config import get_settings
from api.src.db.client import db_client

ENV_PATH = ROOT / ".env"
REPORT_PATH = ROOT / "quality" / "sportmonks_ingestion_report.md"
PROBE_JSON_PATH = ROOT / "quality" / "sportmonks_probe_report.json"

TEAM_ID_FLAMENGO = 1024
EVERTON_RIBEIRO_ID = 215915
PROVIDER = "sportmonks"
COACH_HISTORICAL_YEARS = [2020, 2021, 2022, 2023]
COACH_PROVIDER_YEARS = [2024, 2025]
TRANSFER_WINDOW = ("2023-12-01", "2023-12-31")


def _read_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _setting(name: str, default: str | None = None) -> str | None:
    env_values = _read_env_file()
    return env_values.get(name) or default


class SportMonksClient:
    def __init__(self) -> None:
        token = _setting("API_KEY_SPORTMONKS")
        if not token:
            raise RuntimeError("API_KEY_SPORTMONKS missing in .env")
        self.token = token
        self.base_url = (_setting("SPORTMONKS_BASE_URL", "https://api.sportmonks.com/v3/football") or "").rstrip("/")
        self.request_count = 0

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_params = {"api_token": self.token}
        request_params.update(params or {})
        url = f"{self.base_url}/{path.lstrip('/')}?{urlencode(request_params)}"
        request = Request(url, headers={"User-Agent": "football-analytics-sportmonks-pilot/1.0"})
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                self.request_count += 1
                with urlopen(request, timeout=45) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                body = exc.read().decode("utf-8")
                if exc.code in {429, 500, 502, 503, 504} and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    last_error = exc
                    continue
                raise RuntimeError(f"SportMonks HTTP {exc.code} path={path} body={body[:300]}") from exc
            except URLError as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise RuntimeError(f"SportMonks network error path={path}: {exc}") from exc
        raise RuntimeError(f"SportMonks retries exhausted path={path}: {last_error}")

    def paged(self, path: str, params: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
        page = 1
        rows: list[dict[str, Any]] = []
        messages: list[str] = []
        while True:
            payload = self.get(path, {**(params or {}), "per_page": 50, "page": page})
            data = payload.get("data")
            if isinstance(data, list):
                rows.extend(data)
            if payload.get("message"):
                messages.append(str(payload["message"]))
            pagination = payload.get("pagination") or {}
            if not pagination.get("has_more"):
                break
            page += 1
        return rows, messages


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _coach_name(coach: dict[str, Any]) -> str | None:
    for key in ("display_name", "name", "common_name"):
        value = coach.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _team_name(value: dict[str, Any] | None) -> str | None:
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    return name.strip() if isinstance(name, str) and name.strip() else None


def _load_local_match_teams() -> set[tuple[int, int]]:
    rows = db_client.fetch_all(
        """
        select match_id, home_team_id as team_id
        from mart.fact_matches
        where date_day <= %s
        union all
        select match_id, away_team_id as team_id
        from mart.fact_matches
        where date_day <= %s
        """,
        [get_settings().product_data_cutoff, get_settings().product_data_cutoff],
    )
    return {(int(row["match_id"]), int(row["team_id"])) for row in rows}


def _load_team_ids_by_year(years: list[int]) -> dict[int, list[int]]:
    placeholders = ", ".join(["%s"] * len(years))
    rows = db_client.fetch_all(
        f"""
        with match_teams as (
          select season, home_team_id as team_id
          from mart.fact_matches
          where date_day <= %s
            and season in ({placeholders})
          union all
          select season, away_team_id as team_id
          from mart.fact_matches
          where date_day <= %s
            and season in ({placeholders})
        )
        select season, array_agg(distinct team_id order by team_id) as team_ids
        from match_teams
        where team_id is not null
        group by season
        order by season
        """,
        [get_settings().product_data_cutoff, *years, get_settings().product_data_cutoff, *years],
    )
    return {
        int(row["season"]): [int(team_id) for team_id in (row.get("team_ids") or [])]
        for row in rows
    }


def _coverage(team_id: int | None = None) -> dict[str, Any]:
    team_filter = "and mt.team_id = %s" if team_id is not None else ""
    params: list[Any] = [get_settings().product_data_cutoff, get_settings().product_data_cutoff]
    if team_id is not None:
        params.append(team_id)
    row = db_client.fetch_one(
        f"""
        with match_teams as (
          select match_id, home_team_id as team_id
          from mart.fact_matches
          where date_day <= %s
          union all
          select match_id, away_team_id as team_id
          from mart.fact_matches
          where date_day <= %s
        )
        select
          count(*) as total_match_teams,
          count(fcma.*) filter (where fcma.is_public_eligible) as public_assignments
        from match_teams mt
        left join mart.fact_coach_match_assignment fcma
          on fcma.match_id = mt.match_id
         and fcma.team_id = mt.team_id
        where 1=1 {team_filter}
        """,
        params,
    ) or {}
    total = int(row.get("total_match_teams") or 0)
    assigned = int(row.get("public_assignments") or 0)
    return {
        "total_match_teams": total,
        "public_assignments": assigned,
        "coverage_pct": round((assigned / total * 100), 2) if total else 0.0,
    }


def _flamengo_year_coverage() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with match_teams as (
          select match_id, competition_key, season, home_team_id as team_id
          from mart.fact_matches
          where date_day <= %s
          union all
          select match_id, competition_key, season, away_team_id as team_id
          from mart.fact_matches
          where date_day <= %s
        )
        select
          mt.competition_key,
          mt.season,
          count(*) as matches,
          count(fcma.*) filter (where fcma.is_public_eligible) as assigned,
          round(
            100.0 * count(fcma.*) filter (where fcma.is_public_eligible) / nullif(count(*), 0),
            2
          ) as coverage_pct
        from match_teams mt
        left join mart.fact_coach_match_assignment fcma
          on fcma.match_id = mt.match_id
         and fcma.team_id = mt.team_id
        where mt.team_id = %s
          and mt.season between 2020 and 2025
        group by mt.competition_key, mt.season
        order by mt.season, mt.competition_key
        """,
        [get_settings().product_data_cutoff, get_settings().product_data_cutoff, TEAM_ID_FLAMENGO],
    )


def _coverage_for_years(years: list[int], team_id: int | None = None) -> dict[str, Any]:
    placeholders = ", ".join(["%s"] * len(years))
    params: list[Any] = [get_settings().product_data_cutoff, *years, get_settings().product_data_cutoff, *years]
    team_filter = ""
    if team_id is not None:
        team_filter = "and mt.team_id = %s"
        params.append(team_id)
    row = db_client.fetch_one(
        f"""
        with match_teams as (
          select match_id, season, home_team_id as team_id
          from mart.fact_matches
          where date_day <= %s
            and season in ({placeholders})
          union all
          select match_id, season, away_team_id as team_id
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
        where 1=1 {team_filter}
        """,
        params,
    ) or {}
    total = int(row.get("total_match_teams") or 0)
    assigned = int(row.get("public_assignments") or 0)
    return {
        "years": years,
        "total_match_teams": total,
        "public_assignments": assigned,
        "coverage_pct": round((assigned / total * 100), 2) if total else 0.0,
    }


def _table_count(table: str) -> int:
    row = db_client.fetch_one(f"select count(*) as rows from {table}") or {}
    return int(row.get("rows") or 0)


def _execute_many(cursor: Any, sql: str, rows: list[tuple[Any, ...]]) -> None:
    for row in rows:
        cursor.execute(sql, row)


def _ingest_coach_fixtures(client: SportMonksClient, local_match_teams: set[tuple[int, int]], run_id: str) -> dict[str, Any]:
    fetched_by_year: dict[int, int] = {}
    blocked_years: dict[int, list[str]] = {}
    fixtures: list[dict[str, Any]] = []
    team_ids_by_year = _load_team_ids_by_year(COACH_PROVIDER_YEARS)
    requested_team_years: dict[int, int] = {}

    for year in COACH_HISTORICAL_YEARS:
        rows, messages = client.paged(
            f"fixtures/between/{year}-01-01/{year}-12-31/{TEAM_ID_FLAMENGO}",
            {"include": "coaches;participants;state"},
        )
        fetched_by_year[year] = len(rows)
        if messages and not rows:
            blocked_years[year] = messages
    for year in COACH_PROVIDER_YEARS:
        team_ids = team_ids_by_year.get(year, [])
        requested_team_years[year] = len(team_ids)
        year_rows = 0
        year_messages: list[str] = []
        for team_id in team_ids:
            rows, messages = client.paged(
                f"fixtures/between/{year}-01-01/{year}-12-31/{team_id}",
                {"include": "coaches;participants;state"},
            )
            year_rows += len(rows)
            fixtures.extend(rows)
            year_messages.extend(messages)
        fetched_by_year[year] = year_rows
        if year_messages and year_rows == 0:
            blocked_years[year] = year_messages

    coach_rows: dict[int, dict[str, Any]] = {}
    raw_fixture_rows: dict[tuple[int, int, int], tuple[Any, ...]] = {}
    stg_rows: dict[tuple[int, int, int], tuple[Any, ...]] = {}
    lineup_rows: dict[str, tuple[Any, ...]] = {}
    grouped_candidates: dict[tuple[int, int], dict[int, dict[str, Any]]] = defaultdict(dict)
    probe_records: list[dict[str, Any]] = []

    for fixture in fixtures:
        fixture_id = fixture.get("id")
        if fixture_id is None:
            continue
        fixture_id_int = int(fixture_id)
        fixture_date = _date(fixture.get("starting_at"))
        coaches = fixture.get("coaches") if isinstance(fixture.get("coaches"), list) else []
        participants = fixture.get("participants") if isinstance(fixture.get("participants"), list) else []
        participant_ids = {int(p["id"]) for p in participants if p.get("id") is not None}
        linked = 0

        for coach in coaches:
            coach_id = coach.get("id")
            meta = coach.get("meta") if isinstance(coach.get("meta"), dict) else {}
            team_id = meta.get("participant_id")
            if coach_id is None or team_id is None:
                continue
            coach_id_int = int(coach_id)
            team_id_int = int(team_id)
            linked += 1
            coach_rows[coach_id_int] = coach
            name = _coach_name(coach)
            source_record_id = f"fixture:{fixture_id_int}:team:{team_id_int}:coach:{coach_id_int}"
            is_local = (fixture_id_int, team_id_int) in local_match_teams
            is_public = bool(is_local and fixture_date and fixture_date <= get_settings().product_data_cutoff)
            payload = {"fixture": fixture, "coach": coach}

            row_key = (fixture_id_int, team_id_int, coach_id_int)
            raw_fixture_rows[row_key] = (
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
                    fixture_id_int if is_local else None,
                    team_id_int,
                    team_id_int if is_local else None,
                    coach_id_int,
                    name,
                    coach.get("display_name"),
                    fixture_date,
                    "lineup_source",
                    0.95 if is_public and name else 0.0,
                    is_local,
                    is_public,
                    _json(payload),
                    run_id,
                )
            if is_public:
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
                grouped_candidates[(fixture_id_int, team_id_int)][coach_id_int] = {
                    "coach_id": coach_id_int,
                    "name": name,
                    "source_record_id": source_record_id,
                }

        probe_records.append(
            {
                "fixture_id": fixture_id_int,
                "starting_at": fixture.get("starting_at"),
                "participant_ids": sorted(participant_ids),
                "coaches": len(coaches),
                "coaches_with_team_binding": linked,
                "local_fixture": any((fixture_id_int, team_id) in local_match_teams for team_id in participant_ids),
            }
        )

    identity_rows = [
        (
            PROVIDER,
            coach_id,
            coach.get("name"),
            coach.get("display_name"),
            coach.get("common_name"),
            coach.get("firstname"),
            coach.get("lastname"),
            coach.get("image_path"),
            _json(coach),
            run_id,
        )
        for coach_id, coach in coach_rows.items()
    ]
    identity_candidate_rows = [
        (
            "sportmonks_fixture_coaches",
            f"coach:{coach_id}",
            PROVIDER,
            coach_id,
            coach.get("name"),
            coach.get("display_name") or coach.get("name") or coach.get("common_name"),
            _json([coach.get("common_name")] if coach.get("common_name") else []),
            coach.get("image_path"),
            0.95 if _coach_name(coach) else 0.0,
            _json(coach),
            run_id,
        )
        for coach_id, coach in coach_rows.items()
    ]
    grouped_candidate_lists = {
        key: list(candidates.values())
        for key, candidates in grouped_candidates.items()
    }

    with db_client._connection() as conn:
        with conn.cursor() as cursor:
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
                identity_rows,
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
                list(raw_fixture_rows.values()),
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
                identity_candidate_rows,
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
                  identity_confidence = greatest(
                    coalesce(mart.coach_identity.identity_confidence, 0),
                    coalesce(excluded.identity_confidence, 0)
                  ),
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
            for (match_id, team_id), candidates in grouped_candidate_lists.items():
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
                        """,
                        (match_id, team_id, candidate["source_record_id"], candidate["coach_id"]),
                    )
                else:
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
                        """,
                        (
                            match_id,
                            team_id,
                            "multiple_or_invalid_coaches_in_fixture_payload",
                            f"fixture:{match_id}:team:{team_id}:blocked_conflict",
                        ),
                    )
        conn.commit()

    return {
        "fetched_by_year": fetched_by_year,
        "blocked_years": blocked_years,
        "requested_team_years": requested_team_years,
        "fixtures_fetched": len(fixtures),
        "coach_identities_seen": len(coach_rows),
        "raw_fixture_coach_rows_seen": len(raw_fixture_rows),
        "local_public_candidate_rows": len(lineup_rows),
        "public_assignments_attempted": sum(
            1 for items in grouped_candidate_lists.values() if len(items) == 1 and items[0]["name"]
        ),
        "blocked_conflicts_attempted": sum(
            1 for items in grouped_candidate_lists.values() if len(items) != 1 or not items[0]["name"]
        ),
        "probe_records": probe_records,
    }


def _transfer_name(row: dict[str, Any], relation: str) -> str | None:
    return _team_name(row.get(relation) if isinstance(row.get(relation), dict) else None)


def _ingest_transfers(client: SportMonksClient, run_id: str) -> dict[str, Any]:
    player_rows, player_messages = client.paged(
        f"transfers/players/{EVERTON_RIBEIRO_ID}",
        {"include": "type;fromTeam;toTeam;player"},
    )
    window_rows, window_messages = client.paged(
        f"transfers/between/{TRANSFER_WINDOW[0]}/{TRANSFER_WINDOW[1]}",
        {"include": "type;fromTeam;toTeam;player", "order": "asc"},
    )
    unique: dict[int, dict[str, Any]] = {}
    for row in [*player_rows, *window_rows]:
        if row.get("id") is not None:
            unique[int(row["id"])] = row

    raw_rows: list[tuple[Any, ...]] = []
    stg_rows: list[tuple[Any, ...]] = []
    for transfer_id, row in unique.items():
        player = row.get("player") if isinstance(row.get("player"), dict) else {}
        type_payload = row.get("type") if isinstance(row.get("type"), dict) else {}
        amount = row.get("amount")
        amount_text = None if amount is None else str(amount)
        raw_rows.append(
            (
                PROVIDER,
                transfer_id,
                row.get("player_id"),
                row.get("from_team_id"),
                row.get("to_team_id"),
                _date(row.get("date")),
                row.get("completed"),
                row.get("career_ended"),
                row.get("type_id"),
                row.get("position_id"),
                amount_text,
                _json(row),
                run_id,
            )
        )
        stg_rows.append(
            (
                PROVIDER,
                transfer_id,
                row.get("player_id"),
                player.get("display_name") or player.get("name"),
                row.get("from_team_id"),
                _transfer_name(row, "fromteam"),
                row.get("to_team_id"),
                _transfer_name(row, "toteam"),
                _date(row.get("date")),
                row.get("completed"),
                row.get("career_ended"),
                row.get("type_id"),
                type_payload.get("name"),
                row.get("position_id"),
                amount_text,
                _json(row),
                run_id,
            )
        )

    with db_client._connection() as conn:
        with conn.cursor() as cursor:
            _execute_many(
                cursor,
                """
                insert into raw.sportmonks_transfer_events (
                  provider, transfer_id, player_id, from_team_id, to_team_id, transfer_date,
                  completed, career_ended, type_id, position_id, amount, payload, ingested_run
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                on conflict (provider, transfer_id) do update set
                  player_id = excluded.player_id,
                  from_team_id = excluded.from_team_id,
                  to_team_id = excluded.to_team_id,
                  transfer_date = excluded.transfer_date,
                  completed = excluded.completed,
                  career_ended = excluded.career_ended,
                  type_id = excluded.type_id,
                  position_id = excluded.position_id,
                  amount = excluded.amount,
                  payload = excluded.payload,
                  ingested_run = excluded.ingested_run,
                  updated_at = now()
                """,
                raw_rows,
            )
            _execute_many(
                cursor,
                """
                insert into mart.stg_sportmonks_transfer_events (
                  provider, transfer_id, player_id, player_name, from_team_id, from_team_name,
                  to_team_id, to_team_name, transfer_date, completed, career_ended, type_id,
                  type_name, position_id, amount, payload, ingested_run
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                on conflict (provider, transfer_id) do update set
                  player_id = excluded.player_id,
                  player_name = excluded.player_name,
                  from_team_id = excluded.from_team_id,
                  from_team_name = excluded.from_team_name,
                  to_team_id = excluded.to_team_id,
                  to_team_name = excluded.to_team_name,
                  transfer_date = excluded.transfer_date,
                  completed = excluded.completed,
                  career_ended = excluded.career_ended,
                  type_id = excluded.type_id,
                  type_name = excluded.type_name,
                  position_id = excluded.position_id,
                  amount = excluded.amount,
                  payload = excluded.payload,
                  ingested_run = excluded.ingested_run,
                  updated_at = now()
                """,
                stg_rows,
            )
            _execute_many(
                cursor,
                """
                insert into raw.player_transfers (
                  provider, transfer_id, player_id, from_team_id, to_team_id, transfer_date,
                  completed, career_ended, type_id, position_id, amount, payload, ingested_run
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                on conflict (provider, transfer_id) do update set
                  player_id = excluded.player_id,
                  from_team_id = excluded.from_team_id,
                  to_team_id = excluded.to_team_id,
                  transfer_date = excluded.transfer_date,
                  completed = excluded.completed,
                  career_ended = excluded.career_ended,
                  type_id = excluded.type_id,
                  position_id = excluded.position_id,
                  amount = excluded.amount,
                  payload = excluded.payload,
                  ingested_run = excluded.ingested_run,
                  updated_at = now()
                """,
                [(r[0], r[1], r[2], r[4], r[6], r[8], r[9], r[10], r[11], r[13], r[14], r[15], r[16]) for r in stg_rows],
            )
        conn.commit()

    type_counts = Counter(str(row.get("type_id")) for row in unique.values())
    return {
        "everton_ribeiro_events": len(player_rows),
        "december_2023_events": len(window_rows),
        "unique_transfer_events_ingested": len(unique),
        "player_messages": player_messages,
        "window_messages": window_messages,
        "type_counts": dict(type_counts),
    }


def _write_reports(summary: dict[str, Any]) -> None:
    PROBE_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    before_global = summary["coverage_before"]["global"]
    after_global = summary["coverage_after"]["global"]
    before_flamengo = summary["coverage_before"]["flamengo"]
    after_flamengo = summary["coverage_after"]["flamengo"]
    before_provider_global = summary["provider_window_before"]["global_2024_2025"]
    after_provider_global = summary["provider_window_after"]["global_2024_2025"]
    before_provider_flamengo = summary["provider_window_before"]["flamengo_2024_2025"]
    after_provider_flamengo = summary["provider_window_after"]["flamengo_2024_2025"]
    coach = summary["coach_ingestion"]
    transfers = summary["transfer_ingestion"]

    lines = [
        "# SportMonks reliability ingestion report",
        "",
        "## Run",
        "",
        f"- Run id: `{summary['run_id']}`",
        f"- API requests: `{summary['api_requests']}`",
        f"- Product cutoff: `{get_settings().product_data_cutoff.isoformat()}`",
        "",
        "## Coach assignment coverage",
        "",
        f"- Global before: `{before_global['public_assignments']}/{before_global['total_match_teams']}` ({before_global['coverage_pct']}%)",
        f"- Global after: `{after_global['public_assignments']}/{after_global['total_match_teams']}` ({after_global['coverage_pct']}%)",
        f"- Flamengo 2020-2025 before: `{before_flamengo['public_assignments']}/{before_flamengo['total_match_teams']}` ({before_flamengo['coverage_pct']}%)",
        f"- Flamengo 2020-2025 after: `{after_flamengo['public_assignments']}/{after_flamengo['total_match_teams']}` ({after_flamengo['coverage_pct']}%)",
        f"- Provider window 2024-2025 before: `{before_provider_global['public_assignments']}/{before_provider_global['total_match_teams']}` ({before_provider_global['coverage_pct']}%)",
        f"- Provider window 2024-2025 after: `{after_provider_global['public_assignments']}/{after_provider_global['total_match_teams']}` ({after_provider_global['coverage_pct']}%)",
        f"- Flamengo 2024-2025 before: `{before_provider_flamengo['public_assignments']}/{before_provider_flamengo['total_match_teams']}` ({before_provider_flamengo['coverage_pct']}%)",
        f"- Flamengo 2024-2025 after: `{after_provider_flamengo['public_assignments']}/{after_provider_flamengo['total_match_teams']}` ({after_provider_flamengo['coverage_pct']}%)",
        "",
        "## Coach ingestion",
        "",
        f"- Fixtures fetched by year: `{coach['fetched_by_year']}`",
        f"- Team scopes requested by year: `{coach['requested_team_years']}`",
        f"- Blocked years: `{coach['blocked_years']}`",
        f"- Fixtures fetched total: `{coach['fixtures_fetched']}`",
        f"- Coach identities observed: `{coach['coach_identities_seen']}`",
        f"- Raw fixture-coach rows observed: `{coach['raw_fixture_coach_rows_seen']}`",
        f"- Local public candidate rows: `{coach['local_public_candidate_rows']}`",
        f"- Public assignments materialized: `{coach['public_assignments_attempted']}`",
        f"- Blocked conflicts materialized: `{coach['blocked_conflicts_attempted']}`",
        "",
        "## Flamengo coverage by competition",
        "",
    ]
    for row in summary["flamengo_year_coverage"]:
        lines.append(
            f"- `{row['competition_key']}` {row['season']}: `{row['assigned']}/{row['matches']}` ({row['coverage_pct']}%)"
        )
    lines.extend(
        [
            "",
            "## Transfer ingestion",
            "",
            f"- Everton Ribeiro events fetched: `{transfers['everton_ribeiro_events']}`",
            f"- December 2023 window events fetched: `{transfers['december_2023_events']}`",
            f"- Unique transfer events upserted: `{transfers['unique_transfer_events_ingested']}`",
            f"- Type distribution: `{transfers['type_counts']}`",
            "",
            "## Table counts",
            "",
        ]
    )
    for table, counts in summary["table_counts"].items():
        lines.append(f"- `{table}`: `{counts['before']}` -> `{counts['after']}`")
    lines.extend(
        [
            "",
            "## Residual blockers",
            "",
            "- SportMonks did not return Flamengo fixtures for 2020-2023 with the current subscription/historical coverage.",
            "- Older coach assignments remain blocked until historical add-on/data access or fallback manual source is available.",
            "- `coach_tenure` remains derived from match assignments; it was not treated as authoritative.",
            "- Transfer currency remains null unless a trusted enrichment source supplies it.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    run_id = f"sportmonks_reliability_pilot_{int(time.time())}"
    client = SportMonksClient()
    table_names = [
        "raw.sportmonks_coaches",
        "raw.sportmonks_fixture_coaches",
        "raw.sportmonks_transfer_events",
        "mart.stg_sportmonks_fixture_coach_assignments",
        "mart.stg_sportmonks_transfer_events",
        "mart.coach_identity",
        "mart.stg_coach_lineup_assignments",
        "mart.fact_coach_match_assignment",
        "raw.player_transfers",
        "mart.stg_player_transfers",
    ]
    before_counts = {table: _table_count(table) for table in table_names}
    coverage_before = {"global": _coverage(), "flamengo": _coverage(TEAM_ID_FLAMENGO)}
    provider_window_before = {
        "global_2024_2025": _coverage_for_years(COACH_PROVIDER_YEARS),
        "flamengo_2024_2025": _coverage_for_years(COACH_PROVIDER_YEARS, TEAM_ID_FLAMENGO),
    }
    local_match_teams = _load_local_match_teams()
    coach_summary = _ingest_coach_fixtures(client, local_match_teams, run_id)
    transfer_summary = _ingest_transfers(client, run_id)
    after_counts = {table: _table_count(table) for table in table_names}
    coverage_after = {"global": _coverage(), "flamengo": _coverage(TEAM_ID_FLAMENGO)}
    provider_window_after = {
        "global_2024_2025": _coverage_for_years(COACH_PROVIDER_YEARS),
        "flamengo_2024_2025": _coverage_for_years(COACH_PROVIDER_YEARS, TEAM_ID_FLAMENGO),
    }
    summary = {
        "run_id": run_id,
        "api_requests": client.request_count,
        "coverage_before": coverage_before,
        "coverage_after": coverage_after,
        "provider_window_before": provider_window_before,
        "provider_window_after": provider_window_after,
        "coach_ingestion": coach_summary,
        "transfer_ingestion": transfer_summary,
        "flamengo_year_coverage": _flamengo_year_coverage(),
        "table_counts": {
            table: {"before": before_counts[table], "after": after_counts[table]}
            for table in table_names
        },
    }
    _write_reports(summary)
    print(json.dumps({k: summary[k] for k in ["run_id", "api_requests", "coverage_before", "coverage_after"]}, ensure_ascii=False))
    print(f"report={REPORT_PATH}")
    print(f"probe_json={PROBE_JSON_PATH}")


if __name__ == "__main__":
    main()
