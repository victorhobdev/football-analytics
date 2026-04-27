from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from .errors import AppError
from .context_registry import expand_competition_ids_for_query


class VenueFilter(str, Enum):
    home = "home"
    away = "away"
    all = "all"


class StageFormatFilter(str, Enum):
    league_table = "league_table"
    group_table = "group_table"
    knockout = "knockout"
    qualification_knockout = "qualification_knockout"
    placement_match = "placement_match"


@dataclass(frozen=True)
class GlobalFilters:
    competition_id: int | None
    competition_ids: tuple[int, ...]
    season_id: int | None
    round_id: int | None
    stage_id: int | None
    stage_format: StageFormatFilter | None
    venue: VenueFilter
    last_n: int | None
    date_start: date | None
    date_end: date | None


def _to_optional_int(raw_value: str | int | None, *, field_name: str) -> int | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, int):
        return raw_value
    value = raw_value.strip()
    if value == "":
        return None
    if value.lower() == "all":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise AppError(
            message=f"Invalid value for '{field_name}'. Expected integer.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={field_name: raw_value},
        ) from exc


def _coalesce_date_aliases(
    date_start: date | None,
    date_end: date | None,
    date_range_start: date | None,
    date_range_end: date | None,
) -> tuple[date | None, date | None]:
    normalized_start = date_start or date_range_start
    normalized_end = date_end or date_range_end
    return normalized_start, normalized_end


def _to_optional_stage_format(
    raw_value: str | StageFormatFilter | None,
    *,
    field_name: str,
) -> StageFormatFilter | None:
    if raw_value is None:
        return None

    if isinstance(raw_value, StageFormatFilter):
        return raw_value

    normalized_value = raw_value.strip()
    if normalized_value == "":
        return None

    try:
        return StageFormatFilter(normalized_value)
    except ValueError as exc:
        raise AppError(
            message=f"Invalid value for '{field_name}'. Expected supported stage format.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={field_name: raw_value},
        ) from exc


def validate_and_build_global_filters(
    *,
    competition_id: str | int | None,
    season_id: str | int | None,
    round_id: str | int | None,
    venue: VenueFilter | str | None,
    last_n: int | None,
    date_start: date | None,
    date_end: date | None,
    date_range_start: date | None,
    date_range_end: date | None,
    stage_id: str | int | None = None,
    stage_format: str | StageFormatFilter | None = None,
) -> GlobalFilters:
    normalized_venue = VenueFilter(venue) if venue else VenueFilter.all
    normalized_competition = _to_optional_int(competition_id, field_name="competitionId")
    normalized_competition_ids = expand_competition_ids_for_query(normalized_competition)
    normalized_season = _to_optional_int(season_id, field_name="seasonId")
    normalized_round = _to_optional_int(round_id, field_name="roundId")
    normalized_stage_id = _to_optional_int(stage_id, field_name="stageId")
    normalized_stage_format = _to_optional_stage_format(stage_format, field_name="stageFormat")
    normalized_date_start, normalized_date_end = _coalesce_date_aliases(
        date_start=date_start,
        date_end=date_end,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
    )

    if last_n is not None and last_n <= 0:
        raise AppError(
            message="Invalid value for 'lastN'. It must be greater than zero.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={"lastN": last_n},
        )

    has_last_n = last_n is not None
    has_date_range = normalized_date_start is not None or normalized_date_end is not None

    if has_last_n and has_date_range:
        raise AppError(
            message="Invalid time range. 'lastN' cannot be combined with 'dateStart/dateEnd'.",
            code="INVALID_TIME_RANGE",
            status=400,
            details={
                "lastN": last_n,
                "dateStart": normalized_date_start.isoformat() if normalized_date_start else None,
                "dateEnd": normalized_date_end.isoformat() if normalized_date_end else None,
            },
        )

    if normalized_date_start is not None and normalized_date_end is None:
        raise AppError(
            message="Invalid time range. 'dateStart' requires 'dateEnd'.",
            code="INVALID_TIME_RANGE",
            status=400,
            details={"dateStart": normalized_date_start.isoformat()},
        )

    if normalized_date_end is not None and normalized_date_start is None:
        raise AppError(
            message="Invalid time range. 'dateEnd' requires 'dateStart'.",
            code="INVALID_TIME_RANGE",
            status=400,
            details={"dateEnd": normalized_date_end.isoformat()},
        )

    if normalized_date_start and normalized_date_end and normalized_date_start > normalized_date_end:
        raise AppError(
            message="Invalid time range. 'dateStart' must be less than or equal to 'dateEnd'.",
            code="INVALID_TIME_RANGE",
            status=400,
            details={
                "dateStart": normalized_date_start.isoformat(),
                "dateEnd": normalized_date_end.isoformat(),
            },
        )

    return GlobalFilters(
        competition_id=normalized_competition,
        competition_ids=normalized_competition_ids,
        season_id=normalized_season,
        round_id=normalized_round,
        stage_id=normalized_stage_id,
        stage_format=normalized_stage_format,
        venue=normalized_venue,
        last_n=last_n,
        date_start=normalized_date_start,
        date_end=normalized_date_end,
    )


def append_fact_match_filters(
    clauses: list[str],
    params: list[Any],
    *,
    alias: str,
    filters: GlobalFilters,
    date_column: str = "date_day",
    league_column: str = "league_id",
    season_column: str = "season",
    round_column: str = "round_number",
    stage_column: str = "stage_id",
    competition_key_column: str = "competition_key",
    season_label_column: str = "season_label",
) -> None:
    if filters.competition_ids:
        clauses.append(f"{alias}.{league_column} = any(%s)")
        params.append(list(filters.competition_ids))

    if filters.season_id is not None:
        clauses.append(f"{alias}.{season_column} = %s")
        params.append(filters.season_id)

    if filters.round_id is not None:
        clauses.append(f"{alias}.{round_column} = %s")
        params.append(filters.round_id)

    if filters.stage_id is not None:
        clauses.append(f"{alias}.{stage_column} = %s")
        params.append(filters.stage_id)

    if filters.stage_format is not None:
        clauses.append(
            f"""
            exists (
                select 1
                from mart.dim_stage stage_filter_scope
                where stage_filter_scope.stage_id = {alias}.{stage_column}
                  and stage_filter_scope.competition_key = {alias}.{competition_key_column}
                  and stage_filter_scope.season_label = {alias}.{season_label_column}
                  and stage_filter_scope.stage_format = %s
            )
            """.strip()
        )
        params.append(filters.stage_format.value)

    if filters.date_start is not None:
        clauses.append(f"{alias}.{date_column} >= %s")
        params.append(filters.date_start)

    if filters.date_end is not None:
        clauses.append(f"{alias}.{date_column} <= %s")
        params.append(filters.date_end)
