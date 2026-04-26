from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from fastapi import APIRouter, Request

from ..core.context_registry import get_canonical_competition
from ..core.contracts import build_api_response, build_coverage_from_counts
from ..core.errors import AppError
from ..core.filters import GlobalFilters, VenueFilter, validate_and_build_global_filters
from ..db.client import db_client

router = APIRouter(prefix="/api/v1/standings", tags=["standings"])


@dataclass(frozen=True)
class StandingsScope:
    competition_id: int
    season_id: int
    provider_season_id: int
    competition_name: str
    competition_key: str | None
    season_label: str | None


@dataclass(frozen=True)
class StandingsStage:
    stage_id: int
    stage_name: str | None
    stage_format: str | None
    expected_teams: int


@dataclass(frozen=True)
class StandingsGroup:
    group_id: str
    group_name: str | None
    group_order: int | None
    expected_teams: int


@dataclass(frozen=True)
class StandingsRound:
    round_id: int
    provider_round_id: int
    round_name: str | None
    label: str
    starting_at: str | None
    ending_at: str | None
    is_current: bool


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _empty_standings_coverage() -> dict[str, Any]:
    return {
        "status": "empty",
        "percentage": 0,
        "label": "Standings coverage",
    }


def _require_standings_context(filters: GlobalFilters) -> None:
    missing_fields: list[str] = []
    if filters.competition_id is None:
        missing_fields.append("competitionId")
    if filters.season_id is None:
        missing_fields.append("seasonId")

    if missing_fields:
        raise AppError(
            message="Canonical standings require 'competitionId' and 'seasonId'.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"missing": missing_fields},
        )


def _parse_optional_int_param(raw_value: str | None, *, field_name: str) -> int | None:
    if raw_value is None:
        return None

    normalized_value = raw_value.strip()
    if normalized_value == "":
        return None

    try:
        return int(normalized_value)
    except ValueError as exc:
        raise AppError(
            message=f"Invalid value for '{field_name}'. Expected integer.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={field_name: raw_value},
        ) from exc


def _display_round_label(round_name: str | None, round_id: int) -> str:
    normalized_round_name = (round_name or "").strip()
    if normalized_round_name.isdigit():
        return f"Rodada {normalized_round_name}"
    if normalized_round_name:
        return normalized_round_name
    return f"Rodada {round_id}"


def _format_season_label(season_label: str | None, season_id: int) -> str:
    normalized_label = (season_label or "").strip()
    split_year_match = re.fullmatch(r"(\d{4})_(\d{2})", normalized_label)

    if split_year_match:
        return f"{split_year_match.group(1)}/20{split_year_match.group(2)}"

    if normalized_label:
        return normalized_label

    return str(season_id)


def _serialize_round(round_data: StandingsRound | None) -> dict[str, Any] | None:
    if round_data is None:
        return None

    return {
        "roundId": str(round_data.round_id),
        "providerRoundId": str(round_data.provider_round_id),
        "roundName": round_data.round_name,
        "label": round_data.label,
        "startingAt": round_data.starting_at,
        "endingAt": round_data.ending_at,
        "isCurrent": round_data.is_current,
    }


def _serialize_stage(
    stage: StandingsStage | None,
    *,
    expected_teams: int | None = None,
) -> dict[str, Any] | None:
    if stage is None:
        return None

    return {
        "stageId": str(stage.stage_id),
        "stageName": stage.stage_name,
        "stageFormat": stage.stage_format,
        "expectedTeams": stage.expected_teams if expected_teams is None else expected_teams,
    }


def _serialize_group(group: StandingsGroup | None) -> dict[str, Any] | None:
    if group is None:
        return None

    return {
        "groupId": group.group_id,
        "groupName": group.group_name,
        "groupOrder": group.group_order,
        "expectedTeams": group.expected_teams,
    }


def _serialize_scope(
    filters: GlobalFilters,
    scope: StandingsScope | None,
) -> dict[str, Any]:
    canonical_competition = get_canonical_competition(filters.competition_id)
    competition_name = (
        scope.competition_name
        if scope and scope.competition_name.strip()
        else canonical_competition.default_name if canonical_competition else str(filters.competition_id)
    )
    competition_key = (
        scope.competition_key
        if scope and scope.competition_key
        else canonical_competition.competition_key if canonical_competition else None
    )

    return {
        "competitionId": str(filters.competition_id),
        "competitionKey": competition_key,
        "competitionName": competition_name,
        "seasonId": str(filters.season_id),
        "seasonLabel": _format_season_label(scope.season_label if scope else None, int(filters.season_id)),
        "providerSeasonId": str(scope.provider_season_id) if scope else None,
    }


def _empty_standings_payload(filters: GlobalFilters, scope: StandingsScope | None = None) -> dict[str, Any]:
    return {
        "competition": _serialize_scope(filters, scope),
        "stage": None,
        "group": None,
        "selectedRound": None,
        "currentRound": None,
        "rounds": [],
        "rows": [],
        "updatedAt": None,
    }


def _resolve_standings_scope(filters: GlobalFilters) -> StandingsScope | None:
    row = db_client.fetch_one(
        """
        select
            rf.league_id,
            rf.season,
            max(rf.provider_season_id)::bigint as provider_season_id,
            coalesce(max(rf.league_name), max(dc.league_name)) as competition_name,
            max(nullif(trim(rf.competition_key), '')) as competition_key,
            max(nullif(trim(rf.season_label), '')) as season_label
        from raw.fixtures rf
        left join mart.dim_competition dc
          on dc.league_id = rf.league_id
        where rf.league_id = any(%s)
          and rf.season = %s
        group by rf.league_id, rf.season
        limit 1;
        """,
        [list(filters.competition_ids), filters.season_id],
    )

    if row is None or row.get("provider_season_id") is None:
        return None

    canonical_competition = get_canonical_competition(filters.competition_id)
    fallback_name = canonical_competition.default_name if canonical_competition else str(filters.competition_id)

    return StandingsScope(
        competition_id=int(row["league_id"]),
        season_id=int(row["season"]),
        provider_season_id=int(row["provider_season_id"]),
        competition_name=str(row.get("competition_name") or fallback_name),
        competition_key=row.get("competition_key"),
        season_label=row.get("season_label"),
    )


def _resolve_standings_stage(
    scope: StandingsScope,
    requested_stage_id: int | None = None,
) -> StandingsStage | None:
    params: list[Any] = [scope.competition_id, scope.provider_season_id]
    stage_filter_sql = ""
    if requested_stage_id is not None:
        stage_filter_sql = "  and ss.stage_id = %s\n"
        params.append(requested_stage_id)

    row = db_client.fetch_one(
        f"""
        select
            ss.stage_id,
            max(cs.stage_name) as stage_name,
            max(ds.stage_format) as stage_format,
            count(distinct ss.team_id)::int as expected_teams
        from raw.standings_snapshots ss
        left join raw.competition_stages cs
          on cs.league_id = ss.league_id
         and cs.provider_season_id = ss.provider_season_id
         and cs.stage_id = ss.stage_id
        left join mart.dim_stage ds
          on ds.league_id = ss.league_id
         and ds.provider_season_id = ss.provider_season_id
         and ds.stage_id = ss.stage_id
        where ss.league_id = %s
          and ss.provider_season_id = %s
{stage_filter_sql}        group by ss.stage_id
        order by
            count(distinct ss.team_id) desc,
            max(ss.updated_at) desc nulls last,
            ss.stage_id asc
        limit 1;
        """,
        params,
    )

    if row is None:
        return None

    return StandingsStage(
        stage_id=int(row["stage_id"]),
        stage_name=row.get("stage_name"),
        stage_format=row.get("stage_format"),
        expected_teams=int(row.get("expected_teams") or 0),
    )


def _fetch_stage_rounds(scope: StandingsScope, stage: StandingsStage) -> list[StandingsRound]:
    rows = db_client.fetch_all(
        """
        with ordered_rounds as (
            select
                cr.round_id,
                cr.round_name,
                coalesce(cr.is_current, false) as is_current,
                cr.starting_at,
                cr.ending_at,
                coalesce(
                    nullif(substring(coalesce(cr.round_name, '') from '(\\d+)'), '')::int,
                    row_number() over (order by cr.starting_at nulls last, cr.round_id asc)::int
                ) as round_order
            from raw.competition_rounds cr
            where cr.league_id = %s
              and cr.provider_season_id = %s
              and cr.stage_id = %s
        )
        select
            round_id,
            round_name,
            is_current,
            starting_at,
            ending_at,
            round_order
        from ordered_rounds
        order by round_order asc, starting_at asc nulls last, round_id asc;
        """,
        [scope.competition_id, scope.provider_season_id, stage.stage_id],
    )

    return [
        StandingsRound(
            round_id=int(row["round_order"]),
            provider_round_id=int(row["round_id"]),
            round_name=row.get("round_name"),
            label=_display_round_label(row.get("round_name"), int(row["round_order"])),
            starting_at=row.get("starting_at"),
            ending_at=row.get("ending_at"),
            is_current=bool(row.get("is_current")),
        )
        for row in rows
    ]


def _resolve_group(
    scope: StandingsScope,
    stage: StandingsStage,
    group_id: str,
) -> StandingsGroup | None:
    row = db_client.fetch_one(
        """
        select
            dg.group_id,
            dg.group_name,
            dg.group_order,
            count(distinct fgs.team_id)::int as expected_teams
        from mart.dim_group dg
        left join mart.fact_group_standings fgs
          on fgs.competition_key = dg.competition_key
         and fgs.season_label = dg.season_label
         and fgs.stage_id = dg.stage_id
         and fgs.group_id = dg.group_id
        where dg.competition_key = %s
          and dg.season_label = %s
          and dg.stage_id = %s
          and dg.group_id = %s
        group by dg.group_id, dg.group_name, dg.group_order
        limit 1;
        """,
        [scope.competition_key, scope.season_label, stage.stage_id, group_id],
    )

    if row is None:
        return None

    return StandingsGroup(
        group_id=row["group_id"],
        group_name=row.get("group_name"),
        group_order=int(row["group_order"]) if row.get("group_order") is not None else None,
        expected_teams=int(row.get("expected_teams") or 0),
    )


def _fetch_group_rounds(
    scope: StandingsScope,
    stage: StandingsStage,
    group: StandingsGroup,
) -> list[StandingsRound]:
    rows = db_client.fetch_all(
        """
        select distinct
            dr.round_key,
            dr.round_id,
            dr.round_name,
            dr.starting_at,
            dr.ending_at,
            coalesce(dr.is_current, false) as is_current
        from mart.dim_round dr
        inner join mart.fact_group_standings fgs
          on fgs.competition_key = %s
         and fgs.season_label = %s
         and fgs.stage_id = %s
         and fgs.group_id = %s
         and fgs.round_id = dr.round_id
        where dr.stage_id = %s
        order by dr.round_key asc, dr.round_id asc;
        """,
        [scope.competition_key, scope.season_label, stage.stage_id, group.group_id, stage.stage_id],
    )

    return [
        StandingsRound(
            round_id=int(row["round_key"]),
            provider_round_id=int(row["round_id"]),
            round_name=row.get("round_name"),
            label=_display_round_label(row.get("round_name"), int(row["round_key"])),
            starting_at=row.get("starting_at"),
            ending_at=row.get("ending_at"),
            is_current=bool(row.get("is_current")),
        )
        for row in rows
    ]


def _resolve_selected_round(
    rounds: list[StandingsRound],
    requested_round_id: int | None,
) -> tuple[StandingsRound | None, StandingsRound | None]:
    if not rounds:
        return None, None

    current_round = next((round_data for round_data in rounds if round_data.is_current), rounds[-1])

    if requested_round_id is None:
        return current_round, current_round

    selected_round = next(
        (round_data for round_data in rounds if round_data.round_id == requested_round_id),
        None,
    )
    if selected_round is None:
        raise AppError(
            message="Invalid value for 'roundId'. Requested round does not exist in standings context.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"roundId": requested_round_id},
        )

    return selected_round, current_round


def _fetch_standings_rows(
    scope: StandingsScope,
    stage: StandingsStage,
    selected_round: StandingsRound,
) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with stage_rounds as (
            select
                cr.round_id,
                coalesce(
                    nullif(substring(coalesce(cr.round_name, '') from '(\\d+)'), '')::int,
                    row_number() over (order by cr.starting_at nulls last, cr.round_id asc)::int
                ) as round_order
            from raw.competition_rounds cr
            where cr.league_id = %s
              and cr.provider_season_id = %s
              and cr.stage_id = %s
        ),
        standings_teams as (
            select distinct ss.team_id
            from raw.standings_snapshots ss
            where ss.league_id = %s
              and ss.provider_season_id = %s
              and ss.stage_id = %s
        ),
        team_names as (
            select distinct on (team_id)
                team_id,
                team_name
            from (
                select
                    f.home_team_id as team_id,
                    f.home_team_name as team_name,
                    f.date_utc as observed_at
                from raw.fixtures f
                where f.league_id = %s
                  and f.season = %s
                  and f.provider_season_id = %s
                  and f.stage_id = %s

                union all

                select
                    f.away_team_id as team_id,
                    f.away_team_name as team_name,
                    f.date_utc as observed_at
                from raw.fixtures f
                where f.league_id = %s
                  and f.season = %s
                  and f.provider_season_id = %s
                  and f.stage_id = %s
            ) observed_teams
            order by team_id, observed_at desc nulls last, team_name asc
        ),
        scoped_matches as (
            select
                f.fixture_id,
                f.home_team_id,
                f.away_team_id,
                f.home_goals,
                f.away_goals,
                sr.round_order
            from raw.fixtures f
            inner join stage_rounds sr
              on sr.round_id = f.round_id
            where f.league_id = %s
              and f.season = %s
              and f.provider_season_id = %s
              and f.stage_id = %s
              and f.home_goals is not null
              and f.away_goals is not null
              and sr.round_order <= %s
        ),
        standings_base as (
            select
                sm.home_team_id as team_id,
                1 as matches_played,
                case when sm.home_goals > sm.away_goals then 1 else 0 end as wins,
                case when sm.home_goals = sm.away_goals then 1 else 0 end as draws,
                case when sm.home_goals < sm.away_goals then 1 else 0 end as losses,
                sm.home_goals as goals_for,
                sm.away_goals as goals_against,
                sm.home_goals - sm.away_goals as goal_diff,
                case
                    when sm.home_goals > sm.away_goals then 3
                    when sm.home_goals = sm.away_goals then 1
                    else 0
                end as points
            from scoped_matches sm

            union all

            select
                sm.away_team_id as team_id,
                1 as matches_played,
                case when sm.away_goals > sm.home_goals then 1 else 0 end as wins,
                case when sm.away_goals = sm.home_goals then 1 else 0 end as draws,
                case when sm.away_goals < sm.home_goals then 1 else 0 end as losses,
                sm.away_goals as goals_for,
                sm.home_goals as goals_against,
                sm.away_goals - sm.home_goals as goal_diff,
                case
                    when sm.away_goals > sm.home_goals then 3
                    when sm.away_goals = sm.home_goals then 1
                    else 0
                end as points
            from scoped_matches sm
        ),
        aggregated as (
            select
                st.team_id,
                coalesce(tn.team_name, dt.team_name, st.team_id::text) as team_name,
                coalesce(sum(sb.matches_played), 0)::int as matches_played,
                coalesce(sum(sb.wins), 0)::int as wins,
                coalesce(sum(sb.draws), 0)::int as draws,
                coalesce(sum(sb.losses), 0)::int as losses,
                coalesce(sum(sb.goals_for), 0)::int as goals_for,
                coalesce(sum(sb.goals_against), 0)::int as goals_against,
                coalesce(sum(sb.goal_diff), 0)::int as goal_diff,
                coalesce(sum(sb.points), 0)::int as points
            from standings_teams st
            left join standings_base sb
              on sb.team_id = st.team_id
            left join team_names tn
              on tn.team_id = st.team_id
            left join mart.dim_team dt
              on dt.team_id = st.team_id
            group by st.team_id, tn.team_name, dt.team_name
        ),
        ranked as (
            select
                row_number() over (
                    order by
                        a.points desc,
                        a.goal_diff desc,
                        a.goals_for desc,
                        a.team_name asc,
                        a.team_id asc
                )::int as position,
                a.*
            from aggregated a
        )
        select
            position,
            team_id::text as team_id,
            team_name,
            matches_played,
            wins,
            draws,
            losses,
            goals_for,
            goals_against,
            goal_diff,
            points
        from ranked
        order by position asc;
        """,
        [
            scope.competition_id,
            scope.provider_season_id,
            stage.stage_id,
            scope.competition_id,
            scope.provider_season_id,
            stage.stage_id,
            scope.competition_id,
            scope.season_id,
            scope.provider_season_id,
            stage.stage_id,
            scope.competition_id,
            scope.season_id,
            scope.provider_season_id,
            stage.stage_id,
            scope.competition_id,
            scope.season_id,
            scope.provider_season_id,
            stage.stage_id,
            selected_round.round_id,
        ],
    )


def _fetch_group_standings_rows(
    scope: StandingsScope,
    stage: StandingsStage,
    group: StandingsGroup,
    selected_round: StandingsRound,
) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        select
            fgs.position,
            fgs.team_id::text as team_id,
            coalesce(dt.team_name, fgs.team_id::text) as team_name,
            fgs.games_played,
            fgs.won,
            fgs.draw,
            fgs.lost,
            fgs.goals_for,
            fgs.goals_against,
            fgs.goal_diff,
            fgs.points
        from mart.fact_group_standings fgs
        left join mart.dim_team dt
          on dt.team_sk = fgs.team_sk
        where fgs.competition_key = %s
          and fgs.season_label = %s
          and fgs.stage_id = %s
          and fgs.group_id = %s
          and fgs.round_key = %s
        order by fgs.position asc, dt.team_name asc nulls last, fgs.team_id asc;
        """,
        [
            scope.competition_key,
            scope.season_label,
            stage.stage_id,
            group.group_id,
            selected_round.round_id,
        ],
    )


@router.get("")
def get_standings(
    request: Request,
    competitionId: str | None = None,
    seasonId: str | None = None,
    roundId: str | None = None,
    stageId: str | None = None,
    groupId: str | None = None,
) -> dict[str, Any]:
    requested_stage_id = _parse_optional_int_param(stageId, field_name="stageId")
    normalized_group_id = groupId.strip() if groupId is not None else None
    if normalized_group_id == "":
        normalized_group_id = None

    filters = validate_and_build_global_filters(
        competition_id=competitionId,
        season_id=seasonId,
        round_id=roundId,
        venue=VenueFilter.all,
        last_n=None,
        date_start=None,
        date_end=None,
        date_range_start=None,
        date_range_end=None,
    )
    _require_standings_context(filters)

    scope = _resolve_standings_scope(filters)
    if scope is None:
        return build_api_response(
            _empty_standings_payload(filters),
            request_id=_request_id(request),
            coverage=_empty_standings_coverage(),
        )

    stage = _resolve_standings_stage(scope, requested_stage_id)
    if stage is None:
        if requested_stage_id is not None:
            raise AppError(
                message="Invalid value for 'stageId'. Requested stage does not exist in standings context.",
                code="INVALID_QUERY_PARAM",
                status=400,
                details={"stageId": requested_stage_id},
            )

        return build_api_response(
            _empty_standings_payload(filters, scope),
            request_id=_request_id(request),
            coverage=_empty_standings_coverage(),
        )

    if normalized_group_id is not None and stage.stage_format != "group_table":
        raise AppError(
            message="'groupId' can only be used when the resolved stage has 'stageFormat=group_table'.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={
                "stageId": stage.stage_id,
                "stageFormat": stage.stage_format,
                "groupId": normalized_group_id,
            },
        )

    group: StandingsGroup | None = None
    if stage.stage_format == "group_table":
        if normalized_group_id is None:
            raise AppError(
                message="'groupId' is required when the resolved standings stage is grouped.",
                code="INVALID_QUERY_PARAM",
                status=400,
                details={
                    "stageId": stage.stage_id,
                    "stageFormat": stage.stage_format,
                    "required": ["groupId"],
                },
            )

        group = _resolve_group(scope, stage, normalized_group_id)
        if group is None:
            raise AppError(
                message="Invalid value for 'groupId'. Requested group does not exist in standings context.",
                code="INVALID_QUERY_PARAM",
                status=400,
                details={
                    "stageId": stage.stage_id,
                    "groupId": normalized_group_id,
                },
            )
        rounds = _fetch_group_rounds(scope, stage, group)
    else:
        rounds = _fetch_stage_rounds(scope, stage)

    selected_round, current_round = _resolve_selected_round(rounds, filters.round_id)
    expected_teams = group.expected_teams if group is not None else stage.expected_teams

    if selected_round is None:
        return build_api_response(
            {
                **_empty_standings_payload(filters, scope),
                "stage": _serialize_stage(stage, expected_teams=expected_teams),
                "group": _serialize_group(group),
            },
            request_id=_request_id(request),
            coverage=_empty_standings_coverage(),
        )

    rows = (
        _fetch_group_standings_rows(scope, stage, group, selected_round)
        if group is not None
        else _fetch_standings_rows(scope, stage, selected_round)
    )
    coverage = build_coverage_from_counts(
        len(rows),
        expected_teams,
        "Standings coverage",
    )

    data = {
        "competition": _serialize_scope(filters, scope),
        "stage": _serialize_stage(stage, expected_teams=expected_teams),
        "group": _serialize_group(group),
        "selectedRound": _serialize_round(selected_round),
        "currentRound": _serialize_round(current_round),
        "rounds": [_serialize_round(round_data) for round_data in rounds],
        "rows": [
            {
                "position": int(row["position"]),
                "teamId": row["team_id"],
                "teamName": row.get("team_name"),
                "matchesPlayed": int(row.get("matches_played") or row.get("games_played") or 0),
                "wins": int(row.get("wins") or row.get("won") or 0),
                "draws": int(row.get("draws") or row.get("draw") or 0),
                "losses": int(row.get("losses") or row.get("lost") or 0),
                "goalsFor": int(row.get("goals_for") or 0),
                "goalsAgainst": int(row.get("goals_against") or 0),
                "goalDiff": int(row.get("goal_diff") or 0),
                "points": int(row.get("points") or 0),
            }
            for row in rows
        ],
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=coverage,
    )
