from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Query, Request

from ..core.config import get_settings
from ..core.contracts import build_api_response, build_coverage_from_counts, build_pagination
from ..core.filters import GlobalFilters, append_fact_match_filters, validate_and_build_global_filters
from ..db.client import db_client

router = APIRouter(prefix="/api/v1/market", tags=["market"])
PRODUCT_DATA_CUTOFF = get_settings().product_data_cutoff

MarketSortBy = Literal["transferDate", "playerName", "amount"]
SortDirection = Literal["asc", "desc"]
TeamDirection = Literal["all", "arrivals", "departures"]

ACCENT_SOURCE = "áàâãäéèêëíìîïóòôõöúùûüçñ"
ACCENT_TARGET = "aaaaaeeeeiiiiooooouuuucn"


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def _normalize_search_query(value: str) -> str:
    collapsed = " ".join(value.strip().split())
    normalized = unicodedata.normalize("NFKD", collapsed.lower())
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_marks.strip()


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _search_patterns(value: str | None) -> list[str] | None:
    if not value or not value.strip():
        return None

    tokens = [_escape_like(token) for token in _normalize_search_query(value).split() if token]
    return [f"%{token}%" for token in tokens] if tokens else None


def _normalized_sql(column_sql: str) -> str:
    return (
        f"translate(lower(coalesce({column_sql}, '')), "
        f"'{ACCENT_SOURCE}', '{ACCENT_TARGET}')"
    )


_TRANSFER_TYPE_NAMES = {
    219: "Transferência definitiva",
    218: "Empréstimo",
    220: "Transferência livre",
    9688: "Retorno de empréstimo",
}

_TRANSFER_MOVEMENT_KINDS = {
    219: "permanent_transfer",
    218: "loan_out",
    220: "free_transfer",
    9688: "loan_return",
}

_TECHNICAL_FALLBACK_PATTERN = re.compile(
    r"^(?:Unknown (?:Player|Team|Venue) #\d+|Team #\d+|\d+)$"
)


def _transfer_type_name(value: Any) -> str:
    if value is None:
        return "Tipo desconhecido"
    return _TRANSFER_TYPE_NAMES.get(int(value), "Tipo desconhecido")


def _movement_kind(value: Any, *, career_ended: bool) -> str:
    if career_ended:
        return "career_end"

    if value is None:
        return "unknown"

    return _TRANSFER_MOVEMENT_KINDS.get(int(value), "unknown")


def _is_technical_fallback(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    return bool(_TECHNICAL_FALLBACK_PATTERN.match(value.strip()))


def _public_player_name(value: Any) -> str:
    if isinstance(value, str) and value.strip() and not _is_technical_fallback(value):
        return value.strip()

    return "Nome indisponível"


def _public_team_name(value: Any, *, missing_label: str) -> str:
    if isinstance(value, str) and value.strip() and not _is_technical_fallback(value):
        return value.strip()

    return missing_label


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
    search_patterns = _search_patterns(search)
    club_search_patterns = _search_patterns(clubSearch)
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

    player_name_sql = "coalesce(nullif(trim(spt.player_name), ''), 'Nome indisponível')"
    from_team_name_sql = (
        "coalesce(dim_from.team_name, nullif(trim(spt.payload -> 'fromTeam' ->> 'name'), ''), "
        "nullif(trim(spt.payload -> 'from_team' ->> 'name'), ''), '')"
    )
    to_team_name_sql = (
        "coalesce(dim_to.team_name, nullif(trim(spt.payload -> 'toTeam' ->> 'name'), ''), "
        "nullif(trim(spt.payload -> 'to_team' ->> 'name'), ''), '')"
    )
    amount_sql = "nullif(trim(coalesce(spt.amount, '')), '')"
    normalized_market_search_sql = (
        f"{_normalized_sql(player_name_sql)} || ' ' || "
        f"{_normalized_sql(from_team_name_sql)} || ' ' || "
        f"{_normalized_sql(to_team_name_sql)} || ' ' || "
        f"{_normalized_sql(amount_sql)}"
    )
    normalized_from_team_search_sql = (
        f"{_normalized_sql(from_team_name_sql)} || ' ' || coalesce(spt.from_team_id::text, '')"
    )
    normalized_to_team_search_sql = (
        f"{_normalized_sql(to_team_name_sql)} || ' ' || coalesce(spt.to_team_id::text, '')"
    )

    query = f"""
        with enriched_transfers as (
            select
                spt.transfer_id,
                spt.player_id,
                {player_name_sql} as player_name,
                spt.from_team_id,
                case
                    when spt.from_team_id is null then null
                    else coalesce(
                        dim_from.team_name,
                        nullif(trim(spt.payload -> 'fromTeam' ->> 'name'), ''),
                        nullif(trim(spt.payload -> 'from_team' ->> 'name'), ''),
                        'Origem indisponível'
                    )
                end as from_team_name,
                spt.to_team_id,
                case
                    when spt.to_team_id is null then null
                    else coalesce(
                        dim_to.team_name,
                        nullif(trim(spt.payload -> 'toTeam' ->> 'name'), ''),
                        nullif(trim(spt.payload -> 'to_team' ->> 'name'), ''),
                        'Destino indisponível'
                    )
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
                %s::text[] is null
                or not exists (
                    select 1
                    from unnest(%s::text[]) as search_token(pattern)
                    where {normalized_market_search_sql} not like search_token.pattern
                )
            )
              and (
                %s::text[] is null
                or (
                    %s::text in ('all', 'departures')
                    and not exists (
                        select 1
                        from unnest(%s::text[]) as club_token(pattern)
                        where {normalized_from_team_search_sql} not like club_token.pattern
                    )
                )
                or (
                    %s::text in ('all', 'arrivals')
                    and not exists (
                        select 1
                        from unnest(%s::text[]) as club_token(pattern)
                        where {normalized_to_team_search_sql} not like club_token.pattern
                    )
                )
              )
              and (%s::bigint is null or spt.type_id = %s)
              and (%s::date is null or spt.transfer_date >= %s)
              and (%s::date is null or spt.transfer_date <= %s)
              and (spt.transfer_date is null or spt.transfer_date <= %s)
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
            search_patterns,
            search_patterns,
            club_search_patterns,
            teamDirection,
            club_search_patterns,
            teamDirection,
            club_search_patterns,
            typeId,
            typeId,
            filters.date_start,
            filters.date_start,
            filters.date_end,
            filters.date_end,
            PRODUCT_DATA_CUTOFF,
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
            "playerName": _public_player_name(row.get("player_name")),
            "fromTeamId": str(row["from_team_id"]) if row.get("from_team_id") is not None else None,
            "fromTeamName": (
                _public_team_name(row.get("from_team_name"), missing_label="Origem indisponível")
                if row.get("from_team_id") is not None
                else None
            ),
            "toTeamId": str(row["to_team_id"]) if row.get("to_team_id") is not None else None,
            "toTeamName": (
                _public_team_name(row.get("to_team_name"), missing_label="Destino indisponível")
                if row.get("to_team_id") is not None
                else None
            ),
            "transferDate": row.get("transfer_date"),
            "completed": bool(row.get("completed")),
            "careerEnded": bool(row.get("career_ended")),
            "typeId": _to_int(row.get("type_id")) if row.get("type_id") is not None else None,
            "typeName": _transfer_type_name(row.get("type_id")),
            "movementKind": _movement_kind(row.get("type_id"), career_ended=bool(row.get("career_ended"))),
            "amount": row.get("amount"),
            "amountValue": row.get("amount_value"),
            "currency": None,
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
