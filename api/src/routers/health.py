from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..db.client import db_client

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck():
    try:
        db_client.fetch_val("select 1;")
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "checks": {
                    "database": {
                        "status": "error",
                        "error": type(exc).__name__,
                    },
                },
            },
        )

    return {
        "status": "ok",
        "checks": {
            "database": {
                "status": "ok",
            },
        },
    }
