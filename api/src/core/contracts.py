from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from typing import Any


def build_pagination(page: int, page_size: int, total_count: int) -> dict[str, Any]:
    total_pages = ceil(total_count / page_size) if page_size > 0 else 0
    return {
        "page": page,
        "pageSize": page_size,
        "totalCount": total_count,
        "totalPages": total_pages,
        "hasNextPage": page < total_pages,
        "hasPreviousPage": page > 1 and total_pages > 0,
    }


def build_coverage_from_counts(available_count: int, total_count: int, label: str | None = None) -> dict[str, Any]:
    if total_count <= 0 and available_count <= 0:
        status = "unknown"
        percentage = None
    elif total_count <= 0 and available_count > 0:
        status = "complete"
        percentage = 100
    else:
        percentage = round((available_count / total_count) * 100, 2)
        if available_count <= 0:
            status = "empty"
        elif available_count < total_count:
            status = "partial"
        else:
            status = "complete"

    payload: dict[str, Any] = {"status": status}
    if percentage is not None:
        payload["percentage"] = percentage
    if label:
        payload["label"] = label
    return payload


def build_api_response(
    data: Any,
    *,
    request_id: str | None,
    pagination: dict[str, Any] | None = None,
    coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "requestId": request_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
    if pagination is not None:
        meta["pagination"] = pagination
    if coverage is not None:
        meta["coverage"] = coverage

    return {
        "data": data,
        "meta": meta,
    }
