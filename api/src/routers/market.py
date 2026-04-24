from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Query, Request

from ..core.contracts import build_api_response, build_coverage_from_counts, build_pagination
from ..core.filters import GlobalFilters, append_fact_match_filters, validate_and_build_global_filters
from ..db.client import db_client

router = APIRouter(prefix="/api/v1/market", tags=["market"])

MarketSortBy = Literal["transferDate", "playerName", "amount"]
SortDirection = Literal["asc", "desc"]
TeamDirection = Literal["all", "arrivals", "departures"]


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


_TRANSFER_TYPE_NAMES = {
    219: "Transferência definitiva",
    218: "Empréstimo",
    9688: "Livre / fim de contrato",
    220: "Retorno de empréstimo",
}


def _transfer_type_name(value: Any) -> str:
    if value is None:
        return "Tipo desconhecido"
    return _TRANSFER_TYPE_NAMES.get(int(value), "Tipo desconhecido")


def _market_team_scope_sql(filters: GlobalFilters) -> tuple[str, list[Any], bool]:
    has_scope = bool(
        filters.competition_ids
        or filters.season_id is not None
        or filters.round_id is not None
        or filters.stage_id is not None
        or filters.stage_format is not None
    )

    if not has_scope:
        return "1=0", [], False

    scope_filters = GlobalFilters(
        competition_id=filters.competition_id,
        competition_ids=filters.competition_ids,
        season_id=filters.season_id,
        round_id=filters.round_id,
        stage_id=filters.stage_id,
        stage_format=filters.stage_format,
        venue=filters.venue,
        last_n=None,
        date_start=None,
        date_end=None,
    )
    clauses = ["1=1"]
    params: list[Any] = []
    append_fact_match_filters(clauses, params, alias="fm", filters=scope_filters)
    return " and ".join(clauses), params, True


def _fetch_market_team_scope_ids(filters: GlobalFilters) -> list[int] | None:
    scope_where_sql, scope_where_params, use_team_scope = _market_team_scope_sql(filters)

    if not use_team_scope:
        return None

    rows = db_client.fetch_all(
        f"""
        select distinct scoped.team_id
        from (
            select fm.home_team_id as team_id
            from mart.fact_matches fm
            where {scope_where_sql}

            union

            select fm.away_team_id as team_id
            from mart.fact_matches fm
            where {scope_where_sql}
        ) scoped
        where scoped.team_id is not null;
        """,
        [
            *scope_where_params,
            *scope_where_params,
        ],
    )

    return [_to_int(row.get("team_id")) for row in rows if row.get("team_id") is not None]


@router.get("/transfers")
def get_market_transfers(
    request: Request,
    competitionId: str | None = None,
    seasonId: str | None = None,
    roundId: str | None = None,
    stageId: str | None = None,
    stageFormat: str | None = None,
    venue: str | None = None,
    lastN: int | None = Query(default=None, gt=0),
    dateStart: date | None = None,
    dateEnd: date | None = None,
    dateRangeStart: date | None = None,
    dateRangeEnd: date | None = None,
    search: str | None = None,
    clubSearch: str | None = None,
    teamDirection: TeamDirection = "all",
    typeId: int | None = Query(default=None, gt=0),
    hasAmount: bool | None = None,
    minAmount: float | None = Query(default=None, ge=0),
    maxAmount: float | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=24, ge=1, le=100),
    sortBy: MarketSortBy = "transferDate",
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
    club_search_pattern = f"%{clubSearch.strip()}%" if clubSearch and clubSearch.strip() else None
    offset = (page - 1) * pageSize
    sort_column = {
        "amount": "amount_value",
        "transferDate": "transfer_date",
        "playerName": "player_name",
    }[sortBy]
    sort_dir = "asc" if sortDirection == "asc" else "desc"
    team_scope_ids = _fetch_market_team_scope_ids(filters)
    use_team_scope = team_scope_ids is not None

    if team_scope_ids == []:
        return build_api_response(
            {"items": []},
            request_id=_request_id(request),
            pagination=build_pagination(page, pageSize, 0),
            coverage=build_coverage_from_counts(0, 0, "Market transfers coverage"),
        )

    query = f"""
        with enriched_transfers as (
            select
                spt.transfer_id,
                spt.player_id,
                coalesce(nullif(trim(spt.player_name), ''), concat('Unknown Player #', spt.player_id::text)) as player_name,
                spt.from_team_id,
                case
                    when spt.from_team_id is null then null
                    else coalesce(dim_from.team_name, concat('Team #', spt.from_team_id::text))
                end as from_team_name,
                spt.to_team_id,
                case
                    when spt.to_team_id is null then null
                    else coalesce(dim_to.team_name, concat('Team #', spt.to_team_id::text))
                end as to_team_name,
                spt.transfer_date,
                coalesce(spt.completed, false) as completed,
                coalesce(spt.career_ended, false) as career_ended,
                spt.type_id,
                nullif(trim(coalesce(spt.amount, '')), '') as amount,
                case
                    when nullif(trim(coalesce(spt.amount, '')), '') ~ '^[0-9]+(\\.[0-9]+)?$'
                    then nullif(trim(coalesce(spt.amount, '')), '')::numeric
                    else null
                end as amount_value
            from mart.stg_player_transfers spt
            left join mart.dim_team dim_from
              on dim_from.team_id = spt.from_team_id
            left join mart.dim_team dim_to
              on dim_to.team_id = spt.to_team_id
            where (
                %s::text is null
                or coalesce(nullif(trim(spt.player_name), ''), concat('Unknown Player #', spt.player_id::text)) ilike %s
                or coalesce(dim_from.team_name, '') ilike %s
                or coalesce(dim_to.team_name, '') ilike %s
                or nullif(trim(coalesce(spt.amount, '')), '') ilike %s
            )
              and (
                %s::text is null
                or (
                    %s::text in ('all', 'departures')
                    and (
                        coalesce(dim_from.team_name, '') ilike %s
                        or spt.from_team_id::text ilike %s
                    )
                )
                or (
                    %s::text in ('all', 'arrivals')
                    and (
                        coalesce(dim_to.team_name, '') ilike %s
                        or spt.to_team_id::text ilike %s
                    )
                )
              )
              and (%s::bigint is null or spt.type_id = %s)
              and (%s::date is null or spt.transfer_date >= %s)
              and (%s::date is null or spt.transfer_date <= %s)
              and (
                not %s::boolean
                or spt.from_team_id = any(%s::bigint[])
                or spt.to_team_id = any(%s::bigint[])
              )
        ),
        ranked_transfers as (
            select
                et.*,
                row_number() over (
                    order by et.transfer_date desc nulls last, et.transfer_id desc
                ) as rn_recent
            from enriched_transfers et
            where (%s::boolean is not true or et.amount_value is not null)
              and (%s::numeric is null or et.amount_value >= %s)
              and (%s::numeric is null or et.amount_value <= %s)
        ),
        filtered_transfers as (
            select *
            from ranked_transfers
            where (%s::int is null or rn_recent <= %s)
        )
        select
            transfer_id,
            player_id,
            player_name,
            from_team_id,
            from_team_name,
            to_team_id,
            to_team_name,
            transfer_date,
            completed,
            career_ended,
            type_id,
            amount,
            amount_value,
            count(*) over() as _total_count
        from filtered_transfers
        order by {sort_column} {sort_dir} nulls last, transfer_id desc
        limit %s offset %s;
    """
    rows = db_client.fetch_all(
        query,
        [
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            club_search_pattern,
            teamDirection,
            club_search_pattern,
            club_search_pattern,
            teamDirection,
            club_search_pattern,
            club_search_pattern,
            typeId,
            typeId,
            filters.date_start,
            filters.date_start,
            filters.date_end,
            filters.date_end,
            use_team_scope,
            team_scope_ids or [],
            team_scope_ids or [],
            hasAmount,
            minAmount,
            minAmount,
            maxAmount,
            maxAmount,
            filters.last_n,
            filters.last_n,
            pageSize,
            offset,
        ],
    )

    items = [
        {
            "transferId": str(row["transfer_id"]),
            "playerId": str(row["player_id"]) if row.get("player_id") is not None else None,
            "playerName": row.get("player_name"),
            "fromTeamId": str(row["from_team_id"]) if row.get("from_team_id") is not None else None,
            "fromTeamName": row.get("from_team_name"),
            "toTeamId": str(row["to_team_id"]) if row.get("to_team_id") is not None else None,
            "toTeamName": row.get("to_team_name"),
            "transferDate": row.get("transfer_date"),
            "completed": bool(row.get("completed")),
            "careerEnded": bool(row.get("career_ended")),
            "typeId": _to_int(row.get("type_id")) if row.get("type_id") is not None else None,
            "typeName": _transfer_type_name(row.get("type_id")),
            "amount": row.get("amount"),
            "amountValue": row.get("amount_value"),
            "currency": "EUR" if row.get("amount_value") is not None else None,
        }
        for row in rows
    ]
    total_count = _to_int(rows[0].get("_total_count")) if rows else 0
    available_count = len(rows) if rows else 0

    return build_api_response(
        {"items": items},
        request_id=_request_id(request),
        pagination=build_pagination(page, pageSize, total_count),
        coverage=build_coverage_from_counts(available_count, available_count, "Market transfers coverage"),
    )
