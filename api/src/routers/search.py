from __future__ import annotations

import unicodedata
from typing import Any, Literal, cast

from fastapi import APIRouter, Query, Request

from ..core.context_registry import (
    build_canonical_context,
    get_canonical_competition,
    get_canonical_competition_by_key,
    list_supported_competition_source_ids,
)
from ..core.contracts import build_api_response, build_coverage_from_counts
from ..core.errors import AppError
from ..core.filters import VenueFilter, validate_and_build_global_filters
from ..db.client import db_client

router = APIRouter(prefix="/api/v1/search", tags=["search"])

SearchType = Literal["competition", "team", "player", "match"]

SEARCH_TYPES: tuple[SearchType, ...] = ("competition", "team", "player", "match")
SUPPORTED_COMPETITION_SOURCE_IDS = list_supported_competition_source_ids()
WORLD_CUP_COMPETITION_KEY = "fifa_world_cup_mens"
WORLD_CUP_COMPETITION_ID = 0
WORLD_CUP_COMPETITION_NAME = "Copa do Mundo FIFA"
ACCENT_SOURCE = "áàâãäéèêëíìîïóòôõöúùûüçñ"
ACCENT_TARGET = "aaaaaeeeeiiiiooooouuuucn"


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _normalize_search_query(value: str) -> str:
    collapsed = " ".join(value.strip().split())
    normalized = unicodedata.normalize("NFKD", collapsed.lower())
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_marks.strip()


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _normalized_sql(column_sql: str) -> str:
    return (
        f"translate(lower(coalesce({column_sql}, '')), "
        f"'{ACCENT_SOURCE}', '{ACCENT_TARGET}')"
    )


def _parse_search_types(raw_values: list[str] | None) -> tuple[SearchType, ...]:
    if not raw_values:
        return SEARCH_TYPES

    parsed_types: list[SearchType] = []
    seen_types: set[str] = set()

    for raw_value in raw_values:
        for candidate in raw_value.split(","):
            normalized = candidate.strip().lower()
            if not normalized:
                continue

            if normalized not in SEARCH_TYPES:
                raise AppError(
                    message="Invalid value for 'types'. Expected one or more of competition, team, player, match.",
                    code="INVALID_QUERY_PARAM",
                    status=400,
                    details={"types": raw_values},
                )

            if normalized in seen_types:
                continue

            seen_types.add(normalized)
            parsed_types.append(cast(SearchType, normalized))

    return tuple(parsed_types) if parsed_types else SEARCH_TYPES


def _competition_result_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    competition_id = row.get("competition_id")
    canonical_competition = get_canonical_competition(int(competition_id)) if competition_id is not None else None
    if canonical_competition is None:
        return None

    return {
        "competitionId": str(canonical_competition.competition_id),
        "competitionKey": canonical_competition.competition_key,
        "competitionName": canonical_competition.default_name,
    }


def _control_competition_result_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    competition_key = row.get("competition_key")
    if not isinstance(competition_key, str):
        return None

    canonical_competition = get_canonical_competition_by_key(competition_key)
    if canonical_competition is None:
        return None

    competition_name = row.get("competition_name")
    return {
        "competitionId": str(canonical_competition.competition_id),
        "competitionKey": canonical_competition.competition_key,
        "competitionName": competition_name.strip()
        if isinstance(competition_name, str) and competition_name.strip()
        else canonical_competition.default_name,
    }


def _context_payload(
    competition_id: int | None,
    competition_name: str | None,
    season_id: int | str | None,
) -> dict[str, str] | None:
    return build_canonical_context(
        competition_id=competition_id,
        competition_name=competition_name,
        season_id=season_id,
    )


def _build_search_coverage(
    *,
    returned_count: int,
    skipped_count: int,
) -> dict[str, Any]:
    if skipped_count <= 0:
        return {
            "status": "complete",
            "percentage": 100,
            "label": "Global search navigability coverage",
        }

    return build_coverage_from_counts(
        returned_count,
        returned_count + skipped_count,
        "Global search navigability coverage",
    )


def _search_competitions(query: str, *, limit_per_type: int) -> tuple[list[dict[str, Any]], int]:
    normalized_query = _normalize_search_query(query)
    search_pattern = f"%{_escape_like(normalized_query)}%"
    prefix_pattern = f"{_escape_like(normalized_query)}%"
    normalized_sportmonks_name = _normalized_sql("dc.league_name")
    normalized_control_name = _normalized_sql("c.competition_name")

    rows = db_client.fetch_all(
        f"""
        select
            dc.league_id as competition_id,
            case
                when {normalized_sportmonks_name} = %s then 0
                when {normalized_sportmonks_name} like %s escape '\\' then 1
                else 2
            end as search_rank
        from mart.dim_competition dc
        where dc.league_id = any(%s)
          and {normalized_sportmonks_name} like %s escape '\\'
        order by search_rank asc, lower(dc.league_name) asc, dc.league_id asc
        limit %s;
        """,
        [
            normalized_query,
            prefix_pattern,
            list(SUPPORTED_COMPETITION_SOURCE_IDS),
            search_pattern,
            limit_per_type,
        ],
    )
    control_rows = db_client.fetch_all(
        f"""
        select
            c.competition_key,
            c.competition_name,
            case
                when {normalized_control_name} = %s then 0
                when {normalized_control_name} like %s escape '\\' then 1
                else 2
            end as search_rank
        from control.competitions c
        where c.competition_key = %s
          and {normalized_control_name} like %s escape '\\'
        order by search_rank asc, lower(c.competition_name) asc, c.competition_key asc
        limit %s;
        """,
        [
            normalized_query,
            prefix_pattern,
            WORLD_CUP_COMPETITION_KEY,
            search_pattern,
            limit_per_type,
        ],
    )

    results: list[dict[str, Any]] = []
    seen_competitions: set[str] = set()
    for row in rows:
        payload = _competition_result_payload(row)
        if payload is not None:
            competition_id = payload["competitionId"]
            if competition_id in seen_competitions:
                continue
            seen_competitions.add(competition_id)
            results.append(payload)

    for row in control_rows:
        payload = _control_competition_result_payload(row)
        if payload is None:
            continue

        competition_id = payload["competitionId"]
        if competition_id in seen_competitions:
            continue

        seen_competitions.add(competition_id)
        results.append(payload)

    return results, 0


def _search_teams(
    query: str,
    *,
    preferred_competition_ids: tuple[int, ...],
    preferred_season_id: int | None,
    limit_per_type: int,
) -> tuple[list[dict[str, Any]], int]:
    normalized_query = _normalize_search_query(query)
    search_pattern = f"%{_escape_like(normalized_query)}%"
    prefix_pattern = f"{_escape_like(normalized_query)}%"
    exact_token_start_pattern = f"{_escape_like(normalized_query)} %"
    exact_token_middle_pattern = f"% {_escape_like(normalized_query)} %"
    exact_token_suffix_pattern = f"% {_escape_like(normalized_query)}"
    token_prefix_pattern = f"% {_escape_like(normalized_query)}%"
    normalized_name = _normalized_sql("dt.team_name")
    has_preferred_competition = len(preferred_competition_ids) > 0

    rows = db_client.fetch_all(
        f"""
        with matched_teams as (
            select
                dt.team_id,
                dt.team_name,
                case
                    when {normalized_name} = %s then 0
                    when {normalized_name} like %s escape '\\'
                      or {normalized_name} like %s escape '\\'
                      or {normalized_name} like %s escape '\\' then 1
                    when {normalized_name} like %s escape '\\' then 2
                    when {normalized_name} like %s escape '\\' then 3
                    else 4
                end as search_rank
            from mart.dim_team dt
            where {normalized_name} like %s escape '\\'
        ),
        aggregated_contexts as (
            select
                mt.team_id,
                mt.team_name,
                mt.search_rank,
                case
                    when fm.competition_key = %s then %s
                    else dc.league_id
                end as competition_id,
                case
                    when fm.competition_key = %s then %s
                    else dc.league_name
                end as competition_name,
                fm.season,
                max(fm.date_day) as last_match_date,
                count(*)::int as matches_played
            from matched_teams mt
            inner join mart.fact_matches fm
              on fm.home_team_id = mt.team_id
              or fm.away_team_id = mt.team_id
            inner join mart.dim_competition dc
              on dc.competition_sk = fm.competition_sk
            where dc.league_id = any(%s)
               or fm.competition_key = %s
            group by
                mt.team_id,
                mt.team_name,
                mt.search_rank,
                competition_id,
                competition_name,
                fm.season
        ),
        ranked_contexts as (
            select
                ac.*,
                case
                    when %s::boolean
                      and %s::int is not null
                      and ac.competition_id = any(%s)
                      and ac.season = %s then 0
                    when %s::boolean
                      and ac.competition_id = any(%s) then 1
                    when %s::int is not null
                      and ac.season = %s then 2
                    else 3
                end as context_priority,
                row_number() over (
                    partition by ac.team_id
                    order by
                        case
                            when %s::boolean
                              and %s::int is not null
                              and ac.competition_id = any(%s)
                              and ac.season = %s then 0
                            when %s::boolean
                              and ac.competition_id = any(%s) then 1
                            when %s::int is not null
                              and ac.season = %s then 2
                            else 3
                        end asc,
                        ac.last_match_date desc nulls last,
                        ac.matches_played desc,
                        ac.season desc,
                        ac.competition_id asc
                ) as context_rank
            from aggregated_contexts ac
        )
        select
            team_id,
            team_name,
            competition_id,
            competition_name,
            season,
            last_match_date,
            matches_played,
            search_rank,
            context_priority
        from ranked_contexts
        where context_rank = 1
        order by
            search_rank asc,
            context_priority asc,
            matches_played desc,
            last_match_date desc nulls last,
            lower(team_name) asc,
            team_id asc
        limit %s;
        """,
        [
            normalized_query,
            exact_token_start_pattern,
            exact_token_middle_pattern,
            exact_token_suffix_pattern,
            prefix_pattern,
            token_prefix_pattern,
            search_pattern,
            WORLD_CUP_COMPETITION_KEY,
            WORLD_CUP_COMPETITION_ID,
            WORLD_CUP_COMPETITION_KEY,
            WORLD_CUP_COMPETITION_NAME,
            list(SUPPORTED_COMPETITION_SOURCE_IDS),
            WORLD_CUP_COMPETITION_KEY,
            has_preferred_competition,
            preferred_season_id,
            list(preferred_competition_ids),
            preferred_season_id,
            has_preferred_competition,
            list(preferred_competition_ids),
            preferred_season_id,
            preferred_season_id,
            has_preferred_competition,
            preferred_season_id,
            list(preferred_competition_ids),
            preferred_season_id,
            has_preferred_competition,
            list(preferred_competition_ids),
            preferred_season_id,
            preferred_season_id,
            limit_per_type,
        ],
    )

    results: list[dict[str, Any]] = []
    skipped_count = 0
    for row in rows:
        default_context = _context_payload(
            competition_id=row.get("competition_id"),
            competition_name=row.get("competition_name"),
            season_id=row.get("season"),
        )
        if default_context is None:
            skipped_count += 1
            continue

        results.append(
            {
                "teamId": str(row["team_id"]),
                "teamName": row["team_name"],
                "defaultContext": default_context,
            }
        )

    return results, skipped_count


def _search_players(
    query: str,
    *,
    preferred_competition_ids: tuple[int, ...],
    preferred_season_id: int | None,
    limit_per_type: int,
) -> tuple[list[dict[str, Any]], int]:
    normalized_query = _normalize_search_query(query)
    search_pattern = f"%{_escape_like(normalized_query)}%"
    prefix_pattern = f"{_escape_like(normalized_query)}%"
    exact_token_start_pattern = f"{_escape_like(normalized_query)} %"
    exact_token_middle_pattern = f"% {_escape_like(normalized_query)} %"
    exact_token_suffix_pattern = f"% {_escape_like(normalized_query)}"
    token_prefix_pattern = f"% {_escape_like(normalized_query)}%"
    normalized_name = _normalized_sql("dp.player_name")
    has_preferred_competition = len(preferred_competition_ids) > 0

    rows = db_client.fetch_all(
        f"""
        with matched_players as (
            select
                dp.player_id,
                dp.player_name,
                case
                    when {normalized_name} = %s then 0
                    when {normalized_name} like %s escape '\\'
                      or {normalized_name} like %s escape '\\'
                      or {normalized_name} like %s escape '\\' then 1
                    when {normalized_name} like %s escape '\\' then 2
                    when {normalized_name} like %s escape '\\' then 3
                    else 4
                end as search_rank
            from mart.dim_player dp
            where {normalized_name} like %s escape '\\'
        ),
        aggregated_contexts as (
            select
                mp.player_id,
                mp.player_name,
                mp.search_rank,
                pms.team_id,
                pms.team_name,
                pms.position_name,
                dc.league_id,
                dc.league_name,
                pms.season,
                max(pms.match_date) as last_match_date,
                count(distinct pms.match_id)::int as matches_played
            from matched_players mp
            inner join mart.player_match_summary pms
              on pms.player_id = mp.player_id
            inner join mart.dim_competition dc
              on dc.competition_sk = pms.competition_sk
            where dc.league_id = any(%s)
            group by
                mp.player_id,
                mp.player_name,
                mp.search_rank,
                pms.team_id,
                pms.team_name,
                pms.position_name,
                dc.league_id,
                dc.league_name,
                pms.season
        ),
        ranked_contexts as (
            select
                ac.*,
                case
                    when %s::boolean
                      and %s::int is not null
                      and ac.league_id = any(%s)
                      and ac.season = %s then 0
                    when %s::boolean
                      and ac.league_id = any(%s) then 1
                    when %s::int is not null
                      and ac.season = %s then 2
                    else 3
                end as context_priority,
                row_number() over (
                    partition by ac.player_id
                    order by
                        case
                            when %s::boolean
                              and %s::int is not null
                              and ac.league_id = any(%s)
                              and ac.season = %s then 0
                            when %s::boolean
                              and ac.league_id = any(%s) then 1
                            when %s::int is not null
                              and ac.season = %s then 2
                            else 3
                        end asc,
                        ac.last_match_date desc nulls last,
                        ac.matches_played desc,
                        ac.season desc,
                        ac.league_id asc,
                        ac.team_id asc nulls last
                ) as context_rank
            from aggregated_contexts ac
        )
        select
            player_id,
            player_name,
            team_id,
            team_name,
            position_name,
            league_id,
            league_name,
            season,
            last_match_date,
            matches_played,
            search_rank,
            context_priority
        from ranked_contexts
        where context_rank = 1
        order by
            search_rank asc,
            context_priority asc,
            matches_played desc,
            last_match_date desc nulls last,
            lower(player_name) asc,
            player_id asc
        limit %s;
        """,
        [
            normalized_query,
            exact_token_start_pattern,
            exact_token_middle_pattern,
            exact_token_suffix_pattern,
            prefix_pattern,
            token_prefix_pattern,
            search_pattern,
            list(SUPPORTED_COMPETITION_SOURCE_IDS),
            has_preferred_competition,
            preferred_season_id,
            list(preferred_competition_ids),
            preferred_season_id,
            has_preferred_competition,
            list(preferred_competition_ids),
            preferred_season_id,
            preferred_season_id,
            has_preferred_competition,
            preferred_season_id,
            list(preferred_competition_ids),
            preferred_season_id,
            has_preferred_competition,
            list(preferred_competition_ids),
            preferred_season_id,
            preferred_season_id,
            limit_per_type,
        ],
    )

    results: list[dict[str, Any]] = []
    skipped_count = 0
    for row in rows:
        default_context = _context_payload(
            competition_id=row.get("league_id"),
            competition_name=row.get("league_name"),
            season_id=row.get("season"),
        )
        if default_context is None:
            skipped_count += 1
            continue

        results.append(
            {
                "playerId": str(row["player_id"]),
                "playerName": row["player_name"],
                "teamId": str(row["team_id"]) if row.get("team_id") is not None else None,
                "teamName": row.get("team_name"),
                "position": row.get("position_name"),
                "defaultContext": default_context,
            }
        )

    return results, skipped_count


def _search_matches(
    query: str,
    *,
    preferred_competition_ids: tuple[int, ...],
    preferred_season_id: int | None,
    limit_per_type: int,
) -> tuple[list[dict[str, Any]], int]:
    normalized_query = _normalize_search_query(query)
    search_pattern = f"%{_escape_like(normalized_query)}%"
    prefix_pattern = f"{_escape_like(normalized_query)}%"
    normalized_competition_name = _normalized_sql("dc.league_name")
    normalized_home_team_name = _normalized_sql("home_team.team_name")
    normalized_away_team_name = _normalized_sql("away_team.team_name")
    has_preferred_competition = len(preferred_competition_ids) > 0

    rows = db_client.fetch_all(
        f"""
        with matched_matches as (
            select
                fm.match_id,
                fm.league_id,
                dc.league_name,
                fm.season,
                fm.round_number,
                rf.date_utc as kickoff_at,
                coalesce(rf.status_short, rf.status_long) as status,
                fm.home_team_id,
                home_team.team_name as home_team_name,
                fm.away_team_id,
                away_team.team_name as away_team_name,
                fm.home_goals as home_score,
                fm.away_goals as away_score,
                case
                    when fm.match_id::text = %s then 0
                    when {normalized_home_team_name} = %s or {normalized_away_team_name} = %s then 1
                    when {normalized_home_team_name} like %s escape '\\'
                      or {normalized_away_team_name} like %s escape '\\' then 2
                    when {normalized_competition_name} = %s then 3
                    when {normalized_competition_name} like %s escape '\\' then 4
                    else 5
                end as search_rank,
                case
                    when %s::boolean
                      and %s::int is not null
                      and fm.league_id = any(%s)
                      and fm.season = %s then 0
                    when %s::boolean
                      and fm.league_id = any(%s) then 1
                    when %s::int is not null
                      and fm.season = %s then 2
                    else 3
                end as context_priority
            from mart.fact_matches fm
            left join raw.fixtures rf
              on rf.fixture_id = fm.match_id
            left join mart.dim_competition dc
              on dc.league_id = fm.league_id
            left join mart.dim_team home_team
              on home_team.team_id = fm.home_team_id
            left join mart.dim_team away_team
              on away_team.team_id = fm.away_team_id
            where fm.league_id = any(%s)
              and (
                fm.match_id::text = %s
                or {normalized_home_team_name} like %s escape '\\'
                or {normalized_away_team_name} like %s escape '\\'
                or {normalized_competition_name} like %s escape '\\'
              )
        )
        select
            match_id,
            league_id,
            league_name,
            season,
            round_number,
            kickoff_at,
            status,
            home_team_id,
            home_team_name,
            away_team_id,
            away_team_name,
            home_score,
            away_score
        from matched_matches
        order by
            search_rank asc,
            context_priority asc,
            kickoff_at desc nulls last,
            match_id desc
        limit %s;
        """,
        [
            normalized_query,
            normalized_query,
            normalized_query,
            prefix_pattern,
            prefix_pattern,
            normalized_query,
            prefix_pattern,
            has_preferred_competition,
            preferred_season_id,
            list(preferred_competition_ids),
            preferred_season_id,
            has_preferred_competition,
            list(preferred_competition_ids),
            preferred_season_id,
            preferred_season_id,
            list(SUPPORTED_COMPETITION_SOURCE_IDS),
            normalized_query,
            search_pattern,
            search_pattern,
            search_pattern,
            limit_per_type,
        ],
    )

    results: list[dict[str, Any]] = []
    skipped_count = 0
    for row in rows:
        default_context = _context_payload(
            competition_id=row.get("league_id"),
            competition_name=row.get("league_name"),
            season_id=row.get("season"),
        )
        if default_context is None:
            skipped_count += 1
            continue

        results.append(
            {
                "matchId": str(row["match_id"]),
                "competitionId": str(row["league_id"]),
                "competitionName": row.get("league_name"),
                "seasonId": str(row["season"]) if row.get("season") is not None else None,
                "roundId": str(row["round_number"]) if row.get("round_number") is not None else None,
                "kickoffAt": row.get("kickoff_at"),
                "status": row.get("status"),
                "homeTeamId": str(row["home_team_id"]) if row.get("home_team_id") is not None else None,
                "homeTeamName": row.get("home_team_name"),
                "awayTeamId": str(row["away_team_id"]) if row.get("away_team_id") is not None else None,
                "awayTeamName": row.get("away_team_name"),
                "homeScore": row.get("home_score"),
                "awayScore": row.get("away_score"),
                "defaultContext": default_context,
            }
        )

    return results, skipped_count


@router.get("")
def get_global_search(
    request: Request,
    q: str = Query(..., min_length=1),
    types: list[str] | None = Query(default=None),
    competitionId: str | None = None,
    seasonId: str | None = None,
    limitPerType: int = Query(default=5, ge=1, le=10),
) -> dict[str, Any]:
    normalized_query = _normalize_search_query(q)
    if len(normalized_query) < 2:
        raise AppError(
            message="Invalid value for 'q'. Search requires at least 2 meaningful characters.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"q": q},
        )

    search_types = _parse_search_types(types)
    preference_filters = validate_and_build_global_filters(
        competition_id=competitionId,
        season_id=seasonId,
        round_id=None,
        venue=VenueFilter.all,
        last_n=None,
        date_start=None,
        date_end=None,
        date_range_start=None,
        date_range_end=None,
    )

    groups: list[dict[str, Any]] = []
    total_results = 0
    skipped_results = 0

    for search_type in search_types:
        if search_type == "competition":
            items, skipped_count = _search_competitions(normalized_query, limit_per_type=limitPerType)
        elif search_type == "team":
            items, skipped_count = _search_teams(
                normalized_query,
                preferred_competition_ids=preference_filters.competition_ids,
                preferred_season_id=preference_filters.season_id,
                limit_per_type=limitPerType,
            )
        elif search_type == "player":
            items, skipped_count = _search_players(
                normalized_query,
                preferred_competition_ids=preference_filters.competition_ids,
                preferred_season_id=preference_filters.season_id,
                limit_per_type=limitPerType,
            )
        else:
            items, skipped_count = _search_matches(
                normalized_query,
                preferred_competition_ids=preference_filters.competition_ids,
                preferred_season_id=preference_filters.season_id,
                limit_per_type=limitPerType,
            )

        total_results += len(items)
        skipped_results += skipped_count
        groups.append(
            {
                "type": search_type,
                "items": items,
                "total": len(items),
            }
        )

    return build_api_response(
        {
            "query": " ".join(q.strip().split()),
            "groups": groups,
            "totalResults": total_results,
        },
        request_id=_request_id(request),
        coverage=_build_search_coverage(returned_count=total_results, skipped_count=skipped_results),
    )
