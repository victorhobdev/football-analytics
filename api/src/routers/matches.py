from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Query, Request

from ..core.contracts import build_api_response, build_pagination
from ..core.errors import AppError
from ..core.filters import GlobalFilters, VenueFilter, append_fact_match_filters, validate_and_build_global_filters
from ..db.client import db_client

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])

MatchesSortBy = Literal["kickoffAt", "status", "homeTeamName", "awayTeamName"]
SortDirection = Literal["asc", "desc"]


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _to_match_id(match_id: str) -> int:
    try:
        return int(match_id)
    except ValueError as exc:
        raise AppError(
            message="Invalid match id. Expected integer-compatible identifier.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"matchId": match_id},
        ) from exc


def _to_optional_team_id(team_id: str | None) -> int | None:
    if team_id is None:
        return None

    normalized_team_id = team_id.strip()
    if normalized_team_id == "":
        return None

    try:
        return int(normalized_team_id)
    except ValueError as exc:
        raise AppError(
            message="Invalid value for 'teamId'. Expected integer.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"teamId": team_id},
        ) from exc


def _match_filters_sql(filters: GlobalFilters) -> tuple[str, list[Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    append_fact_match_filters(clauses, params, alias="fm", filters=filters)
    return " and ".join(clauses), params


def _can_use_unfiltered_match_list(
    *,
    filters: GlobalFilters,
    team_id: int | None,
    search_pattern: str | None,
    status_pattern: str | None,
) -> bool:
    return (
        not filters.competition_ids
        and filters.season_id is None
        and filters.round_id is None
        and filters.stage_id is None
        and filters.stage_format is None
        and filters.venue == VenueFilter.all
        and filters.last_n is None
        and filters.date_start is None
        and filters.date_end is None
        and team_id is None
        and search_pattern is None
        and status_pattern is None
    )


def _fetch_unfiltered_match_list(
    *,
    page_size: int,
    offset: int,
    sort_column: str,
    sort_direction: SortDirection,
) -> list[dict[str, Any]]:
    sort_dir = "asc" if sort_direction == "asc" else "desc"
    return db_client.fetch_all(
        f"""
        with enriched as (
            select
                fm.match_id::text as match_id,
                fm.match_id::text as fixture_id,
                fm.league_id::text as competition_id,
                fm.competition_key,
                coalesce(dc.league_name, fm.league_id::text) as competition_name,
                fm.competition_type,
                fm.season::text as season_id,
                fm.season_label,
                fm.round_number::text as round_id,
                fm.round_name,
                fm.stage_id::text as stage_id,
                coalesce(fm.stage_name, ds.stage_name) as stage_name,
                ds.stage_format,
                fm.group_id::text as group_id,
                nullif(trim(rf.group_name), '') as group_name,
                fm.tie_id::text as tie_id,
                ftr.tie_order,
                ftr.match_count as tie_match_count,
                fm.leg_number,
                fm.is_knockout,
                rf.date_utc as kickoff_at,
                coalesce(rf.status_short, rf.status_long) as status,
                dv.venue_name as venue_name,
                fm.home_team_id::text as home_team_id,
                home_team.team_name as home_team_name,
                fm.away_team_id::text as away_team_id,
                away_team.team_name as away_team_name,
                fm.home_goals as home_score,
                fm.away_goals as away_score
            from mart.fact_matches fm
            left join raw.fixtures rf
              on rf.fixture_id = fm.match_id
            left join mart.dim_competition dc
              on dc.league_id = fm.league_id
            left join mart.dim_stage ds
              on ds.provider = fm.provider
             and ds.stage_id = fm.stage_id
            left join mart.fact_tie_results ftr
              on ftr.tie_id = fm.tie_id
            left join mart.dim_team home_team
              on home_team.team_id = fm.home_team_id
            left join mart.dim_team away_team
              on away_team.team_id = fm.away_team_id
            left join mart.dim_venue dv
              on dv.venue_id = rf.venue_id
        )
        select
            f.*,
            count(*) over() as _total_count
        from enriched f
        order by {sort_column} {sort_dir} nulls last, f.match_id desc
        limit %s offset %s;
        """,
        [page_size, offset],
    )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None

    return float(value)


def _build_match_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "matchId": row["match_id"],
        "fixtureId": row["fixture_id"],
        "competitionId": row["competition_id"],
        "competitionKey": row.get("competition_key"),
        "competitionName": row["competition_name"],
        "competitionType": row.get("competition_type"),
        "seasonId": row["season_id"],
        "seasonLabel": row.get("season_label"),
        "roundId": row["round_id"],
        "roundName": row.get("round_name"),
        "stageId": row.get("stage_id"),
        "stageName": row.get("stage_name"),
        "stageFormat": row.get("stage_format"),
        "groupId": row.get("group_id"),
        "groupName": row.get("group_name"),
        "tieId": row.get("tie_id"),
        "tieOrder": row.get("tie_order"),
        "tieMatchCount": row.get("tie_match_count"),
        "legNumber": row.get("leg_number"),
        "isKnockout": row.get("is_knockout"),
        "kickoffAt": row.get("kickoff_at"),
        "status": row.get("status"),
        "venueName": row.get("venue_name"),
        "homeTeamId": row["home_team_id"],
        "homeTeamName": row.get("home_team_name"),
        "awayTeamId": row["away_team_id"],
        "awayTeamName": row.get("away_team_name"),
        "homeScore": row.get("home_score"),
        "awayScore": row.get("away_score"),
    }


def _build_section_coverage(status: str, *, label: str, percentage: float | int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "label": label,
    }

    if percentage is not None:
        payload["percentage"] = round(float(percentage), 2)

    return payload


def _coverage_score(coverage: dict[str, Any]) -> float:
    percentage = coverage.get("percentage")
    if isinstance(percentage, (int, float)):
        return float(percentage)

    status = coverage.get("status")
    if status == "complete":
        return 100.0
    if status == "partial":
        return 50.0
    if status == "empty":
        return 0.0

    return 0.0


def _build_timeline_coverage(timeline_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not timeline_rows:
        return _build_section_coverage("empty", label="Timeline", percentage=0)

    return _build_section_coverage("complete", label="Timeline", percentage=100)


def _build_lineups_coverage(
    match_row: dict[str, Any],
    lineup_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not lineup_rows:
        return _build_section_coverage("empty", label="Lineups", percentage=0)

    expected_team_ids = [
        team_id
        for team_id in [match_row.get("home_team_id"), match_row.get("away_team_id")]
        if team_id is not None
    ]
    lineup_team_ids = {row.get("teamId") for row in lineup_rows if row.get("teamId")}
    starters_by_team: dict[str, int] = {}

    for row in lineup_rows:
        team_id = row.get("teamId")
        if not team_id:
            continue
        if not row.get("isStarter"):
            continue
        starters_by_team[team_id] = starters_by_team.get(team_id, 0) + 1

    if not expected_team_ids:
        return _build_section_coverage("complete", label="Lineups", percentage=100)

    teams_with_rows = len(lineup_team_ids.intersection(expected_team_ids))
    team_ratio = teams_with_rows / len(expected_team_ids)
    starter_ratio = sum(
        min(starters_by_team.get(team_id, 0), 11) / 11 for team_id in expected_team_ids
    ) / len(expected_team_ids)

    if team_ratio == 1 and all(starters_by_team.get(team_id, 0) >= 11 for team_id in expected_team_ids):
        return _build_section_coverage("complete", label="Lineups", percentage=100)

    return _build_section_coverage(
        "partial",
        label="Lineups",
        percentage=((team_ratio + starter_ratio) / 2) * 100,
    )


def _build_player_stats_coverage(
    match_row: dict[str, Any],
    lineup_rows: list[dict[str, Any]],
    player_stat_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not player_stat_rows:
        return _build_section_coverage("empty", label="Player stats", percentage=0)

    expected_team_ids = [
        team_id
        for team_id in [match_row.get("home_team_id"), match_row.get("away_team_id")]
        if team_id is not None
    ]
    stats_team_ids = {row.get("teamId") for row in player_stat_rows if row.get("teamId")}

    team_ratio = 1.0
    if expected_team_ids:
        team_ratio = len(stats_team_ids.intersection(expected_team_ids)) / len(expected_team_ids)

    lineup_player_ids = {row.get("playerId") for row in lineup_rows if row.get("playerId")}
    stat_player_ids = {row.get("playerId") for row in player_stat_rows if row.get("playerId")}

    player_ratio = 1.0
    if lineup_player_ids:
        player_ratio = len(stat_player_ids.intersection(lineup_player_ids)) / len(lineup_player_ids)

    if team_ratio == 1 and player_ratio == 1:
        return _build_section_coverage("complete", label="Player stats", percentage=100)

    return _build_section_coverage(
        "partial",
        label="Player stats",
        percentage=((team_ratio + player_ratio) / 2) * 100,
    )


def _build_team_stats_coverage(
    match_row: dict[str, Any],
    team_stat_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not team_stat_rows:
        return _build_section_coverage("empty", label="Team stats", percentage=0)

    expected_team_ids = [
        team_id
        for team_id in [match_row.get("home_team_id"), match_row.get("away_team_id")]
        if team_id is not None
    ]
    if not expected_team_ids:
        expected_team_ids = [row.get("teamId") for row in team_stat_rows if row.get("teamId")]

    if not expected_team_ids:
        return _build_section_coverage("empty", label="Team stats", percentage=0)

    tracked_fields = [
        "totalShots",
        "shotsOnGoal",
        "possessionPct",
        "totalPasses",
        "passAccuracyPct",
        "corners",
        "fouls",
        "yellowCards",
        "redCards",
        "goalkeeperSaves",
    ]
    expected_team_ids_set = set(expected_team_ids)
    rows_by_team_id = {
        row.get("teamId"): row
        for row in team_stat_rows
        if row.get("teamId") in expected_team_ids_set
    }

    teams_with_rows = len(rows_by_team_id)
    if teams_with_rows == 0:
        return _build_section_coverage("empty", label="Team stats", percentage=0)

    metric_slots = len(expected_team_ids) * len(tracked_fields)
    available_metric_slots = 0

    for team_id in expected_team_ids:
        row = rows_by_team_id.get(team_id)
        if row is None:
            continue

        available_metric_slots += sum(1 for field in tracked_fields if row.get(field) is not None)

    team_ratio = teams_with_rows / len(expected_team_ids)
    metric_ratio = available_metric_slots / metric_slots if metric_slots > 0 else 1.0

    if available_metric_slots == 0:
        return _build_section_coverage("empty", label="Team stats", percentage=0)

    if team_ratio == 1 and metric_ratio == 1:
        return _build_section_coverage("complete", label="Team stats", percentage=100)

    return _build_section_coverage(
        "partial",
        label="Team stats",
        percentage=((team_ratio + metric_ratio) / 2) * 100,
    )


def _build_match_sections_coverage(section_coverage: dict[str, dict[str, Any]]) -> dict[str, Any]:
    requested_coverages = list(section_coverage.values())

    if not requested_coverages:
        return _build_section_coverage("unknown", label="Match center sections coverage")

    statuses = {coverage.get("status") for coverage in requested_coverages}
    if statuses == {"complete"}:
        return _build_section_coverage("complete", label="Match center sections coverage", percentage=100)
    if statuses == {"empty"}:
        return _build_section_coverage("empty", label="Match center sections coverage", percentage=0)

    return _build_section_coverage(
        "partial",
        label="Match center sections coverage",
        percentage=sum(_coverage_score(coverage) for coverage in requested_coverages) / len(requested_coverages),
    )


@router.get("")
def get_matches(
    request: Request,
    competitionId: str | None = None,
    seasonId: str | None = None,
    roundId: str | None = None,
    stageId: str | None = None,
    stageFormat: str | None = None,
    venue: VenueFilter = VenueFilter.all,
    lastN: int | None = Query(default=None, gt=0),
    dateStart: date | None = None,
    dateEnd: date | None = None,
    dateRangeStart: date | None = None,
    dateRangeEnd: date | None = None,
    teamId: str | None = None,
    search: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    sortBy: MatchesSortBy = "kickoffAt",
    sortDirection: SortDirection = "desc",
) -> dict[str, Any]:
    global_filters = validate_and_build_global_filters(
        competition_id=competitionId,
        season_id=seasonId,
        round_id=roundId,
        stage_id=stageId,
        stage_format=stageFormat,
        venue=venue,
        last_n=lastN,
        date_start=dateStart,
        date_end=dateEnd,
        date_range_start=dateRangeStart,
        date_range_end=dateRangeEnd,
    )

    where_sql, where_params = _match_filters_sql(global_filters)
    team_id_int = _to_optional_team_id(teamId)
    if team_id_int is not None:
        where_sql = f"{where_sql} and (fm.home_team_id = %s or fm.away_team_id = %s)"
        where_params.extend([team_id_int, team_id_int])

    search_pattern = f"%{search.strip()}%" if search and search.strip() else None
    status_pattern = f"%{status.strip()}%" if status and status.strip() else None
    sort_column = {
        "kickoffAt": "f.kickoff_at",
        "status": "f.status",
        "homeTeamName": "f.home_team_name",
        "awayTeamName": "f.away_team_name",
    }[sortBy]
    sort_dir = "asc" if sortDirection == "asc" else "desc"
    offset = (page - 1) * pageSize

    if _can_use_unfiltered_match_list(
        filters=global_filters,
        team_id=team_id_int,
        search_pattern=search_pattern,
        status_pattern=status_pattern,
    ):
        rows = _fetch_unfiltered_match_list(
            page_size=pageSize,
            offset=offset,
            sort_column=sort_column,
            sort_direction=sortDirection,
        )
    else:
        query = f"""
        with scoped_matches as (
            select
                fm.match_id,
                fm.provider,
                fm.competition_key,
                fm.competition_type,
                fm.league_id,
                fm.season,
                fm.season_label,
                fm.round_number,
                fm.round_name,
                fm.stage_id,
                fm.stage_name,
                fm.group_id,
                fm.tie_id,
                fm.leg_number,
                fm.is_knockout,
                fm.date_day,
                fm.home_team_id,
                fm.away_team_id,
                fm.home_goals,
                fm.away_goals,
                row_number() over (order by fm.date_day desc, fm.match_id desc) as rn_recent
            from mart.fact_matches fm
            where {where_sql}
        ),
        filtered_matches as (
            select *
            from scoped_matches sm
            where (%s::int is null or sm.rn_recent <= %s)
        ),
        enriched as (
            select
                fm.match_id::text as match_id,
                fm.match_id::text as fixture_id,
                fm.league_id::text as competition_id,
                fm.competition_key,
                coalesce(dc.league_name, fm.league_id::text) as competition_name,
                fm.competition_type,
                fm.season::text as season_id,
                fm.season_label,
                fm.round_number::text as round_id,
                fm.round_name,
                fm.stage_id::text as stage_id,
                coalesce(fm.stage_name, ds.stage_name) as stage_name,
                ds.stage_format,
                fm.group_id::text as group_id,
                nullif(trim(rf.group_name), '') as group_name,
                fm.tie_id::text as tie_id,
                ftr.tie_order,
                ftr.match_count as tie_match_count,
                fm.leg_number,
                fm.is_knockout,
                rf.date_utc as kickoff_at,
                coalesce(rf.status_short, rf.status_long) as status,
                dv.venue_name as venue_name,
                fm.home_team_id::text as home_team_id,
                home_team.team_name as home_team_name,
                fm.away_team_id::text as away_team_id,
                away_team.team_name as away_team_name,
                fm.home_goals as home_score,
                fm.away_goals as away_score
            from filtered_matches fm
            left join raw.fixtures rf
              on rf.fixture_id = fm.match_id
            left join mart.dim_competition dc
              on dc.league_id = fm.league_id
            left join mart.dim_stage ds
              on ds.provider = fm.provider
             and ds.stage_id = fm.stage_id
            left join mart.fact_tie_results ftr
              on ftr.tie_id = fm.tie_id
            left join mart.dim_team home_team
              on home_team.team_id = fm.home_team_id
            left join mart.dim_team away_team
              on away_team.team_id = fm.away_team_id
            left join mart.dim_venue dv
              on dv.venue_id = rf.venue_id
        ),
        filtered_rows as (
            select *
            from enriched e
            where (%s::text is null or e.home_team_name ilike %s or e.away_team_name ilike %s)
              and (%s::text is null or coalesce(e.status, '') ilike %s)
        )
        select
            f.*,
            count(*) over() as _total_count
        from filtered_rows f
        order by {sort_column} {sort_dir} nulls last, f.match_id desc
        limit %s offset %s;
        """
        rows = db_client.fetch_all(
            query,
            [
                *where_params,
                global_filters.last_n,
                global_filters.last_n,
                search_pattern,
                search_pattern,
                search_pattern,
                status_pattern,
                status_pattern,
                pageSize,
                offset,
            ],
        )
    total_count = int(rows[0]["_total_count"]) if rows else 0
    pagination = build_pagination(page, pageSize, total_count)

    items = [_build_match_item(row) for row in rows]

    return build_api_response(
        {"items": items},
        request_id=_request_id(request),
        pagination=pagination,
        coverage=None,
    )


@router.get("/{matchId}")
def get_match_center(
    matchId: str,
    request: Request,
    competitionId: str | None = None,
    seasonId: str | None = None,
    roundId: str | None = None,
    stageId: str | None = None,
    stageFormat: str | None = None,
    venue: VenueFilter = VenueFilter.all,
    lastN: int | None = Query(default=None, gt=0),
    dateStart: date | None = None,
    dateEnd: date | None = None,
    dateRangeStart: date | None = None,
    dateRangeEnd: date | None = None,
    includeTimeline: bool = True,
    includeLineups: bool = True,
    includeTeamStats: bool = True,
    includePlayerStats: bool = True,
) -> dict[str, Any]:
    match_id = _to_match_id(matchId)
    global_filters = validate_and_build_global_filters(
        competition_id=competitionId,
        season_id=seasonId,
        round_id=roundId,
        stage_id=stageId,
        stage_format=stageFormat,
        venue=venue,
        last_n=lastN,
        date_start=dateStart,
        date_end=dateEnd,
        date_range_start=dateRangeStart,
        date_range_end=dateRangeEnd,
    )

    match_where, match_params = _match_filters_sql(global_filters)
    match_query = f"""
        select
            fm.match_id::text as match_id,
            fm.match_id::text as fixture_id,
            fm.league_id::text as competition_id,
            fm.competition_key,
            coalesce(dc.league_name, fm.league_id::text) as competition_name,
            fm.competition_type,
            fm.season::text as season_id,
            fm.season_label,
            fm.round_number::text as round_id,
            fm.round_name,
            fm.stage_id::text as stage_id,
            coalesce(fm.stage_name, ds.stage_name) as stage_name,
            ds.stage_format,
            fm.group_id::text as group_id,
            nullif(trim(rf.group_name), '') as group_name,
            fm.tie_id::text as tie_id,
            ftr.tie_order,
            ftr.match_count as tie_match_count,
            fm.leg_number,
            fm.is_knockout,
            rf.date_utc as kickoff_at,
            coalesce(rf.status_short, rf.status_long) as status,
            dv.venue_name as venue_name,
            fm.home_team_id::text as home_team_id,
            home_team.team_name as home_team_name,
            fm.away_team_id::text as away_team_id,
            away_team.team_name as away_team_name,
            fm.home_goals as home_score,
            fm.away_goals as away_score
        from mart.fact_matches fm
        left join raw.fixtures rf
          on rf.fixture_id = fm.match_id
        left join mart.dim_competition dc
          on dc.league_id = fm.league_id
        left join mart.dim_stage ds
          on ds.provider = fm.provider
         and ds.stage_id = fm.stage_id
        left join mart.fact_tie_results ftr
          on ftr.tie_id = fm.tie_id
        left join mart.dim_team home_team
          on home_team.team_id = fm.home_team_id
        left join mart.dim_team away_team
          on away_team.team_id = fm.away_team_id
        left join mart.dim_venue dv
          on dv.venue_id = rf.venue_id
        where fm.match_id = %s
          and {match_where}
        limit 1;
    """
    match_row = db_client.fetch_one(match_query, [match_id, *match_params])
    if match_row is None:
        raise AppError(
            message="Match not found.",
            code="MATCH_NOT_FOUND",
            status=404,
            details={"matchId": matchId},
        )

    data: dict[str, Any] = {
        "match": _build_match_item(match_row)
    }

    timeline_rows: list[dict[str, Any]] = []
    lineup_rows: list[dict[str, Any]] = []
    team_stat_rows: list[dict[str, Any]] = []
    player_stat_rows: list[dict[str, Any]] = []
    section_coverage: dict[str, dict[str, Any]] = {}

    if includeTimeline:
        timeline_query = """
            select
                fme.event_id,
                fme.time_elapsed as minute,
                cast(null as integer) as second,
                cast(null as text) as period,
                fme.event_type as type,
                fme.event_detail as detail,
                fme.team_id::text as team_id,
                team.team_name,
                fme.player_id::text as player_id,
                player.player_name
            from mart.fact_match_events fme
            left join mart.dim_team team
              on team.team_id = fme.team_id
            left join mart.dim_player player
              on player.player_id = fme.player_id
            where fme.match_id = %s
            order by fme.time_elapsed asc nulls last, fme.event_id asc;
        """
        timeline_result = db_client.fetch_all(timeline_query, [match_id])
        timeline_rows = [
            {
                "eventId": row.get("event_id"),
                "minute": row.get("minute"),
                "second": row.get("second"),
                "period": row.get("period"),
                "type": row.get("type"),
                "detail": row.get("detail"),
                "teamId": row.get("team_id"),
                "teamName": row.get("team_name"),
                "playerId": row.get("player_id"),
                "playerName": row.get("player_name"),
            }
            for row in timeline_result
        ]
        data["timeline"] = timeline_rows
        section_coverage["timeline"] = _build_timeline_coverage(timeline_rows)

    if includeLineups:
        lineups_query = """
            select
                ffl.player_id::text as player_id,
                ffl.player_name,
                ffl.team_id::text as team_id,
                team.team_name as team_name,
                ffl.position_name as position,
                ffl.formation_field,
                ffl.formation_position,
                ffl.jersey_number as shirt_number,
                ffl.is_starter,
                ffl.minutes_played
            from mart.fact_fixture_lineups ffl
            left join mart.dim_team team
              on team.team_id = ffl.team_id
            where ffl.match_id = %s
            order by
                ffl.team_id asc,
                ffl.is_starter desc,
                ffl.formation_position asc nulls last,
                ffl.jersey_number asc nulls last,
                ffl.player_name asc;
        """
        lineups_result = db_client.fetch_all(lineups_query, [match_id])
        lineup_rows = [
            {
                "playerId": row.get("player_id"),
                "playerName": row.get("player_name"),
                "teamId": row.get("team_id"),
                "teamName": row.get("team_name"),
                "position": row.get("position"),
                "formationField": row.get("formation_field"),
                "formationPosition": row.get("formation_position"),
                "shirtNumber": row.get("shirt_number"),
                "isStarter": row.get("is_starter"),
                "minutesPlayed": row.get("minutes_played"),
            }
            for row in lineups_result
        ]
        data["lineups"] = lineup_rows
        section_coverage["lineups"] = _build_lineups_coverage(match_row, lineup_rows)

    if includeTeamStats:
        team_stats_query = """
            select
                ms.team_id::text as team_id,
                coalesce(ms.team_name, team.team_name) as team_name,
                ms.total_shots,
                ms.shots_on_goal,
                ms.ball_possession,
                ms.total_passes,
                ms.passes_accurate,
                ms.passes_pct,
                ms.corner_kicks,
                ms.fouls,
                ms.yellow_cards,
                ms.red_cards,
                ms.goalkeeper_saves
            from raw.match_statistics ms
            left join mart.dim_team team
              on team.team_id = ms.team_id
            where ms.fixture_id = %s
            order by
                case
                    when ms.team_id::text = %s then 0
                    when ms.team_id::text = %s then 1
                    else 2
                end,
                ms.team_id asc;
        """
        team_stats_result = db_client.fetch_all(
            team_stats_query,
            [
                match_id,
                match_row.get("home_team_id"),
                match_row.get("away_team_id"),
            ],
        )
        team_stat_rows = [
            {
                "teamId": row.get("team_id"),
                "teamName": row.get("team_name"),
                "totalShots": _to_float(row.get("total_shots")),
                "shotsOnGoal": _to_float(row.get("shots_on_goal")),
                "possessionPct": _to_float(row.get("ball_possession")),
                "totalPasses": _to_float(row.get("total_passes")),
                "passesAccurate": _to_float(row.get("passes_accurate")),
                "passAccuracyPct": _to_float(row.get("passes_pct")),
                "corners": _to_float(row.get("corner_kicks")),
                "fouls": _to_float(row.get("fouls")),
                "yellowCards": _to_float(row.get("yellow_cards")),
                "redCards": _to_float(row.get("red_cards")),
                "goalkeeperSaves": _to_float(row.get("goalkeeper_saves")),
            }
            for row in team_stats_result
        ]
        data["teamStats"] = team_stat_rows
        section_coverage["teamStats"] = _build_team_stats_coverage(match_row, team_stat_rows)

    if includePlayerStats:
        player_stats_query = """
            select
                fps.player_id::text as player_id,
                fps.player_name,
                fps.team_id::text as team_id,
                coalesce(fps.team_name, team.team_name) as team_name,
                fps.position_name,
                fps.is_starter,
                fps.minutes_played,
                fps.goals,
                fps.assists,
                fps.shots_total,
                fps.shots_on_goal,
                fps.passes_total,
                fps.key_passes,
                fps.tackles,
                fps.interceptions,
                fps.duels,
                fps.fouls_committed,
                fps.yellow_cards,
                fps.red_cards,
                fps.goalkeeper_saves,
                fps.clean_sheets,
                fps.xg,
                fps.rating
            from mart.fact_fixture_player_stats fps
            left join mart.dim_team team
              on team.team_id = fps.team_id
            where fps.match_id = %s
            order by fps.team_id asc, fps.rating desc nulls last, fps.player_name asc;
        """
        stats_result = db_client.fetch_all(player_stats_query, [match_id])
        player_stat_rows = [
            {
                "playerId": row.get("player_id"),
                "playerName": row.get("player_name"),
                "teamId": row.get("team_id"),
                "teamName": row.get("team_name"),
                "positionName": row.get("position_name"),
                "isStarter": row.get("is_starter"),
                "minutesPlayed": _to_float(row.get("minutes_played")),
                "goals": _to_float(row.get("goals")),
                "assists": _to_float(row.get("assists")),
                "shotsTotal": _to_float(row.get("shots_total")),
                "shotsOnGoal": _to_float(row.get("shots_on_goal")),
                "passesTotal": _to_float(row.get("passes_total")),
                "keyPasses": _to_float(row.get("key_passes")),
                "tackles": _to_float(row.get("tackles")),
                "interceptions": _to_float(row.get("interceptions")),
                "duels": _to_float(row.get("duels")),
                "foulsCommitted": _to_float(row.get("fouls_committed")),
                "yellowCards": _to_float(row.get("yellow_cards")),
                "redCards": _to_float(row.get("red_cards")),
                "goalkeeperSaves": _to_float(row.get("goalkeeper_saves")),
                "cleanSheets": _to_float(row.get("clean_sheets")),
                "xg": _to_float(row.get("xg")),
                "rating": _to_float(row.get("rating")),
            }
            for row in stats_result
        ]
        data["playerStats"] = player_stat_rows
        section_coverage["playerStats"] = _build_player_stats_coverage(
            match_row,
            lineup_rows,
            player_stat_rows,
        )

    if section_coverage:
        data["sectionCoverage"] = section_coverage

    coverage = _build_match_sections_coverage(section_coverage)

    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=coverage,
    )
