from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Query, Request

from ..core.contracts import build_api_response, build_coverage_from_counts, build_pagination
from ..core.errors import AppError
from ..core.filters import GlobalFilters, VenueFilter, append_fact_match_filters, validate_and_build_global_filters
from ..db.client import db_client

router = APIRouter(prefix="/api/v1/rankings", tags=["rankings"])

SortDirection = Literal["asc", "desc"]
FreshnessClass = Literal["season", "fast"]

SEARCH_NORMALIZATION_SOURCE = "áàâãäéèêëíìîïóòôõöúùûüçñ"
SEARCH_NORMALIZATION_TARGET = "aaaaaeeeeiiiiooooouuuucn"
LEGACY_RANKING_ALIASES = {
    "player-yellow-cards": "player-cards",
}


def _normalize_recent_teams(value: Any) -> list[dict[str, str | None]]:
    if not isinstance(value, list):
        return []

    items: list[dict[str, str | None]] = []
    for entry in value[:5]:
        if not isinstance(entry, dict):
            continue

        team_id = entry.get("teamId")
        if team_id is None:
            continue

        items.append(
            {
                "teamId": str(team_id),
                "teamName": str(entry["teamName"]) if entry.get("teamName") is not None else None,
            }
        )

    return items


@dataclass(frozen=True)
class RankingStageScope:
    stage_id: int
    stage_name: str | None
    stage_format: str | None


@dataclass(frozen=True)
class RankingContextScope:
    competition_id: int | None
    competition_name: str | None
    season_id: int | None
    season_label: str | None

RANKING_CONFIG: dict[str, dict[str, Any]] = {
    "player-goals": {
        "metricKey": "goals",
        "domain": "player",
        "valueColumn": "goals",
        "defaultSort": "desc",
        "defaultMinSample": 180,
        "sampleField": "minutesPlayed",
        "sampleLabel": "Amostra mínima",
        "sampleUnit": "minutes",
        "sampleUnitLabel": "minutos",
    },
    "player-assists": {
        "metricKey": "assists",
        "domain": "player",
        "valueColumn": "assists",
        "defaultSort": "desc",
        "defaultMinSample": 180,
        "sampleField": "minutesPlayed",
        "sampleLabel": "Amostra mínima",
        "sampleUnit": "minutes",
        "sampleUnitLabel": "minutos",
    },
    "player-shots-total": {
        "metricKey": "shots_total",
        "domain": "player",
        "valueColumn": "shots_total",
        "defaultSort": "desc",
        "defaultMinSample": 180,
        "sampleField": "minutesPlayed",
        "sampleLabel": "Amostra mínima",
        "sampleUnit": "minutes",
        "sampleUnitLabel": "minutos",
    },
    "player-shots-on-target": {
        "metricKey": "shots_on_target",
        "domain": "player",
        "valueColumn": "shots_on_goal",
        "defaultSort": "desc",
        "defaultMinSample": 180,
        "sampleField": "minutesPlayed",
        "sampleLabel": "Amostra mínima",
        "sampleUnit": "minutes",
        "sampleUnitLabel": "minutos",
    },
    "player-pass-accuracy": {
        "metricKey": "pass_accuracy_pct",
        "domain": "player",
        "unsupported": True,
        "defaultSort": "desc",
        "defaultMinSample": 180,
        "sampleField": "minutesPlayed",
        "sampleLabel": "Amostra mínima",
        "sampleUnit": "minutes",
        "sampleUnitLabel": "minutos",
    },
    "player-rating": {
        "metricKey": "player_rating",
        "domain": "player",
        "valueColumn": "rating",
        "defaultSort": "desc",
        "defaultMinSample": 180,
        "sampleField": "minutesPlayed",
        "sampleLabel": "Amostra mínima",
        "sampleUnit": "minutes",
        "sampleUnitLabel": "minutos",
    },
    "player-cards": {
        "metricKey": "cards_total",
        "domain": "player",
        "valueColumn": "cards_total",
        "defaultSort": "desc",
        "sampleField": "minutesPlayed",
        "sampleLabel": "Amostra mínima",
        "sampleUnit": "minutes",
        "sampleUnitLabel": "minutos",
    },
    "team-possession": {
        "metricKey": "team_possession_pct",
        "domain": "team_possession",
        "defaultSort": "desc",
    },
    "team-pass-accuracy": {
        "metricKey": "team_pass_accuracy_pct",
        "domain": "team_pass_accuracy",
        "defaultSort": "desc",
    },
}


def _normalize_ranking_type(ranking_type: str) -> str:
    return LEGACY_RANKING_ALIASES.get(ranking_type, ranking_type)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _resolve_ranking_stage_scope(filters: GlobalFilters) -> RankingStageScope | None:
    if filters.stage_id is None:
        return None

    where_clauses = ["fm.stage_id = %s"]
    params: list[Any] = [filters.stage_id]
    if filters.competition_ids:
        where_clauses.append("fm.league_id = any(%s)")
        params.append(list(filters.competition_ids))
    if filters.season_id is not None:
        where_clauses.append("fm.season = %s")
        params.append(filters.season_id)

    row = db_client.fetch_one(
        f"""
        select
            fm.stage_id,
            max(ds.stage_name) as stage_name,
            max(ds.stage_format) as stage_format
        from mart.fact_matches fm
        left join mart.dim_stage ds
          on ds.competition_key = fm.competition_key
         and ds.season_label = fm.season_label
         and ds.stage_id = fm.stage_id
        where {" and ".join(where_clauses)}
        group by fm.stage_id
        order by fm.stage_id asc
        limit 1;
        """,
        params,
    )
    if row is None:
        return None

    return RankingStageScope(
        stage_id=int(row["stage_id"]),
        stage_name=row.get("stage_name"),
        stage_format=row.get("stage_format"),
    )


def _validate_ranking_stage_scope(filters: GlobalFilters) -> RankingStageScope | None:
    stage_scope = _resolve_ranking_stage_scope(filters)
    if filters.stage_id is None:
        return stage_scope

    if stage_scope is None:
        raise AppError(
            message="Invalid value for 'stageId'. Requested stage does not exist in ranking context.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"stageId": filters.stage_id},
        )

    if filters.stage_format is not None and stage_scope.stage_format != filters.stage_format.value:
        raise AppError(
            message="Invalid stage scope. 'stageId' and 'stageFormat' refer to different structural contexts.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={
                "stageId": filters.stage_id,
                "stageFormat": filters.stage_format.value,
                "resolvedStageFormat": stage_scope.stage_format,
            },
        )

    return stage_scope


def _get_ranking_config(ranking_type: str) -> dict[str, Any]:
    config = RANKING_CONFIG.get(_normalize_ranking_type(ranking_type))
    if config is None:
        raise AppError(
            message="Invalid ranking type.",
            code="INVALID_RANKING_TYPE",
            status=400,
            details={"rankingType": ranking_type},
        )
    return config


def _format_stage_format_label(stage_format: str | None) -> str | None:
    if stage_format == "league_table":
        return "Fase classificatória"
    if stage_format == "group_table":
        return "Fase de grupos"
    if stage_format == "knockout":
        return "Mata-mata"
    if stage_format == "qualification_knockout":
        return "Eliminatória preliminar"
    if stage_format == "placement_match":
        return "Disputa de colocação"
    return None


def _format_venue_label(venue: VenueFilter) -> str:
    if venue == VenueFilter.home:
        return "Somente mandante"
    if venue == VenueFilter.away:
        return "Somente visitante"
    return "Todos os mandos"


def _normalize_search_value(search: str | None) -> str | None:
    if not search:
        return None

    normalized_search = search.strip().lower().translate(
        str.maketrans(SEARCH_NORMALIZATION_SOURCE, SEARCH_NORMALIZATION_TARGET)
    )
    return normalized_search or None


def _normalized_search_sql(expression: str) -> str:
    return (
        f"translate(lower(coalesce({expression}, '')), "
        f"'{SEARCH_NORMALIZATION_SOURCE}', '{SEARCH_NORMALIZATION_TARGET}')"
    )


def _resolve_ranking_context_scope(filters: GlobalFilters) -> RankingContextScope:
    where_clauses = ["1=1"]
    params: list[Any] = []
    append_fact_match_filters(where_clauses, params, alias="fm", filters=filters)

    row = db_client.fetch_one(
        f"""
        select
            case when count(distinct dc.league_id) = 1 then max(dc.league_id) end as competition_id,
            case when count(distinct dc.league_name) = 1 then max(dc.league_name) end as competition_name,
            case when count(distinct fm.season) = 1 then max(fm.season) end as season_id,
            case when count(distinct fm.season_label) = 1 then max(fm.season_label) end as season_label
        from mart.fact_matches fm
        left join mart.dim_competition dc
          on dc.competition_sk = fm.competition_sk
        where {" and ".join(where_clauses)};
        """,
        params,
    ) or {}

    return RankingContextScope(
        competition_id=int(row["competition_id"]) if row.get("competition_id") is not None else None,
        competition_name=row.get("competition_name"),
        season_id=int(row["season_id"]) if row.get("season_id") is not None else None,
        season_label=row.get("season_label"),
    )


def _resolve_scope_kind(scope: RankingContextScope) -> str:
    if scope.competition_id is not None and scope.season_id is not None:
        return "competitionSeason"
    if scope.competition_id is not None:
        return "competition"
    if scope.season_id is not None:
        return "season"
    return "catalog"


def _resolve_scope_label(scope: RankingContextScope) -> str:
    if scope.competition_name and scope.season_label:
        return f"{scope.competition_name} · {scope.season_label}"
    if scope.competition_name:
        return scope.competition_name
    if scope.season_label:
        return f"Temporada {scope.season_label}"
    return "Acervo publicado"


def _build_window_payload(filters: GlobalFilters, *, entity_label: str) -> dict[str, Any]:
    if filters.last_n is not None:
        return {
            "kind": "lastN",
            "label": f"Últimos {filters.last_n} jogos por {entity_label}",
            "lastN": filters.last_n,
            "appliesPerEntity": True,
        }

    if filters.date_start is not None and filters.date_end is not None:
        return {
            "kind": "dateRange",
            "label": "Janela personalizada",
            "dateStart": filters.date_start.isoformat(),
            "dateEnd": filters.date_end.isoformat(),
            "appliesPerEntity": False,
        }

    if filters.round_id is not None:
        return {
            "kind": "round",
            "label": f"Rodada {filters.round_id}",
            "roundId": str(filters.round_id),
            "appliesPerEntity": False,
        }

    return {
        "kind": "all",
        "label": "Todos os jogos do recorte",
        "appliesPerEntity": False,
    }


def _build_sample_payload(
    ranking_config: dict[str, Any],
    min_sample_value: int | None,
) -> dict[str, Any] | None:
    sample_field = ranking_config.get("sampleField")
    default_sample = ranking_config.get("defaultMinSample")

    if sample_field is None and default_sample is None and min_sample_value is None:
        return None

    applied_value = min_sample_value if min_sample_value is not None else default_sample

    return {
        "field": sample_field,
        "label": ranking_config.get("sampleLabel") or "Amostra mínima",
        "unit": ranking_config.get("sampleUnit"),
        "unitLabel": ranking_config.get("sampleUnitLabel"),
        "defaultValue": default_sample,
        "appliedValue": applied_value,
        "isDefault": min_sample_value is None,
    }


def _build_scope_payload(
    *,
    ranking_config: dict[str, Any],
    filters: GlobalFilters,
    stage_scope: RankingStageScope | None,
    min_sample_value: int | None,
) -> dict[str, Any]:
    context_scope = _resolve_ranking_context_scope(filters)
    entity_label = "jogador" if ranking_config["domain"] == "player" else "time"

    return {
        "kind": _resolve_scope_kind(context_scope),
        "label": _resolve_scope_label(context_scope),
        "competitionId": str(context_scope.competition_id) if context_scope.competition_id is not None else None,
        "competitionName": context_scope.competition_name,
        "seasonId": str(context_scope.season_id) if context_scope.season_id is not None else None,
        "seasonLabel": context_scope.season_label,
        "venue": {
            "value": filters.venue.value,
            "label": _format_venue_label(filters.venue),
        },
        "window": _build_window_payload(filters, entity_label=entity_label),
        "sample": _build_sample_payload(ranking_config, min_sample_value),
        "stage": (
            {
                "stageId": str(stage_scope.stage_id),
                "stageName": stage_scope.stage_name,
                "stageFormat": stage_scope.stage_format,
                "stageFormatLabel": _format_stage_format_label(stage_scope.stage_format),
            }
            if stage_scope is not None
            else None
        ),
    }


def _resolve_entity_key(ranking_config: dict[str, Any]) -> str:
    return "player" if ranking_config["domain"] == "player" else "team"


def _player_scope_filters_sql(filters: GlobalFilters) -> tuple[str, list[Any]]:
    where_clauses = ["1=1"]
    params: list[Any] = []
    append_fact_match_filters(where_clauses, params, alias="fm", filters=filters)
    if filters.venue == VenueFilter.home:
        where_clauses.append("pms.team_id = fm.home_team_id")
    elif filters.venue == VenueFilter.away:
        where_clauses.append("pms.team_id = fm.away_team_id")
    return " and ".join(where_clauses), params


def _can_use_player_serving_summary(filters: GlobalFilters) -> bool:
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
    )


def _player_ranking_coverage(filters: GlobalFilters) -> dict[str, Any]:
    match_where: list[str] = ["1=1"]
    match_params: list[Any] = []
    append_fact_match_filters(match_where, match_params, alias="fm", filters=filters)

    player_where, player_params = _player_scope_filters_sql(filters)
    query = f"""
        with scoped_matches as (
            select distinct fm.match_id
            from mart.fact_matches fm
            where {" and ".join(match_where)}
        ),
        scoped_stats as (
            select distinct pms.match_id
            from mart.player_match_summary pms
            inner join mart.fact_matches fm
              on fm.match_id = pms.match_id
            where {player_where}
        )
        select
            (select count(*) from scoped_stats) as available_count,
            (select count(*) from scoped_matches) as total_count;
    """
    row = db_client.fetch_one(query, [*match_params, *player_params]) or {}
    return build_coverage_from_counts(
        int(row.get("available_count") or 0),
        int(row.get("total_count") or 0),
        "Player ranking coverage",
    )


def _team_possession_coverage(filters: GlobalFilters) -> dict[str, Any]:
    where_clauses = ["1=1"]
    params: list[Any] = []
    append_fact_match_filters(where_clauses, params, alias="fm", filters=filters)

    venue_selects: list[str] = []
    if filters.venue in (VenueFilter.all, VenueFilter.home):
        venue_selects.append(
            "select fm.match_id, fm.home_team_id as team_id, fm.home_possession::numeric as possession from scoped_matches fm"
        )
    if filters.venue in (VenueFilter.all, VenueFilter.away):
        venue_selects.append(
            "select fm.match_id, fm.away_team_id as team_id, fm.away_possession::numeric as possession from scoped_matches fm"
        )

    query = f"""
        with scoped_matches as (
            select fm.match_id, fm.home_team_id, fm.away_team_id, fm.home_possession, fm.away_possession
            from mart.fact_matches fm
            where {" and ".join(where_clauses)}
        ),
        team_rows as (
            {" union all ".join(venue_selects)}
        )
        select
            count(*) filter (where possession is not null) as available_count,
            count(*) as total_count
        from team_rows;
    """
    row = db_client.fetch_one(query, params) or {}
    return build_coverage_from_counts(
        int(row.get("available_count") or 0),
        int(row.get("total_count") or 0),
        "Team possession coverage",
    )


def _team_pass_accuracy_coverage(filters: GlobalFilters) -> dict[str, Any]:
    where_clauses = ["1=1"]
    params: list[Any] = []
    append_fact_match_filters(where_clauses, params, alias="fm", filters=filters)
    if filters.venue == VenueFilter.home:
        where_clauses.append("ms.team_id = fm.home_team_id")
    elif filters.venue == VenueFilter.away:
        where_clauses.append("ms.team_id = fm.away_team_id")

    query = f"""
        with scoped as (
            select ms.fixture_id, ms.team_id, ms.passes_pct
            from raw.match_statistics ms
            inner join mart.fact_matches fm
              on fm.match_id = ms.fixture_id
            where {" and ".join(where_clauses)}
        ),
        expected as (
            select
                case
                    when %s = 'all' then count(*) * 2
                    else count(*)
                end as total_expected
            from mart.fact_matches fm
            where {" and ".join([c for c in where_clauses if not c.startswith("ms.")])}
        )
        select
            (select count(*) filter (where passes_pct is not null) from scoped) as available_count,
            (select total_expected from expected) as total_count;
    """
    params_with_venue = [*params, filters.venue.value, *params]
    row = db_client.fetch_one(query, params_with_venue) or {}
    return build_coverage_from_counts(
        int(row.get("available_count") or 0),
        int(row.get("total_count") or 0),
        "Team pass accuracy coverage",
    )


def _fetch_player_ranking_rows_from_serving_summary(
    *,
    ranking_config: dict[str, Any],
    search: str | None,
    min_sample_value: int | None,
    page: int,
    page_size: int,
    sort_direction: str,
) -> tuple[list[dict[str, Any]], int, str | None]:
    value_column = ranking_config["valueColumn"]
    metric_expression = {
        "rating": "pss.rating",
        "goals": "pss.goals",
        "assists": "pss.assists",
        "shots_total": "pss.shots_total",
        "shots_on_goal": "pss.shots_on_goal",
        "yellow_cards": "pss.yellow_cards",
        "cards_total": "pss.cards_total",
    }[value_column]

    normalized_search = _normalize_search_value(search)
    search_pattern = f"%{normalized_search}%" if normalized_search else None
    offset = (page - 1) * page_size
    order_dir = "asc" if sort_direction == "asc" else "desc"
    rank_order_sql = f"c.metric_value {order_dir} nulls last, lower(c.player_name) asc nulls last, c.player_id asc"
    final_order_sql = "r.rank asc, lower(r.player_name) asc nulls last, r.player_id asc"

    rows = db_client.fetch_all(
        f"""
        with constrained as (
            select
                pss.player_id,
                pss.player_name,
                pss.team_id,
                pss.team_name,
                pss.team_count,
                pss.recent_teams_5 as recent_teams,
                pss.matches_played,
                pss.minutes_played,
                {metric_expression} as metric_value,
                case
                    when pss.minutes_played > 0 and {metric_expression} is not null
                        then round(({metric_expression} * 90) / pss.minutes_played, 2)
                    else null
                end as metric_per90,
                pss.data_updated_at
            from mart.player_serving_summary pss
            where (%s::text is null or {_normalized_search_sql("pss.player_name")} like %s)
              and (%s::numeric is null or pss.minutes_played >= %s)
        ),
        ranked as (
            select
                c.player_id,
                c.player_name,
                c.team_id,
                c.team_name,
                c.team_count,
                c.recent_teams,
                c.matches_played,
                c.minutes_played,
                c.metric_value,
                c.metric_per90,
                c.data_updated_at,
                dense_rank() over (order by {rank_order_sql}) as rank
            from constrained c
        )
        select
            r.*,
            count(*) over() as _total_count,
            max(r.data_updated_at) over() as _max_updated_at
        from ranked r
        order by {final_order_sql}
        limit %s offset %s;
        """,
        [
            search_pattern,
            search_pattern,
            min_sample_value,
            min_sample_value,
            page_size,
            offset,
        ],
    )
    total_count = int(rows[0]["_total_count"]) if rows else 0
    max_updated_at = rows[0].get("_max_updated_at") if rows else None
    return rows, total_count, max_updated_at.isoformat() if isinstance(max_updated_at, datetime) else max_updated_at


def _fetch_player_ranking_rows(
    *,
    ranking_config: dict[str, Any],
    filters: GlobalFilters,
    search: str | None,
    min_sample_value: int | None,
    page: int,
    page_size: int,
    sort_direction: str,
) -> tuple[list[dict[str, Any]], int, str | None]:
    if _can_use_player_serving_summary(filters):
        return _fetch_player_ranking_rows_from_serving_summary(
            ranking_config=ranking_config,
            search=search,
            min_sample_value=min_sample_value,
            page=page,
            page_size=page_size,
            sort_direction=sort_direction,
        )

    where_sql, where_params = _player_scope_filters_sql(filters)
    value_column = ranking_config["valueColumn"]
    metric_expression = {
        "rating": "avg(fs.rating)::numeric",
        "goals": "sum(fs.goals)::numeric",
        "assists": "sum(fs.assists)::numeric",
        "shots_total": "sum(fs.shots_total)::numeric",
        "shots_on_goal": "sum(fs.shots_on_goal)::numeric",
        "yellow_cards": "sum(fs.yellow_cards)::numeric",
        "cards_total": "sum(fs.yellow_cards + fs.red_cards)::numeric",
    }[value_column]

    normalized_search = _normalize_search_value(search)
    search_pattern = f"%{normalized_search}%" if normalized_search else None
    offset = (page - 1) * page_size
    order_dir = "asc" if sort_direction == "asc" else "desc"
    rank_order_sql = f"c.metric_value {order_dir} nulls last, lower(c.player_name) asc nulls last, c.player_id asc"
    final_order_sql = "r.rank asc, lower(r.player_name) asc nulls last, r.player_id asc"

    query = f"""
        with scoped as (
            select
                pms.player_id,
                pms.player_name,
                pms.team_id,
                pms.team_name,
                pms.match_id,
                pms.match_date,
                coalesce(pms.minutes_played, 0) as minutes_played,
                coalesce(pms.goals, 0) as goals,
                coalesce(pms.assists, 0) as assists,
                coalesce(pms.shots_total, 0) as shots_total,
                coalesce(pms.shots_on_goal, 0) as shots_on_goal,
                coalesce(pms.yellow_cards, 0) as yellow_cards,
                coalesce(pms.red_cards, 0) as red_cards,
                pms.rating,
                pms.updated_at,
                row_number() over (
                    partition by pms.player_id
                    order by pms.match_date desc, pms.match_id desc
                ) as rn_recent
            from mart.player_match_summary pms
            inner join mart.fact_matches fm
              on fm.match_id = pms.match_id
            where {where_sql}
        ),
        filtered_scoped as (
            select *
            from scoped
            where (%s::int is null or rn_recent <= %s)
        ),
        aggregated as (
            select
                fs.player_id,
                max(fs.player_name) as player_name,
                count(distinct fs.match_id) as matches_played,
                count(distinct fs.team_id) filter (where fs.team_id is not null)::int as team_count,
                sum(fs.minutes_played)::numeric as minutes_played,
                {metric_expression} as metric_value,
                max(fs.updated_at) as data_updated_at
            from filtered_scoped fs
            group by fs.player_id
        ),
        latest_context as (
            select distinct on (fs.player_id)
                fs.player_id,
                fs.team_id,
                fs.team_name
            from filtered_scoped fs
            order by fs.player_id, fs.match_date desc, fs.match_id desc
        ),
        recent_teams as (
            select
                ranked_teams.player_id,
                json_agg(
                    json_build_object(
                        'teamId', ranked_teams.team_id::text,
                        'teamName', ranked_teams.team_name
                    )
                    order by ranked_teams.last_match_date desc, ranked_teams.last_match_id desc
                ) as recent_teams
            from (
                select
                    team_context.player_id,
                    team_context.team_id,
                    team_context.team_name,
                    team_context.last_match_date,
                    team_context.last_match_id,
                    row_number() over (
                        partition by team_context.player_id
                        order by team_context.last_match_date desc, team_context.last_match_id desc
                    ) as recent_team_rank
                from (
                    select
                        fs.player_id,
                        fs.team_id,
                        coalesce(max(fs.team_name), max(dt.team_name)) as team_name,
                        max(fs.match_date) as last_match_date,
                        max(fs.match_id) as last_match_id
                    from filtered_scoped fs
                    left join mart.dim_team dt
                      on dt.team_id = fs.team_id
                    where fs.team_id is not null
                    group by fs.player_id, fs.team_id
                ) team_context
            ) ranked_teams
            where ranked_teams.recent_team_rank <= 5
            group by ranked_teams.player_id
        ),
        enriched as (
            select
                a.player_id,
                a.player_name,
                lc.team_id,
                lc.team_name,
                a.team_count,
                rt.recent_teams,
                a.matches_played,
                a.minutes_played,
                a.metric_value,
                case
                    when a.minutes_played > 0 and a.metric_value is not null
                        then round((a.metric_value * 90) / a.minutes_played, 2)
                    else null
                end as metric_per90,
                a.data_updated_at
            from aggregated a
            left join latest_context lc
              on lc.player_id = a.player_id
            left join recent_teams rt
              on rt.player_id = a.player_id
        ),
        constrained as (
            select *
            from enriched
            where (%s::text is null or {_normalized_search_sql("player_name")} like %s)
              and (%s::numeric is null or minutes_played >= %s)
        ),
        ranked as (
            select
                c.player_id,
                c.player_name,
                c.team_id,
                c.team_name,
                c.team_count,
                c.recent_teams,
                c.matches_played,
                c.minutes_played,
                c.metric_value,
                c.metric_per90,
                c.data_updated_at,
                dense_rank() over (order by {rank_order_sql}) as rank
            from constrained c
        )
        select
            r.*,
            count(*) over() as _total_count,
            max(r.data_updated_at) over() as _max_updated_at
        from ranked r
        order by {final_order_sql}
        limit %s offset %s;
    """

    rows = db_client.fetch_all(
        query,
        [
            *where_params,
            filters.last_n,
            filters.last_n,
            search_pattern,
            search_pattern,
            min_sample_value,
            min_sample_value,
            page_size,
            offset,
        ],
    )
    total_count = int(rows[0]["_total_count"]) if rows else 0
    max_updated_at = rows[0].get("_max_updated_at") if rows else None
    return rows, total_count, max_updated_at.isoformat() if isinstance(max_updated_at, datetime) else max_updated_at


def _fetch_team_possession_rows(
    *,
    filters: GlobalFilters,
    search: str | None,
    min_sample_value: int | None,
    page: int,
    page_size: int,
    sort_direction: str,
) -> tuple[list[dict[str, Any]], int, str | None]:
    where_clauses = ["1=1"]
    params: list[Any] = []
    append_fact_match_filters(where_clauses, params, alias="fm", filters=filters)
    normalized_search = _normalize_search_value(search)
    search_pattern = f"%{normalized_search}%" if normalized_search else None
    offset = (page - 1) * page_size
    order_dir = "asc" if sort_direction == "asc" else "desc"

    venue_selects: list[str] = []
    if filters.venue in (VenueFilter.all, VenueFilter.home):
        venue_selects.append(
            """
            select
                fm.match_id,
                fm.date_day as match_date,
                fm.home_team_id as team_id,
                dt.team_name,
                fm.home_possession::numeric as metric_value
            from scoped_matches fm
            left join mart.dim_team dt
              on dt.team_id = fm.home_team_id
            """
        )
    if filters.venue in (VenueFilter.all, VenueFilter.away):
        venue_selects.append(
            """
            select
                fm.match_id,
                fm.date_day as match_date,
                fm.away_team_id as team_id,
                dt.team_name,
                fm.away_possession::numeric as metric_value
            from scoped_matches fm
            left join mart.dim_team dt
              on dt.team_id = fm.away_team_id
            """
        )

    query = f"""
        with scoped_matches as (
            select fm.match_id, fm.date_day, fm.home_team_id, fm.away_team_id, fm.home_possession, fm.away_possession
            from mart.fact_matches fm
            where {" and ".join(where_clauses)}
        ),
        team_rows as (
            {" union all ".join(venue_selects)}
        ),
        ranked_rows as (
            select
                tr.*,
                row_number() over (partition by tr.team_id order by tr.match_date desc, tr.match_id desc) as rn_recent
            from team_rows tr
        ),
        filtered_rows as (
            select *
            from ranked_rows
            where (%s::int is null or rn_recent <= %s)
        ),
        aggregated as (
            select
                fr.team_id,
                max(fr.team_name) as team_name,
                count(*) as matches_played,
                avg(fr.metric_value)::numeric as metric_value
            from filtered_rows fr
            group by fr.team_id
        ),
        constrained as (
            select *
            from aggregated
            where (%s::text is null or {_normalized_search_sql("team_name")} like %s)
              and (%s::int is null or matches_played >= %s)
        ),
        ranked as (
            select
                c.*,
                dense_rank() over (order by c.metric_value {order_dir} nulls last, c.team_id asc) as rank
            from constrained c
        )
        select
            r.*,
            count(*) over() as _total_count
        from ranked r
        order by r.rank asc, r.team_id asc
        limit %s offset %s;
    """
    rows = db_client.fetch_all(
        query,
        [
            *params,
            filters.last_n,
            filters.last_n,
            search_pattern,
            search_pattern,
            min_sample_value,
            min_sample_value,
            page_size,
            offset,
        ],
    )
    total_count = int(rows[0]["_total_count"]) if rows else 0
    return rows, total_count, None


def _fetch_team_pass_accuracy_rows(
    *,
    filters: GlobalFilters,
    search: str | None,
    min_sample_value: int | None,
    page: int,
    page_size: int,
    sort_direction: str,
) -> tuple[list[dict[str, Any]], int, str | None]:
    where_clauses = ["1=1"]
    params: list[Any] = []
    append_fact_match_filters(where_clauses, params, alias="fm", filters=filters)
    if filters.venue == VenueFilter.home:
        where_clauses.append("ms.team_id = fm.home_team_id")
    elif filters.venue == VenueFilter.away:
        where_clauses.append("ms.team_id = fm.away_team_id")

    normalized_search = _normalize_search_value(search)
    search_pattern = f"%{normalized_search}%" if normalized_search else None
    offset = (page - 1) * page_size
    order_dir = "asc" if sort_direction == "asc" else "desc"

    query = f"""
        with scoped as (
            select
                ms.fixture_id,
                ms.team_id,
                coalesce(ms.team_name, dt.team_name) as team_name,
                fm.date_day as match_date,
                ms.passes_pct::numeric as metric_value
            from raw.match_statistics ms
            inner join mart.fact_matches fm
              on fm.match_id = ms.fixture_id
            left join mart.dim_team dt
              on dt.team_id = ms.team_id
            where {" and ".join(where_clauses)}
        ),
        ranked_rows as (
            select
                s.*,
                row_number() over (partition by s.team_id order by s.match_date desc, s.fixture_id desc) as rn_recent
            from scoped s
        ),
        filtered_rows as (
            select *
            from ranked_rows
            where (%s::int is null or rn_recent <= %s)
        ),
        aggregated as (
            select
                fr.team_id,
                max(fr.team_name) as team_name,
                count(distinct fr.fixture_id) as matches_played,
                avg(fr.metric_value)::numeric as metric_value
            from filtered_rows fr
            group by fr.team_id
        ),
        constrained as (
            select *
            from aggregated
            where (%s::text is null or {_normalized_search_sql("team_name")} like %s)
              and (%s::int is null or matches_played >= %s)
        ),
        ranked as (
            select
                c.*,
                dense_rank() over (order by c.metric_value {order_dir} nulls last, c.team_id asc) as rank
            from constrained c
        )
        select
            r.*,
            count(*) over() as _total_count
        from ranked r
        order by r.rank asc, r.team_id asc
        limit %s offset %s;
    """
    rows = db_client.fetch_all(
        query,
        [
            *params,
            filters.last_n,
            filters.last_n,
            search_pattern,
            search_pattern,
            min_sample_value,
            min_sample_value,
            page_size,
            offset,
        ],
    )
    total_count = int(rows[0]["_total_count"]) if rows else 0
    return rows, total_count, None


@router.get("/{rankingType}")
def get_ranking(
    rankingType: str,
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
    search: str | None = None,
    minSampleValue: int | None = Query(default=None, ge=0),
    freshnessClass: FreshnessClass = "season",
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    sortDirection: SortDirection | None = None,
) -> dict[str, Any]:
    normalized_ranking_type = _normalize_ranking_type(rankingType)
    ranking_config = _get_ranking_config(normalized_ranking_type)
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
    if ranking_config.get("unsupported"):
        raise AppError(
            message="Ranking metric is not implemented yet.",
            code="RANKING_NOT_IMPLEMENTED",
            status=501,
            details={
                "rankingType": normalized_ranking_type,
                "metricKey": ranking_config["metricKey"],
                "reason": "Metric currently not materialized in DW for ranking calculation.",
            },
        )

    stage_scope = _validate_ranking_stage_scope(global_filters)

    effective_sort = sortDirection or ranking_config["defaultSort"]
    scope_payload = _build_scope_payload(
        ranking_config=ranking_config,
        filters=global_filters,
        stage_scope=stage_scope,
        min_sample_value=minSampleValue,
    )

    rows: list[dict[str, Any]]
    total_count: int
    data_updated_at: str | None
    if ranking_config["domain"] == "player":
        rows, total_count, data_updated_at = _fetch_player_ranking_rows(
            ranking_config=ranking_config,
            filters=global_filters,
            search=search,
            min_sample_value=minSampleValue,
            page=page,
            page_size=pageSize,
            sort_direction=effective_sort,
        )
        coverage = _player_ranking_coverage(global_filters)
    elif ranking_config["domain"] == "team_possession":
        rows, total_count, data_updated_at = _fetch_team_possession_rows(
            filters=global_filters,
            search=search,
            min_sample_value=minSampleValue,
            page=page,
            page_size=pageSize,
            sort_direction=effective_sort,
        )
        coverage = _team_possession_coverage(global_filters)
    elif ranking_config["domain"] == "team_pass_accuracy":
        rows, total_count, data_updated_at = _fetch_team_pass_accuracy_rows(
            filters=global_filters,
            search=search,
            min_sample_value=minSampleValue,
            page=page,
            page_size=pageSize,
            sort_direction=effective_sort,
        )
        coverage = _team_pass_accuracy_coverage(global_filters)
    else:
        raise AppError(
            message="Invalid ranking domain configuration.",
            code="INTERNAL_ERROR",
            status=500,
            details={"rankingType": normalized_ranking_type},
        )

    normalized_rows = [
        {
            "entityId": str(row["player_id"] if "player_id" in row else row["team_id"]),
            "entityName": row.get("player_name") or row.get("team_name"),
            "rank": int(row.get("rank") or 0),
            "metricValue": float(row["metric_value"]) if row.get("metric_value") is not None else None,
            "matchesPlayed": int(row.get("matches_played") or 0),
            "minutesPlayed": float(row["minutes_played"]) if row.get("minutes_played") is not None else None,
            "metricPer90": float(row["metric_per90"]) if row.get("metric_per90") is not None else None,
            "teamId": str(row["team_id"]) if row.get("team_id") is not None else None,
            "teamName": row.get("team_name"),
            "teamCount": int(row.get("team_count") or 0) if row.get("team_count") is not None else None,
            "recentTeams": _normalize_recent_teams(row.get("recent_teams")),
            "teamContextLabel": (
                f"{int(row['team_count'])} clubes no recorte"
                if row.get("team_count") is not None and int(row["team_count"]) > 1
                else row.get("team_name")
            ),
        }
        for row in rows
    ]

    pagination = build_pagination(page, pageSize, total_count)
    data = {
        "rankingId": normalized_ranking_type,
        "metricKey": ranking_config["metricKey"],
        "entity": _resolve_entity_key(ranking_config),
        "scope": scope_payload,
        "rows": normalized_rows,
        "updatedAt": data_updated_at,
        "freshnessClass": freshnessClass,
        "sort": {
            "direction": effective_sort,
            "label": "Maior para menor" if effective_sort == "desc" else "Menor para maior",
            "serverSide": True,
        },
    }
    return build_api_response(
        data,
        request_id=_request_id(request),
        pagination=pagination,
        coverage=coverage,
    )
