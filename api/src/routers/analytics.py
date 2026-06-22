from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Query, Request

from ..core.contracts import build_api_response, build_coverage_from_counts
from ..core.errors import AppError
from ..core.filters import (
    GlobalFilters,
    VenueFilter,
    append_fact_match_filters,
    validate_and_build_global_filters,
)
from ..db.client import db_client

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

VALID_METRICS_TRENDS: list[str] = [
    "matches", "goals", "avg_goals", "home_wins", "away_wins", "draws",
    "points", "goals_for", "goals_against", "goal_diff",
]
VALID_METRICS_OLAP: list[str] = VALID_METRICS_TRENDS + ["points_per_match", "win_rate", "ppg"]
VALID_PERIOD_TYPES: list[str] = ["round", "month"]
VALID_DIMENSIONS: list[str] = ["round", "team", "coach", "venue", "period"]
VALID_GRAINS: list[str] = [
    "competition_season",
    "competition_season_round",
    "competition_season_team",
    "competition_season_team_round",
    "competition_season_coach",
]
VALID_OPERATIONS: list[str] = ["slice", "dice", "drill_down", "roll_up", "pivot", "drill_through"]
VALID_BREAKDOWNS: list[str] = ["venue", "round", "team", "none"]
VALID_COMPARISON_TYPES: list[str] = [
    "team_vs_team", "season_vs_season", "home_vs_away", "period_vs_period",
]
VALID_SUPERLATIVE_CATEGORIES: list[str] = [
    "most_goals_match", "biggest_win", "best_attack", "best_defense",
    "best_goal_diff", "most_goals_round", "highest_avg_goals_round",
    "best_team_ppg", "coach_best_ppm", "coach_most_matches",
]

MATCH_GRAINS = {"competition_season", "competition_season_round"}
TEAM_GRAINS = {"competition_season_team", "competition_season_team_round", "competition_season_coach"}
TEAM_GROUPING_DIMS = {"team", "coach"}

GRAIN_DIMENSION_COMPAT: dict[str, set[str]] = {
    "competition_season": {"team", "period"},
    "competition_season_round": {"round", "period"},
    "competition_season_team": {"team", "venue", "period"},
    "competition_season_team_round": {"round", "team", "venue", "period"},
    "competition_season_coach": {"coach", "period"},
}

DIMENSION_BREAKDOWN_COMPAT: dict[str, set[str]] = {
    "round": {"venue", "team", "none"},
    "team": {"venue", "round", "none"},
    "coach": {"round", "team", "none"},
    "venue": {"round", "team", "none"},
    "period": {"venue", "round", "team", "none"},
}

SUPERLATIVE_THRESHOLDS: dict[str, int] = {
    "most_goals_match": 1,
    "biggest_win": 1,
    "best_attack": 3,
    "best_defense": 3,
    "best_goal_diff": 3,
    "most_goals_round": 2,
    "highest_avg_goals_round": 2,
    "best_team_ppg": 3,
    "coach_best_ppm": 5,
    "coach_most_matches": 5,
}

MATCH_METRIC_EXPRESSIONS: dict[str, str] = {
    "matches": "count(distinct case when fm.home_team_id = tr.team_id then fm.match_id end)::int",
    "goals": "sum(case when fm.home_team_id = tr.team_id then coalesce(fm.total_goals, 0) else 0 end)::int",
    "avg_goals": "round(avg(case when fm.home_team_id = tr.team_id then coalesce(fm.total_goals, 0) else null end), 4)",
    "home_wins": "sum(case when fm.home_team_id = tr.team_id and coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0) then 1 else 0 end)::int",
    "away_wins": "sum(case when fm.home_team_id = tr.team_id and coalesce(fm.home_goals, 0) < coalesce(fm.away_goals, 0) then 1 else 0 end)::int",
    "draws": "sum(case when fm.home_team_id = tr.team_id and coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 1 else 0 end)::int",
}

TEAM_METRIC_EXPRESSIONS: dict[str, str] = {
    **MATCH_METRIC_EXPRESSIONS,
    "matches": "count(distinct tr.match_id)::int",
    "goals": "sum(tr.goals_for)::int",
    "avg_goals": "round(sum(tr.goals_for)::numeric / nullif(count(distinct tr.match_id), 0), 4)",
    "points": "sum(tr.points_round)::int",
    "goals_for": "sum(tr.goals_for)::int",
    "goals_against": "sum(tr.goals_against)::int",
    "goal_diff": "(sum(tr.goals_for) - sum(tr.goals_against))::int",
    "points_per_match": "round(sum(tr.points_round)::numeric / nullif(count(distinct tr.match_id), 0), 4)",
    "win_rate": "round(100.0 * sum(tr.wins) / nullif(count(distinct tr.match_id), 0), 2)",
    "ppg": "round(sum(tr.points_round)::numeric / nullif(count(distinct tr.match_id), 0), 4)",
}

TREND_MATCH_METRICS = {"matches", "goals", "avg_goals", "home_wins", "away_wins", "draws"}
TREND_TEAM_METRICS = {"points", "goals_for", "goals_against", "goal_diff"}

DIMENSION_DEFS: dict[str, dict[str, str]] = {
    "round": {
        "key": "fm.round_number::text",
        "label": "concat('Rodada ', fm.round_number)",
        "joins": "",
        "group_by": "fm.round_number",
        "order_by": "min(fm.round_number)",
    },
    "team": {
        "key": "tr.team_id::text",
        "label": "coalesce(dt.team_name, 'Time indisponivel')",
        "joins": "left join mart.dim_team dt on dt.team_id = tr.team_id",
        "group_by": "tr.team_id, coalesce(dt.team_name, 'Time indisponivel')",
        "order_by": "min(coalesce(dt.team_name, 'Time indisponivel'))",
    },
    "coach": {
        "key": "coalesce(dc.coach_id::text, 'unknown')",
        "label": "coalesce(dc.coach_name, 'Nome indisponivel')",
        "joins": (
            "left join mart.stg_team_coaches tc on tc.team_id = tr.team_id"
            " and fm.date_day >= coalesce(tc.start_date, date '1900-01-01')"
            " and fm.date_day <= coalesce(tc.end_date, date '2999-12-31')"
            " left join mart.dim_coach dc on dc.provider = tc.provider and dc.coach_id = tc.coach_id"
        ),
        "group_by": "dc.coach_id, dc.coach_name",
        "order_by": "min(coalesce(dc.coach_name, 'Nome indisponivel'))",
    },
    "venue": {
        "key": "case when fm.home_team_id = tr.team_id then 'home' else 'away' end",
        "label": "case when fm.home_team_id = tr.team_id then 'Casa' else 'Fora' end",
        "joins": "",
        "group_by": "case when fm.home_team_id = tr.team_id then 'home' else 'away' end",
        "order_by": "min(case when fm.home_team_id = tr.team_id then 0 else 1 end)",
    },
    "period": {
        "key": "to_char(fm.date_day, 'YYYY-MM')",
        "label": "to_char(fm.date_day, 'YYYY-MM')",
        "joins": "",
        "group_by": "to_char(fm.date_day, 'YYYY-MM')",
        "order_by": "min(fm.date_day)",
    },
}

BREAKDOWN_DEFS: dict[str, dict[str, str]] = {
    "venue": {
        "key": "case when fm.home_team_id = tr.team_id then 'home' else 'away' end",
        "label": "case when fm.home_team_id = tr.team_id then 'Casa' else 'Fora' end",
        "group_by": ", case when fm.home_team_id = tr.team_id then 'home' else 'away' end",
        "value_expr": "case when fm.home_team_id = tr.team_id then 'home' else 'away' end",
    },
    "round": {
        "key": "fm.round_number::text",
        "label": "concat('Rodada ', fm.round_number)",
        "group_by": ", fm.round_number",
        "value_expr": "fm.round_number::text",
    },
    "team": {
        "key": "tr.team_id::text",
        "label": "coalesce(dt.team_name, 'Time indisponivel')",
        "joins": "left join mart.dim_team dt on dt.team_id = tr.team_id",
        "group_by": ", tr.team_id, coalesce(dt.team_name, 'Time indisponivel')",
        "value_expr": "tr.team_id::text",
    },
}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _build_match_filters(
    filters: GlobalFilters,
    alias: str = "fm",
) -> tuple[str, list[Any]]:
    where_clauses: list[str] = []
    params: list[Any] = []
    append_fact_match_filters(where_clauses, params, alias=alias, filters=filters)

    if filters.venue == VenueFilter.home:
        where_clauses.append(f"{alias}.home_team_id is not null")
    elif filters.venue == VenueFilter.away:
        where_clauses.append(f"{alias}.away_team_id is not null")

    return " and ".join(where_clauses) if where_clauses else "1=1", params


def _join_where_clauses(where_clauses: list[str]) -> str:
    return " and ".join(where_clauses) if where_clauses else "1=1"


def _build_scope_cid(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"competitionId": None, "seasonId": None}
    first = rows[0]
    return {
        "competitionId": _to_text(first.get("competition_key")),
        "seasonId": _to_text(first.get("season") or first.get("season_label")),
    }


def _not_available_coverage(label: str) -> dict[str, Any]:
    return {
        "status": "not_available",
        "percentage": None,
        "sampleSize": 0,
        "expectedSize": 0,
        "label": label,
        "details": "No data available for this combination of filters.",
    }


def _compute_trend_direction(values: list[float]) -> str | None:
    if len(values) < 3:
        return None
    n = len(values)
    first_half = values[: n // 2]
    second_half = values[n // 2 :]
    avg_first = sum(first_half) / len(first_half) if first_half else 0
    avg_second = sum(second_half) / len(second_half) if second_half else 0
    diff = avg_second - avg_first
    threshold = max(0.01, abs(avg_first) * 0.02) if abs(avg_first) > 0.01 else 0.01
    if diff > threshold:
        return "up"
    if diff < -threshold:
        return "down"
    return "stable"


@router.get("/overview")
def get_overview(
    request: Request,
    competitionId: str | None = None,
    seasonId: str | None = None,
    roundId: str | None = None,
    stageId: str | None = None,
    venue: VenueFilter = VenueFilter.all,
    lastN: int | None = Query(default=None, gt=0),
    dateStart: date | None = None,
    dateEnd: date | None = None,
) -> dict[str, Any]:
    filters = validate_and_build_global_filters(
        competition_id=competitionId,
        season_id=seasonId,
        round_id=roundId,
        stage_id=stageId,
        venue=venue,
        last_n=lastN,
        date_start=dateStart,
        date_end=dateEnd,
    date_range_start=None,
    date_range_end=None,
    )
    where_sql, where_params = _build_match_filters(filters)

    query = f"""
        with match_scope as (
            select
                fm.competition_key,
                fm.season,
                fm.season_label,
                fm.match_id,
                fm.home_team_id,
                fm.away_team_id,
                fm.date_day,
                coalesce(fm.total_goals, 0) as total_goals,
                coalesce(fm.home_goals, 0) as home_goals,
                coalesce(fm.away_goals, 0) as away_goals,
                case when coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0) then 1 else 0 end as home_win,
                case when coalesce(fm.home_goals, 0) < coalesce(fm.away_goals, 0) then 1 else 0 end as away_win,
                case when coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 1 else 0 end as draw
            from mart.fact_matches fm
            where {where_sql}
        ),
        match_agg as (
            select
                coalesce(max(ms.competition_key), '') as competition_key,
                coalesce(max(ms.season), 0) as season,
                coalesce(max(ms.season_label), '') as season_label,
                count(distinct ms.match_id)::int as total_matches,
                sum(ms.total_goals)::int as total_goals,
                case when count(distinct ms.match_id) > 0
                    then round(sum(ms.total_goals)::numeric / count(distinct ms.match_id), 4)
                end as avg_goals_per_match,
                sum(ms.home_win)::int as home_wins,
                sum(ms.away_win)::int as away_wins,
                sum(ms.draw)::int as draws
            from match_scope ms
        ),
        team_list as (
            select home_team_id as team_id from match_scope
            union
            select away_team_id as team_id from match_scope
        ),
        team_agg as (
            select count(distinct team_id)::int as total_teams
            from team_list
        ),
        team_match_stats as (
            select
                tr.team_id,
                sum(tr.goals_for) as goals_for,
                sum(tr.goals_against) as goals_against
            from mart.int_team_match_rows tr
            join match_scope ms on ms.match_id = tr.match_id
            group by tr.team_id
        ),
        coach_match_stats as (
            select
                concat(tc.provider, ':', tc.coach_id::text) as coach_key,
                coalesce(dc.coach_id::text, tc.coach_id::text) as coach_id,
                coalesce(dc.coach_name, concat('Tecnico #', tc.coach_id::text)) as coach_name,
                count(distinct tr.match_id)::int as matches,
                round(sum(tr.points_round)::numeric / nullif(count(distinct tr.match_id), 0), 4) as points_per_match
            from match_scope ms
            join mart.int_team_match_rows tr on tr.match_id = ms.match_id
            join mart.stg_team_coaches tc
                on tc.team_id = tr.team_id
                and ms.date_day >= coalesce(tc.start_date, date '1900-01-01')
                and ms.date_day <= coalesce(tc.end_date, date '2999-12-31')
            left join mart.dim_coach dc on dc.provider = tc.provider and dc.coach_id = tc.coach_id
            where tc.coach_id is not null
            group by tc.provider, tc.coach_id, dc.coach_id, dc.coach_name
        ),
        coach_agg as (
            select count(distinct coach_key)::int as total_coaches
            from coach_match_stats
        ),
        player_list as (
            select fl.player_id
            from mart.fact_fixture_lineups fl
            join match_scope ms on ms.match_id = fl.match_id
            where fl.player_id is not null
            union
            select fps.player_id
            from mart.fact_fixture_player_stats fps
            join match_scope ms on ms.match_id = fps.match_id
            where fps.player_id is not null
        ),
        player_agg as (
            select count(distinct player_id)::int as total_players
            from player_list
        ),
        best_ppm_coach as (
            select coach_id, coach_name, points_per_match, matches
            from coach_match_stats
            where matches >= 1
            order by points_per_match desc nulls last, matches desc, coach_name
            limit 1
        ),
        top_scorer as (
            select tms.team_id, dt.team_name, tms.goals_for
            from team_match_stats tms
            left join mart.dim_team dt on dt.team_id = tms.team_id
            order by tms.goals_for desc
            limit 1
        ),
        best_def as (
            select tms.team_id, dt.team_name, tms.goals_against
            from team_match_stats tms
            left join mart.dim_team dt on dt.team_id = tms.team_id
            order by tms.goals_against asc
            limit 1
        )
        select
            ma.competition_key,
            ma.season,
            ma.season_label,
            ma.total_matches,
            ma.total_goals,
            ma.avg_goals_per_match,
            ma.home_wins,
            ma.away_wins,
            ma.draws,
            coalesce(ta.total_teams, 0) as total_teams,
            coalesce(ca.total_coaches, 0) as total_coaches,
            coalesce(pa.total_players, 0) as total_players,
            case
                when ma.total_matches > 0
                then round(100.0 * ma.home_wins / ma.total_matches, 2)
            end as home_win_rate,
            case
                when ma.total_matches > 0
                then round(100.0 * ma.away_wins / ma.total_matches, 2)
            end as away_win_rate,
            case
                when ma.total_matches > 0
                then round(100.0 * ma.draws / ma.total_matches, 2)
            end as draw_rate,
            ts.team_id as top_scorer_team_id,
            ts.team_name as top_scorer_team_name,
            ts.goals_for as top_scorer_goals,
            bd.team_id as best_defense_team_id,
            bd.team_name as best_defense_team_name,
            bd.goals_against as best_defense_goals_against,
            bpc.coach_id as best_ppm_coach_id,
            bpc.coach_name as best_ppm_coach_name,
            bpc.points_per_match as best_ppm_coach_points_per_match,
            bpc.matches as best_ppm_coach_matches
        from match_agg ma
        cross join team_agg ta
        cross join coach_agg ca
        cross join player_agg pa
        left join top_scorer ts on 1=1
        left join best_def bd on 1=1
        left join best_ppm_coach bpc on 1=1
    """
    rows = db_client.fetch_all(query, where_params)

    if not rows or _to_int(rows[0].get("total_matches")) == 0:
        return build_api_response(
            {
                "scope": {"competitionId": _to_text(competitionId), "seasonId": _to_text(seasonId)},
                "summary": {
                    "totalMatches": 0, "totalGoals": 0, "avgGoalsPerMatch": None,
                    "totalTeams": 0, "totalCoaches": 0, "totalPlayers": 0,
                    "homeWins": 0, "awayWins": 0, "draws": 0,
                    "homeWinRate": None, "awayWinRate": None, "drawRate": None,
                },
            },
            request_id=_request_id(request),
            coverage=_not_available_coverage("Analytics overview coverage"),
        )

    row = rows[0]
    summary = {
        "totalMatches": _to_int(row.get("total_matches")),
        "totalGoals": _to_int(row.get("total_goals")),
        "avgGoalsPerMatch": _to_float(row.get("avg_goals_per_match")),
        "totalTeams": _to_int(row.get("total_teams")),
        "totalCoaches": _to_int(row.get("total_coaches")),
        "totalPlayers": _to_int(row.get("total_players")),
        "homeWins": _to_int(row.get("home_wins")),
        "awayWins": _to_int(row.get("away_wins")),
        "draws": _to_int(row.get("draws")),
        "homeWinRate": _to_float(row.get("home_win_rate")),
        "awayWinRate": _to_float(row.get("away_win_rate")),
        "drawRate": _to_float(row.get("draw_rate")),
    }
    data: dict[str, Any] = {
        "scope": {
            "competitionId": _to_text(row.get("competition_key")),
            "competitionLabel": None,
            "seasonId": _to_text(row.get("season")),
            "seasonLabel": _to_text(row.get("season_label")),
        },
        "summary": summary,
    }
    if row.get("top_scorer_team_id") is not None:
        data["topScorerTeam"] = {
            "teamId": str(row["top_scorer_team_id"]),
            "teamName": row.get("top_scorer_team_name") or "Time indisponivel",
            "goalsFor": _to_int(row.get("top_scorer_goals")),
        }
    if row.get("best_defense_team_id") is not None:
        data["bestDefenseTeam"] = {
            "teamId": str(row["best_defense_team_id"]),
            "teamName": row.get("best_defense_team_name") or "Time indisponivel",
            "goalsAgainst": _to_int(row.get("best_defense_goals_against")),
        }
    if row.get("best_ppm_coach_id") is not None:
        data["bestPpmCoach"] = {
            "coachId": str(row["best_ppm_coach_id"]),
            "coachName": row.get("best_ppm_coach_name") or "Tecnico indisponivel",
            "pointsPerMatch": _to_float(row.get("best_ppm_coach_points_per_match")),
            "matches": _to_int(row.get("best_ppm_coach_matches")),
            "coverageStatus": "available",
        }

    total = _to_int(row.get("total_matches"))
    coverage = build_coverage_from_counts(total, total, "Match score coverage")

    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=coverage,
    )


@router.get("/trends")
def get_trends(
    request: Request,
    metric: str,
    periodType: str,
    entityId: str | None = None,
    competitionId: str | None = None,
    seasonId: str | None = None,
    roundId: str | None = None,
    stageId: str | None = None,
    venue: VenueFilter = VenueFilter.all,
    lastN: int | None = Query(default=None, gt=0),
    dateStart: date | None = None,
    dateEnd: date | None = None,
) -> dict[str, Any]:
    if metric not in VALID_METRICS_TRENDS:
        raise AppError(
            message=f"Invalid metric '{metric}'. Valid options: {', '.join(VALID_METRICS_TRENDS)}",
            code="INVALID_METRIC",
            status=400,
            details={"validMetrics": VALID_METRICS_TRENDS},
        )
    if periodType not in VALID_PERIOD_TYPES:
        raise AppError(
            message=f"Invalid periodType '{periodType}'. Valid options: round, month",
            code="INVALID_PERIOD_TYPE",
            status=400,
            details={"validPeriodTypes": VALID_PERIOD_TYPES},
        )

    filters = validate_and_build_global_filters(
        competition_id=competitionId,
        season_id=seasonId,
        round_id=roundId,
        stage_id=stageId,
        venue=venue,
        last_n=lastN,
        date_start=dateStart,
        date_end=dateEnd,
    date_range_start=None,
    date_range_end=None,
    )

    filter_clauses: list[str] = []
    filter_params: list[Any] = []
    append_fact_match_filters(filter_clauses, filter_params, alias="fm", filters=filters)

    if filters.venue == VenueFilter.home:
        filter_clauses.append("fm.home_team_id is not null")
    elif filters.venue == VenueFilter.away:
        filter_clauses.append("fm.away_team_id is not null")

    if metric in TREND_TEAM_METRICS:
        trend_metrics: dict[str, str] = {
            "points": "sum(tr.points_round)::int",
            "goals_for": "sum(tr.goals_for)::int",
            "goals_against": "sum(tr.goals_against)::int",
            "goal_diff": "(sum(tr.goals_for) - sum(tr.goals_against))::int",
        }
        metric_expr = trend_metrics[metric]

        if periodType == "round":
            period_expr = "fm.round_number::text"
            period_label_expr = "concat('Rodada ', fm.round_number)"
            group_by = "fm.round_number"
            order_by = "min(fm.round_number)"
        else:
            period_expr = "to_char(fm.date_day, 'YYYY-MM')"
            period_label_expr = "to_char(fm.date_day, 'YYYY-MM')"
            group_by = "to_char(fm.date_day, 'YYYY-MM')"
            order_by = "min(fm.date_day)"

        entity_filter = ""
        if entityId:
            filter_clauses.append("tr.team_id = %s")
            filter_params.append(int(entityId))

        query = f"""
            select
                {period_expr} as period,
                {period_label_expr} as period_label,
                {metric_expr} as value,
                count(distinct tr.match_id)::int as sample_size
            from mart.int_team_match_rows tr
            join mart.fact_matches fm on fm.match_id = tr.match_id
            where {_join_where_clauses(filter_clauses)}
            group by {group_by}
            order by {order_by}
        """
    else:
        metric_expr = {
            "matches": "count(distinct fm.match_id)::int",
            "goals": "sum(coalesce(fm.total_goals, 0))::int",
            "avg_goals": "round(avg(coalesce(fm.total_goals, 0)), 4)",
            "home_wins": "sum(case when coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0) then 1 else 0 end)::int",
            "away_wins": "sum(case when coalesce(fm.home_goals, 0) < coalesce(fm.away_goals, 0) then 1 else 0 end)::int",
            "draws": "sum(case when coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 1 else 0 end)::int",
        }[metric]

        if periodType == "round":
            period_expr = "fm.round_number::text"
            period_label_expr = "concat('Rodada ', fm.round_number)"
            group_by = "fm.round_number"
            order_by = "min(fm.round_number)"
        else:
            period_expr = "to_char(fm.date_day, 'YYYY-MM')"
            period_label_expr = "to_char(fm.date_day, 'YYYY-MM')"
            group_by = "to_char(fm.date_day, 'YYYY-MM')"
            order_by = "min(fm.date_day)"

        entity_filter = ""
        if entityId:
            filter_clauses.append("(fm.home_team_id = %s or fm.away_team_id = %s)")
            filter_params.append(int(entityId))
            filter_params.append(int(entityId))

        query = f"""
            select
                {period_expr} as period,
                {period_label_expr} as period_label,
                {metric_expr} as value,
                count(distinct fm.match_id)::int as sample_size
            from mart.fact_matches fm
            where {_join_where_clauses(filter_clauses)}
            group by {group_by}
            order by {order_by}
        """

    rows = db_client.fetch_all(query, filter_params)

    series = [
        {
            "period": row.get("period"),
            "periodLabel": row.get("period_label"),
            "value": row.get("value"),
            "sampleSize": _to_int(row.get("sample_size")),
        }
        for row in rows
    ]

    num_periods = len(series)
    values_list = [float(s["value"]) for s in series if s["value"] is not None]
    trend_direction = _compute_trend_direction(values_list) if len(values_list) >= 3 else None

    if num_periods >= 5:
        coverage = build_coverage_from_counts(num_periods, num_periods, "Round coverage for trends")
    elif num_periods >= 3:
        coverage = build_coverage_from_counts(num_periods, max(num_periods, 5), "Round coverage for trends")
    else:
        coverage = _not_available_coverage("Trend series coverage")

    return build_api_response(
        {
            "metric": metric,
            "periodType": periodType,
            "series": series,
            "trendDirection": trend_direction,
            "minPeriodsRequired": 3,
            "totalPeriods": num_periods,
        },
        request_id=_request_id(request),
        coverage=coverage,
    )


@router.get("/olap")
def get_olap(
    request: Request,
    metric: str,
    dimension: str,
    grain: str,
    operation: str | None = "slice",
    breakdown: str | None = "none",
    competitionId: str | None = None,
    seasonId: str | None = None,
    roundId: str | None = None,
    stageId: str | None = None,
    venue: VenueFilter = VenueFilter.all,
    lastN: int | None = Query(default=None, gt=0),
    dateStart: date | None = None,
    dateEnd: date | None = None,
) -> dict[str, Any]:
    if metric not in VALID_METRICS_OLAP:
        raise AppError(
            message=f"Invalid metric '{metric}'. Valid options: {', '.join(VALID_METRICS_OLAP)}",
            code="INVALID_METRIC",
            status=400,
            details={"validMetrics": VALID_METRICS_OLAP},
        )
    if dimension not in VALID_DIMENSIONS:
        raise AppError(
            message=f"Invalid dimension '{dimension}'. Valid options: {', '.join(VALID_DIMENSIONS)}",
            code="INVALID_DIMENSION",
            status=400,
            details={"validDimensions": VALID_DIMENSIONS},
        )
    if grain not in VALID_GRAINS:
        raise AppError(
            message=f"Invalid grain '{grain}'. Valid options: {', '.join(VALID_GRAINS)}",
            code="INVALID_GRAIN",
            status=400,
            details={"validGrains": VALID_GRAINS},
        )
    if operation not in VALID_OPERATIONS:
        raise AppError(
            message=f"Invalid operation '{operation}'. Valid options: {', '.join(VALID_OPERATIONS)}",
            code="INVALID_OPERATION",
            status=400,
            details={"validOperations": VALID_OPERATIONS},
        )
    if breakdown not in VALID_BREAKDOWNS:
        raise AppError(
            message=f"Invalid breakdown '{breakdown}'. Valid options: {', '.join(VALID_BREAKDOWNS)}",
            code="INVALID_BREAKDOWN",
            status=400,
            details={"validBreakdowns": VALID_BREAKDOWNS},
        )

    compatible_dims = GRAIN_DIMENSION_COMPAT.get(grain, set())
    if dimension not in compatible_dims:
        raise AppError(
            message=f"Incompatible combination: grain='{grain}' and dimension='{dimension}'.",
            code="INCOMPATIBLE_COMBINATION",
            status=400,
            details={
                "grain": grain,
                "dimension": dimension,
                "compatibleDimensions": sorted(compatible_dims),
            },
        )

    if breakdown != "none":
        compatible_breakdowns = DIMENSION_BREAKDOWN_COMPAT.get(dimension, set())
        if breakdown not in compatible_breakdowns:
            raise AppError(
                message=f"Incompatible breakdown: dimension='{dimension}' and breakdown='{breakdown}'.",
                code="INCOMPATIBLE_BREAKDOWN",
                status=400,
                details={
                    "dimension": dimension,
                    "breakdown": breakdown,
                    "compatibleBreakdowns": sorted(compatible_breakdowns),
                },
            )

    filters = validate_and_build_global_filters(
        competition_id=competitionId,
        season_id=seasonId,
        round_id=roundId,
        stage_id=stageId,
        venue=venue,
        last_n=lastN,
        date_start=dateStart,
        date_end=dateEnd,
    date_range_start=None,
    date_range_end=None,
    )

    if operation == "drill_through":
        where_sql, where_params = _build_match_filters(filters)
        drill_query = f"""
            select distinct fm.match_id
            from mart.fact_matches fm
            where {where_sql}
            limit 100
        """
        drill_rows = db_client.fetch_all(drill_query, where_params)
        return build_api_response(
            {
                "metric": metric,
                "dimension": dimension,
                "grain": grain,
                "operation": operation,
                "rows": [{"matchId": str(r["match_id"])} for r in drill_rows],
                "total": len(drill_rows),
                "drillThroughAvailable": True,
            },
            request_id=_request_id(request),
            coverage=build_coverage_from_counts(len(drill_rows), max(len(drill_rows), 1), "OLAP drill-through coverage"),
        )

    where_clauses: list[str] = []
    where_params: list[Any] = []
    append_fact_match_filters(where_clauses, where_params, alias="fm", filters=filters)

    if filters.venue == VenueFilter.home:
        where_clauses.append("fm.home_team_id is not null")
    elif filters.venue == VenueFilter.away:
        where_clauses.append("fm.away_team_id is not null")

    is_team_grouping = dimension in TEAM_GROUPING_DIMS or dimension == "venue" or breakdown in {"team", "venue"}
    metric_exprs = TEAM_METRIC_EXPRESSIONS if is_team_grouping else MATCH_METRIC_EXPRESSIONS

    if metric not in metric_exprs:
        raise AppError(
            message=f"Metric '{metric}' is not available for dimension '{dimension}' at grain '{grain}'.",
            code="INVALID_METRIC",
            status=400,
            details={"validMetrics": sorted(metric_exprs)},
        )

    metric_expr = metric_exprs[metric]
    dim = DIMENSION_DEFS[dimension]

    sample_size_expr = (
        "count(distinct tr.match_id)::int"
        if is_team_grouping
        else "count(distinct case when fm.home_team_id = tr.team_id then fm.match_id end)::int"
    )

    select_parts = [
        f"{dim['key']} as dimension_key",
        f"{dim['label']} as dimension_label",
        f"{metric_expr} as value",
        f"{sample_size_expr} as sample_size",
    ]

    join_parts = dim["joins"]
    group_parts = dim["group_by"]
    order_parts = dim["order_by"]

    bd_select = ""
    bd_group_extra = ""
    if breakdown and breakdown != "none":
        bd = BREAKDOWN_DEFS[breakdown]
        select_parts.append(f"{bd['key']} as breakdown_key")
        select_parts.append(f"{bd['label']} as breakdown_label")
        bd_group_extra = bd["group_by"]
        if bd.get("joins"):
            join_parts += " " + bd["joins"]

    final_group_by = group_parts + bd_group_extra

    olap_query = f"""
        select {', '.join(select_parts)}
        from mart.int_team_match_rows tr
        inner join mart.fact_matches fm on fm.match_id = tr.match_id
        {join_parts}
        where {_join_where_clauses(where_clauses)}
        group by {final_group_by}
        order by {order_parts}
    """
    rows = db_client.fetch_all(olap_query, where_params)

    result_rows = []
    for row in rows:
        r: dict[str, Any] = {
            "dimensionKey": row.get("dimension_key"),
            "dimensionLabel": row.get("dimension_label"),
            "value": row.get("value"),
            "sampleSize": _to_int(row.get("sample_size")),
        }
        if breakdown and breakdown != "none" and row.get("breakdown_key") is not None:
            r["breakdown"] = {
                "key": row["breakdown_key"],
                "label": row["breakdown_label"],
                "value": row.get("value"),
            }
        else:
            r["breakdown"] = None
        result_rows.append(r)

    total = sum(_to_int(r.get("sample_size") or 0) for r in rows) if rows else 0
    drill_available = grain not in {"competition_season"}
    coverage = build_coverage_from_counts(len(rows), max(len(rows), 1), "OLAP query coverage")

    return build_api_response(
        {
            "metric": metric,
            "dimension": dimension,
            "grain": grain,
            "operation": operation,
            "rows": result_rows,
            "total": total,
            "drillThroughAvailable": drill_available,
        },
        request_id=_request_id(request),
        coverage=coverage,
    )


@router.get("/comparisons")
def get_comparisons(
    request: Request,
    type: str,
    entityA: str,
    entityB: str,
    scope: str | None = None,
    competitionId: str | None = None,
    seasonId: str | None = None,
    roundId: str | None = None,
    stageId: str | None = None,
    venue: VenueFilter = VenueFilter.all,
    lastN: int | None = Query(default=None, gt=0),
    dateStart: date | None = None,
    dateEnd: date | None = None,
) -> dict[str, Any]:
    if type not in VALID_COMPARISON_TYPES:
        raise AppError(
            message=f"Invalid comparison type '{type}'. Valid options: {', '.join(VALID_COMPARISON_TYPES)}",
            code="INVALID_COMPARISON_TYPE",
            status=400,
            details={"validTypes": VALID_COMPARISON_TYPES},
        )

    filters = validate_and_build_global_filters(
        competition_id=competitionId,
        season_id=seasonId,
        round_id=roundId,
        stage_id=stageId,
        venue=venue,
        last_n=lastN,
        date_start=dateStart,
        date_end=dateEnd,
    date_range_start=None,
    date_range_end=None,
    )

    where_clauses: list[str] = []
    where_params: list[Any] = []
    append_fact_match_filters(where_clauses, where_params, alias="fm", filters=filters)

    if filters.venue == VenueFilter.home:
        where_clauses.append("fm.home_team_id is not null")
    elif filters.venue == VenueFilter.away:
        where_clauses.append("fm.away_team_id is not null")

    ENTITY_SQL = """
        select
            {entity_id_expr} as entity_id,
            {entity_label_expr} as entity_label,
            count(distinct tr.match_id)::int as matches,
            sum(tr.wins)::int as wins,
            sum(tr.draws)::int as draws,
            sum(tr.losses)::int as losses,
            sum(tr.points_round)::int as points,
            sum(tr.goals_for)::int as goals_for,
            sum(tr.goals_against)::int as goals_against,
            (sum(tr.goals_for) - sum(tr.goals_against))::int as goal_diff,
            case when count(distinct tr.match_id) > 0
                then round(avg(coalesce(fm.total_goals, 0)), 4)
            end as avg_goals_per_match,
            case when count(distinct tr.match_id) > 0
                then round(sum(tr.points_round)::numeric / count(distinct tr.match_id), 4)
            end as points_per_match
        from mart.int_team_match_rows tr
        join mart.fact_matches fm on fm.match_id = tr.match_id
        {extra_join}
        where {where_sql}
        group by {entity_id_expr}, {entity_label_expr}
    """

    def _fetch_entity(
        label: str,
        entity_id_expr: str,
        entity_label_expr: str,
        extra_join: str,
        extra_where: str,
        extra_params: list[Any],
    ) -> dict[str, Any] | None:
        wc = list(where_clauses)
        wp = list(where_params) + extra_params
        if extra_where:
            wc.append(extra_where)
        sql = ENTITY_SQL.format(
            entity_id_expr=entity_id_expr,
            entity_label_expr=entity_label_expr,
            extra_join=extra_join,
            where_sql=_join_where_clauses(wc),
        )
        rows = db_client.fetch_all(sql, wp)
        if not rows:
            return None
        row = rows[0]
        return {
            "id": row.get("entity_id"),
            "label": row.get("entity_label") or label,
            "matches": _to_int(row.get("matches")),
            "wins": _to_int(row.get("wins")),
            "draws": _to_int(row.get("draws")),
            "losses": _to_int(row.get("losses")),
            "points": _to_int(row.get("points")),
            "goalsFor": _to_int(row.get("goals_for")),
            "goalsAgainst": _to_int(row.get("goals_against")),
            "goalDiff": _to_int(row.get("goal_diff")),
            "avgGoalsPerMatch": _to_float(row.get("avg_goals_per_match")),
            "pointsPerMatch": _to_float(row.get("points_per_match")),
        }

    entity_a_data: dict[str, Any] | None = None
    entity_b_data: dict[str, Any] | None = None
    comp_entity_a: str = entityA
    comp_entity_b: str = entityB

    if type == "team_vs_team":
        team_a_id = int(entityA) if entityA.isdigit() else entityA
        team_b_id = int(entityB) if entityB.isdigit() else entityB
        entity_a_data = _fetch_entity(
            entityA,
            "tr.team_id::text",
            "coalesce(dt.team_name, 'Time indisponivel')",
            "left join mart.dim_team dt on dt.team_id = tr.team_id",
            "tr.team_id = %s",
            [team_a_id],
        )
        entity_b_data = _fetch_entity(
            entityB,
            "tr.team_id::text",
            "coalesce(dt.team_name, 'Time indisponivel')",
            "left join mart.dim_team dt on dt.team_id = tr.team_id",
            "tr.team_id = %s",
            [team_b_id],
        )
        if entity_a_data:
            entity_a_data["label"] = _row_label(rows=db_client.fetch_all("select team_name from mart.dim_team where team_id = %s", [team_a_id]), fallback=entityA)
        if entity_b_data:
            entity_b_data["label"] = _row_label(rows=db_client.fetch_all("select team_name from mart.dim_team where team_id = %s", [team_b_id]), fallback=entityB)

    elif type == "season_vs_season":
        entity_a_data = _fetch_entity(
            entityA,
            "fm.season_label::text",
            "concat('Temporada ', fm.season_label)",
            "",
            "fm.season_label = %s",
            [entityA],
        )
        entity_b_data = _fetch_entity(
            entityB,
            "fm.season_label::text",
            "concat('Temporada ', fm.season_label)",
            "",
            "fm.season_label = %s",
            [entityB],
        )

    elif type == "home_vs_away":
        team_id_parsed = int(entityA) if entityA.isdigit() else 0
        entity_a_data = _fetch_entity(
            "Casa",
            "'home'",
            "'Casa'",
            "left join mart.dim_team dt on dt.team_id = tr.team_id",
            "fm.home_team_id = tr.team_id and tr.team_id = %s",
            [team_id_parsed],
        )
        entity_b_data = _fetch_entity(
            "Fora",
            "'away'",
            "'Fora'",
            "left join mart.dim_team dt on dt.team_id = tr.team_id",
            "fm.away_team_id = tr.team_id and tr.team_id = %s",
            [team_id_parsed],
        )
        if entity_a_data:
            entity_a_data["label"] = "Casa"
        if entity_b_data:
            entity_b_data["label"] = "Fora"

    elif type == "period_vs_period":
        team_id_parsed = int(entityA) if entityA.isdigit() else 0
        entity_a_data = _fetch_entity(
            "1o Turno",
            "'first_half'",
            "'1o Turno'",
            "left join mart.dim_team dt on dt.team_id = tr.team_id",
            "fm.round_number <= (select max(round_number)/2 from mart.fact_matches where league_id = coalesce(%s::int, league_id)) and tr.team_id = %s",
            [filters.competition_id, team_id_parsed],
        )
        entity_b_data = _fetch_entity(
            "2o Turno",
            "'second_half'",
            "'2o Turno'",
            "left join mart.dim_team dt on dt.team_id = tr.team_id",
            "fm.round_number > (select max(round_number)/2 from mart.fact_matches where league_id = coalesce(%s::int, league_id)) and tr.team_id = %s",
            [filters.competition_id, team_id_parsed],
        )
        if entity_a_data:
            entity_a_data["label"] = "1o Turno"
        if entity_b_data:
            entity_b_data["label"] = "2o Turno"

    def _safe_entity(data: dict[str, Any] | None, eid: str, elabel: str) -> dict[str, Any]:
        if data is not None:
            return data
        return {
            "id": eid, "label": elabel,
            "matches": None, "wins": None, "draws": None, "losses": None,
            "points": None, "goalsFor": None, "goalsAgainst": None,
            "goalDiff": None, "avgGoalsPerMatch": None, "pointsPerMatch": None,
        }

    entity_a_final = _safe_entity(entity_a_data, comp_entity_a, comp_entity_a)
    entity_b_final = _safe_entity(entity_b_data, comp_entity_b, comp_entity_b)

    diff: dict[str, Any] = {}
    for key in ("points", "goalDiff", "wins", "draws", "losses"):
        va = entity_a_final.get(key)
        vb = entity_b_final.get(key)
        if va is not None and vb is not None:
            diff[key] = va - vb
        else:
            diff[key] = None

    combined_matches = (
        (_to_int(entity_a_final.get("matches")) or 0)
        + (_to_int(entity_b_final.get("matches")) or 0)
    )
    combined_coverage = build_coverage_from_counts(
        combined_matches, max(combined_matches, 1), "Combined match coverage",
    )

    return build_api_response(
        {
            "type": type,
            "entityA": entity_a_final,
            "entityB": entity_b_final,
            "difference": diff,
            "coverage": {
                "entityA": build_coverage_from_counts(
                    _to_int(entity_a_final.get("matches")),
                    max(_to_int(entity_a_final.get("matches")), 1),
                    "Entity A match coverage",
                ),
                "entityB": build_coverage_from_counts(
                    _to_int(entity_b_final.get("matches")),
                    max(_to_int(entity_b_final.get("matches")), 1),
                    "Entity B match coverage",
                ),
            },
        },
        request_id=_request_id(request),
        coverage=combined_coverage,
    )


@router.get("/superlatives")
def get_superlatives(
    request: Request,
    category: str = "most_goals_match",
    limit: int = Query(default=10, ge=1, le=50),
    competitionId: str | None = None,
    seasonId: str | None = None,
    roundId: str | None = None,
    stageId: str | None = None,
    venue: VenueFilter = VenueFilter.all,
    lastN: int | None = Query(default=None, gt=0),
    dateStart: date | None = None,
    dateEnd: date | None = None,
) -> dict[str, Any]:
    if category not in VALID_SUPERLATIVE_CATEGORIES:
        raise AppError(
            message=f"Invalid category '{category}'. Valid options: {', '.join(VALID_SUPERLATIVE_CATEGORIES)}",
            code="INVALID_SUPERLATIVE_CATEGORY",
            status=400,
            details={"validCategories": VALID_SUPERLATIVE_CATEGORIES},
        )

    filters = validate_and_build_global_filters(
        competition_id=competitionId,
        season_id=seasonId,
        round_id=roundId,
        stage_id=stageId,
        venue=venue,
        last_n=lastN,
        date_start=dateStart,
        date_end=dateEnd,
    date_range_start=None,
    date_range_end=None,
    )

    where_sql, where_params = _build_match_filters(filters)

    CATEGORY_LABELS: dict[str, str] = {
        "most_goals_match": "Partida com mais gols",
        "biggest_win": "Maior goleada",
        "best_attack": "Melhor ataque",
        "best_defense": "Melhor defesa",
        "best_goal_diff": "Melhor saldo de gols",
        "most_goals_round": "Rodada com mais gols",
        "highest_avg_goals_round": "Rodada com maior media de gols",
        "best_team_ppg": "Melhor aproveitamento (PPG)",
        "coach_best_ppm": "Tecnico melhor PPM",
        "coach_most_matches": "Tecnico com mais partidas",
    }

    QUERIES: dict[str, str] = {
        "most_goals_match": f"""
            select
                fm.match_id::text as entity_id,
                concat('Match ', fm.match_id) as entity_label,
                coalesce(fm.total_goals, 0) as value,
                concat(fm.competition_key, '/', fm.season_label) as scope,
                count(*) over()::int as sample_size
            from mart.fact_matches fm
            where {where_sql} and fm.total_goals is not null
            order by fm.total_goals desc, fm.match_id
            limit %s
        """,
        "biggest_win": f"""
            select
                fm.match_id::text as entity_id,
                concat('Match ', fm.match_id) as entity_label,
                abs(coalesce(fm.home_goals, 0) - coalesce(fm.away_goals, 0)) as value,
                concat(fm.competition_key, '/', fm.season_label) as scope,
                count(*) over()::int as sample_size
            from mart.fact_matches fm
            where {where_sql} and fm.home_goals is not null and fm.away_goals is not null
            order by value desc, fm.match_id
            limit %s
        """,
        "best_attack": f"""
            select
                tr.team_id::text as entity_id,
                coalesce(dt.team_name, 'Time indisponivel') as entity_label,
                sum(tr.goals_for) as value,
                concat(fm.competition_key, '/', fm.season_label) as scope,
                count(distinct tr.match_id)::int as sample_size
            from mart.int_team_match_rows tr
            join mart.fact_matches fm on fm.match_id = tr.match_id
            left join mart.dim_team dt on dt.team_id = tr.team_id
            where {where_sql}
            group by tr.team_id, dt.team_name, fm.competition_key, fm.season_label
            order by value desc, tr.team_id
            limit %s
        """,
        "best_defense": f"""
            select
                tr.team_id::text as entity_id,
                coalesce(dt.team_name, 'Time indisponivel') as entity_label,
                sum(tr.goals_against) as value,
                concat(fm.competition_key, '/', fm.season_label) as scope,
                count(distinct tr.match_id)::int as sample_size
            from mart.int_team_match_rows tr
            join mart.fact_matches fm on fm.match_id = tr.match_id
            left join mart.dim_team dt on dt.team_id = tr.team_id
            where {where_sql}
            group by tr.team_id, dt.team_name, fm.competition_key, fm.season_label
            order by value asc, tr.team_id
            limit %s
        """,
        "best_goal_diff": f"""
            select
                tr.team_id::text as entity_id,
                coalesce(dt.team_name, 'Time indisponivel') as entity_label,
                (sum(tr.goals_for) - sum(tr.goals_against)) as value,
                concat(fm.competition_key, '/', fm.season_label) as scope,
                count(distinct tr.match_id)::int as sample_size
            from mart.int_team_match_rows tr
            join mart.fact_matches fm on fm.match_id = tr.match_id
            left join mart.dim_team dt on dt.team_id = tr.team_id
            where {where_sql}
            group by tr.team_id, dt.team_name, fm.competition_key, fm.season_label
            order by value desc, tr.team_id
            limit %s
        """,
        "most_goals_round": f"""
            select
                fm.round_number::text as entity_id,
                concat('Rodada ', fm.round_number) as entity_label,
                sum(coalesce(fm.total_goals, 0)) as value,
                concat(fm.competition_key, '/', fm.season_label) as scope,
                count(distinct fm.match_id)::int as sample_size
            from mart.fact_matches fm
            where {where_sql} and fm.round_number > 0
            group by fm.round_number, fm.competition_key, fm.season_label
            order by value desc, fm.round_number
            limit %s
        """,
        "highest_avg_goals_round": f"""
            select
                fm.round_number::text as entity_id,
                concat('Rodada ', fm.round_number) as entity_label,
                round(avg(coalesce(fm.total_goals, 0)), 4) as value,
                concat(fm.competition_key, '/', fm.season_label) as scope,
                count(distinct fm.match_id)::int as sample_size
            from mart.fact_matches fm
            where {where_sql} and fm.round_number > 0
            group by fm.round_number, fm.competition_key, fm.season_label
            order by avg(coalesce(fm.total_goals, 0)) desc, fm.round_number
            limit %s
        """,
        "best_team_ppg": f"""
            select
                tr.team_id::text as entity_id,
                coalesce(dt.team_name, 'Time indisponivel') as entity_label,
                round(sum(tr.points_round)::numeric / nullif(count(distinct tr.match_id), 0), 4) as value,
                concat(fm.competition_key, '/', fm.season_label) as scope,
                count(distinct tr.match_id)::int as sample_size
            from mart.int_team_match_rows tr
            join mart.fact_matches fm on fm.match_id = tr.match_id
            left join mart.dim_team dt on dt.team_id = tr.team_id
            where {where_sql}
            group by tr.team_id, dt.team_name, fm.competition_key, fm.season_label
            order by value desc, sum(tr.goals_for) desc, tr.team_id
            limit %s
        """,
        "coach_best_ppm": f"""
            select
                dc.coach_id::text as entity_id,
                coalesce(dc.coach_name, 'Nome indisponivel') as entity_label,
                round(sum(tr.points_round)::numeric / nullif(count(distinct tr.match_id), 0), 4) as value,
                concat(fm.competition_key, '/', fm.season_label) as scope,
                count(distinct tr.match_id)::int as sample_size
            from mart.int_team_match_rows tr
            join mart.fact_matches fm on fm.match_id = tr.match_id
            left join mart.stg_team_coaches tc on tc.team_id = tr.team_id
                and fm.date_day >= coalesce(tc.start_date, date '1900-01-01')
                and fm.date_day <= coalesce(tc.end_date, date '2999-12-31')
            left join mart.dim_coach dc on dc.provider = tc.provider and dc.coach_id = tc.coach_id
            where {where_sql} and dc.coach_id is not null
            group by dc.coach_id, dc.coach_name, fm.competition_key, fm.season_label
            having count(distinct tr.match_id) >= 5
            order by value desc, count(distinct tr.match_id) desc
            limit %s
        """,
        "coach_most_matches": f"""
            select
                dc.coach_id::text as entity_id,
                coalesce(dc.coach_name, 'Nome indisponivel') as entity_label,
                count(distinct tr.match_id)::int as value,
                concat(fm.competition_key, '/', fm.season_label) as scope,
                count(distinct tr.match_id)::int as sample_size
            from mart.int_team_match_rows tr
            join mart.fact_matches fm on fm.match_id = tr.match_id
            left join mart.stg_team_coaches tc on tc.team_id = tr.team_id
                and fm.date_day >= coalesce(tc.start_date, date '1900-01-01')
                and fm.date_day <= coalesce(tc.end_date, date '2999-12-31')
            left join mart.dim_coach dc on dc.provider = tc.provider and dc.coach_id = tc.coach_id
            where {where_sql} and dc.coach_id is not null
            group by dc.coach_id, dc.coach_name, fm.competition_key, fm.season_label
            having count(distinct tr.match_id) >= 5
            order by count(distinct tr.match_id) desc, dc.coach_id
            limit %s
        """,
    }

    query = QUERIES[category]
    params = list(where_params) + [limit]
    rows = db_client.fetch_all(query, params)

    threshold = SUPERLATIVE_THRESHOLDS.get(category, 1)
    sample_size = _to_int(rows[0].get("sample_size")) if rows else 0

    if sample_size < threshold:
        return build_api_response(
            {
                "category": category,
                "categoryLabel": CATEGORY_LABELS.get(category, category),
                "limit": limit,
                "records": [],
            },
            request_id=_request_id(request),
            coverage={
                "status": "insufficient",
                "percentage": round((sample_size / threshold) * 100, 2) if threshold > 0 else 0,
                "sampleSize": sample_size,
                "expectedSize": threshold,
                "label": "Superlative category coverage",
                "details": f"Insufficient data for category '{category}'. Minimum threshold: {threshold}.",
            },
        )

    records = [
        {
            "position": idx + 1,
            "entityId": row.get("entity_id"),
            "entityLabel": row.get("entity_label"),
            "value": row.get("value"),
            "scope": row.get("scope"),
            "sampleSize": _to_int(row.get("sample_size")),
            "tiebreaker": None,
        }
        for idx, row in enumerate(rows)
    ]

    coverage = build_coverage_from_counts(
        len(rows), max(len(rows), threshold), "Superlative category coverage",
    )

    return build_api_response(
        {
            "category": category,
            "categoryLabel": CATEGORY_LABELS.get(category, category),
            "limit": limit,
            "records": records,
        },
        request_id=_request_id(request),
        coverage=coverage,
    )


@router.get("/coverage")
def get_coverage(
    request: Request,
    competitionId: str | None = None,
    seasonId: str | None = None,
    roundId: str | None = None,
    stageId: str | None = None,
    venue: VenueFilter = VenueFilter.all,
    lastN: int | None = Query(default=None, gt=0),
    dateStart: date | None = None,
    dateEnd: date | None = None,
) -> dict[str, Any]:
    filters = validate_and_build_global_filters(
        competition_id=competitionId,
        season_id=seasonId,
        round_id=roundId,
        stage_id=stageId,
        venue=venue,
        last_n=lastN,
        date_start=dateStart,
        date_end=dateEnd,
    date_range_start=None,
    date_range_end=None,
    )
    where_sql, where_params = _build_match_filters(filters)

    query = f"""
        with match_scope as (
            select
                fm.match_id,
                fm.home_team_id,
                fm.away_team_id,
                fm.date_day
            from mart.fact_matches fm
            where {where_sql}
        ),
        match_count as (
            select count(distinct match_id)::int as total_matches
            from match_scope
        ),
        events_count as (
            select count(distinct me.match_id)::int as cnt
            from mart.fact_match_events me
            join match_scope ms on ms.match_id = me.match_id
        ),
        lineups_count as (
            select count(distinct fl.match_id)::int as cnt
            from mart.fact_fixture_lineups fl
            join match_scope ms on ms.match_id = fl.match_id
        ),
        player_stats_count as (
            select count(distinct fps.match_id)::int as cnt
            from mart.fact_fixture_player_stats fps
            join match_scope ms on ms.match_id = fps.match_id
        ),
        team_stats_count as (
            select count(distinct tr.match_id)::int as cnt
            from mart.int_team_match_rows tr
            join match_scope ms on ms.match_id = tr.match_id
        ),
        coach_assignment_count as (
            select count(distinct ms.match_id)::int as cnt
            from match_scope ms
            join mart.int_team_match_rows tr on tr.match_id = ms.match_id
            join mart.stg_team_coaches tc
                on tc.team_id = tr.team_id
                and ms.date_day >= coalesce(tc.start_date, date '1900-01-01')
                and ms.date_day <= coalesce(tc.end_date, date '2999-12-31')
        )
        select
            mc.total_matches,
            coalesce(ec.cnt, 0) as matches_with_events,
            coalesce(lc.cnt, 0) as matches_with_lineups,
            coalesce(psc.cnt, 0) as matches_with_player_stats,
            coalesce(tsc.cnt, 0) as matches_with_team_stats,
            coalesce(cac.cnt, 0) as matches_with_coach_assignment
        from match_count mc
        left join events_count ec on 1=1
        left join lineups_count lc on 1=1
        left join player_stats_count psc on 1=1
        left join team_stats_count tsc on 1=1
        left join coach_assignment_count cac on 1=1
    """
    rows = db_client.fetch_all(query, where_params)

    if not rows or _to_int(rows[0].get("total_matches")) == 0:
        return build_api_response(
            {
                "scope": {"competitionId": _to_text(competitionId), "seasonId": _to_text(seasonId)},
                "totalMatches": 0,
                "metrics": {
                    "scores": {"count": 0, "percentage": None, "status": "not_available"},
                    "events": {"count": 0, "percentage": None, "status": "not_available"},
                    "lineups": {"count": 0, "percentage": None, "status": "not_available"},
                    "playerStats": {"count": 0, "percentage": None, "status": "not_available"},
                    "teamStats": {"count": 0, "percentage": None, "status": "not_available"},
                    "coachAssignment": {"count": 0, "percentage": None, "status": "not_available"},
                },
                "hiddenMetrics": [
                    {"metric": "xg", "reason": "Advanced statistics (xG, passes) are only available for StatBomb-covered matches."},
                    {"metric": "passes", "reason": "Advanced statistics (xG, passes) are only available for StatBomb-covered matches."},
                    {"metric": "rating", "reason": "Rating data is only available for StatBomb-covered matches."},
                ],
                "enabledMetrics": [],
            },
            request_id=_request_id(request),
            coverage=_not_available_coverage("Overall coverage report"),
        )

    row = rows[0]
    total = _to_int(row.get("total_matches"))

    def _metric_status(count: int, total: int) -> dict[str, Any]:
        pct = round((count / total) * 100, 2) if total > 0 else 0.0
        if pct >= 95:
            status = "complete"
        elif pct >= 60:
            status = "partial"
        elif total > 0:
            status = "insufficient"
        else:
            status = "not_available"
        return {"count": count, "percentage": pct, "status": status}

    metrics = {
        "scores": _metric_status(total, total),
        "events": _metric_status(_to_int(row.get("matches_with_events")), total),
        "lineups": _metric_status(_to_int(row.get("matches_with_lineups")), total),
        "playerStats": _metric_status(_to_int(row.get("matches_with_player_stats")), total),
        "teamStats": _metric_status(_to_int(row.get("matches_with_team_stats")), total),
        "coachAssignment": _metric_status(_to_int(row.get("matches_with_coach_assignment")), total),
    }

    enabled = []
    for mk, mv in metrics.items():
        if mv["status"] in ("complete", "partial"):
            metric_map = {
                "scores": ["matches", "goals", "avg_goals"],
                "events": ["home_wins", "away_wins", "draws"],
                "lineups": [],
                "playerStats": [],
                "teamStats": ["points", "goals_for", "goals_against", "goal_diff", "points_per_match", "win_rate", "ppg"],
                "coachAssignment": ["coach_best_ppm", "coach_most_matches"],
            }
            enabled.extend(metric_map.get(mk, []))

    hidden = [
        {"metric": "xg", "reason": "Advanced statistics (xG, passes) are only available for StatBomb-covered matches."},
        {"metric": "passes", "reason": "Advanced statistics (xG, passes) are only available for StatBomb-covered matches."},
        {"metric": "rating", "reason": "Rating data is only available for StatBomb-covered matches."},
    ]

    coverage_pct = metrics["scores"]["percentage"]
    coverage_status = metrics["scores"]["status"]
    coverage = build_coverage_from_counts(
        total, total, "Overall coverage report",
    )

    return build_api_response(
        {
            "scope": {"competitionId": _to_text(competitionId), "seasonId": _to_text(seasonId)},
            "totalMatches": total,
            "metrics": metrics,
            "hiddenMetrics": hidden,
            "enabledMetrics": sorted(set(enabled)),
        },
        request_id=_request_id(request),
        coverage=coverage,
    )


def _row_label(rows: list[dict[str, Any]] | None, fallback: str) -> str:
    if rows and rows[0].get("team_name"):
        return str(rows[0]["team_name"])
    return fallback
