from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Query, Request

from ..core.context_registry import build_canonical_context
from ..core.contracts import build_api_response, build_coverage_from_counts, build_pagination
from ..core.errors import AppError
from ..core.filters import GlobalFilters, VenueFilter, append_fact_match_filters, validate_and_build_global_filters
from ..core.config import get_settings
from ..db.client import db_client

router = APIRouter(prefix="/api/v1/coaches", tags=["coaches"])

ADJUSTED_PPM_PRIOR_MATCHES = 10
PRODUCT_DATA_CUTOFF = get_settings().product_data_cutoff
COACHES_DATA_CUTOFF_SQL = f"date '{PRODUCT_DATA_CUTOFF.isoformat()}'"

CoachesSortBy = Literal["coachName", "teamName", "matches", "adjustedPpm", "pointsPerMatch", "wins", "startDate"]
SortDirection = Literal["asc", "desc"]


def _coach_name_sql(*, include_pending_placeholder: bool) -> str:
    resolved_name_sql = """
        coalesce(
            nullif(trim(dc.coach_name), ''),
            nullif(trim(rc.coach_name), ''),
            case
                when lower(trim(tc.coach_name)) like 'not applicable %%' then null
                else nullif(trim(tc.coach_name), '')
            end,
            nullif(
                trim(concat_ws(
                    ' ',
                    case
                        when lower(trim(tc.payload->>'given_name')) in ('not applicable', 'n/a', 'na') then null
                        else nullif(trim(tc.payload->>'given_name'), '')
                    end,
                    nullif(trim(tc.payload->>'family_name'), '')
                )),
                ''
            )
        )
    """

    if not include_pending_placeholder:
        return resolved_name_sql

    return f"coalesce({resolved_name_sql}, concat('Nome pendente #', tc.coach_id::text))"


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _to_coach_id(coach_id: str) -> int:
    try:
        return int(coach_id)
    except ValueError as exc:
        raise AppError(
            message="Invalid coach id. Expected integer-compatible identifier.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"coachId": coach_id},
        ) from exc


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


def _coach_match_scope_filters_sql(
    filters: GlobalFilters,
    *,
    tenure_alias: str,
) -> tuple[str, list[Any]]:
    where_clauses = ["1=1"]
    params: list[Any] = []
    append_fact_match_filters(where_clauses, params, alias="fm", filters=filters)

    if filters.venue == VenueFilter.home:
        where_clauses.append(f"fm.home_team_id = {tenure_alias}.team_id")
    elif filters.venue == VenueFilter.away:
        where_clauses.append(f"fm.away_team_id = {tenure_alias}.team_id")

    return " and ".join(where_clauses), params


def _build_match_scope_ctes(where_sql: str, *, tenure_source: str = "filtered_tenures") -> str:
    return f"""
        match_candidate_tenures as (
            select
                ft.*,
                exists (
                    select 1
                    from {tenure_source} peer
                    where peer.team_id = ft.team_id
                      and peer.coach_tenure_id <> ft.coach_tenure_id
                      and peer.position_id = 221
                      and daterange(coalesce(peer.start_date, date '1900-01-01'), coalesce(peer.end_date, {COACHES_DATA_CUTOFF_SQL}), '[]')
                          && daterange(coalesce(ft.start_date, date '1900-01-01'), coalesce(ft.end_date, {COACHES_DATA_CUTOFF_SQL}), '[]')
                ) as has_head_coach_overlap
            from {tenure_source} ft
        ),
        base_scoped_matches as (
            select
                ft.coach_id,
                ft.coach_tenure_id,
                ft.team_id,
                ft.position_id,
                ft.active,
                ft.temporary,
                ft.start_date,
                ft.end_date,
                ft.payload,
                fm.match_id,
                fm.date_day,
                fm.league_id,
                null::text as league_name,
                fm.season,
                case
                    when fm.home_team_id = ft.team_id and coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0) then 'W'
                    when fm.away_team_id = ft.team_id and coalesce(fm.away_goals, 0) > coalesce(fm.home_goals, 0) then 'W'
                    when coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 'D'
                    else 'L'
                end as result,
                case
                    when fm.home_team_id = ft.team_id and coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0) then 3
                    when fm.away_team_id = ft.team_id and coalesce(fm.away_goals, 0) > coalesce(fm.home_goals, 0) then 3
                    when coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 1
                    else 0
                end as points,
                case
                    when fm.home_team_id = ft.team_id then coalesce(fm.home_goals, 0)
                    else coalesce(fm.away_goals, 0)
                end as goals_for,
                case
                    when fm.home_team_id = ft.team_id then coalesce(fm.away_goals, 0)
                    else coalesce(fm.home_goals, 0)
                end as goals_against
            from match_candidate_tenures ft
            inner join mart.fact_matches fm
              on (fm.home_team_id = ft.team_id or fm.away_team_id = ft.team_id)
             and fm.date_day >= coalesce(ft.start_date, date '1900-01-01')
             and fm.date_day <= coalesce(ft.end_date, date '2999-12-31')
             and fm.date_day <= {COACHES_DATA_CUTOFF_SQL}
            where {where_sql}
              and (
                ft.payload->>'edition_key' is null
                or (
                    fm.competition_key = split_part(ft.payload->>'edition_key', '__', 1)
                    and fm.season::text = split_part(ft.payload->>'edition_key', '__', 2)
                )
              )
              and (
                ft.position_id is null
                or ft.position_id <> 560
                or coalesce(ft.active, false)
                or coalesce(ft.temporary, false)
                or not ft.has_head_coach_overlap
              )
        ),
        ranked_match_candidates as (
            select
                bsm.*,
                row_number() over (
                    partition by bsm.match_id, bsm.team_id
                    order by
                        case
                            when bsm.position_id = 221 then 0
                            when bsm.payload->>'coach_tenure_scope' = 'edition_scoped_manager_appointment' then 0
                            when coalesce(bsm.temporary, false) then 1
                            when coalesce(bsm.active, false) then 2
                            else 3
                        end,
                        coalesce(bsm.start_date, date '1900-01-01') desc,
                        coalesce(bsm.end_date, {COACHES_DATA_CUTOFF_SQL}) asc,
                        bsm.coach_tenure_id desc
                ) as rn_match_owner
            from base_scoped_matches bsm
        ),
        owned_scoped_matches as (
            select *
            from ranked_match_candidates
            where rn_match_owner = 1
        ),
        ranked_matches as (
            select
                bsm.*,
                row_number() over (
                    partition by bsm.coach_id
                    order by bsm.date_day desc, bsm.match_id desc
                ) as rn_recent
            from owned_scoped_matches bsm
        ),
        filtered_matches as (
            select *
            from ranked_matches
            where (%s::int is null or rn_recent <= %s)
        )
    """


def _serialize_context(
    competition_id: Any,
    competition_name: Any,
    season_id: Any,
) -> dict[str, str] | None:
    if competition_id is None or season_id is None:
        return None

    return build_canonical_context(
        competition_id=int(competition_id),
        competition_name=str(competition_name) if competition_name is not None else None,
        season_id=season_id,
    )


def _directory_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"status": "unknown", "label": "Coach directory coverage"}

    return build_coverage_from_counts(
        sum(1 for row in rows if _to_int(row.get("matches")) > 0),
        len(rows),
        "Coach directory coverage",
    )


def _profile_coverage(total_matches: int) -> dict[str, Any]:
    if total_matches > 0:
        return {"status": "complete", "percentage": 100, "label": "Coach profile coverage"}

    return {"status": "partial", "percentage": 0, "label": "Coach profile coverage"}


@router.get("")
def get_coaches(
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
    minMatches: int = Query(default=1, ge=0),
    includeUnknown: bool = False,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=24, ge=1, le=100),
    sortBy: CoachesSortBy = "adjustedPpm",
    sortDirection: SortDirection = "desc",
) -> dict[str, Any]:
    filters = validate_and_build_global_filters(
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
    search_pattern = f"%{search.strip()}%" if search and search.strip() else None
    offset = (page - 1) * pageSize
    sort_column = {
        "coachName": "coach_name",
        "teamName": "team_name",
        "matches": "matches",
        "adjustedPpm": "adjusted_ppm",
        "pointsPerMatch": "points_per_match",
        "wins": "wins",
        "startDate": "start_date",
    }[sortBy]
    sort_dir = "asc" if sortDirection == "asc" else "desc"
    order_by_sql = (
        f"adjusted_ppm {sort_dir} nulls last, matches desc, active desc, points_per_match desc nulls last, coach_name asc, coach_id asc"
        if sortBy == "adjustedPpm"
        else f"{sort_column} {sort_dir} nulls last, coach_name asc, coach_id asc"
    )
    match_where_sql, match_where_params = _coach_match_scope_filters_sql(filters, tenure_alias="ft")
    coach_name_sql = _coach_name_sql(include_pending_placeholder=True)
    resolved_coach_name_sql = _coach_name_sql(include_pending_placeholder=False)

    query = f"""
        with filtered_tenures as (
            select
                tc.provider,
                tc.coach_tenure_id,
                tc.coach_id,
                {coach_name_sql} as coach_name,
                coalesce(nullif(trim(dc.image_path), ''), nullif(trim(rc.image_path), '')) as photo_url,
                (
                    coalesce(dc.has_real_photo, false)
                    or (
                        nullif(trim(rc.image_path), '') is not null
                        and rc.image_path not ilike '%%placeholder%%'
                    )
                ) as has_real_photo,
                tc.team_id,
                coalesce(nullif(trim(tc.team_name), ''), concat('Unknown Team #', tc.team_id::text)) as team_name,
                (
                    tc.start_date is not null
                    and tc.start_date <= {COACHES_DATA_CUTOFF_SQL}
                    and (tc.end_date is null or tc.end_date > {COACHES_DATA_CUTOFF_SQL})
                ) as active,
                coalesce(tc.temporary, false) as temporary,
                tc.position_id,
                tc.start_date,
                case
                    when tc.start_date is not null and (tc.end_date is null or tc.end_date > {COACHES_DATA_CUTOFF_SQL})
                        then {COACHES_DATA_CUTOFF_SQL}
                    else tc.end_date
                end as end_date,
                tc.payload
            from mart.stg_team_coaches tc
            left join mart.dim_coach dc
              on dc.provider = tc.provider
             and dc.coach_id = tc.coach_id
            left join raw.coaches rc
              on rc.provider = tc.provider
             and rc.coach_id = tc.coach_id
            where tc.coach_id is not null
              and (tc.start_date is null or tc.end_date is null or tc.start_date <= tc.end_date)
              and (tc.start_date is null or tc.start_date <= {COACHES_DATA_CUTOFF_SQL})
              and (
                %s::boolean
                or {resolved_coach_name_sql} is not null
              )
              and (
                %s::text is null
                or {coach_name_sql} ilike %s
                or coalesce(nullif(trim(tc.team_name), ''), concat('Unknown Team #', tc.team_id::text)) ilike %s
              )
        ),
        {_build_match_scope_ctes(match_where_sql)},
        tenure_stats as (
            select
                ft.provider,
                ft.coach_tenure_id,
                ft.coach_id,
                ft.coach_name,
                ft.photo_url,
                ft.has_real_photo,
                ft.team_id,
                ft.team_name,
                ft.active,
                ft.temporary,
                ft.start_date,
                ft.end_date,
                count(distinct fm.match_id) as matches,
                coalesce(sum(case when fm.result = 'W' then 1 else 0 end), 0) as wins,
                coalesce(sum(case when fm.result = 'D' then 1 else 0 end), 0) as draws,
                coalesce(sum(case when fm.result = 'L' then 1 else 0 end), 0) as losses,
                coalesce(sum(fm.points), 0) as points,
                coalesce(sum(fm.goals_for), 0) as goals_for,
                coalesce(sum(fm.goals_against), 0) as goals_against,
                max(fm.date_day) as last_match_date
            from filtered_tenures ft
            left join filtered_matches fm
              on fm.coach_tenure_id = ft.coach_tenure_id
            group by
                ft.provider,
                ft.coach_tenure_id,
                ft.coach_id,
                ft.coach_name,
                ft.photo_url,
                ft.has_real_photo,
                ft.team_id,
                ft.team_name,
                ft.active,
                ft.temporary,
                ft.start_date,
                ft.end_date
        ),
        latest_tenure as (
            select distinct on (ts.coach_id)
                ts.coach_id,
                ts.team_id,
                ts.team_name,
                ts.active,
                ts.temporary,
                ts.start_date,
                ts.end_date
            from tenure_stats ts
            order by
                ts.coach_id,
                (ts.matches > 0) desc,
                ts.last_match_date desc nulls last,
                ts.active desc,
                coalesce(ts.end_date, date '2999-12-31') desc,
                coalesce(ts.start_date, date '1900-01-01') desc,
                ts.coach_tenure_id desc
        ),
        latest_context as (
            select distinct on (fm.coach_id)
                fm.coach_id,
                fm.league_id,
                null::text as league_name,
                fm.season
            from filtered_matches fm
            order by fm.coach_id, fm.date_day desc, fm.match_id desc
        ),
        final_rows as (
            select
                ts.coach_id,
                max(ts.coach_name) as coach_name,
                max(ts.photo_url) filter (where ts.photo_url is not null) as photo_url,
                bool_or(ts.has_real_photo) as has_real_photo,
                count(distinct ts.coach_tenure_id) as tenure_count,
                coalesce(sum(case when ts.active then 1 else 0 end), 0) as active_tenures,
                coalesce(sum(ts.matches), 0) as matches,
                coalesce(sum(ts.wins), 0) as wins,
                coalesce(sum(ts.draws), 0) as draws,
                coalesce(sum(ts.losses), 0) as losses,
                coalesce(sum(ts.points), 0) as points,
                coalesce(sum(ts.goals_for), 0) as goals_for,
                coalesce(sum(ts.goals_against), 0) as goals_against,
                case
                    when coalesce(sum(ts.matches), 0) > 0 then round(sum(ts.points)::numeric / sum(ts.matches), 4)
                    else null
                end as points_per_match,
                max(ts.last_match_date) as last_match_date,
                lt.team_id,
                lt.team_name,
                lt.active,
                lt.temporary,
                lt.start_date,
                lt.end_date,
                lc.league_id,
                lc.league_name,
                lc.season
            from tenure_stats ts
            left join latest_tenure lt
              on lt.coach_id = ts.coach_id
            left join latest_context lc
              on lc.coach_id = ts.coach_id
            group by
                ts.coach_id,
                lt.team_id,
                lt.team_name,
                lt.active,
                lt.temporary,
                lt.start_date,
                lt.end_date,
                lc.league_id,
                lc.league_name,
                lc.season
        ),
        scope_average as (
            select
                avg(case when fr.matches > 0 then fr.points::numeric / fr.matches end) as avg_points_per_match
            from final_rows fr
            where fr.matches > 0
        ),
        ranked_rows as (
            select
                fr.*,
                case
                    when fr.matches > 0 and sa.avg_points_per_match is not null then round(
                        (fr.points::numeric + (%s::numeric * sa.avg_points_per_match))
                        / (fr.matches + %s::numeric),
                        4
                    )
                    else null
                end as adjusted_ppm
            from final_rows fr
            cross join scope_average sa
        )
        select
            coach_id,
            coach_name,
            photo_url,
            has_real_photo,
            tenure_count,
            active_tenures,
            matches,
            wins,
            draws,
            losses,
            points,
            goals_for,
            goals_against,
            adjusted_ppm,
            points_per_match,
            last_match_date,
            team_id,
            team_name,
            active,
            temporary,
            start_date,
            end_date,
            league_id,
            league_name,
            season,
            count(*) over() as _total_count
        from ranked_rows
        where matches >= %s
        order by {order_by_sql}
        limit %s offset %s;
    """
    rows = db_client.fetch_all(
        query,
        [
            includeUnknown,
            search_pattern,
            search_pattern,
            search_pattern,
            *match_where_params,
            filters.last_n,
            filters.last_n,
            ADJUSTED_PPM_PRIOR_MATCHES,
            ADJUSTED_PPM_PRIOR_MATCHES,
            minMatches,
            pageSize,
            offset,
        ],
    )

    items = [
        {
            "coachId": str(row["coach_id"]),
            "coachName": row.get("coach_name"),
            "photoUrl": _to_text(row.get("photo_url")),
            "hasRealPhoto": bool(row.get("has_real_photo")),
            "teamId": str(row["team_id"]) if row.get("team_id") is not None else None,
            "teamName": row.get("team_name"),
            "active": bool(row.get("active")),
            "temporary": bool(row.get("temporary")),
            "tenureCount": _to_int(row.get("tenure_count")),
            "activeTenures": _to_int(row.get("active_tenures")),
            "matches": _to_int(row.get("matches")),
            "wins": _to_int(row.get("wins")),
            "draws": _to_int(row.get("draws")),
            "losses": _to_int(row.get("losses")),
            "points": _to_int(row.get("points")),
            "goalsFor": _to_int(row.get("goals_for")),
            "goalsAgainst": _to_int(row.get("goals_against")),
            "goalDiff": _to_int(row.get("goals_for")) - _to_int(row.get("goals_against")),
            "adjustedPpm": _to_float(row.get("adjusted_ppm")),
            "pointsPerMatch": _to_float(row.get("points_per_match")),
            "lastMatchDate": row.get("last_match_date"),
            "startDate": row.get("start_date"),
            "endDate": row.get("end_date"),
            "context": _serialize_context(row.get("league_id"), row.get("league_name"), row.get("season")),
        }
        for row in rows
    ]
    total_count = _to_int(rows[0].get("_total_count")) if rows else 0

    return build_api_response(
        {"items": items},
        request_id=_request_id(request),
        pagination=build_pagination(page, pageSize, total_count),
        coverage=_directory_coverage(rows),
    )


@router.get("/{coachId}")
def get_coach_profile(
    coachId: str,
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
) -> dict[str, Any]:
    normalized_coach_id = _to_coach_id(coachId)
    filters = validate_and_build_global_filters(
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
    match_where_sql, match_where_params = _coach_match_scope_filters_sql(filters, tenure_alias="ft")
    coach_name_sql = _coach_name_sql(include_pending_placeholder=True)

    query = f"""
        with all_filtered_tenures as (
            select
                tc.provider,
                tc.coach_tenure_id,
                tc.coach_id,
                {coach_name_sql} as coach_name,
                coalesce(nullif(trim(dc.image_path), ''), nullif(trim(rc.image_path), '')) as photo_url,
                (
                    coalesce(dc.has_real_photo, false)
                    or (
                        nullif(trim(rc.image_path), '') is not null
                        and rc.image_path not ilike '%%placeholder%%'
                    )
                ) as has_real_photo,
                tc.team_id,
                coalesce(nullif(trim(tc.team_name), ''), concat('Unknown Team #', tc.team_id::text)) as team_name,
                (
                    tc.start_date is not null
                    and tc.start_date <= {COACHES_DATA_CUTOFF_SQL}
                    and (tc.end_date is null or tc.end_date > {COACHES_DATA_CUTOFF_SQL})
                ) as active,
                coalesce(tc.temporary, false) as temporary,
                tc.position_id,
                tc.start_date,
                case
                    when tc.start_date is not null and (tc.end_date is null or tc.end_date > {COACHES_DATA_CUTOFF_SQL})
                        then {COACHES_DATA_CUTOFF_SQL}
                    else tc.end_date
                end as end_date,
                tc.payload
            from mart.stg_team_coaches tc
            left join mart.dim_coach dc
              on dc.provider = tc.provider
             and dc.coach_id = tc.coach_id
            left join raw.coaches rc
              on rc.provider = tc.provider
             and rc.coach_id = tc.coach_id
            where tc.coach_id is not null
              and (tc.start_date is null or tc.end_date is null or tc.start_date <= tc.end_date)
              and (tc.start_date is null or tc.start_date <= {COACHES_DATA_CUTOFF_SQL})
        ),
        filtered_tenures as (
            select *
            from all_filtered_tenures
            where coach_id = %s
        ),
        {_build_match_scope_ctes(match_where_sql, tenure_source="all_filtered_tenures")},
        all_tenure_stats as (
            select
                ft.provider,
                ft.coach_tenure_id,
                ft.coach_id,
                ft.coach_name,
                ft.photo_url,
                ft.has_real_photo,
                ft.team_id,
                ft.team_name,
                ft.active,
                ft.temporary,
                ft.start_date,
                ft.end_date,
                count(distinct fm.match_id) as matches,
                coalesce(sum(case when fm.result = 'W' then 1 else 0 end), 0) as wins,
                coalesce(sum(case when fm.result = 'D' then 1 else 0 end), 0) as draws,
                coalesce(sum(case when fm.result = 'L' then 1 else 0 end), 0) as losses,
                coalesce(sum(fm.points), 0) as points,
                coalesce(sum(fm.goals_for), 0) as goals_for,
                coalesce(sum(fm.goals_against), 0) as goals_against,
                max(fm.date_day) as last_match_date
            from all_filtered_tenures ft
            left join filtered_matches fm
              on fm.coach_tenure_id = ft.coach_tenure_id
            group by
                ft.provider,
                ft.coach_tenure_id,
                ft.coach_id,
                ft.coach_name,
                ft.photo_url,
                ft.has_real_photo,
                ft.team_id,
                ft.team_name,
                ft.active,
                ft.temporary,
                ft.start_date,
                ft.end_date
        ),
        tenure_stats as (
            select *
            from all_tenure_stats
            where coach_id = %s
        ),
        latest_tenure as (
            select distinct on (ts.coach_id)
                ts.coach_id,
                ts.team_id,
                ts.team_name,
                ts.active,
                ts.temporary,
                ts.start_date,
                ts.end_date
            from tenure_stats ts
            order by
                ts.coach_id,
                (ts.matches > 0) desc,
                ts.last_match_date desc nulls last,
                ts.active desc,
                coalesce(ts.end_date, date '2999-12-31') desc,
                coalesce(ts.start_date, date '1900-01-01') desc,
                ts.coach_tenure_id desc
        ),
        latest_context as (
            select distinct on (fm.coach_tenure_id)
                fm.coach_tenure_id,
                fm.league_id,
                null::text as league_name,
                fm.season
            from filtered_matches fm
            order by fm.coach_tenure_id, fm.date_day desc, fm.match_id desc
        ),
        coach_scope_summary as (
            select
                ats.coach_id,
                coalesce(sum(ats.matches), 0) as matches,
                coalesce(sum(ats.points), 0) as points
            from all_tenure_stats ats
            group by ats.coach_id
        ),
        scope_average as (
            select
                avg(case when css.matches > 0 then css.points::numeric / css.matches end) as avg_points_per_match
            from coach_scope_summary css
            where css.matches > 0
        ),
        coach_summary as (
            select
                ts.coach_id,
                max(ts.coach_name) as coach_name,
                max(ts.photo_url) filter (where ts.photo_url is not null) as photo_url,
                bool_or(ts.has_real_photo) as has_real_photo,
                count(distinct ts.coach_tenure_id) as tenure_count,
                coalesce(sum(case when ts.active then 1 else 0 end), 0) as active_tenures,
                count(distinct ts.team_id) as teams_count,
                coalesce(sum(ts.matches), 0) as matches,
                coalesce(sum(ts.wins), 0) as wins,
                coalesce(sum(ts.draws), 0) as draws,
                coalesce(sum(ts.losses), 0) as losses,
                coalesce(sum(ts.points), 0) as points,
                coalesce(sum(ts.goals_for), 0) as goals_for,
                coalesce(sum(ts.goals_against), 0) as goals_against,
                max(ts.last_match_date) as last_match_date,
                case
                    when coalesce(sum(ts.matches), 0) > 0 and max(sa.avg_points_per_match) is not null then round(
                        (coalesce(sum(ts.points), 0)::numeric + (%s::numeric * max(sa.avg_points_per_match)))
                        / (coalesce(sum(ts.matches), 0) + %s::numeric),
                        4
                    )
                    else null
                end as adjusted_ppm
            from tenure_stats ts
            cross join scope_average sa
            group by ts.coach_id
        )
        select
            cs.coach_id,
            cs.coach_name,
            cs.photo_url,
            cs.has_real_photo,
            cs.tenure_count,
            cs.active_tenures,
            cs.teams_count,
            cs.matches as total_matches,
            cs.wins as total_wins,
            cs.draws as total_draws,
            cs.losses as total_losses,
            cs.points as total_points,
            cs.goals_for as total_goals_for,
            cs.goals_against as total_goals_against,
            cs.adjusted_ppm as total_adjusted_ppm,
            case
                when cs.matches > 0 then round(cs.points::numeric / cs.matches, 4)
                else null
            end as total_points_per_match,
            cs.last_match_date as total_last_match_date,
            lt.team_id as current_team_id,
            lt.team_name as current_team_name,
            lt.active as current_active,
            lt.temporary as current_temporary,
            lt.start_date as current_start_date,
            lt.end_date as current_end_date,
            ts.coach_tenure_id,
            ts.team_id,
            ts.team_name,
            ts.active,
            ts.temporary,
            ts.start_date,
            ts.end_date,
            ts.matches,
            ts.wins,
            ts.draws,
            ts.losses,
            ts.points,
            ts.goals_for,
            ts.goals_against,
            case
                when ts.matches > 0 then round(ts.points::numeric / ts.matches, 4)
                else null
            end as points_per_match,
            ts.last_match_date,
            lc.league_id,
            lc.league_name,
            lc.season
        from coach_summary cs
        inner join tenure_stats ts
          on ts.coach_id = cs.coach_id
        left join latest_tenure lt
          on lt.coach_id = cs.coach_id
        left join latest_context lc
          on lc.coach_tenure_id = ts.coach_tenure_id
        order by
            ts.active desc,
            coalesce(ts.end_date, date '2999-12-31') desc,
            coalesce(ts.start_date, date '1900-01-01') desc,
            ts.coach_tenure_id desc;
    """
    rows = db_client.fetch_all(
        query,
        [
            normalized_coach_id,
            *match_where_params,
            filters.last_n,
            filters.last_n,
            normalized_coach_id,
            ADJUSTED_PPM_PRIOR_MATCHES,
            ADJUSTED_PPM_PRIOR_MATCHES,
        ],
    )

    if not rows:
        raise AppError(
            message="Coach not found.",
            code="NOT_FOUND",
            status=404,
            details={"coachId": coachId},
        )

    first_row = rows[0]
    total_matches = _to_int(first_row.get("total_matches"))
    tenures = [
        {
            "coachTenureId": str(row["coach_tenure_id"]),
            "teamId": str(row["team_id"]) if row.get("team_id") is not None else None,
            "teamName": row.get("team_name"),
            "active": bool(row.get("active")),
            "temporary": bool(row.get("temporary")),
            "startDate": row.get("start_date"),
            "endDate": row.get("end_date"),
            "matches": _to_int(row.get("matches")),
            "wins": _to_int(row.get("wins")),
            "draws": _to_int(row.get("draws")),
            "losses": _to_int(row.get("losses")),
            "points": _to_int(row.get("points")),
            "goalsFor": _to_int(row.get("goals_for")),
            "goalsAgainst": _to_int(row.get("goals_against")),
            "goalDiff": _to_int(row.get("goals_for")) - _to_int(row.get("goals_against")),
            "pointsPerMatch": _to_float(row.get("points_per_match")),
            "lastMatchDate": row.get("last_match_date"),
            "context": _serialize_context(row.get("league_id"), row.get("league_name"), row.get("season")),
        }
        for row in rows
    ]

    profile = {
        "coach": {
            "coachId": str(first_row["coach_id"]),
            "coachName": first_row.get("coach_name"),
            "photoUrl": _to_text(first_row.get("photo_url")),
            "hasRealPhoto": bool(first_row.get("has_real_photo")),
            "teamId": str(first_row["current_team_id"]) if first_row.get("current_team_id") is not None else None,
            "teamName": first_row.get("current_team_name"),
            "active": bool(first_row.get("current_active")),
            "temporary": bool(first_row.get("current_temporary")),
            "startDate": first_row.get("current_start_date"),
            "endDate": first_row.get("current_end_date"),
            "lastMatchDate": first_row.get("total_last_match_date"),
        },
        "summary": {
            "tenureCount": _to_int(first_row.get("tenure_count")),
            "activeTenures": _to_int(first_row.get("active_tenures")),
            "teamsCount": _to_int(first_row.get("teams_count")),
            "matches": total_matches,
            "wins": _to_int(first_row.get("total_wins")),
            "draws": _to_int(first_row.get("total_draws")),
            "losses": _to_int(first_row.get("total_losses")),
            "points": _to_int(first_row.get("total_points")),
            "goalsFor": _to_int(first_row.get("total_goals_for")),
            "goalsAgainst": _to_int(first_row.get("total_goals_against")),
            "goalDiff": _to_int(first_row.get("total_goals_for")) - _to_int(first_row.get("total_goals_against")),
            "adjustedPpm": _to_float(first_row.get("total_adjusted_ppm")),
            "pointsPerMatch": _to_float(first_row.get("total_points_per_match")),
        },
        "tenures": tenures,
        "sectionCoverage": {
            "overview": {
                "status": "complete" if total_matches > 0 else "partial",
                "percentage": 100 if total_matches > 0 else 0,
                "label": "Coach overview coverage",
            },
            "tenures": build_coverage_from_counts(
                len(tenures),
                len(tenures),
                "Coach tenure coverage",
            ),
        },
    }

    return build_api_response(
        profile,
        request_id=_request_id(request),
        coverage=_profile_coverage(total_matches),
    )
