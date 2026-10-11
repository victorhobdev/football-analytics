from __future__ import annotations

import csv
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Query, Request

from ..core.config import get_settings
from ..core.context_registry import (
    build_canonical_context,
    get_canonical_competition,
    get_canonical_competition_by_key,
    select_default_context,
)
from ..core.contracts import (
    build_api_response,
    build_catalog_scope,
    build_coverage_from_counts,
    build_pagination,
)
from ..core.errors import AppError
from ..core.filters import (
    GlobalFilters,
    VenueFilter,
    append_fact_match_filters,
    validate_and_build_global_filters,
)
from ..core.team_identity import resolve_legacy_team_ids
from ..db.client import db_client

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])

_TEAM_HONORS_PATH = Path(__file__).resolve().parents[2] / "data" / "team_honors_seed.csv"
_TEAM_HONORS_CRITERION = "Títulos oficiais selecionados para o acervo histórico."
_TEAM_TYPES = {"club", "national_team", "representative", "other", "unknown"}

TeamsSortBy = Literal["relevance", "teamName", "points", "goalDiff", "wins", "position"]
TeamType = Literal["club", "national_team", "representative", "other", "unknown"]
SortDirection = Literal["asc", "desc"]


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _to_team_id(team_id: str) -> int:
    try:
        return int(team_id)
    except ValueError as exc:
        raise AppError(
            message="Invalid team id. Expected integer-compatible identifier.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"teamId": team_id},
        ) from exc


def _require_canonical_team_context(filters: GlobalFilters) -> None:
    missing_fields: list[str] = []
    if filters.competition_id is None:
        missing_fields.append("competitionId")
    if filters.season_id is None:
        missing_fields.append("seasonId")

    if missing_fields:
        raise AppError(
            message="Canonical team profile requires 'competitionId' and 'seasonId'.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"missing": missing_fields},
        )


def _fetch_team_reference(team_id: int, filters: GlobalFilters) -> dict[str, Any] | None:
    query = "select team_id, team_name from mart.dim_team where team_id = %s;"
    team = db_client.fetch_one(query, [team_id])
    if team is not None:
        return team
    context = build_canonical_context(
        competition_id=filters.competition_id,
        competition_name=None,
        season_id=filters.season_id,
    )
    canonical_id = resolve_legacy_team_ids(
        [str(team_id)], context["seasonLabel"] if context else None,
    ).get(str(team_id))
    return db_client.fetch_one(query, [int(canonical_id)]) if canonical_id is not None else None


def _team_scope_filters_sql(team_id: int, filters: GlobalFilters) -> tuple[str, list[Any]]:
    clauses = ["1=1", "(fm.home_team_id = %s or fm.away_team_id = %s)"]
    params: list[Any] = [team_id, team_id]
    append_fact_match_filters(clauses, params, alias="fm", filters=filters)

    if filters.venue == VenueFilter.home:
        clauses.append("fm.home_team_id = %s")
        params.append(team_id)
    elif filters.venue == VenueFilter.away:
        clauses.append("fm.away_team_id = %s")
        params.append(team_id)

    return " and ".join(clauses), params


def _competition_scope_filters_sql(filters: GlobalFilters) -> tuple[str, list[Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    append_fact_match_filters(clauses, params, alias="fm", filters=filters)
    return " and ".join(clauses), params


def _section_coverage_from_match_count(match_count: int, label: str) -> dict[str, Any]:
    if match_count <= 0:
        return {"status": "empty", "percentage": 0, "label": label}

    return {"status": "complete", "percentage": 100, "label": label}


def _visual_asset_id_sql(team_id_expression: str) -> str:
    return f"""
        (
            select p.source_id
            from raw.provider_entity_map p
            where p.provider = 'legacy_dim_team'
              and p.entity_type = 'team'
              and p.canonical_id = ({team_id_expression})::text
              and p.mapping_state = 'approved'
            order by length(p.source_id), p.source_id
            limit 1
        ) as visual_asset_id
    """


def _coverage_score(coverage: dict[str, Any]) -> float | None:
    if isinstance(coverage.get("percentage"), (int, float)):
        return float(coverage["percentage"])

    status = coverage.get("status")
    if status == "complete":
        return 100.0
    if status == "empty":
        return 0.0
    if status == "partial":
        return 50.0
    return None


def _merge_coverages(label: str, coverages: list[dict[str, Any]]) -> dict[str, Any]:
    if not coverages:
        return {"status": "unknown", "label": label}

    statuses = {str(coverage.get("status") or "unknown") for coverage in coverages}
    if statuses == {"complete"}:
        status = "complete"
    elif statuses == {"empty"}:
        status = "empty"
    elif statuses == {"unknown"}:
        status = "unknown"
    else:
        status = "partial"

    payload: dict[str, Any] = {"status": status, "label": label}
    scores = [score for score in (_coverage_score(coverage) for coverage in coverages) if score is not None]
    if scores:
        payload["percentage"] = round(sum(scores) / len(scores), 2)
    return payload


def _normalize_team_name(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(character for character in normalized if not unicodedata.combining(character)).strip().casefold()


def _team_names_match(seed_name: str | None, team_name: str | None) -> bool:
    seed = _normalize_team_name(seed_name)
    team = _normalize_team_name(team_name)
    if not seed or not team:
        return False
    if seed == team:
        return True

    shorter, longer = sorted((seed, team), key=len)
    return len(shorter) >= 5 and longer.endswith(f" {shorter}")


def _load_team_honors(team_id: int | None, team_name: str | None) -> dict[str, Any] | None:
    if (team_id is None and not team_name) or not _TEAM_HONORS_PATH.exists():
        return None

    with _TEAM_HONORS_PATH.open("r", encoding="utf-8", newline="") as handle:
        champion_rows = [
            row
            for row in csv.DictReader(handle)
            if row.get("title_type") == "champion"
        ]

    rows = []
    if team_id is not None:
        canonical_team_id = str(team_id)
        rows = [row for row in champion_rows if row.get("team_id") == canonical_team_id]

    if not rows and team_name:
        rows = [
            row
            for row in champion_rows
            if _team_names_match(row.get("team_name"), team_name)
        ]

    if not rows:
        return None

    items: list[dict[str, Any]] = []
    for row in rows:
        scope = row.get("scope")
        if scope not in {"mundial", "continental", "nacional", "estadual"}:
            scope = "other"
        confidence = row.get("confidence")
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"
        year_value = row.get("year")
        year = int(year_value) if year_value and year_value.isdigit() else None
        items.append(
            {
                "competitionName": row.get("competition_name") or "Conquista documentada",
                "competitionKey": row.get("competition_family") or None,
                "scope": scope,
                "seasonLabel": row.get("season_label") or None,
                "year": year,
                "sourceName": row.get("source_name") or "unknown",
                "sourceUrl": row.get("source_url") or None,
                "confidence": confidence,
            }
        )

    return {
        "criterionLabel": _TEAM_HONORS_CRITERION,
        "total": len(items),
        "items": items,
        "coverage": {"status": "complete", "percentage": 100, "label": "Honors coverage"},
    }


def _fetch_team_profile_foundation(team_id: int, fallback_team_name: str) -> dict[str, Any]:
    row = db_client.fetch_one(
        f"""
        select
            tss.team_id,
            tss.team_name,
            tss.team_type,
            tss.country_or_territory,
            tss.stadium_name,
            tss.competition_count,
            tss.season_count,
            tss.matches_played,
            tss.first_match_at,
            tss.last_match_at,
            {_visual_asset_id_sql("tss.team_id")}
        from mart.team_serving_summary tss
        where tss.team_id = %s;
        """,
        [team_id],
    ) or {}
    team_type = row.get("team_type") if row.get("team_type") in _TEAM_TYPES else "unknown"
    official_name = row.get("team_name") or fallback_team_name
    identity_complete = bool(row) and team_type != "unknown" and bool(official_name)
    matches_played = int(row.get("matches_played") or 0)
    archive_complete = bool(row) and matches_played > 0

    return {
        "visualAssetId": row.get("visual_asset_id"),
        "identity": {
            "teamType": team_type,
            "officialName": official_name,
            "countryOrTerritory": row.get("country_or_territory"),
            "city": None,
            "foundedYear": None,
            "stadiumName": row.get("stadium_name"),
            "stadiumCapacity": None,
        },
        "archive": {
            "competitionCount": int(row.get("competition_count") or 0),
            "seasonCount": int(row.get("season_count") or 0),
            "matchesPlayed": matches_played,
            "firstMatchAt": row.get("first_match_at"),
            "lastMatchAt": row.get("last_match_at"),
        },
        "identityCoverage": {
            "status": "complete" if identity_complete else "partial",
            "percentage": 100 if identity_complete else 50,
            "label": "Team identity coverage",
        },
        "archiveCoverage": {
            "status": "complete" if archive_complete else "empty",
            "percentage": 100 if archive_complete else 0,
            "label": "Team archive coverage",
        },
    }


def _resolve_result(goals_for: int, goals_against: int) -> str:
    if goals_for > goals_against:
        return "win"
    if goals_for < goals_against:
        return "loss"
    return "draw"


def _build_team_match_scope_cte(where_sql: str) -> str:
    return f"""
        with scoped_matches as (
            select
                fm.match_id,
                fm.date_day,
                case
                    when fm.home_team_id = %s then coalesce(fm.home_goals, 0)
                    else coalesce(fm.away_goals, 0)
                end as goals_for,
                case
                    when fm.home_team_id = %s then coalesce(fm.away_goals, 0)
                    else coalesce(fm.home_goals, 0)
                end as goals_against,
                row_number() over (
                    order by fm.date_day desc, fm.match_id desc
                ) as rn_recent
            from mart.fact_matches fm
            where {where_sql}
        ),
        filtered_scoped as (
            select *
            from scoped_matches
            where (%s::int is null or rn_recent <= %s)
        )
    """


def _build_team_match_scope_params(
    team_id: int,
    where_params: list[Any],
    filters: GlobalFilters,
) -> list[Any]:
    return [team_id, team_id, *where_params, filters.last_n, filters.last_n]


@router.get("")
def get_teams(
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
    entityType: TeamType | None = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=24, ge=1, le=100),
    sortBy: TeamsSortBy = "relevance",
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
    competition_scope_sql, competition_scope_params = _competition_scope_filters_sql(global_filters)
    search_pattern = f"%{search.strip()}%" if search and search.strip() else None
    offset = (page - 1) * pageSize
    sort_column = {
        "relevance": (
            "r.season_count desc nulls last, "
            "r.competition_count desc nulls last, "
            "r.matches_played desc nulls last, "
            "r.first_match_at asc nulls last, "
            "r.last_match_at desc nulls last"
        ),
        "teamName": "r.team_name",
        "points": "r.points",
        "goalDiff": "r.goal_diff",
        "wins": "r.wins",
        "position": "r.position",
    }[sortBy]
    sort_dir = "asc" if sortDirection == "asc" else "desc"
    order_by = sort_column if sortBy == "relevance" else f"{sort_column} {sort_dir}"

    use_serving_summary = (
        global_filters.competition_id is None
        and global_filters.season_id is None
        and global_filters.round_id is None
        and global_filters.stage_id is None
        and global_filters.stage_format is None
        and global_filters.venue == VenueFilter.all
        and global_filters.last_n is None
        and global_filters.date_start is None
        and global_filters.date_end is None
        and search_pattern is None
    )

    if use_serving_summary:
        rows = db_client.fetch_all(
            f"""
            with classified as (
                select
                    tss.*,
                    {_visual_asset_id_sql("tss.team_id")},
                    coalesce(tss.team_type, 'unknown') as resolved_team_type
                from mart.team_serving_summary tss
                where (%s::text is null or tss.team_type = %s)
            ),
            ranked as (
                select
                    classified.*,
                    row_number() over (
                        order by classified.points desc, classified.goal_diff desc,
                                 classified.goals_for desc, classified.team_name asc
                    )::int as position,
                    count(*) over()::int as total_teams
                from classified
            )
            select r.*, count(*) over()::int as _total_count
            from ranked r
            order by {order_by}, r.team_id asc
            limit %s offset %s;
            """,
            [entityType, entityType, pageSize, offset],
        )
    else:
        rows = None

    home_branch = f"""
        select
            fm.home_team_id as team_id,
            coalesce(home_team.team_name, fm.home_team_id::text) as team_name,
            fm.competition_key,
            fm.season_label,
            coalesce(fm.home_goals, 0) as goals_for,
            coalesce(fm.away_goals, 0) as goals_against,
            fm.match_id,
            fm.date_day
        from mart.fact_matches fm
        left join mart.dim_team home_team
          on home_team.team_id = fm.home_team_id
        where {competition_scope_sql}
          and (%s::text is null or home_team.team_name ilike %s)
    """
    away_branch = f"""
        select
            fm.away_team_id as team_id,
            coalesce(away_team.team_name, fm.away_team_id::text) as team_name,
            fm.competition_key,
            fm.season_label,
            coalesce(fm.away_goals, 0) as goals_for,
            coalesce(fm.home_goals, 0) as goals_against,
            fm.match_id,
            fm.date_day
        from mart.fact_matches fm
        left join mart.dim_team away_team
          on away_team.team_id = fm.away_team_id
        where {competition_scope_sql}
          and (%s::text is null or away_team.team_name ilike %s)
    """
    if global_filters.venue == VenueFilter.home:
        team_rows_sql = home_branch
        team_rows_params = [*competition_scope_params, search_pattern, search_pattern]
    elif global_filters.venue == VenueFilter.away:
        team_rows_sql = away_branch
        team_rows_params = [*competition_scope_params, search_pattern, search_pattern]
    else:
        team_rows_sql = f"{home_branch} union all {away_branch}"
        team_rows_params = [
            *competition_scope_params,
            search_pattern,
            search_pattern,
            *competition_scope_params,
            search_pattern,
            search_pattern,
        ]

    query = f"""
        with team_rows as (
            {team_rows_sql}
        ),
        ranked_team_rows as (
            select
                tr.*,
                row_number() over (
                    partition by tr.team_id
                    order by tr.date_day desc, tr.match_id desc
                ) as rn_recent
            from team_rows tr
        ),
        filtered_team_rows as (
            select *
            from ranked_team_rows
            where (%s::int is null or rn_recent <= %s)
        ),
        aggregated as (
            select
                ftr.team_id,
                max(ftr.team_name) as team_name,
                count(distinct ftr.competition_key)::int as competition_count,
                count(distinct ftr.season_label)::int as season_count,
                count(*)::int as matches_played,
                min(ftr.date_day) as first_match_at,
                max(ftr.date_day) as last_match_at,
                sum(case when ftr.goals_for > ftr.goals_against then 1 else 0 end)::int as wins,
                sum(case when ftr.goals_for = ftr.goals_against then 1 else 0 end)::int as draws,
                sum(case when ftr.goals_for < ftr.goals_against then 1 else 0 end)::int as losses,
                sum(ftr.goals_for)::int as goals_for,
                sum(ftr.goals_against)::int as goals_against,
                sum(ftr.goals_for - ftr.goals_against)::int as goal_diff,
                sum(
                    case
                        when ftr.goals_for > ftr.goals_against then 3
                        when ftr.goals_for = ftr.goals_against then 1
                        else 0
                    end
                )::int as points
            from filtered_team_rows ftr
            group by ftr.team_id
        ),
        documented as (
            select
                a.*,
                {_visual_asset_id_sql("a.team_id")},
                coalesce(tss.team_type, 'unknown') as team_type,
                tss.country_or_territory,
                tss.stadium_name
            from aggregated a
            left join mart.team_serving_summary tss
              on tss.team_id = a.team_id
        ),
        ranked as (
            select
                d.*,
                row_number() over (
                    order by d.points desc, d.goal_diff desc, d.goals_for desc, d.team_name asc
                )::int as position,
                count(*) over()::int as total_teams
            from documented d
            where (%s::text is null or d.team_type = %s)
        )
        select
            r.*,
            count(*) over()::int as _total_count
        from ranked r
        order by {order_by}, r.team_id asc
        limit %s offset %s;
    """
    if rows is None:
        rows = db_client.fetch_all(
            query,
            [
                *team_rows_params,
                global_filters.last_n,
                global_filters.last_n,
                entityType,
                entityType,
                pageSize,
                offset,
            ],
        )
    total_count = int(rows[0]["_total_count"]) if rows else 0
    pagination = build_pagination(page, pageSize, total_count)
    coverage = (
        {"status": "complete", "percentage": 100, "label": "Teams list coverage"}
        if rows
        else {"status": "empty", "percentage": 0, "label": "Teams list coverage"}
    )

    show_sporting_position = (
        sortBy != "relevance"
        or global_filters.competition_id is not None
        or global_filters.season_id is not None
        or global_filters.round_id is not None
        or global_filters.stage_id is not None
        or global_filters.stage_format is not None
    )
    items = [
        {
            "teamId": str(row["team_id"]),
            "teamName": row["team_name"],
            "visualAssetId": row.get("visual_asset_id"),
            "competitionId": str(global_filters.competition_id) if global_filters.competition_id is not None else None,
            "seasonId": str(global_filters.season_id) if global_filters.season_id is not None else None,
            "teamType": row.get("resolved_team_type") or row.get("team_type") or "unknown",
            "countryOrTerritory": row.get("country_or_territory"),
            "competitionCount": int(row.get("competition_count") or 0),
            "seasonCount": int(row.get("season_count") or 0),
            "firstMatchAt": row.get("first_match_at"),
            "lastMatchAt": row.get("last_match_at"),
            "stadiumName": row.get("stadium_name"),
            "position": int(row["position"]) if show_sporting_position and row.get("position") is not None else None,
            "totalTeams": int(row["total_teams"])
            if show_sporting_position and row.get("total_teams") is not None
            else None,
            "matchesPlayed": int(row.get("matches_played") or 0),
            "wins": int(row.get("wins") or 0),
            "draws": int(row.get("draws") or 0),
            "losses": int(row.get("losses") or 0),
            "goalsFor": int(row.get("goals_for") or 0),
            "goalsAgainst": int(row.get("goals_against") or 0),
            "goalDiff": int(row.get("goal_diff") or 0),
            "points": int(row.get("points") or 0),
        }
        for row in rows
    ]

    is_filtered = any(
        (
            global_filters.competition_id is not None,
            global_filters.season_id is not None,
            global_filters.round_id is not None,
            global_filters.stage_id is not None,
            global_filters.stage_format is not None,
            global_filters.venue != VenueFilter.all,
            global_filters.last_n is not None,
            global_filters.date_start is not None,
            global_filters.date_end is not None,
            search_pattern is not None,
        )
    )

    return build_api_response(
        {"items": items, "scope": build_catalog_scope(is_filtered=is_filtered)},
        request_id=_request_id(request),
        pagination=pagination,
        coverage=coverage,
    )


@router.get("/{teamId}/contexts")
def get_team_contexts(
    teamId: str,
    request: Request,
    competitionId: str | None = None,
    seasonId: str | None = None,
) -> dict[str, Any]:
    team_id = _to_team_id(teamId)
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

    if get_settings().data_layer == "serving_v2":
        context_rows = db_client.fetch_all(
            """
            select competition_key, competition_name, season_label,
                   max(match_date) as last_match_date, count(*)::int as matches_played
            from serving_v2.match_catalog
            where home_team_id = %s or away_team_id = %s
            group by competition_key, competition_name, season_label
            order by last_match_date desc nulls last, matches_played desc, competition_key, season_label desc;
            """,
            [team_id, team_id],
        )
        available_contexts: list[dict[str, str]] = []
        seen_contexts: set[tuple[str, str]] = set()
        for row in context_rows:
            canonical_competition = get_canonical_competition_by_key(row.get("competition_key"))
            if canonical_competition is None:
                continue
            context = build_canonical_context(
                competition_id=canonical_competition.competition_id,
                competition_name=canonical_competition.default_name,
                season_id=row.get("season_label"),
            )
            if context is None:
                continue
            identity = (context["competitionId"], context["seasonId"])
            if identity in seen_contexts:
                continue
            seen_contexts.add(identity)
            available_contexts.append(context)

        if not available_contexts:
            raise AppError(
                message="Team not found.",
                code="TEAM_NOT_FOUND",
                status=404,
                details={"teamId": teamId},
            )
        return build_api_response(
            {
                "defaultContext": select_default_context(
                    available_contexts,
                    preferred_competition_id=preference_filters.competition_id,
                    preferred_season_id=preference_filters.season_id,
                ),
                "availableContexts": available_contexts,
            },
            request_id=_request_id(request),
        )

    team_ref = _fetch_team_reference(team_id, preference_filters)
    if team_ref is None:
        raise AppError(
            message="Team not found.",
            code="TEAM_NOT_FOUND",
            status=404,
            details={"teamId": teamId},
        )

    team_id = int(team_ref["team_id"])
    context_rows = db_client.fetch_all(
        """
        with team_contexts as (
            select
                dc.league_id,
                dc.league_name,
                fm.season,
                max(fm.date_day) as last_match_date,
                count(*) as matches_played
            from mart.fact_matches fm
            inner join mart.dim_competition dc
              on dc.competition_sk = fm.competition_sk
            where fm.home_team_id = %s or fm.away_team_id = %s
            group by dc.league_id, dc.league_name, fm.season
        )
        select
            league_id,
            league_name,
            season,
            last_match_date,
            matches_played
        from team_contexts
        order by
            last_match_date desc nulls last,
            matches_played desc,
            season desc,
            league_id asc;
        """,
        [team_id, team_id],
    )

    available_contexts: list[dict[str, str]] = []
    seen_contexts: set[tuple[str, str]] = set()

    for row in context_rows:
        context = build_canonical_context(
            competition_id=row.get("league_id"),
            competition_name=row.get("league_name"),
            season_id=row.get("season"),
        )
        if context is None:
            continue

        identity = (context["competitionId"], context["seasonId"])
        if identity in seen_contexts:
            continue

        seen_contexts.add(identity)
        available_contexts.append(context)

    default_context = select_default_context(
        available_contexts,
        preferred_competition_id=preference_filters.competition_id,
        preferred_season_id=preference_filters.season_id,
    )

    return build_api_response(
        {
            "defaultContext": default_context,
            "availableContexts": available_contexts,
        },
        request_id=_request_id(request),
    )


def _get_team_profile_serving_v2(
    *,
    team_id: int,
    team_id_text: str,
    request: Request,
    filters: GlobalFilters,
    include_recent_matches: bool,
    include_squad: bool,
    include_stats: bool,
    recent_matches_limit: int,
) -> dict[str, Any]:
    canonical_competition = get_canonical_competition(filters.competition_id)
    if canonical_competition is None or filters.season_id is None:
        raise AppError(
            message="Unsupported team profile context.",
            code="TEAM_CONTEXT_NOT_FOUND",
            status=404,
            details={"teamId": team_id_text},
        )

    season_label = str(filters.season_id)
    if canonical_competition.season_calendar == "split_year" and len(season_label) == 4 and season_label.isdigit():
        season_label = f"{season_label}/{int(season_label) + 1}"
    edition_key = f"{canonical_competition.competition_key}:{season_label}"

    team = db_client.fetch_one(
        """
        select team_id, team_name, country_or_territory, team_type, gender,
               category, identity_state, match_count, competition_count,
               edition_count, first_match_date, last_match_date, asset_url,
               asset_type, metadata
        from serving_v2.team_profile
        where team_id = %s and match_count > 0;
        """,
        [team_id],
    )
    edition = db_client.fetch_one(
        """
        select edition_key, competition_name, season_label, published_match_count,
               first_match_date, last_match_date
        from serving_v2.edition_catalog
        where edition_key = %s and is_selectable;
        """,
        [edition_key],
    )
    if team is None or edition is None:
        raise AppError(
            message="Team profile is unavailable for this context.",
            code="TEAM_CONTEXT_NOT_FOUND",
            status=404,
            details={"teamId": team_id_text, "editionKey": edition_key},
        )

    scope_clauses = [
        "(m.home_team_id = %s or m.away_team_id = %s)",
        "m.competition_key = %s",
        "m.edition_key = %s",
    ]
    scope_params: list[Any] = [team_id, team_id, canonical_competition.competition_key, edition_key]
    if filters.venue == VenueFilter.home:
        scope_clauses.append("m.home_team_id = %s")
        scope_params.append(team_id)
    elif filters.venue == VenueFilter.away:
        scope_clauses.append("m.away_team_id = %s")
        scope_params.append(team_id)
    if filters.date_start is not None:
        scope_clauses.append("m.match_date >= %s")
        scope_params.append(filters.date_start)
    if filters.date_end is not None:
        scope_clauses.append("m.match_date <= %s")
        scope_params.append(filters.date_end)
    scope_sql = " and ".join(scope_clauses)
    match_scope_cte = f"""
        with scoped_matches as (
            select
                m.*,
                row_number() over (order by m.match_date desc, m.match_id desc) as rn_recent
            from serving_v2.match_catalog m
            where {scope_sql}
        ), filtered_matches as (
            select *
            from scoped_matches
            where (%s::int is null or rn_recent <= %s)
        )
    """
    match_scope_params = [*scope_params, filters.last_n, filters.last_n]

    summary = db_client.fetch_one(
        f"""
        {match_scope_cte}
        select
            count(*)::int as matches_played,
            coalesce(sum(case when home_team_id = %s and home_goals > away_goals then 1
                              when away_team_id = %s and away_goals > home_goals then 1 else 0 end), 0)::int as wins,
            coalesce(sum(case when home_goals = away_goals then 1 else 0 end), 0)::int as draws,
            coalesce(sum(case when home_team_id = %s and home_goals < away_goals then 1
                              when away_team_id = %s and away_goals < home_goals then 1 else 0 end), 0)::int as losses,
            coalesce(sum(case when home_team_id = %s then home_goals else away_goals end), 0)::int as goals_for,
            coalesce(sum(case when home_team_id = %s then away_goals else home_goals end), 0)::int as goals_against
        from filtered_matches;
        """,
        [*match_scope_params, team_id, team_id, team_id, team_id, team_id, team_id],
    ) or {}
    matches_played = int(summary.get("matches_played") or 0)
    wins = int(summary.get("wins") or 0)
    draws = int(summary.get("draws") or 0)
    losses = int(summary.get("losses") or 0)
    goals_for = int(summary.get("goals_for") or 0)
    goals_against = int(summary.get("goals_against") or 0)

    standing = db_client.fetch_one(
        """
        with team_rows as (
            select home_team_id as team_id,
                   case when home_goals > away_goals then 3 when home_goals = away_goals then 1 else 0 end as points,
                   home_goals - away_goals as goal_diff,
                   home_goals as goals_for
            from serving_v2.match_catalog
            where competition_key = %s and edition_key = %s
            union all
            select away_team_id,
                   case when away_goals > home_goals then 3 when away_goals = home_goals then 1 else 0 end,
                   away_goals - home_goals,
                   away_goals
            from serving_v2.match_catalog
            where competition_key = %s and edition_key = %s
        ), totals as (
            select team_id, sum(points)::int as points, sum(goal_diff)::int as goal_diff,
                   sum(goals_for)::int as goals_for
            from team_rows
            group by team_id
        ), ranked as (
            select *, row_number() over (order by points desc, goal_diff desc, goals_for desc, team_id)::int as position,
                   count(*) over()::int as total_teams
            from totals
        )
        select position, total_teams from ranked where team_id = %s;
        """,
        [canonical_competition.competition_key, edition_key, canonical_competition.competition_key, edition_key, team_id],
    ) or {}

    recent_matches: list[dict[str, Any]] | None = None
    if include_recent_matches:
        recent_rows = db_client.fetch_all(
            f"""
            {match_scope_cte}
            select match_id::text as match_id, match_date as played_at,
                   case when home_team_id = %s then away_team_id else home_team_id end::text as opponent_team_id,
                   case when home_team_id = %s then away_team_name else home_team_name end as opponent_name,
                   case when home_team_id = %s then 'home' else 'away' end as venue_role,
                   case when home_team_id = %s then home_goals else away_goals end as goals_for,
                   case when home_team_id = %s then away_goals else home_goals end as goals_against
            from filtered_matches
            order by match_date desc, match_id desc
            limit %s;
            """,
            [*match_scope_params, team_id, team_id, team_id, team_id, team_id, recent_matches_limit],
        )
        recent_matches = [
            {
                "matchId": row["match_id"],
                "playedAt": row.get("played_at"),
                "opponentTeamId": row.get("opponent_team_id"),
                "opponentName": row.get("opponent_name"),
                "venue": row.get("venue_role"),
                "goalsFor": int(row.get("goals_for") or 0),
                "goalsAgainst": int(row.get("goals_against") or 0),
                "result": _resolve_result(int(row.get("goals_for") or 0), int(row.get("goals_against") or 0)),
            }
            for row in recent_rows
        ]

    squad: list[dict[str, Any]] | None = None
    if include_squad:
        squad_rows = db_client.fetch_all(
            f"""
            {match_scope_cte}
            select fl.player_key, max(dp.display_name) as player_name,
                   max(fl.position_name) as position_name, max(fl.jersey_number) as jersey_number,
                   count(distinct fl.match_id)::int as appearances,
                   count(distinct fl.match_id) filter (where fl.lineup_type in ('11', 'starter', 'starting'))::int as starts,
                   max(fm.match_date) as last_appearance_at
            from mart_v2.fact_lineup fl
            join filtered_matches fm on fm.match_id = fl.match_id
            join mart_v2.dim_player dp on dp.player_key = fl.player_key
            where fl.team_id = %s
            group by fl.player_key
            order by appearances desc, player_name asc;
            """,
            [*match_scope_params, team_id],
        )
        squad = [
            {
                "playerId": row.get("player_key"),
                "playerName": row.get("player_name"),
                "positionName": row.get("position_name"),
                "shirtNumber": row.get("jersey_number"),
                "appearances": int(row.get("appearances") or 0),
                "starts": int(row.get("starts") or 0),
                "minutesPlayed": None,
                "averageMinutes": None,
                "lastAppearanceAt": row.get("last_appearance_at"),
            }
            for row in squad_rows
        ]

    stats_payload: dict[str, Any] | None = None
    if include_stats:
        trend_rows = db_client.fetch_all(
            f"""
            {match_scope_cte}
            select to_char(date_trunc('month', match_date), 'YYYY-MM') as period_key,
                   extract(year from match_date)::int as period_year,
                   extract(month from match_date)::int as period_month,
                   count(*)::int as matches,
                   sum(case when (home_team_id = %s and home_goals > away_goals) or (away_team_id = %s and away_goals > home_goals) then 1 else 0 end)::int as wins,
                   sum(case when home_goals = away_goals then 1 else 0 end)::int as draws,
                   sum(case when (home_team_id = %s and home_goals < away_goals) or (away_team_id = %s and away_goals < home_goals) then 1 else 0 end)::int as losses,
                   sum(case when home_team_id = %s then home_goals else away_goals end)::int as goals_for,
                   sum(case when home_team_id = %s then away_goals else home_goals end)::int as goals_against
            from filtered_matches
            group by date_trunc('month', match_date), extract(year from match_date), extract(month from match_date)
            order by date_trunc('month', match_date) desc;
            """,
            [*match_scope_params, team_id, team_id, team_id, team_id, team_id, team_id],
        )
        stats_payload = {
            "pointsPerMatch": round((wins * 3 + draws) / matches_played, 2) if matches_played else None,
            "winRatePct": round(wins / matches_played * 100, 2) if matches_played else None,
            "goalsForPerMatch": round(goals_for / matches_played, 2) if matches_played else None,
            "goalsAgainstPerMatch": round(goals_against / matches_played, 2) if matches_played else None,
            "cleanSheets": None,
            "failedToScore": None,
            "trend": [
                {
                    "periodKey": row.get("period_key"),
                    "label": f"{int(row.get('period_month') or 0):02d}/{int(row.get('period_year') or 0)}",
                    "matches": int(row.get("matches") or 0),
                    "wins": int(row.get("wins") or 0),
                    "draws": int(row.get("draws") or 0),
                    "losses": int(row.get("losses") or 0),
                    "goalsFor": int(row.get("goals_for") or 0),
                    "goalsAgainst": int(row.get("goals_against") or 0),
                    "goalDiff": int(row.get("goals_for") or 0) - int(row.get("goals_against") or 0),
                    "points": int(row.get("wins") or 0) * 3 + int(row.get("draws") or 0),
                }
                for row in trend_rows
            ],
        }

    honors = _load_team_honors(team_id, str(team["team_name"]))
    canonical_context = build_canonical_context(
        competition_id=filters.competition_id,
        competition_name=canonical_competition.default_name,
        season_id=filters.season_id,
    )
    identity_coverage = {"status": "complete", "percentage": 100, "label": "Team identity coverage"}
    archive_coverage = _section_coverage_from_match_count(int(team["match_count"]), "Team archive coverage")
    overview_coverage = _section_coverage_from_match_count(matches_played, "Team overview coverage")
    section_coverage: dict[str, Any] = {
        "overview": overview_coverage,
        "identity": identity_coverage,
        "archive": archive_coverage,
        "honors": honors["coverage"] if honors else {"status": "empty", "percentage": 0, "label": "Honors coverage"},
    }
    if include_squad:
        section_coverage["squad"] = _section_coverage_from_match_count(len(squad or []), "Squad coverage")
    if include_stats:
        section_coverage["stats"] = _section_coverage_from_match_count(matches_played, "Team stats coverage")

    data: dict[str, Any] = {
        "identity": {
            "teamType": team.get("team_type") if team.get("team_type") in _TEAM_TYPES else "unknown",
            "officialName": team["team_name"],
            "countryOrTerritory": team.get("country_or_territory"),
            "city": None,
            "foundedYear": None,
            "stadiumName": None,
            "stadiumCapacity": None,
            "assetUrl": team.get("asset_url"),
            "assetType": team.get("asset_type"),
        },
        "archive": {
            "competitionCount": int(team.get("competition_count") or 0),
            "seasonCount": int(team.get("edition_count") or 0),
            "matchesPlayed": int(team.get("match_count") or 0),
            "firstMatchAt": team.get("first_match_date"),
            "lastMatchAt": team.get("last_match_date"),
        },
        "honors": honors,
        "team": {
            "teamId": team_id_text,
            "teamName": team["team_name"],
            "visualAssetId": team_id_text if team.get("asset_url") else None,
            "visualAssetUrl": team.get("asset_url"),
            "competitionId": str(canonical_competition.competition_id),
            "competitionName": canonical_competition.default_name,
            "seasonId": str(filters.season_id),
            "seasonLabel": canonical_context["seasonLabel"] if canonical_context else season_label,
        },
        "summary": {
            "matchesPlayed": matches_played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goalsFor": goals_for,
            "goalsAgainst": goals_against,
            "goalDiff": goals_for - goals_against,
            "points": wins * 3 + draws,
        },
        "standing": {
            "position": int(standing["position"]) if standing.get("position") is not None else None,
            "totalTeams": int(standing["total_teams"]) if standing.get("total_teams") is not None else None,
        },
        "form": [item["result"] for item in (recent_matches or [])[:5]],
        "sectionCoverage": section_coverage,
    }
    if include_recent_matches:
        data["recentMatches"] = recent_matches or []
    if include_squad:
        data["squad"] = squad or []
    if include_stats:
        data["stats"] = stats_payload or {"pointsPerMatch": None, "winRatePct": None, "goalsForPerMatch": None, "goalsAgainstPerMatch": None, "cleanSheets": None, "failedToScore": None, "trend": []}

    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=_merge_coverages(
            "Team profile coverage",
            [
                coverage
                for coverage in [overview_coverage, archive_coverage, section_coverage.get("squad"), section_coverage.get("stats")]
                if coverage is not None
            ],
        ),
    )


@router.get("/{teamId}")
def get_team_profile(
    teamId: str,
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
    includeRecentMatches: bool = True,
    includeSquad: bool = True,
    includeStats: bool = True,
    recentMatchesLimit: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    team_id = _to_team_id(teamId)
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
    _require_canonical_team_context(global_filters)

    if get_settings().data_layer == "serving_v2":
        return _get_team_profile_serving_v2(
            team_id=team_id,
            team_id_text=teamId,
            request=request,
            filters=global_filters,
            include_recent_matches=includeRecentMatches,
            include_squad=includeSquad,
            include_stats=includeStats,
            recent_matches_limit=recentMatchesLimit,
        )

    team_ref = _fetch_team_reference(team_id, global_filters)
    if team_ref is None:
        raise AppError(
            message="Team not found.",
            code="TEAM_NOT_FOUND",
            status=404,
            details={"teamId": teamId},
        )

    team_id = int(team_ref["team_id"])
    foundation = _fetch_team_profile_foundation(team_id, str(team_ref["team_name"]))
    honors = _load_team_honors(team_id, foundation["identity"]["officialName"])

    competition_ref = db_client.fetch_one(
        "select league_id, league_name from mart.dim_competition where league_id = %s;",
        [global_filters.competition_id],
    )
    canonical_context = build_canonical_context(
        competition_id=global_filters.competition_id,
        competition_name=competition_ref.get("league_name") if competition_ref else None,
        season_id=global_filters.season_id,
    )

    where_sql, where_params = _team_scope_filters_sql(team_id, global_filters)
    competition_scope_sql, competition_scope_params = _competition_scope_filters_sql(global_filters)
    match_scope_cte = _build_team_match_scope_cte(where_sql)
    match_scope_params = _build_team_match_scope_params(team_id, where_params, global_filters)

    summary_row = db_client.fetch_one(
        f"""
        {match_scope_cte}
        select
            count(*)::int as matches_played,
            sum(case when goals_for > goals_against then 1 else 0 end)::int as wins,
            sum(case when goals_for = goals_against then 1 else 0 end)::int as draws,
            sum(case when goals_for < goals_against then 1 else 0 end)::int as losses,
            sum(goals_for)::int as goals_for,
            sum(goals_against)::int as goals_against,
            sum(goals_for - goals_against)::int as goal_diff,
            sum(case when goals_against = 0 then 1 else 0 end)::int as clean_sheets,
            sum(case when goals_for = 0 then 1 else 0 end)::int as failed_to_score,
            sum(
                case
                    when goals_for > goals_against then 3
                    when goals_for = goals_against then 1
                    else 0
                end
            )::int as points
        from filtered_scoped;
        """,
        match_scope_params,
    ) or {}
    matches_played = int(summary_row.get("matches_played") or 0)

    standing_row = db_client.fetch_one(
        f"""
        with competition_matches as (
            select
                fm.home_team_id,
                fm.away_team_id,
                coalesce(fm.home_goals, 0) as home_goals,
                coalesce(fm.away_goals, 0) as away_goals
            from mart.fact_matches fm
            where {competition_scope_sql}
        ),
        standings_base as (
            select
                home_team_id as team_id,
                case
                    when home_goals > away_goals then 3
                    when home_goals = away_goals then 1
                    else 0
                end as points,
                home_goals - away_goals as goal_diff,
                home_goals as goals_for
            from competition_matches
            union all
            select
                away_team_id as team_id,
                case
                    when away_goals > home_goals then 3
                    when away_goals = home_goals then 1
                    else 0
                end as points,
                away_goals - home_goals as goal_diff,
                away_goals as goals_for
            from competition_matches
        ),
        standings as (
            select
                sb.team_id,
                sum(sb.points)::int as points,
                sum(sb.goal_diff)::int as goal_diff,
                sum(sb.goals_for)::int as goals_for
            from standings_base sb
            group by sb.team_id
        ),
        ranked as (
            select
                s.team_id,
                row_number() over (
                    order by s.points desc, s.goal_diff desc, s.goals_for desc, s.team_id asc
                )::int as position,
                count(*) over()::int as total_teams
            from standings s
        )
        select
            position,
            total_teams
        from ranked
        where team_id = %s
        limit 1;
        """,
        [*competition_scope_params, team_id],
    ) or {}

    recent_matches: list[dict[str, Any]] | None = None
    recent_match_items: list[dict[str, Any]] = []
    if includeRecentMatches:
        recent_rows = db_client.fetch_all(
            f"""
            {match_scope_cte}
            select
                fs.match_id::text as match_id,
                fs.date_day as played_at,
                case
                    when %s = fm.home_team_id then away_team.team_id
                    else home_team.team_id
                end::text as opponent_team_id,
                case
                    when %s = fm.home_team_id then away_team.team_name
                    else home_team.team_name
                end as opponent_team_name,
                case
                    when %s = fm.home_team_id then 'home'
                    else 'away'
                end as venue_role,
                fs.goals_for,
                fs.goals_against
            from filtered_scoped fs
            inner join mart.fact_matches fm
              on fm.match_id = fs.match_id
            left join mart.dim_team home_team
              on home_team.team_id = fm.home_team_id
            left join mart.dim_team away_team
              on away_team.team_id = fm.away_team_id
            order by fs.date_day desc, fs.match_id desc
            limit %s;
            """,
            [*match_scope_params, team_id, team_id, team_id, recentMatchesLimit],
        )
        recent_match_items = [
            {
                "matchId": row["match_id"],
                "playedAt": row.get("played_at"),
                "opponentTeamId": row.get("opponent_team_id"),
                "opponentName": row.get("opponent_team_name"),
                "venue": row.get("venue_role"),
                "goalsFor": int(row.get("goals_for") or 0),
                "goalsAgainst": int(row.get("goals_against") or 0),
                "result": _resolve_result(
                    int(row.get("goals_for") or 0),
                    int(row.get("goals_against") or 0),
                ),
            }
            for row in recent_rows
        ]
        recent_matches = recent_match_items[:recentMatchesLimit]

    squad: list[dict[str, Any]] | None = None
    squad_coverage: dict[str, Any] | None = None
    if includeSquad:
        squad_rows = db_client.fetch_all(
            f"""
            {match_scope_cte}
            ,
            scoped_lineups as (
                select
                    fl.player_id,
                    coalesce(dp.player_name, fl.player_name) as player_name,
                    fl.position_name,
                    fl.jersey_number,
                    coalesce(fl.is_starter, false) as is_starter,
                    coalesce(fl.minutes_played, 0) as minutes_played,
                    fl.match_id,
                    fs.date_day,
                    row_number() over (
                        partition by fl.player_id
                        order by fs.date_day desc, fl.match_id desc, fl.lineup_id desc
                    ) as rn_latest
                from mart.fact_fixture_lineups fl
                inner join filtered_scoped fs
                  on fs.match_id = fl.match_id
                left join mart.dim_player dp
                  on dp.player_id = fl.player_id
                where fl.team_id = %s
            ),
            latest_context as (
                select
                    player_id,
                    position_name,
                    jersey_number
                from scoped_lineups
                where rn_latest = 1
            ),
            aggregated as (
                select
                    sl.player_id,
                    max(sl.player_name) as player_name,
                    count(distinct sl.match_id)::int as appearances,
                    sum(case when sl.is_starter then 1 else 0 end)::int as starts,
                    sum(sl.minutes_played)::int as minutes_played,
                    round(avg(sl.minutes_played)::numeric, 2) as average_minutes,
                    max(sl.date_day) as last_appearance_at
                from scoped_lineups sl
                group by sl.player_id
            )
            select
                a.player_id::text as player_id,
                a.player_name,
                lc.position_name,
                lc.jersey_number,
                a.appearances,
                a.starts,
                a.minutes_played,
                a.average_minutes,
                a.last_appearance_at
            from aggregated a
            left join latest_context lc
              on lc.player_id = a.player_id
            order by
                a.minutes_played desc,
                a.starts desc,
                a.player_name asc;
            """,
            [*match_scope_params, team_id],
        )
        squad = [
            {
                "playerId": row.get("player_id"),
                "playerName": row.get("player_name"),
                "positionName": row.get("position_name"),
                "shirtNumber": int(row["jersey_number"]) if row.get("jersey_number") is not None else None,
                "appearances": int(row.get("appearances") or 0),
                "starts": int(row.get("starts") or 0),
                "minutesPlayed": int(row.get("minutes_played") or 0),
                "averageMinutes": float(row["average_minutes"]) if row.get("average_minutes") is not None else None,
                "lastAppearanceAt": row.get("last_appearance_at"),
            }
            for row in squad_rows
        ]

        squad_counts = db_client.fetch_one(
            f"""
            {match_scope_cte}
            ,
            available_matches as (
                select count(distinct fl.match_id)::int as available_count
                from mart.fact_fixture_lineups fl
                inner join filtered_scoped fs
                  on fs.match_id = fl.match_id
                where fl.team_id = %s
            ),
            raw_matches as (
                select count(distinct rl.fixture_id)::int as total_count
                from raw.fixture_lineups rl
                inner join filtered_scoped fs
                  on fs.match_id = rl.fixture_id
                where rl.team_id = %s
            )
            select
                coalesce((select available_count from available_matches), 0) as available_count,
                coalesce((select total_count from raw_matches), 0) as total_count;
            """,
            [*match_scope_params, team_id, team_id],
        ) or {}
        squad_coverage = build_coverage_from_counts(
            int(squad_counts.get("available_count") or 0),
            int(squad_counts.get("total_count") or 0),
            "Squad coverage",
        )

    stats_payload: dict[str, Any] | None = None
    stats_coverage: dict[str, Any] | None = None
    if includeStats:
        stats_rows = db_client.fetch_all(
            f"""
            {match_scope_cte}
            select
                to_char(date_trunc('month', fs.date_day), 'YYYY-MM') as period_key,
                extract(year from fs.date_day)::int as period_year,
                extract(month from fs.date_day)::int as period_month,
                count(*)::int as matches,
                sum(case when fs.goals_for > fs.goals_against then 1 else 0 end)::int as wins,
                sum(case when fs.goals_for = fs.goals_against then 1 else 0 end)::int as draws,
                sum(case when fs.goals_for < fs.goals_against then 1 else 0 end)::int as losses,
                sum(fs.goals_for)::int as goals_for,
                sum(fs.goals_against)::int as goals_against,
                sum(fs.goals_for - fs.goals_against)::int as goal_diff,
                sum(
                    case
                        when fs.goals_for > fs.goals_against then 3
                        when fs.goals_for = fs.goals_against then 1
                        else 0
                    end
                )::int as points
            from filtered_scoped fs
            group by
                date_trunc('month', fs.date_day),
                extract(year from fs.date_day),
                extract(month from fs.date_day)
            order by
                date_trunc('month', fs.date_day) desc;
            """,
            match_scope_params,
        )
        stats_payload = {
            "pointsPerMatch": round(int(summary_row.get("points") or 0) / matches_played, 2)
            if matches_played > 0
            else None,
            "winRatePct": round((int(summary_row.get("wins") or 0) / matches_played) * 100, 2)
            if matches_played > 0
            else None,
            "goalsForPerMatch": round(int(summary_row.get("goals_for") or 0) / matches_played, 2)
            if matches_played > 0
            else None,
            "goalsAgainstPerMatch": round(int(summary_row.get("goals_against") or 0) / matches_played, 2)
            if matches_played > 0
            else None,
            "cleanSheets": int(summary_row.get("clean_sheets") or 0),
            "failedToScore": int(summary_row.get("failed_to_score") or 0),
            "trend": [
                {
                    "periodKey": row.get("period_key"),
                    "label": f"{int(row.get('period_month') or 0):02d}/{int(row.get('period_year') or 0)}",
                    "matches": int(row.get("matches") or 0),
                    "wins": int(row.get("wins") or 0),
                    "draws": int(row.get("draws") or 0),
                    "losses": int(row.get("losses") or 0),
                    "goalsFor": int(row.get("goals_for") or 0),
                    "goalsAgainst": int(row.get("goals_against") or 0),
                    "goalDiff": int(row.get("goal_diff") or 0),
                    "points": int(row.get("points") or 0),
                }
                for row in stats_rows
            ],
        }
        stats_coverage = _section_coverage_from_match_count(matches_played, "Team stats coverage")

    overview_coverage = _section_coverage_from_match_count(matches_played, "Team overview coverage")
    data: dict[str, Any] = {
        "identity": foundation["identity"],
        "archive": foundation["archive"],
        "honors": honors,
        "team": {
            "teamId": str(team_ref["team_id"]),
            "teamName": team_ref["team_name"],
            "visualAssetId": foundation.get("visualAssetId"),
            "competitionId": str(global_filters.competition_id),
            "competitionName": canonical_context["competitionName"]
            if canonical_context
            else competition_ref.get("league_name") if competition_ref else str(global_filters.competition_id),
            "seasonId": str(global_filters.season_id),
            "seasonLabel": canonical_context["seasonLabel"]
            if canonical_context
            else str(global_filters.season_id),
        },
        "summary": {
            "matchesPlayed": matches_played,
            "wins": int(summary_row.get("wins") or 0),
            "draws": int(summary_row.get("draws") or 0),
            "losses": int(summary_row.get("losses") or 0),
            "goalsFor": int(summary_row.get("goals_for") or 0),
            "goalsAgainst": int(summary_row.get("goals_against") or 0),
            "goalDiff": int(summary_row.get("goal_diff") or 0),
            "points": int(summary_row.get("points") or 0),
        },
        "standing": {
            "position": int(standing_row["position"]) if standing_row.get("position") is not None else None,
            "totalTeams": int(standing_row["total_teams"]) if standing_row.get("total_teams") is not None else None,
        },
        "form": [
            result
            for result in (match.get("result") for match in recent_match_items[:5])
            if isinstance(result, str)
        ],
        "sectionCoverage": {
            "overview": overview_coverage,
            "identity": foundation["identityCoverage"],
            "archive": foundation["archiveCoverage"],
            "honors": honors["coverage"]
            if honors
            else {"status": "empty", "percentage": 0, "label": "Honors coverage"},
        },
    }

    if includeRecentMatches:
        data["recentMatches"] = recent_matches or []
    if includeSquad:
        data["squad"] = squad or []
        data["sectionCoverage"]["squad"] = squad_coverage or {"status": "unknown", "label": "Squad coverage"}
    if includeStats:
        data["stats"] = stats_payload or {
            "pointsPerMatch": None,
            "winRatePct": None,
            "goalsForPerMatch": None,
            "goalsAgainstPerMatch": None,
            "cleanSheets": 0,
            "failedToScore": 0,
            "trend": [],
        }
        data["sectionCoverage"]["stats"] = stats_coverage or {
            "status": "unknown",
            "label": "Team stats coverage",
        }

    aggregate_coverage = _merge_coverages(
        "Team profile coverage",
        [
            coverage
            for coverage in [
                overview_coverage,
                squad_coverage if includeSquad else None,
                stats_coverage if includeStats else None,
            ]
            if coverage is not None
        ],
    )

    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=aggregate_coverage,
    )
