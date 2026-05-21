from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Query, Request

from ..core.errors import AppError
from ..core.filters import VenueFilter, validate_and_build_global_filters

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])

EntityType = Literal["player", "team", "match", "competition", "global"]
Severity = Literal["info", "warning", "critical"]
SortBy = Literal["severity", "referencePeriod"]
SortDirection = Literal["asc", "desc"]


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("", deprecated=True)
def get_insights(
    request: Request,
    entityType: EntityType = "global",
    entityId: str | None = None,
    competitionId: str | None = None,
    seasonId: str | None = None,
    roundId: str | None = None,
    venue: VenueFilter = VenueFilter.all,
    lastN: int | None = Query(default=None, gt=0),
    dateStart: date | None = None,
    dateEnd: date | None = None,
    dateRangeStart: date | None = None,
    dateRangeEnd: date | None = None,
    severity: Severity | None = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    sortBy: SortBy = "severity",
    sortDirection: SortDirection = "desc",
) -> dict[str, Any]:
    validate_and_build_global_filters(
        competition_id=competitionId,
        season_id=seasonId,
        round_id=roundId,
        venue=venue,
        last_n=lastN,
        date_start=dateStart,
        date_end=dateEnd,
        date_range_start=dateRangeStart,
        date_range_end=dateRangeEnd,
    )

    if entityType != "global" and (entityId is None or entityId.strip() == ""):
        raise AppError(
            message="Invalid insight context. 'entityId' is required when entityType is not 'global'.",
            code="INVALID_INSIGHT_CONTEXT",
            status=400,
            details={"entityType": entityType},
        )

    raise AppError(
        message="Insights endpoint is not implemented yet.",
        code="FEATURE_NOT_IMPLEMENTED",
        status=501,
        details={
            "entityType": entityType,
            "entityId": entityId,
            "unsupportedParameters": {
                "severity": severity,
                "sortBy": sortBy,
                "sortDirection": sortDirection,
                "page": page,
                "pageSize": pageSize,
            },
        },
    )
