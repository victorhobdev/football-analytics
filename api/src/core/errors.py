from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class AppError(Exception):
    message: str
    code: str
    status: int
    details: Any | None = None

    def __str__(self) -> str:
        return self.message


def error_payload(
    message: str,
    code: str,
    status: int,
    details: Any | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "message": message,
        "code": code,
        "status": status,
    }
    if details is not None:
        error["details"] = details

    payload: dict[str, Any] = {
        "data": None,
        "error": error,
        "meta": {
            "requestId": request_id,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        },
        "message": message,
        "code": code,
        "status": status,
    }
    if details is not None:
        payload["details"] = details
    return payload
