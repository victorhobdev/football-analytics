from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import get_settings
from .core.errors import AppError, error_payload
from .routers.coaches import router as coaches_router
from .routers.competition_hub import router as competition_hub_router
from .routers.health import router as health_router
from .routers.home import router as home_router
from .routers.insights import router as insights_router
from .routers.market import router as market_router
from .routers.matches import router as matches_router
from .routers.players import router as players_router
from .routers.rankings import router as rankings_router
from .routers.search import router as search_router
from .routers.standings import router as standings_router
from .routers.teams import router as teams_router
from .routers.world_cup_2022 import router as world_cup_2022_router


def _configure_logging() -> logging.Logger:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("football_bff")


logger = _configure_logging()
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "request_failed method=%s path=%s request_id=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            request_id,
            elapsed_ms,
        )
        response = JSONResponse(
            status_code=500,
            content=error_payload(
                message="Internal server error.",
                code="INTERNAL_ERROR",
                status=500,
                details={"error": type(exc).__name__},
            ),
        )

    response.headers["X-Request-Id"] = request_id
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    if response.status_code >= 500:
        logger.error(
            "request method=%s path=%s status=%s request_id=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
            elapsed_ms,
        )
    else:
        logger.info(
            "request method=%s path=%s status=%s request_id=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
            elapsed_ms,
        )
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:  # type: ignore[no-untyped-def]
    logger.warning(
        "app_error code=%s status=%s path=%s request_id=%s",
        exc.code,
        exc.status,
        request.url.path,
        getattr(request.state, "request_id", "-"),
    )
    return JSONResponse(
        status_code=exc.status,
        content=error_payload(exc.message, exc.code, exc.status, exc.details),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:  # type: ignore[no-untyped-def]
    details: dict[str, Any] = {"errors": exc.errors()}
    return JSONResponse(
        status_code=400,
        content=error_payload(
            message="Invalid query parameters.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details=details,
        ),
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:  # type: ignore[no-untyped-def]
    code = "INTERNAL_ERROR" if exc.status_code >= 500 else "INVALID_QUERY_PARAM"
    message = str(exc.detail) if exc.detail else "HTTP error."
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(message=message, code=code, status=exc.status_code),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:  # type: ignore[no-untyped-def]
    logger.exception(
        "unhandled_error path=%s request_id=%s",
        request.url.path,
        getattr(request.state, "request_id", "-"),
    )
    return JSONResponse(
        status_code=500,
        content=error_payload(
            message="Internal server error.",
            code="INTERNAL_ERROR",
            status=500,
            details={"error": type(exc).__name__},
        ),
    )


app.include_router(health_router)
app.include_router(competition_hub_router)
app.include_router(home_router)
app.include_router(coaches_router)
app.include_router(market_router)
app.include_router(players_router)
app.include_router(teams_router)
app.include_router(rankings_router)
app.include_router(search_router)
app.include_router(standings_router)
app.include_router(matches_router)
app.include_router(insights_router)
app.include_router(world_cup_2022_router)
