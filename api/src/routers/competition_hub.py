from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Any

from fastapi import APIRouter, Request

from ..core.context_registry import get_canonical_competition_by_key
from ..core.contracts import build_api_response, build_coverage_from_counts
from ..core.errors import AppError
from ..db.client import db_client

router = APIRouter(tags=["competition-hub"])

COMPETITION_KEY_ALIASES = {
    "serie_a_italy": "serie_a_it",
}

PUBLIC_COMPETITION_KEY_ALIASES = {
    internal_key: public_key for public_key, internal_key in COMPETITION_KEY_ALIASES.items()
}


@dataclass(frozen=True)
class CompetitionSeasonScope:
    competition_key: str
    competition_name: str
    competition_id: int | None
    season_label: str
    season_id: int | None
    provider_season_id: int | None
    format_family: str
    season_format_code: str
    participant_scope: str
    group_ranking_rule_code: str | None
    tie_rule_code: str | None


@dataclass(frozen=True)
class CompetitionStage:
    stage_id: int
    stage_name: str | None
    stage_code: str | None
    stage_format: str | None
    stage_order: int | None
    standings_context_mode: str | None
    bracket_context_mode: str | None
    group_mode: str | None
    elimination_mode: str | None
    is_current: bool


@dataclass(frozen=True)
class CompetitionGroup:
    group_id: str
    group_name: str | None
    group_order: int | None
    expected_teams: int


@dataclass(frozen=True)
class CompetitionRound:
    round_id: int
    provider_round_id: int
    round_name: str | None
    label: str
    starting_at: str | None
    ending_at: str | None
    is_current: bool


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _normalize_competition_key(value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = value.strip()
    if normalized_value == "":
        return None

    return COMPETITION_KEY_ALIASES.get(normalized_value, normalized_value)


def _public_competition_key(value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = value.strip()
    if normalized_value == "":
        return None

    return PUBLIC_COMPETITION_KEY_ALIASES.get(normalized_value, normalized_value)


def _resolve_canonical_competition(competition_key: str | None):
    normalized_competition_key = _normalize_competition_key(competition_key)

    if normalized_competition_key is None:
        return None

    public_competition_key = _public_competition_key(normalized_competition_key)

    return get_canonical_competition_by_key(public_competition_key) or get_canonical_competition_by_key(
        normalized_competition_key
    )


def _normalize_season_label(value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = value.strip()
    if normalized_value == "":
        return None

    split_year_match = re.fullmatch(r"(\d{4})/(\d{4})", normalized_value)
    if split_year_match:
        return f"{split_year_match.group(1)}_{split_year_match.group(2)[-2:]}"

    return normalized_value


def _format_season_label(season_label: str | None) -> str | None:
    if season_label is None:
        return None

    normalized_label = season_label.strip()
    if normalized_label == "":
        return None

    split_year_match = re.fullmatch(r"(\d{4})_(\d{2})", normalized_label)
    if split_year_match:
        return f"{split_year_match.group(1)}/20{split_year_match.group(2)}"

    return normalized_label


def _display_round_label(round_name: str | None, round_id: int) -> str:
    normalized_round_name = (round_name or "").strip()
    if normalized_round_name.isdigit():
        return f"Rodada {normalized_round_name}"
    if normalized_round_name:
        return normalized_round_name
    return f"Rodada {round_id}"


def _parse_required_int(raw_value: str | None, *, field_name: str) -> int:
    if raw_value is None or raw_value.strip() == "":
        raise AppError(
            message=f"'{field_name}' is required.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"missing": [field_name]},
        )

    try:
        return int(raw_value)
    except ValueError as exc:
        raise AppError(
            message=f"Invalid value for '{field_name}'. Expected integer.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={field_name: raw_value},
        ) from exc


def _parse_optional_int(raw_value: str | None, *, field_name: str) -> int | None:
    if raw_value is None or raw_value.strip() == "":
        return None

    try:
        return int(raw_value)
    except ValueError as exc:
        raise AppError(
            message=f"Invalid value for '{field_name}'. Expected integer.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={field_name: raw_value},
        ) from exc


def _require_competition_scope(
    competition_key: str | None,
    season_label: str | None,
) -> tuple[str, str]:
    normalized_competition_key = _normalize_competition_key(competition_key)
    normalized_season_label = _normalize_season_label(season_label)

    missing_fields: list[str] = []
    if normalized_competition_key is None:
        missing_fields.append("competitionKey")
    if normalized_season_label is None:
        missing_fields.append("seasonLabel")

    if missing_fields:
        raise AppError(
            message="Competition hub routes require 'competitionKey' and 'seasonLabel'.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"missing": missing_fields},
        )

    return normalized_competition_key, normalized_season_label


def _fetch_stage_scope_row(
    competition_key: str,
    season_label: str,
) -> dict[str, Any] | None:
    return db_client.fetch_one(
        """
        select
            ds.competition_key,
            ds.season_label,
            max(ds.league_id)::int as competition_id,
            max(ds.season_id)::int as season_id,
            max(ds.provider_season_id)::bigint as provider_season_id,
            max(dc.league_name) as competition_name
        from mart.dim_stage ds
        left join mart.dim_competition dc
          on dc.league_id = ds.league_id
        where ds.competition_key = %s
          and ds.season_label = %s
        group by ds.competition_key, ds.season_label
        limit 1;
        """,
        [competition_key, season_label],
    )


def _resolve_competition_scope(
    competition_key: str,
    season_label: str,
) -> CompetitionSeasonScope | None:
    row = db_client.fetch_one(
        """
        with scoped_config as (
            select
                csc.competition_key,
                csc.season_label,
                csc.format_family,
                csc.season_format_code,
                csc.participant_scope,
                csc.group_ranking_rule_code,
                csc.tie_rule_code
            from mart_control.competition_season_config csc
            where csc.competition_key = %s
              and csc.season_label = %s
        ),
        stage_scope as (
            select
                ds.competition_key,
                ds.season_label,
                max(ds.league_id)::int as competition_id,
                max(ds.season_id)::int as season_id,
                max(ds.provider_season_id)::bigint as provider_season_id,
                max(dc.league_name) as competition_name
            from mart.dim_stage ds
            left join mart.dim_competition dc
              on dc.league_id = ds.league_id
            where ds.competition_key = %s
              and ds.season_label = %s
            group by ds.competition_key, ds.season_label
        )
        select
            cfg.competition_key,
            cfg.season_label,
            cfg.format_family,
            cfg.season_format_code,
            cfg.participant_scope,
            cfg.group_ranking_rule_code,
            cfg.tie_rule_code,
            ss.competition_id,
            ss.season_id,
            ss.provider_season_id,
            ss.competition_name
        from scoped_config cfg
        left join stage_scope ss
          on ss.competition_key = cfg.competition_key
         and ss.season_label = cfg.season_label
        limit 1;
        """,
        [competition_key, season_label, competition_key, season_label],
    )

    if row is None:
        stage_scope_row = _fetch_stage_scope_row(competition_key, season_label)

        if stage_scope_row is None:
            return None

        row = {
            "competition_key": stage_scope_row["competition_key"],
            "competition_name": stage_scope_row.get("competition_name"),
            "competition_id": stage_scope_row.get("competition_id"),
            "season_label": stage_scope_row["season_label"],
            "season_id": stage_scope_row.get("season_id"),
            "provider_season_id": stage_scope_row.get("provider_season_id"),
            "format_family": "unknown",
            "season_format_code": "unconfigured",
            "participant_scope": "unknown",
            "group_ranking_rule_code": None,
            "tie_rule_code": None,
        }

    canonical_competition = _resolve_canonical_competition(competition_key)
    fallback_competition_name = canonical_competition.default_name if canonical_competition else competition_key

    return CompetitionSeasonScope(
        competition_key=row["competition_key"],
        competition_name=str(row.get("competition_name") or fallback_competition_name),
        competition_id=int(row["competition_id"]) if row.get("competition_id") is not None else None,
        season_label=row["season_label"],
        season_id=int(row["season_id"]) if row.get("season_id") is not None else None,
        provider_season_id=int(row["provider_season_id"]) if row.get("provider_season_id") is not None else None,
        format_family=row["format_family"],
        season_format_code=row["season_format_code"],
        participant_scope=row["participant_scope"],
        group_ranking_rule_code=row.get("group_ranking_rule_code"),
        tie_rule_code=row.get("tie_rule_code"),
    )

def _serialize_scope(scope: CompetitionSeasonScope) -> dict[str, Any]:
    return {
        "competitionId": str(scope.competition_id) if scope.competition_id is not None else None,
        "competitionKey": _public_competition_key(scope.competition_key),
        "competitionName": scope.competition_name,
        "seasonId": str(scope.season_id) if scope.season_id is not None else None,
        "seasonLabel": _format_season_label(scope.season_label),
        "providerSeasonId": str(scope.provider_season_id) if scope.provider_season_id is not None else None,
        "formatFamily": scope.format_family,
        "seasonFormatCode": scope.season_format_code,
        "participantScope": scope.participant_scope,
        "groupRankingRuleCode": scope.group_ranking_rule_code,
        "tieRuleCode": scope.tie_rule_code,
    }


def _fetch_competition_stages(
    competition_key: str,
    season_label: str,
) -> list[CompetitionStage]:
    rows = db_client.fetch_all(
        """
        select
            ds.stage_id,
            ds.stage_name,
            ds.stage_code,
            ds.stage_format,
            ds.sort_order,
            ds.standings_context_mode,
            ds.bracket_context_mode,
            ds.group_mode,
            ds.elimination_mode,
            coalesce(ds.is_current, false) as is_current
        from mart.dim_stage ds
        where ds.competition_key = %s
          and ds.season_label = %s
        order by ds.sort_order asc nulls last, ds.stage_id asc;
        """,
        [competition_key, season_label],
    )

    return [
        CompetitionStage(
            stage_id=int(row["stage_id"]),
            stage_name=row.get("stage_name"),
            stage_code=row.get("stage_code"),
            stage_format=row.get("stage_format"),
            stage_order=int(row["sort_order"]) if row.get("sort_order") is not None else None,
            standings_context_mode=row.get("standings_context_mode"),
            bracket_context_mode=row.get("bracket_context_mode"),
            group_mode=row.get("group_mode"),
            elimination_mode=row.get("elimination_mode"),
            is_current=bool(row.get("is_current")),
        )
        for row in rows
    ]


def _fetch_stage_groups(
    competition_key: str,
    season_label: str,
) -> dict[int, list[CompetitionGroup]]:
    rows = db_client.fetch_all(
        """
        select
            dg.stage_id,
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
        group by
            dg.stage_id,
            dg.group_id,
            dg.group_name,
            dg.group_order
        order by dg.stage_id asc, dg.group_order asc nulls last, dg.group_name asc nulls last;
        """,
        [competition_key, season_label],
    )

    grouped: dict[int, list[CompetitionGroup]] = {}
    for row in rows:
        grouped.setdefault(int(row["stage_id"]), []).append(
            CompetitionGroup(
                group_id=row["group_id"],
                group_name=row.get("group_name"),
                group_order=int(row["group_order"]) if row.get("group_order") is not None else None,
                expected_teams=int(row.get("expected_teams") or 0),
            )
        )
    return grouped


def _fetch_structure_transitions(
    competition_key: str,
    season_label: str,
) -> dict[int, list[dict[str, Any]]]:
    rows = db_client.fetch_all(
        """
        select
            csh.from_stage_id,
            csh.progression_scope,
            csh.position_from,
            csh.position_to,
            csh.tie_outcome,
            csh.progression_type,
            csh.to_stage_id,
            csh.to_stage_name,
            csh.to_stage_format,
            csh.to_stage_order
        from mart.competition_structure_hub csh
        where csh.competition_key = %s
          and csh.season_label = %s
        order by csh.from_stage_order asc, csh.rule_order asc;
        """,
        [competition_key, season_label],
    )

    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(int(row["from_stage_id"]), []).append(
            {
                "progressionScope": row.get("progression_scope"),
                "progressionType": row.get("progression_type"),
                "positionFrom": int(row["position_from"]) if row.get("position_from") is not None else None,
                "positionTo": int(row["position_to"]) if row.get("position_to") is not None else None,
                "tieOutcome": row.get("tie_outcome"),
                "toStageId": str(row["to_stage_id"]) if row.get("to_stage_id") is not None else None,
                "toStageName": row.get("to_stage_name"),
                "toStageFormat": row.get("to_stage_format"),
                "toStageOrder": int(row["to_stage_order"]) if row.get("to_stage_order") is not None else None,
            }
        )
    return grouped


def _resolve_stage(
    competition_key: str,
    season_label: str,
    stage_id: int,
) -> CompetitionStage | None:
    row = db_client.fetch_one(
        """
        select
            ds.stage_id,
            ds.stage_name,
            ds.stage_code,
            ds.stage_format,
            ds.sort_order,
            ds.standings_context_mode,
            ds.bracket_context_mode,
            ds.group_mode,
            ds.elimination_mode,
            coalesce(ds.is_current, false) as is_current
        from mart.dim_stage ds
        where ds.competition_key = %s
          and ds.season_label = %s
          and ds.stage_id = %s
        limit 1;
        """,
        [competition_key, season_label, stage_id],
    )

    if row is None:
        return None

    return CompetitionStage(
        stage_id=int(row["stage_id"]),
        stage_name=row.get("stage_name"),
        stage_code=row.get("stage_code"),
        stage_format=row.get("stage_format"),
        stage_order=int(row["sort_order"]) if row.get("sort_order") is not None else None,
        standings_context_mode=row.get("standings_context_mode"),
        bracket_context_mode=row.get("bracket_context_mode"),
        group_mode=row.get("group_mode"),
        elimination_mode=row.get("elimination_mode"),
        is_current=bool(row.get("is_current")),
    )


def _resolve_group(
    competition_key: str,
    season_label: str,
    stage_id: int,
    group_id: str,
) -> CompetitionGroup | None:
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
        [competition_key, season_label, stage_id, group_id],
    )

    if row is None:
        return None

    return CompetitionGroup(
        group_id=row["group_id"],
        group_name=row.get("group_name"),
        group_order=int(row["group_order"]) if row.get("group_order") is not None else None,
        expected_teams=int(row.get("expected_teams") or 0),
    )


def _fetch_group_rounds(
    competition_key: str,
    season_label: str,
    stage_id: int,
    group_id: str,
) -> list[CompetitionRound]:
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
        [competition_key, season_label, stage_id, group_id, stage_id],
    )

    return [
        CompetitionRound(
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
    rounds: list[CompetitionRound],
    requested_round_id: int | None,
) -> tuple[CompetitionRound | None, CompetitionRound | None]:
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


def _serialize_round(round_data: CompetitionRound | None) -> dict[str, Any] | None:
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


def _serialize_stage(stage: CompetitionStage, *, expected_teams: int | None = None) -> dict[str, Any]:
    return {
        "stageId": str(stage.stage_id),
        "stageName": stage.stage_name,
        "stageCode": stage.stage_code,
        "stageFormat": stage.stage_format,
        "stageOrder": stage.stage_order,
        "standingsContextMode": stage.standings_context_mode,
        "bracketContextMode": stage.bracket_context_mode,
        "groupMode": stage.group_mode,
        "eliminationMode": stage.elimination_mode,
        "isCurrent": stage.is_current,
        "expectedTeams": expected_teams,
    }


def _serialize_group(group: CompetitionGroup) -> dict[str, Any]:
    return {
        "groupId": group.group_id,
        "groupName": group.group_name,
        "groupOrder": group.group_order,
        "expectedTeams": group.expected_teams,
    }


def _fetch_group_standings_rows(
    competition_key: str,
    season_label: str,
    stage_id: int,
    group_id: str,
    round_key: int,
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
        [competition_key, season_label, stage_id, group_id, round_key],
    )


def _fetch_stage_ties(
    competition_key: str,
    season_label: str,
    stage_id: int,
) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        select
            ftr.tie_id,
            ftr.tie_order,
            ftr.home_side_team_id::text as home_team_id,
            ftr.home_side_team_name,
            ftr.away_side_team_id::text as away_team_id,
            ftr.away_side_team_name,
            ftr.match_count,
            ftr.first_leg_at,
            ftr.last_leg_at,
            ftr.home_side_goals,
            ftr.away_side_goals,
            ftr.winner_team_id::text as winner_team_id,
            case
                when ftr.winner_team_id = ftr.home_side_team_id then ftr.home_side_team_name
                when ftr.winner_team_id = ftr.away_side_team_id then ftr.away_side_team_name
                else null
            end as winner_team_name,
            ftr.resolution_type,
            ftr.has_extra_time_match,
            ftr.has_penalties_match,
            ftr.next_stage_id::text as next_stage_id,
            ftr.next_stage_name
        from mart.fact_tie_results ftr
        where ftr.competition_key = %s
          and ftr.season_label = %s
          and ftr.stage_id = %s
        order by ftr.tie_order asc, ftr.tie_id asc;
        """,
        [competition_key, season_label, stage_id],
    )


def _fetch_team_progression(
    competition_key: str,
    season_label: str,
    team_id: int,
) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        select
            sp.stage_progression_id,
            sp.team_id::text as team_id,
            coalesce(dt.team_name, sp.team_id::text) as team_name,
            sp.from_stage_id::text as from_stage_id,
            sp.from_stage_name,
            sp.from_stage_format,
            sp.from_stage_order,
            sp.to_stage_id::text as to_stage_id,
            sp.to_stage_name,
            sp.to_stage_format,
            sp.to_stage_order,
            sp.progression_scope,
            sp.progression_type,
            sp.source_position,
            sp.tie_outcome,
            sp.group_id,
            sp.group_name
        from mart.fact_stage_progression sp
        left join mart.dim_team dt
          on dt.team_id = sp.team_id
        where sp.competition_key = %s
          and sp.season_label = %s
          and sp.team_id = %s
        order by
            sp.from_stage_order asc,
            coalesce(sp.source_position, 0) asc,
            coalesce(sp.tie_outcome, '') asc,
            coalesce(sp.to_stage_order, 999) asc;
        """,
        [competition_key, season_label, team_id],
    )


def _fetch_competition_stage_analytics(
    competition_key: str,
    season_label: str,
) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with stage_catalog as (
            select
                ds.stage_id,
                ds.stage_name,
                ds.stage_code,
                ds.stage_format,
                ds.sort_order,
                coalesce(ds.is_current, false) as is_current
            from mart.dim_stage ds
            where ds.competition_key = %s
              and ds.season_label = %s
        ),
        stage_match_summary as (
            select
                fm.stage_id,
                count(distinct fm.match_id)::int as match_count,
                round(avg(fm.total_goals)::numeric, 2) as average_goals,
                sum(case when fm.home_goals > fm.away_goals then 1 else 0 end)::int as home_wins,
                sum(case when fm.home_goals = fm.away_goals then 1 else 0 end)::int as draws,
                sum(case when fm.home_goals < fm.away_goals then 1 else 0 end)::int as away_wins
            from mart.fact_matches fm
            where fm.competition_key = %s
              and fm.season_label = %s
            group by fm.stage_id
        ),
        stage_team_summary as (
            select
                stage_rows.stage_id,
                count(distinct stage_rows.team_id)::int as team_count
            from (
                select fm.stage_id, fm.home_team_id as team_id
                from mart.fact_matches fm
                where fm.competition_key = %s
                  and fm.season_label = %s
                  and fm.home_team_id is not null
                union all
                select fm.stage_id, fm.away_team_id as team_id
                from mart.fact_matches fm
                where fm.competition_key = %s
                  and fm.season_label = %s
                  and fm.away_team_id is not null
            ) stage_rows
            group by stage_rows.stage_id
        ),
        stage_group_summary as (
            select
                dg.stage_id,
                count(*)::int as group_count
            from mart.dim_group dg
            where dg.competition_key = %s
              and dg.season_label = %s
            group by dg.stage_id
        ),
        stage_tie_summary as (
            select
                ftr.stage_id,
                count(*)::int as tie_count,
                count(*) filter (where ftr.winner_team_id is not null)::int as resolved_ties,
                count(*) filter (where coalesce(ftr.is_inferred, false))::int as inferred_ties
            from mart.fact_tie_results ftr
            where ftr.competition_key = %s
              and ftr.season_label = %s
            group by ftr.stage_id
        )
        select
            sc.stage_id::text as stage_id,
            sc.stage_name,
            sc.stage_code,
            sc.stage_format,
            sc.sort_order,
            sc.is_current,
            coalesce(sms.match_count, 0) as match_count,
            coalesce(sts.team_count, 0) as team_count,
            coalesce(sgs.group_count, 0) as group_count,
            sms.average_goals,
            coalesce(sms.home_wins, 0) as home_wins,
            coalesce(sms.draws, 0) as draws,
            coalesce(sms.away_wins, 0) as away_wins,
            coalesce(stis.tie_count, 0) as tie_count,
            coalesce(stis.resolved_ties, 0) as resolved_ties,
            coalesce(stis.inferred_ties, 0) as inferred_ties
        from stage_catalog sc
        left join stage_match_summary sms
          on sms.stage_id = sc.stage_id
        left join stage_team_summary sts
          on sts.stage_id = sc.stage_id
        left join stage_group_summary sgs
          on sgs.stage_id = sc.stage_id
        left join stage_tie_summary stis
          on stis.stage_id = sc.stage_id
        order by sc.sort_order asc nulls last, sc.stage_id asc;
        """,
        [
            competition_key,
            season_label,
            competition_key,
            season_label,
            competition_key,
            season_label,
            competition_key,
            season_label,
            competition_key,
            season_label,
            competition_key,
            season_label,
        ],
    )


def _fetch_competition_season_comparisons(competition_key: str) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with season_match_summary as (
            select
                fm.competition_key,
                fm.season_label,
                count(distinct fm.match_id)::int as match_count,
                round(avg(fm.total_goals)::numeric, 2) as average_goals
            from mart.fact_matches fm
            where fm.competition_key = %s
            group by fm.competition_key, fm.season_label
        ),
        season_stage_summary as (
            select
                ds.competition_key,
                ds.season_label,
                count(distinct ds.stage_id)::int as stage_count,
                count(distinct ds.stage_id) filter (
                    where ds.stage_format in ('league_table', 'group_table')
                )::int as table_stage_count,
                count(distinct ds.stage_id) filter (
                    where ds.stage_format in ('knockout', 'qualification_knockout')
                )::int as knockout_stage_count
            from mart.dim_stage ds
            where ds.competition_key = %s
            group by ds.competition_key, ds.season_label
        ),
        season_group_summary as (
            select
                dg.competition_key,
                dg.season_label,
                count(*)::int as group_count
            from mart.dim_group dg
            where dg.competition_key = %s
            group by dg.competition_key, dg.season_label
        ),
        season_tie_summary as (
            select
                ftr.competition_key,
                ftr.season_label,
                count(*)::int as tie_count
            from mart.fact_tie_results ftr
            where ftr.competition_key = %s
            group by ftr.competition_key, ftr.season_label
        )
        select
            csc.season_label,
            csc.format_family,
            csc.season_format_code,
            csc.participant_scope,
            coalesce(sms.match_count, 0) as match_count,
            coalesce(sss.stage_count, 0) as stage_count,
            coalesce(sss.table_stage_count, 0) as table_stage_count,
            coalesce(sss.knockout_stage_count, 0) as knockout_stage_count,
            coalesce(sgs.group_count, 0) as group_count,
            coalesce(sts.tie_count, 0) as tie_count,
            sms.average_goals
        from mart_control.competition_season_config csc
        left join season_match_summary sms
          on sms.competition_key = csc.competition_key
         and sms.season_label = csc.season_label
        left join season_stage_summary sss
          on sss.competition_key = csc.competition_key
         and sss.season_label = csc.season_label
        left join season_group_summary sgs
          on sgs.competition_key = csc.competition_key
         and sgs.season_label = csc.season_label
        left join season_tie_summary sts
          on sts.competition_key = csc.competition_key
         and sts.season_label = csc.season_label
        where csc.competition_key = %s
          and coalesce(sms.match_count, 0) > 0
        order by csc.season_label desc;
        """,
        [competition_key, competition_key, competition_key, competition_key, competition_key],
    )


def _fetch_competition_season_average_goals(
    competition_key: str,
    season_label: str,
) -> float | None:
    average_goals = db_client.fetch_val(
        """
        select round(avg(fm.total_goals)::numeric, 2) as average_goals
        from mart.fact_matches fm
        where fm.competition_key = %s
          and fm.season_label = %s;
        """,
        [competition_key, season_label],
    )

    if average_goals is None:
        return None

    return float(average_goals)


def _fetch_team_journey_history_rows(
    competition_key: str,
    team_id: int,
) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with team_match_scope as (
            select
                fm.competition_key,
                fm.season_label,
                fm.stage_id,
                max(fm.stage_name) as stage_name,
                max(ds.stage_format) as stage_format,
                max(ds.sort_order)::int as stage_order,
                count(distinct fm.match_id)::int as matches_played,
                sum(
                    case
                        when fm.home_team_id = %s and coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0) then 1
                        when fm.away_team_id = %s and coalesce(fm.away_goals, 0) > coalesce(fm.home_goals, 0) then 1
                        else 0
                    end
                )::int as wins,
                sum(case when coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 1 else 0 end)::int as draws,
                sum(
                    case
                        when fm.home_team_id = %s and coalesce(fm.home_goals, 0) < coalesce(fm.away_goals, 0) then 1
                        when fm.away_team_id = %s and coalesce(fm.away_goals, 0) < coalesce(fm.home_goals, 0) then 1
                        else 0
                    end
                )::int as losses,
                sum(
                    case
                        when fm.home_team_id = %s then coalesce(fm.home_goals, 0)
                        else coalesce(fm.away_goals, 0)
                    end
                )::int as goals_for,
                sum(
                    case
                        when fm.home_team_id = %s then coalesce(fm.away_goals, 0)
                        else coalesce(fm.home_goals, 0)
                    end
                )::int as goals_against
            from mart.fact_matches fm
            left join mart.dim_stage ds
              on ds.competition_key = fm.competition_key
             and ds.season_label = fm.season_label
             and ds.stage_id = fm.stage_id
            where fm.competition_key = %s
              and (fm.home_team_id = %s or fm.away_team_id = %s)
            group by fm.competition_key, fm.season_label, fm.stage_id
        ),
        progression_scope as (
            select
                sp.competition_key,
                sp.season_label,
                sp.from_stage_id as stage_id,
                max(sp.from_stage_name) as stage_name,
                max(sp.from_stage_format) as stage_format,
                max(sp.from_stage_order)::int as stage_order,
                max(sp.progression_type) as progression_type,
                max(sp.tie_outcome) as tie_outcome,
                max(sp.source_position)::int as source_position,
                max(sp.group_id) as group_id,
                max(sp.group_name) as group_name
            from mart.fact_stage_progression sp
            where sp.competition_key = %s
              and sp.team_id = %s
            group by sp.competition_key, sp.season_label, sp.from_stage_id
        ),
        structural_stage_scope as (
            select
                ds.competition_key,
                ds.season_label,
                ds.stage_id,
                ds.stage_format,
                case
                    when ds.stage_format in ('knockout', 'placement_match')
                     and not exists (
                        select 1
                        from mart.competition_structure_hub csh
                        where csh.competition_key = ds.competition_key
                          and csh.season_label = ds.season_label
                          and csh.from_stage_id = ds.stage_id
                          and csh.progression_type = 'qualified'
                          and csh.to_stage_id is not null
                     ) then true
                    else false
                end as is_structurally_terminal_stage,
                case
                    when ds.stage_format = 'knockout'
                     and not exists (
                        select 1
                        from mart.competition_structure_hub csh
                        where csh.competition_key = ds.competition_key
                          and csh.season_label = ds.season_label
                          and csh.from_stage_id = ds.stage_id
                          and csh.progression_type = 'qualified'
                          and csh.to_stage_id is not null
                     ) then true
                    else false
                end as is_championship_stage
            from mart.dim_stage ds
            where ds.competition_key = %s
        ),
        tie_scope as (
            select
                ftr.competition_key,
                ftr.season_label,
                ftr.stage_id,
                max(ftr.stage_name) as stage_name,
                max(ftr.stage_format) as stage_format,
                count(*)::int as tie_count,
                sum(case when ftr.winner_team_id = %s then 1 else 0 end)::int as ties_won,
                sum(
                    case
                        when ftr.winner_team_id is not null and ftr.winner_team_id <> %s then 1
                        else 0
                    end
                )::int as ties_lost,
                bool_or(coalesce(sss.is_structurally_terminal_stage, false)) as is_structurally_terminal_stage,
                bool_or(coalesce(sss.is_championship_stage, false)) as is_championship_stage,
                bool_or(coalesce(sss.is_championship_stage, false) and ftr.winner_team_id = %s) as is_champion,
                bool_or(
                    coalesce(sss.is_championship_stage, false)
                    and ftr.winner_team_id is not null
                    and ftr.winner_team_id <> %s
                ) as is_runner_up
            from mart.fact_tie_results ftr
            left join structural_stage_scope sss
              on sss.competition_key = ftr.competition_key
             and sss.season_label = ftr.season_label
             and sss.stage_id = ftr.stage_id
            where ftr.competition_key = %s
              and (ftr.home_side_team_id = %s or ftr.away_side_team_id = %s)
            group by ftr.competition_key, ftr.season_label, ftr.stage_id
        ),
        stage_catalog as (
            select
                ds.competition_key,
                ds.season_label,
                ds.stage_id,
                ds.stage_name,
                ds.stage_format,
                ds.sort_order::int as stage_order
            from mart.dim_stage ds
            where ds.competition_key = %s
        )
        select
            sc.season_label,
            csc.format_family,
            csc.season_format_code,
            sc.stage_id::text as stage_id,
            coalesce(tms.stage_name, ps.stage_name, ts.stage_name, sc.stage_name) as stage_name,
            coalesce(tms.stage_format, ps.stage_format, ts.stage_format, sc.stage_format) as stage_format,
            coalesce(tms.stage_order, ps.stage_order, sc.stage_order) as stage_order,
            coalesce(tms.matches_played, 0) as matches_played,
            coalesce(tms.wins, 0) as wins,
            coalesce(tms.draws, 0) as draws,
            coalesce(tms.losses, 0) as losses,
            coalesce(tms.goals_for, 0) as goals_for,
            coalesce(tms.goals_against, 0) as goals_against,
            ps.progression_type,
            coalesce(ps.tie_outcome, case when ts.ties_won > 0 then 'winner' when ts.ties_lost > 0 then 'loser' else null end) as tie_outcome,
            ps.source_position,
            ps.group_id,
            ps.group_name,
            coalesce(ts.tie_count, 0) as tie_count,
            coalesce(ts.ties_won, 0) as ties_won,
            coalesce(ts.ties_lost, 0) as ties_lost,
            coalesce(ts.is_structurally_terminal_stage, false) as is_structurally_terminal_stage,
            coalesce(ts.is_championship_stage, false) as is_championship_stage,
            coalesce(ts.is_champion, false) as is_champion,
            coalesce(ts.is_runner_up, false) as is_runner_up
        from stage_catalog sc
        left join team_match_scope tms
          on tms.competition_key = sc.competition_key
         and tms.season_label = sc.season_label
         and tms.stage_id = sc.stage_id
        left join progression_scope ps
          on ps.competition_key = sc.competition_key
         and ps.season_label = sc.season_label
         and ps.stage_id = sc.stage_id
        left join tie_scope ts
          on ts.competition_key = sc.competition_key
         and ts.season_label = sc.season_label
         and ts.stage_id = sc.stage_id
        inner join mart_control.competition_season_config csc
          on csc.competition_key = sc.competition_key
         and csc.season_label = sc.season_label
        where
            coalesce(tms.matches_played, 0) > 0
            or ps.stage_id is not null
            or ts.stage_id is not null
        order by sc.season_label desc, coalesce(tms.stage_order, ps.stage_order, sc.stage_order) asc, sc.stage_id asc;
        """,
        [
            team_id,
            team_id,
            team_id,
            team_id,
            team_id,
            team_id,
            competition_key,
            team_id,
            team_id,
            competition_key,
            team_id,
            competition_key,
            team_id,
            team_id,
            team_id,
            team_id,
            competition_key,
            team_id,
            team_id,
            competition_key,
        ],
    )


def _resolve_team_journey_stage_result(row: dict[str, Any]) -> str:
    if bool(row.get("is_champion")):
        return "champion"
    if bool(row.get("is_runner_up")):
        return "runner_up"

    is_structurally_terminal_stage = bool(row.get("is_structurally_terminal_stage"))
    progression_type = row.get("progression_type")
    tie_outcome = row.get("tie_outcome")

    if progression_type == "qualified":
        return "qualified"
    if progression_type == "repechage":
        return "repechage"
    if progression_type == "eliminated":
        return "eliminated"

    if tie_outcome == "winner":
        return "unknown" if is_structurally_terminal_stage else "qualified"
    if tie_outcome == "loser":
        return "unknown" if is_structurally_terminal_stage else "eliminated"

    if is_structurally_terminal_stage and int(row.get("tie_count") or 0) > 0:
        return "unknown"

    return "participated"


def _resolve_team_journey_final_outcome(stages: list[dict[str, Any]]) -> str:
    if any(stage["stageResult"] == "champion" for stage in stages):
        return "champion"
    if any(stage["stageResult"] == "runner_up" for stage in stages):
        return "runner_up"
    if stages:
        return stages[-1]["stageResult"]
    return "not_applicable"


def _build_team_journey_history_payload(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seasons: dict[str, dict[str, Any]] = {}

    for row in rows:
        season_key = row["season_label"]
        season_payload = seasons.setdefault(
            season_key,
            {
                "seasonLabel": _format_season_label(row["season_label"]),
                "formatFamily": row.get("format_family"),
                "seasonFormatCode": row.get("season_format_code"),
                "summary": {
                    "matchesPlayed": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goalsFor": 0,
                    "goalsAgainst": 0,
                },
                "stages": [],
            },
        )

        stage_payload = {
            "stageId": row.get("stage_id"),
            "stageName": row.get("stage_name"),
            "stageFormat": row.get("stage_format"),
            "stageOrder": int(row["stage_order"]) if row.get("stage_order") is not None else None,
            "matchesPlayed": int(row.get("matches_played") or 0),
            "wins": int(row.get("wins") or 0),
            "draws": int(row.get("draws") or 0),
            "losses": int(row.get("losses") or 0),
            "goalsFor": int(row.get("goals_for") or 0),
            "goalsAgainst": int(row.get("goals_against") or 0),
            "progressionType": row.get("progression_type"),
            "tieOutcome": row.get("tie_outcome"),
            "sourcePosition": int(row["source_position"]) if row.get("source_position") is not None else None,
            "groupId": row.get("group_id"),
            "groupName": row.get("group_name"),
            "tieCount": int(row.get("tie_count") or 0),
            "tiesWon": int(row.get("ties_won") or 0),
            "tiesLost": int(row.get("ties_lost") or 0),
            "stageResult": _resolve_team_journey_stage_result(row),
        }
        season_payload["stages"].append(stage_payload)

        season_payload["summary"]["matchesPlayed"] += stage_payload["matchesPlayed"]
        season_payload["summary"]["wins"] += stage_payload["wins"]
        season_payload["summary"]["draws"] += stage_payload["draws"]
        season_payload["summary"]["losses"] += stage_payload["losses"]
        season_payload["summary"]["goalsFor"] += stage_payload["goalsFor"]
        season_payload["summary"]["goalsAgainst"] += stage_payload["goalsAgainst"]

    ordered_seasons = []
    for season_payload in seasons.values():
        season_payload["stages"].sort(
            key=lambda stage: (
                stage["stageOrder"] if stage["stageOrder"] is not None else 999,
                stage["stageName"] or "",
            )
        )
        season_payload["summary"]["finalOutcome"] = _resolve_team_journey_final_outcome(
            season_payload["stages"]
        )
        ordered_seasons.append(season_payload)

    ordered_seasons.sort(
        key=lambda season_payload: season_payload["seasonLabel"] or "",
        reverse=True,
    )
    return ordered_seasons


def _build_competition_analytics_coverage(stage_analytics_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_stage_count = len(stage_analytics_rows)
    if total_stage_count <= 0:
        return {
            "status": "unknown",
            "label": "Competition analytics coverage",
        }

    available_stage_count = sum(
        1
        for row in stage_analytics_rows
        if any(
            int(row.get(metric_name) or 0) > 0
            for metric_name in ("match_count", "team_count", "group_count", "tie_count", "resolved_ties")
        )
    )
    if available_stage_count <= 0:
        return {
            "status": "unknown",
            "label": "Competition analytics coverage",
        }

    return build_coverage_from_counts(
        available_stage_count,
        total_stage_count,
        "Competition analytics coverage",
    )


def _build_team_journey_coverage(seasons: list[dict[str, Any]]) -> dict[str, Any]:
    total_season_count = len(seasons)
    if total_season_count <= 0:
        return {
            "status": "unknown",
            "label": "Team journey coverage",
        }

    resolved_season_count = sum(
        1
        for season in seasons
        if season.get("stages")
        and season.get("summary", {}).get("finalOutcome") not in {None, "unknown"}
        and all(stage.get("stageResult") != "unknown" for stage in season["stages"])
    )
    if resolved_season_count <= 0:
        return {
            "status": "unknown",
            "label": "Team journey coverage",
        }

    return build_coverage_from_counts(
        resolved_season_count,
        total_season_count,
        "Team journey coverage",
    )


HISTORICAL_STATS_GROUP_KEYS = {
    "champions": "champions",
    "scorers": "scorers",
}

def _normalize_historical_stats_competition_key(competition_key: str) -> str:
    return _normalize_competition_key(competition_key) or competition_key


def _empty_historical_stats_payload(as_of_year: int) -> dict[str, Any]:
    return {
        "champions": {"items": [], "source": "wikipedia", "asOfYear": as_of_year},
        "scorers": {"items": [], "source": "wikipedia", "asOfYear": as_of_year},
    }


def _fetch_competition_historical_stats(competition_key: str, as_of_year: int) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with competition_lookup as (
            select
                dc.competition_sk,
                min(ds.competition_key) as competition_key
            from mart.dim_competition dc
            join mart.dim_stage ds
              on ds.league_id = dc.league_id
            group by dc.competition_sk
        ),
        player_candidates as (
            select
                player_id,
                player_name,
                normalized_player_name,
                row_number() over (
                    partition by normalized_player_name
                    order by
                        competition_matches desc,
                        last_match_date desc nulls last,
                        player_id asc
                ) as candidate_rank
            from (
                select
                    dp.player_id,
                    dp.player_name,
                    regexp_replace(lower(trim(dp.player_name)), '\\s+', ' ', 'g') as normalized_player_name,
                    (count(distinct pms.match_id) filter (where cl.competition_key = %s))::int as competition_matches,
                    max(pms.match_date) filter (where cl.competition_key = %s) as last_match_date
                from mart.dim_player dp
                left join mart.player_match_summary pms
                  on pms.player_id = dp.player_id
                 and pms.season <= %s
                left join competition_lookup cl
                  on cl.competition_sk = pms.competition_sk
                group by dp.player_id, dp.player_name
            ) candidates
            where normalized_player_name <> ''
        ),
        historical_source as (
          select
            h.stat_code,
            h.stat_group,
            h.entity_type,
            coalesce(h.entity_id, pc.player_id) as entity_id,
            h.entity_name,
            h.value_numeric,
            h.value_label,
            h.rank,
            h.season_label,
            h.occurred_on,
            h.source,
            h.source_url,
            h.as_of_year,
            h.metadata || case
                when h.entity_id is null and pc.player_id is not null then
                    jsonb_build_object('resolvedEntityIdSource', 'dim_player_name_match')
                else '{}'::jsonb
            end as metadata
          from mart.competition_historical_stats h
          left join player_candidates pc
            on h.entity_type = 'player'
           and h.entity_id is null
           and pc.candidate_rank = 1
           and regexp_replace(lower(trim(coalesce(h.entity_name, ''))), '\\s+', ' ', 'g') = pc.normalized_player_name
          where h.competition_key = %s
            and h.as_of_year = %s
            and h.stat_group in ('champions', 'scorers')
        ),
        ranked as (
          select
            historical_source.*,
            row_number() over (
              partition by historical_source.as_of_year, historical_source.stat_group
              order by
                coalesce(historical_source.rank, 999999) asc,
                historical_source.value_numeric desc nulls last,
                historical_source.entity_name asc nulls last,
                historical_source.entity_id asc nulls last
            ) as group_position
          from historical_source
        )
        select
          r.stat_code,
          r.stat_group,
          d.display_name,
          r.entity_type,
          r.entity_id,
          r.entity_name,
          r.value_numeric,
          r.value_label,
          r.rank,
          r.season_label,
          r.occurred_on,
          r.source,
          r.source_url,
          r.as_of_year,
          r.metadata
        from ranked r
        join control.historical_stat_definitions d
          on d.stat_code = r.stat_code
        where r.group_position <= 5
        order by
          case r.stat_group
            when 'champions' then 1
            when 'scorers' then 2
            else 99
          end,
          r.group_position asc,
          r.stat_code,
          r.value_numeric desc nulls last,
          r.entity_name nulls last;
        """,
        [competition_key, competition_key, as_of_year, competition_key, as_of_year],
    )


def _fetch_competition_historical_scorers_fallback(
    competition_key: str,
    as_of_year: int,
    limit: int = 5,
) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with competition_lookup as (
            select
                dc.competition_sk,
                min(ds.competition_key) as competition_key
            from mart.dim_competition dc
            join mart.dim_stage ds
              on ds.league_id = dc.league_id
            group by dc.competition_sk
        ),
        scorer_totals as (
            select
                fps.player_id,
                max(fps.player_name) as player_name,
                sum(coalesce(fps.goals, 0))::numeric as goals
            from mart.player_season_summary fps
            join competition_lookup cl
              on cl.competition_sk = fps.competition_sk
            where cl.competition_key = %s
              and fps.season <= %s
            group by fps.player_id
        )
        select
            player_id,
            player_name,
            goals,
            row_number() over (order by goals desc, player_name asc, player_id asc) as rank
        from scorer_totals
        where goals > 0
        order by goals desc, player_name asc, player_id asc
        limit %s;
        """,
        [competition_key, as_of_year, limit],
    )


def _serialize_historical_stat_row(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("value_numeric")
    if isinstance(value, float) and value.is_integer():
        value = int(value)

    return {
        "statCode": row.get("stat_code"),
        "label": row.get("display_name"),
        "entityType": row.get("entity_type"),
        "entityId": str(row["entity_id"]) if row.get("entity_id") is not None else None,
        "entityName": row.get("entity_name"),
        "value": value,
        "valueLabel": row.get("value_label"),
        "rank": int(row["rank"]) if row.get("rank") is not None else None,
        "seasonLabel": row.get("season_label"),
        "occurredOn": row.get("occurred_on"),
        "sourceUrl": row.get("source_url"),
        "metadata": row.get("metadata") or {},
    }


def _serialize_historical_scorer_fallback_row(row: dict[str, Any]) -> dict[str, Any]:
    goals = row.get("goals")
    if isinstance(goals, float) and goals.is_integer():
        goals = int(goals)

    return {
        "statCode": "player_most_goals",
        "label": "Mais gols",
        "entityType": "player",
        "entityId": str(row["player_id"]) if row.get("player_id") is not None else None,
        "entityName": row.get("player_name") or "Jogador não identificado",
        "value": goals,
        "valueLabel": None,
        "rank": int(row["rank"]) if row.get("rank") is not None else None,
        "seasonLabel": None,
        "occurredOn": None,
        "sourceUrl": None,
        "metadata": {"fallbackSource": "player_season_summary"},
    }


def _build_historical_stats_coverage(data: dict[str, Any]) -> dict[str, Any]:
    total_rows = len(data["champions"]["items"]) + len(data["scorers"]["items"])
    if total_rows <= 0:
        return {"status": "empty", "percentage": 0, "label": "Historical stats coverage"}
    return build_coverage_from_counts(total_rows, total_rows, "Dados Históricos")


@router.get("/api/v1/competition-historical-stats")
def get_competition_historical_stats(
    request: Request,
    competitionKey: str | None = None,
    asOfYear: str | None = None,
) -> dict[str, Any]:
    normalized_competition_key = (competitionKey or "").strip()
    if normalized_competition_key == "":
        raise AppError(
            message="'competitionKey' is required.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"missing": ["competitionKey"]},
        )

    normalized_as_of_year = _parse_optional_int(asOfYear, field_name="asOfYear") or 2025
    resolved_competition_key = _normalize_historical_stats_competition_key(normalized_competition_key)
    rows = _fetch_competition_historical_stats(resolved_competition_key, normalized_as_of_year)
    data = _empty_historical_stats_payload(normalized_as_of_year)

    for row in rows:
        group_key = HISTORICAL_STATS_GROUP_KEYS.get(str(row.get("stat_group") or ""))
        if group_key is None:
            continue
        data[group_key]["items"].append(_serialize_historical_stat_row(row))
        data[group_key]["source"] = row.get("source") or "wikipedia"
        data[group_key]["asOfYear"] = row.get("as_of_year") or normalized_as_of_year

    if len(data["scorers"]["items"]) == 0:
        fallback_scorer_rows = _fetch_competition_historical_scorers_fallback(
            resolved_competition_key,
            normalized_as_of_year,
        )
        if fallback_scorer_rows:
            data["scorers"]["items"] = [
                _serialize_historical_scorer_fallback_row(row) for row in fallback_scorer_rows
            ]
            data["scorers"]["source"] = "player_season_summary"
            data["scorers"]["asOfYear"] = normalized_as_of_year

    data["updatedAt"] = datetime.now(UTC).isoformat()

    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=_build_historical_stats_coverage(data),
    )


@router.get("/api/v1/competition-structure")
def get_competition_structure(
    request: Request,
    competitionKey: str | None = None,
    seasonLabel: str | None = None,
) -> dict[str, Any]:
    normalized_competition_key, normalized_season_label = _require_competition_scope(
        competitionKey,
        seasonLabel,
    )
    scope = _resolve_competition_scope(normalized_competition_key, normalized_season_label)
    if scope is None:
        raise AppError(
            message="Competition season not found.",
            code="COMPETITION_SEASON_NOT_FOUND",
            status=404,
            details={
                "competitionKey": _public_competition_key(normalized_competition_key),
                "seasonLabel": seasonLabel,
            },
        )

    stages = _fetch_competition_stages(scope.competition_key, scope.season_label)
    groups_by_stage = _fetch_stage_groups(scope.competition_key, scope.season_label)
    transitions_by_stage = _fetch_structure_transitions(scope.competition_key, scope.season_label)

    data = {
        "competition": _serialize_scope(scope),
        "stages": [
            {
                **_serialize_stage(stage),
                "groups": [_serialize_group(group) for group in groups_by_stage.get(stage.stage_id, [])],
                "transitions": transitions_by_stage.get(stage.stage_id, []),
            }
            for stage in stages
        ],
        "updatedAt": datetime.now(UTC).isoformat(),
    }

    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=build_coverage_from_counts(
            len(stages),
            len(stages),
            "Competition structure coverage",
        ),
    )


@router.get("/api/v1/group-standings")
def get_group_standings(
    request: Request,
    competitionKey: str | None = None,
    seasonLabel: str | None = None,
    stageId: str | None = None,
    groupId: str | None = None,
    roundId: str | None = None,
) -> dict[str, Any]:
    normalized_competition_key, normalized_season_label = _require_competition_scope(
        competitionKey,
        seasonLabel,
    )
    normalized_stage_id = _parse_required_int(stageId, field_name="stageId")
    normalized_group_id = (groupId or "").strip()
    if normalized_group_id == "":
        raise AppError(
            message="'groupId' is required for group standings.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"missing": ["groupId"]},
        )
    normalized_round_id = _parse_optional_int(roundId, field_name="roundId")

    scope = _resolve_competition_scope(normalized_competition_key, normalized_season_label)
    if scope is None:
        raise AppError(
            message="Competition season not found.",
            code="COMPETITION_SEASON_NOT_FOUND",
            status=404,
            details={
                "competitionKey": _public_competition_key(normalized_competition_key),
                "seasonLabel": seasonLabel,
            },
        )

    stage = _resolve_stage(scope.competition_key, scope.season_label, normalized_stage_id)
    if stage is None:
        raise AppError(
            message="Invalid value for 'stageId'. Requested stage does not exist in competition context.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"stageId": normalized_stage_id},
        )
    if stage.stage_format != "group_table":
        raise AppError(
            message="Group standings are only available for stages with 'stageFormat=group_table'.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={
                "stageId": normalized_stage_id,
                "stageFormat": stage.stage_format,
            },
        )

    group = _resolve_group(
        scope.competition_key,
        scope.season_label,
        stage.stage_id,
        normalized_group_id,
    )
    if group is None:
        raise AppError(
            message="Invalid value for 'groupId'. Requested group does not exist in stage context.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={
                "stageId": normalized_stage_id,
                "groupId": normalized_group_id,
            },
        )

    rounds = _fetch_group_rounds(
        scope.competition_key,
        scope.season_label,
        stage.stage_id,
        group.group_id,
    )
    selected_round, current_round = _resolve_selected_round(rounds, normalized_round_id)

    rows = (
        _fetch_group_standings_rows(
            scope.competition_key,
            scope.season_label,
            stage.stage_id,
            group.group_id,
            selected_round.round_id,
        )
        if selected_round is not None
        else []
    )

    data = {
        "competition": _serialize_scope(scope),
        "stage": _serialize_stage(stage, expected_teams=group.expected_teams),
        "group": _serialize_group(group),
        "selectedRound": _serialize_round(selected_round),
        "currentRound": _serialize_round(current_round),
        "rounds": [_serialize_round(round_data) for round_data in rounds],
        "rows": [
            {
                "position": int(row["position"]),
                "teamId": row["team_id"],
                "teamName": row.get("team_name"),
                "matchesPlayed": int(row.get("games_played") or 0),
                "wins": int(row.get("won") or 0),
                "draws": int(row.get("draw") or 0),
                "losses": int(row.get("lost") or 0),
                "goalsFor": int(row.get("goals_for") or 0),
                "goalsAgainst": int(row.get("goals_against") or 0),
                "goalDiff": int(row.get("goal_diff") or 0),
                "points": int(row.get("points") or 0),
            }
            for row in rows
        ],
        "updatedAt": datetime.now(UTC).isoformat(),
    }

    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=build_coverage_from_counts(len(rows), group.expected_teams, "Standings coverage"),
    )


@router.get("/api/v1/ties")
def get_stage_ties(
    request: Request,
    competitionKey: str | None = None,
    seasonLabel: str | None = None,
    stageId: str | None = None,
) -> dict[str, Any]:
    normalized_competition_key, normalized_season_label = _require_competition_scope(
        competitionKey,
        seasonLabel,
    )
    normalized_stage_id = _parse_required_int(stageId, field_name="stageId")

    scope = _resolve_competition_scope(normalized_competition_key, normalized_season_label)
    if scope is None:
        raise AppError(
            message="Competition season not found.",
            code="COMPETITION_SEASON_NOT_FOUND",
            status=404,
            details={
                "competitionKey": _public_competition_key(normalized_competition_key),
                "seasonLabel": seasonLabel,
            },
        )

    stage = _resolve_stage(scope.competition_key, scope.season_label, normalized_stage_id)
    if stage is None:
        raise AppError(
            message="Invalid value for 'stageId'. Requested stage does not exist in competition context.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"stageId": normalized_stage_id},
        )
    if stage.stage_format not in {"knockout", "qualification_knockout", "placement_match"}:
        raise AppError(
            message="Ties are only available for stages with knockout structure.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={
                "stageId": normalized_stage_id,
                "stageFormat": stage.stage_format,
            },
        )

    ties = _fetch_stage_ties(scope.competition_key, scope.season_label, stage.stage_id)
    data = {
        "competition": _serialize_scope(scope),
        "stage": _serialize_stage(stage),
        "ties": [
            {
                "tieId": row["tie_id"],
                "tieOrder": int(row.get("tie_order") or 0),
                "homeTeamId": row.get("home_team_id"),
                "homeTeamName": row.get("home_side_team_name"),
                "awayTeamId": row.get("away_team_id"),
                "awayTeamName": row.get("away_side_team_name"),
                "matchCount": int(row.get("match_count") or 0),
                "firstLegAt": row.get("first_leg_at"),
                "lastLegAt": row.get("last_leg_at"),
                "homeGoals": int(row.get("home_side_goals") or 0),
                "awayGoals": int(row.get("away_side_goals") or 0),
                "winnerTeamId": row.get("winner_team_id"),
                "winnerTeamName": row.get("winner_team_name"),
                "resolutionType": row.get("resolution_type"),
                "hasExtraTimeMatch": bool(row.get("has_extra_time_match")),
                "hasPenaltiesMatch": bool(row.get("has_penalties_match")),
                "nextStageId": row.get("next_stage_id"),
                "nextStageName": row.get("next_stage_name"),
            }
            for row in ties
        ],
        "updatedAt": datetime.now(UTC).isoformat(),
    }

    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=build_coverage_from_counts(len(ties), len(ties), "Tie coverage"),
    )


@router.get("/api/v1/competition-analytics")
def get_competition_analytics(
    request: Request,
    competitionKey: str | None = None,
    seasonLabel: str | None = None,
) -> dict[str, Any]:
    normalized_competition_key, normalized_season_label = _require_competition_scope(
        competitionKey,
        seasonLabel,
    )
    scope = _resolve_competition_scope(normalized_competition_key, normalized_season_label)
    if scope is None:
        raise AppError(
            message="Competition season not found.",
            code="COMPETITION_SEASON_NOT_FOUND",
            status=404,
            details={
                "competitionKey": _public_competition_key(normalized_competition_key),
                "seasonLabel": seasonLabel,
            },
        )

    stage_analytics_rows = _fetch_competition_stage_analytics(scope.competition_key, scope.season_label)
    comparison_rows = _fetch_competition_season_comparisons(scope.competition_key)
    season_average_goals = _fetch_competition_season_average_goals(
        scope.competition_key,
        scope.season_label,
    )

    season_summary = {
        "matchCount": sum(int(row.get("match_count") or 0) for row in stage_analytics_rows),
        "totalStages": len(stage_analytics_rows),
        "tableStages": sum(
            1
            for row in stage_analytics_rows
            if row.get("stage_format") in {"league_table", "group_table"}
        ),
        "knockoutStages": sum(
            1
            for row in stage_analytics_rows
            if row.get("stage_format") in {"knockout", "qualification_knockout"}
        ),
        "groupCount": sum(int(row.get("group_count") or 0) for row in stage_analytics_rows),
        "tieCount": sum(int(row.get("tie_count") or 0) for row in stage_analytics_rows),
        "averageGoals": season_average_goals,
    }

    data = {
        "competition": _serialize_scope(scope),
        "seasonSummary": season_summary,
        "stageAnalytics": [
            {
                "stageId": row.get("stage_id"),
                "stageName": row.get("stage_name"),
                "stageCode": row.get("stage_code"),
                "stageFormat": row.get("stage_format"),
                "stageOrder": int(row["sort_order"]) if row.get("sort_order") is not None else None,
                "isCurrent": bool(row.get("is_current")),
                "matchCount": int(row.get("match_count") or 0),
                "teamCount": int(row.get("team_count") or 0),
                "groupCount": int(row.get("group_count") or 0),
                "averageGoals": float(row["average_goals"]) if row.get("average_goals") is not None else None,
                "homeWins": int(row.get("home_wins") or 0),
                "draws": int(row.get("draws") or 0),
                "awayWins": int(row.get("away_wins") or 0),
                "tieCount": int(row.get("tie_count") or 0),
                "resolvedTies": int(row.get("resolved_ties") or 0),
                "inferredTies": int(row.get("inferred_ties") or 0),
            }
            for row in stage_analytics_rows
        ],
        "seasonComparisons": [
            {
                "seasonLabel": _format_season_label(row["season_label"]),
                "formatFamily": row.get("format_family"),
                "seasonFormatCode": row.get("season_format_code"),
                "participantScope": row.get("participant_scope"),
                "matchCount": int(row.get("match_count") or 0),
                "stageCount": int(row.get("stage_count") or 0),
                "tableStageCount": int(row.get("table_stage_count") or 0),
                "knockoutStageCount": int(row.get("knockout_stage_count") or 0),
                "groupCount": int(row.get("group_count") or 0),
                "tieCount": int(row.get("tie_count") or 0),
                "averageGoals": float(row["average_goals"]) if row.get("average_goals") is not None else None,
            }
            for row in comparison_rows
        ],
        "updatedAt": datetime.now(UTC).isoformat(),
    }

    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=_build_competition_analytics_coverage(stage_analytics_rows),
    )


@router.get("/api/v1/team-journey-history")
def get_team_journey_history(
    request: Request,
    competitionKey: str | None = None,
    teamId: str | None = None,
) -> dict[str, Any]:
    normalized_competition_key = _normalize_competition_key(competitionKey)
    if normalized_competition_key is None:
        raise AppError(
            message="'competitionKey' is required.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"missing": ["competitionKey"]},
        )
    normalized_team_id = _parse_required_int(teamId, field_name="teamId")

    canonical_competition = _resolve_canonical_competition(normalized_competition_key)
    journey_rows = _fetch_team_journey_history_rows(normalized_competition_key, normalized_team_id)
    if not journey_rows:
        raise AppError(
            message="Team journey not found in competition history context.",
            code="TEAM_JOURNEY_NOT_FOUND",
            status=404,
            details={
                "competitionKey": _public_competition_key(normalized_competition_key),
                "teamId": normalized_team_id,
            },
        )

    team_name_row = db_client.fetch_one(
        "select team_name from mart.dim_team where team_id = %s limit 1;",
        [normalized_team_id],
    )

    data = {
        "competition": {
            "competitionKey": _public_competition_key(normalized_competition_key),
            "competitionName": canonical_competition.default_name
            if canonical_competition
            else _public_competition_key(normalized_competition_key),
        },
        "team": {
            "teamId": str(normalized_team_id),
            "teamName": team_name_row.get("team_name") if team_name_row else str(normalized_team_id),
        },
        "seasons": _build_team_journey_history_payload(journey_rows),
        "updatedAt": datetime.now(UTC).isoformat(),
    }

    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=_build_team_journey_coverage(data["seasons"]),
    )


@router.get("/api/v1/team-progression")
def get_team_progression(
    request: Request,
    competitionKey: str | None = None,
    seasonLabel: str | None = None,
    teamId: str | None = None,
) -> dict[str, Any]:
    normalized_competition_key, normalized_season_label = _require_competition_scope(
        competitionKey,
        seasonLabel,
    )
    normalized_team_id = _parse_required_int(teamId, field_name="teamId")

    scope = _resolve_competition_scope(normalized_competition_key, normalized_season_label)
    if scope is None:
        raise AppError(
            message="Competition season not found.",
            code="COMPETITION_SEASON_NOT_FOUND",
            status=404,
            details={
                "competitionKey": _public_competition_key(normalized_competition_key),
                "seasonLabel": seasonLabel,
            },
        )

    progression_rows = _fetch_team_progression(
        scope.competition_key,
        scope.season_label,
        normalized_team_id,
    )
    if not progression_rows:
        raise AppError(
            message="Team progression not found in competition season context.",
            code="TEAM_PROGRESSION_NOT_FOUND",
            status=404,
            details={
                "competitionKey": _public_competition_key(scope.competition_key),
                "seasonLabel": _format_season_label(scope.season_label),
                "teamId": normalized_team_id,
            },
        )

    team_name = progression_rows[0].get("team_name")
    data = {
        "competition": _serialize_scope(scope),
        "team": {
            "teamId": str(normalized_team_id),
            "teamName": team_name,
        },
        "progression": [
            {
                "progressionId": row["stage_progression_id"],
                "fromStageId": row.get("from_stage_id"),
                "fromStageName": row.get("from_stage_name"),
                "fromStageFormat": row.get("from_stage_format"),
                "fromStageOrder": int(row["from_stage_order"]) if row.get("from_stage_order") is not None else None,
                "toStageId": row.get("to_stage_id"),
                "toStageName": row.get("to_stage_name"),
                "toStageFormat": row.get("to_stage_format"),
                "toStageOrder": int(row["to_stage_order"]) if row.get("to_stage_order") is not None else None,
                "progressionScope": row.get("progression_scope"),
                "progressionType": row.get("progression_type"),
                "sourcePosition": int(row["source_position"]) if row.get("source_position") is not None else None,
                "tieOutcome": row.get("tie_outcome"),
                "groupId": row.get("group_id"),
                "groupName": row.get("group_name"),
            }
            for row in progression_rows
        ],
        "updatedAt": datetime.now(UTC).isoformat(),
    }

    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=build_coverage_from_counts(
            len(progression_rows),
            len(progression_rows),
            "Progression coverage",
        ),
    )
