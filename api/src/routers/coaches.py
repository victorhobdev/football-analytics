from __future__ import annotations

from datetime import date
import re
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
COACHES_DATA_START = date(2020, 1, 1)
PRODUCT_DATA_CUTOFF = get_settings().product_data_cutoff
COACHES_DATA_START_SQL = f"date '{COACHES_DATA_START.isoformat()}'"
COACHES_DATA_CUTOFF_SQL = f"date '{PRODUCT_DATA_CUTOFF.isoformat()}'"

CoachesSortBy = Literal["coachName", "teamName", "matches", "adjustedPpm", "pointsPerMatch", "wins", "startDate"]
SortDirection = Literal["asc", "desc"]

TECHNICAL_FALLBACK_LABEL_PATTERN = re.compile(
    r"^(?:Unknown (?:Coach|Team) #\d+|(?:Coach|Team) #\d+|T[eé]cnico #\d+|\d+)$",
    re.IGNORECASE,
)
PLACEHOLDER_IMAGE_PATTERN = re.compile(r"placeholder", re.IGNORECASE)


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


def _is_technical_fallback_label(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    return bool(TECHNICAL_FALLBACK_LABEL_PATTERN.match(value.strip()))


def _is_placeholder_image(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    return bool(PLACEHOLDER_IMAGE_PATTERN.search(value))


def _public_coach_name(value: Any) -> str:
    text_value = _to_text(value)
    if text_value is not None and not _is_technical_fallback_label(text_value):
        return text_value

    return "Nome indisponível"


def _public_team_name(value: Any) -> str:
    text_value = _to_text(value)
    if text_value is not None and not _is_technical_fallback_label(text_value):
        return text_value

    return "Time indisponível"


def _public_photo_url(row: dict[str, Any]) -> str | None:
    photo_url = _to_text(row.get("photo_url"))
    if photo_url is None or _is_placeholder_image(photo_url):
        return None

    return photo_url


def _has_public_photo(row: dict[str, Any]) -> bool:
    return bool(row.get("has_real_photo")) and _public_photo_url(row) is not None


def _media_status(row: dict[str, Any]) -> str:
    if _has_public_photo(row):
        return "real"

    if bool(row.get("is_placeholder_image")) or _is_placeholder_image(row.get("photo_url")):
        return "provider_placeholder"

    return "editorial_fallback"


def _coach_data_status(*, coach_name: Any, team_name: Any) -> str:
    if _is_technical_fallback_label(coach_name) or _is_technical_fallback_label(team_name):
        return "partial"
    if _to_text(coach_name) is None or _to_text(team_name) is None:
        return "partial"

    return "confirmed"


def _coach_assignment_scope_filters_sql(
    filters: GlobalFilters,
    *,
    assignment_alias: str,
) -> tuple[str, list[Any]]:
    where_clauses = [
        f"fm.date_day >= {COACHES_DATA_START_SQL}",
        f"fm.date_day <= {COACHES_DATA_CUTOFF_SQL}",
    ]
    params: list[Any] = []
    append_fact_match_filters(where_clauses, params, alias="fm", filters=filters)

    if filters.venue == VenueFilter.home:
        where_clauses.append(f"fm.home_team_id = {assignment_alias}.team_id")
    elif filters.venue == VenueFilter.away:
        where_clauses.append(f"fm.away_team_id = {assignment_alias}.team_id")

    return " and ".join(where_clauses), params


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
    match_where_sql, match_where_params = _coach_assignment_scope_filters_sql(filters, assignment_alias="f")

    query = f"""
        with assignment_scope as (
            select
                f.match_id,
                f.team_id,
                f.coach_identity_id as coach_id,
                coalesce(
                    nullif(trim(ci.display_name), ''),
                    nullif(trim(ci.canonical_name), '')
                ) as coach_name,
                coalesce(
                    case
                        when nullif(trim(coalesce(ci.image_url, '')), '') is not null
                         and ci.image_url not ilike '%%placeholder%%'
                            then nullif(trim(ci.image_url), '')
                    end,
                    case
                        when nullif(trim(coalesce(dc.image_path, '')), '') is not null
                         and coalesce(dc.has_real_photo, false)
                         and dc.image_path not ilike '%%placeholder%%'
                            then nullif(trim(dc.image_path), '')
                    end,
                    case
                        when nullif(trim(coalesce(rc.image_path, '')), '') is not null
                         and rc.image_path not ilike '%%placeholder%%'
                            then nullif(trim(rc.image_path), '')
                    end
                ) as photo_url,
                (
                    (
                        nullif(trim(coalesce(ci.image_url, '')), '') is not null
                        and ci.image_url not ilike '%%placeholder%%'
                    )
                    or (
                        coalesce(dc.has_real_photo, false)
                        and coalesce(dc.image_path, '') not ilike '%%placeholder%%'
                    )
                    or (
                        nullif(trim(coalesce(rc.image_path, '')), '') is not null
                        and rc.image_path not ilike '%%placeholder%%'
                    )
                ) as has_real_photo,
                (
                    coalesce(ci.image_url, '') ilike '%%placeholder%%'
                    or coalesce(dc.is_placeholder_image, false)
                    or coalesce(rc.image_path, '') ilike '%%placeholder%%'
                ) as is_placeholder_image,
                nullif(trim(dt.team_name), '') as team_name,
                coalesce(ct.role = 'interim_head_coach', false) as temporary,
                (
                    ct.start_date is not null
                    and ct.start_date <= {COACHES_DATA_CUTOFF_SQL}
                    and (ct.end_date is null or ct.end_date > {COACHES_DATA_CUTOFF_SQL} or ct.is_current_as_of_source)
                ) as active,
                coalesce(
                    ct.start_date,
                    min(fm.date_day) over (
                        partition by f.coach_identity_id, f.team_id, coalesce(f.coach_tenure_id, 0), f.source
                    )
                ) as start_date,
                coalesce(
                    case
                        when ct.end_date is not null and ct.end_date > {COACHES_DATA_CUTOFF_SQL} then {COACHES_DATA_CUTOFF_SQL}
                        else ct.end_date
                    end,
                    max(fm.date_day) over (
                        partition by f.coach_identity_id, f.team_id, coalesce(f.coach_tenure_id, 0), f.source
                    )
                ) as end_date,
                f.coach_tenure_id,
                f.source,
                fm.date_day,
                fm.league_id,
                null::text as league_name,
                fm.season,
                case
                    when fm.home_team_id = f.team_id and coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0) then 'W'
                    when fm.away_team_id = f.team_id and coalesce(fm.away_goals, 0) > coalesce(fm.home_goals, 0) then 'W'
                    when coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 'D'
                    else 'L'
                end as result,
                case
                    when fm.home_team_id = f.team_id and coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0) then 3
                    when fm.away_team_id = f.team_id and coalesce(fm.away_goals, 0) > coalesce(fm.home_goals, 0) then 3
                    when coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 1
                    else 0
                end as points,
                case when fm.home_team_id = f.team_id then coalesce(fm.home_goals, 0) else coalesce(fm.away_goals, 0) end as goals_for,
                case when fm.home_team_id = f.team_id then coalesce(fm.away_goals, 0) else coalesce(fm.home_goals, 0) end as goals_against
            from mart.fact_coach_match_assignment f
            join mart.fact_matches fm
              on fm.match_id = f.match_id
            left join mart.coach_identity ci
              on ci.coach_identity_id = f.coach_identity_id
            left join mart.dim_team dt
              on dt.team_id = f.team_id
            left join mart.coach_tenure ct
              on ct.coach_tenure_id = f.coach_tenure_id
            left join mart.dim_coach dc
              on dc.provider = ci.provider
             and dc.coach_id = ci.provider_coach_id
            left join raw.coaches rc
              on rc.provider = ci.provider
             and rc.coach_id = ci.provider_coach_id
            where f.is_public_eligible = true
              and f.coach_identity_id is not null
              and {match_where_sql}
              and (
                %s::boolean
                or (
                  coalesce(nullif(trim(ci.display_name), ''), nullif(trim(ci.canonical_name), '')) is not null
                  and lower(trim(coalesce(ci.display_name, ci.canonical_name))) not in ('not applicable', 'unknown', 'n/a', 'na', 'none', 'null')
                )
              )
              and (
                %s::text is null
                or coalesce(ci.display_name, ci.canonical_name) ilike %s
                or dt.team_name ilike %s
              )
        ),
        ranked_assignments as (
            select
                assignment_scope.*,
                row_number() over (
                    partition by coach_id
                    order by date_day desc, match_id desc
                ) as rn_recent
            from assignment_scope
        ),
        filtered_assignments as (
            select *
            from ranked_assignments
            where (%s::int is null or rn_recent <= %s)
        ),
        tenure_stats as (
            select
                coach_id,
                coach_name,
                max(photo_url) filter (where photo_url is not null) as photo_url,
                bool_or(has_real_photo) as has_real_photo,
                bool_or(is_placeholder_image) as is_placeholder_image,
                team_id,
                team_name,
                bool_or(active) as active,
                bool_or(temporary) as temporary,
                min(start_date) as start_date,
                max(end_date) as end_date,
                count(distinct match_id) as matches,
                coalesce(sum(case when result = 'W' then 1 else 0 end), 0) as wins,
                coalesce(sum(case when result = 'D' then 1 else 0 end), 0) as draws,
                coalesce(sum(case when result = 'L' then 1 else 0 end), 0) as losses,
                coalesce(sum(points), 0) as points,
                coalesce(sum(goals_for), 0) as goals_for,
                coalesce(sum(goals_against), 0) as goals_against,
                max(date_day) as last_match_date
            from filtered_assignments
            group by coach_id, coach_name, team_id, team_name
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
                ts.last_match_date desc nulls last,
                ts.active desc,
                coalesce(ts.end_date, date '2999-12-31') desc,
                coalesce(ts.start_date, date '1900-01-01') desc
        ),
        latest_context as (
            select distinct on (fa.coach_id)
                fa.coach_id,
                fa.league_id,
                fa.league_name,
                fa.season
            from filtered_assignments fa
            order by fa.coach_id, fa.date_day desc, fa.match_id desc
        ),
        final_rows as (
            select
                ts.coach_id,
                max(ts.coach_name) as coach_name,
                max(ts.photo_url) filter (where ts.photo_url is not null) as photo_url,
                bool_or(ts.has_real_photo) as has_real_photo,
                bool_or(ts.is_placeholder_image) as is_placeholder_image,
                count(*) as tenure_count,
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
            select avg(case when fr.matches > 0 then fr.points::numeric / fr.matches end) as avg_points_per_match
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
            is_placeholder_image,
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
            *match_where_params,
            includeUnknown,
            search_pattern,
            search_pattern,
            search_pattern,
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
            "coachName": _public_coach_name(row.get("coach_name")),
            "photoUrl": _public_photo_url(row),
            "hasRealPhoto": _has_public_photo(row),
            "mediaStatus": _media_status(row),
            "teamId": str(row["team_id"]) if row.get("team_id") is not None else None,
            "teamName": _public_team_name(row.get("team_name")),
            "dataStatus": _coach_data_status(coach_name=row.get("coach_name"), team_name=row.get("team_name")),
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
    match_where_sql, match_where_params = _coach_assignment_scope_filters_sql(filters, assignment_alias="f")

    query = f"""
        with requested_coach as (
            select coalesce(r.canonical_coach_identity_id, ci.coach_identity_id) as coach_id
            from mart.coach_identity ci
            left join mart.v_coach_identity_resolution r
              on r.source_coach_identity_id = ci.coach_identity_id
            where ci.coach_identity_id = %s
            limit 1
        ),
        assignment_scope as (
            select
                f.match_id,
                f.team_id,
                f.coach_identity_id as coach_id,
                coalesce(
                    nullif(trim(ci.display_name), ''),
                    nullif(trim(ci.canonical_name), '')
                ) as coach_name,
                coalesce(
                    case
                        when nullif(trim(coalesce(ci.image_url, '')), '') is not null
                         and ci.image_url not ilike '%%placeholder%%'
                            then nullif(trim(ci.image_url), '')
                    end,
                    case
                        when nullif(trim(coalesce(dc.image_path, '')), '') is not null
                         and coalesce(dc.has_real_photo, false)
                         and dc.image_path not ilike '%%placeholder%%'
                            then nullif(trim(dc.image_path), '')
                    end,
                    case
                        when nullif(trim(coalesce(rc.image_path, '')), '') is not null
                         and rc.image_path not ilike '%%placeholder%%'
                            then nullif(trim(rc.image_path), '')
                    end
                ) as photo_url,
                (
                    (
                        nullif(trim(coalesce(ci.image_url, '')), '') is not null
                        and ci.image_url not ilike '%%placeholder%%'
                    )
                    or (
                        coalesce(dc.has_real_photo, false)
                        and coalesce(dc.image_path, '') not ilike '%%placeholder%%'
                    )
                    or (
                        nullif(trim(coalesce(rc.image_path, '')), '') is not null
                        and rc.image_path not ilike '%%placeholder%%'
                    )
                ) as has_real_photo,
                (
                    coalesce(ci.image_url, '') ilike '%%placeholder%%'
                    or coalesce(dc.is_placeholder_image, false)
                    or coalesce(rc.image_path, '') ilike '%%placeholder%%'
                ) as is_placeholder_image,
                nullif(trim(dt.team_name), '') as team_name,
                coalesce(ct.role = 'interim_head_coach', false) as temporary,
                (
                    ct.start_date is not null
                    and ct.start_date <= {COACHES_DATA_CUTOFF_SQL}
                    and (ct.end_date is null or ct.end_date > {COACHES_DATA_CUTOFF_SQL} or ct.is_current_as_of_source)
                ) as active,
                coalesce(
                    ct.start_date,
                    min(fm.date_day) over (
                        partition by f.coach_identity_id, f.team_id, coalesce(f.coach_tenure_id, 0), f.source
                    )
                ) as start_date,
                coalesce(
                    case
                        when ct.end_date is not null and ct.end_date > {COACHES_DATA_CUTOFF_SQL} then {COACHES_DATA_CUTOFF_SQL}
                        else ct.end_date
                    end,
                    max(fm.date_day) over (
                        partition by f.coach_identity_id, f.team_id, coalesce(f.coach_tenure_id, 0), f.source
                    )
                ) as end_date,
                f.coach_tenure_id,
                f.source,
                fm.date_day,
                fm.league_id,
                null::text as league_name,
                fm.season,
                case
                    when fm.home_team_id = f.team_id and coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0) then 'W'
                    when fm.away_team_id = f.team_id and coalesce(fm.away_goals, 0) > coalesce(fm.home_goals, 0) then 'W'
                    when coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 'D'
                    else 'L'
                end as result,
                case
                    when fm.home_team_id = f.team_id and coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0) then 3
                    when fm.away_team_id = f.team_id and coalesce(fm.away_goals, 0) > coalesce(fm.home_goals, 0) then 3
                    when coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 1
                    else 0
                end as points,
                case when fm.home_team_id = f.team_id then coalesce(fm.home_goals, 0) else coalesce(fm.away_goals, 0) end as goals_for,
                case when fm.home_team_id = f.team_id then coalesce(fm.away_goals, 0) else coalesce(fm.home_goals, 0) end as goals_against
            from mart.fact_coach_match_assignment f
            join mart.fact_matches fm
              on fm.match_id = f.match_id
            left join mart.coach_identity ci
              on ci.coach_identity_id = f.coach_identity_id
            left join mart.dim_team dt
              on dt.team_id = f.team_id
            left join mart.coach_tenure ct
              on ct.coach_tenure_id = f.coach_tenure_id
            left join mart.dim_coach dc
              on dc.provider = ci.provider
             and dc.coach_id = ci.provider_coach_id
            left join raw.coaches rc
              on rc.provider = ci.provider
             and rc.coach_id = ci.provider_coach_id
            where f.is_public_eligible = true
              and f.coach_identity_id is not null
              and {match_where_sql}
        ),
        ranked_assignments as (
            select
                assignment_scope.*,
                row_number() over (
                    partition by coach_id
                    order by date_day desc, match_id desc
                ) as rn_recent
            from assignment_scope
        ),
        filtered_assignments as (
            select *
            from ranked_assignments
            where (%s::int is null or rn_recent <= %s)
        ),
        selected_assignments as (
            select fa.*
            from filtered_assignments fa
            join requested_coach rc
              on rc.coach_id = fa.coach_id
        ),
        all_coach_scope_summary as (
            select
                coach_id,
                count(distinct match_id) as matches,
                coalesce(sum(points), 0) as points
            from filtered_assignments
            group by coach_id
        ),
        scope_average as (
            select avg(case when matches > 0 then points::numeric / matches end) as avg_points_per_match
            from all_coach_scope_summary
            where matches > 0
        ),
        tenure_stats as (
            select
                coach_id,
                coach_name,
                max(photo_url) filter (where photo_url is not null) as photo_url,
                bool_or(has_real_photo) as has_real_photo,
                bool_or(is_placeholder_image) as is_placeholder_image,
                team_id,
                team_name,
                bool_or(active) as active,
                bool_or(temporary) as temporary,
                min(start_date) as start_date,
                max(end_date) as end_date,
                count(distinct match_id) as matches,
                coalesce(sum(case when result = 'W' then 1 else 0 end), 0) as wins,
                coalesce(sum(case when result = 'D' then 1 else 0 end), 0) as draws,
                coalesce(sum(case when result = 'L' then 1 else 0 end), 0) as losses,
                coalesce(sum(points), 0) as points,
                coalesce(sum(goals_for), 0) as goals_for,
                coalesce(sum(goals_against), 0) as goals_against,
                max(date_day) as last_match_date,
                min(league_id) filter (where league_id is not null) as league_id,
                max(league_name) as league_name,
                max(season) as season,
                min(coalesce(coach_tenure_id, 0)) as coach_tenure_id
            from selected_assignments
            group by coach_id, coach_name, team_id, team_name
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
                ts.last_match_date desc nulls last,
                ts.active desc,
                coalesce(ts.end_date, date '2999-12-31') desc,
                coalesce(ts.start_date, date '1900-01-01') desc
        ),
        coach_summary as (
            select
                ts.coach_id,
                max(ts.coach_name) as coach_name,
                max(ts.photo_url) filter (where ts.photo_url is not null) as photo_url,
                bool_or(ts.has_real_photo) as has_real_photo,
                bool_or(ts.is_placeholder_image) as is_placeholder_image,
                count(*) as tenure_count,
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
            cs.is_placeholder_image,
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
            ts.league_id,
            ts.league_name,
            ts.season
        from coach_summary cs
        inner join tenure_stats ts
          on ts.coach_id = cs.coach_id
        left join latest_tenure lt
          on lt.coach_id = cs.coach_id
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
            "teamName": _public_team_name(row.get("team_name")),
            "dataStatus": _coach_data_status(coach_name=first_row.get("coach_name"), team_name=row.get("team_name")),
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
            "coachName": _public_coach_name(first_row.get("coach_name")),
            "photoUrl": _public_photo_url(first_row),
            "hasRealPhoto": _has_public_photo(first_row),
            "mediaStatus": _media_status(first_row),
            "teamId": str(first_row["current_team_id"]) if first_row.get("current_team_id") is not None else None,
            "teamName": _public_team_name(first_row.get("current_team_name")),
            "dataStatus": _coach_data_status(
                coach_name=first_row.get("coach_name"),
                team_name=first_row.get("current_team_name"),
            ),
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

