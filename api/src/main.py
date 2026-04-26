from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import Settings, get_settings
from .core.errors import AppError, error_payload
from .core.rate_limit import InMemoryRateLimiter
from .core.request_context import begin_request_context, get_query_stats, reset_request_context
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
from .routers.world_cup import router as world_cup_router


def _configure_logging() -> logging.Logger:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("football_bff")


logger = _configure_logging()


def _api_docs_url(settings: Settings) -> str | None:
    return "/docs" if settings.expose_api_docs else None


def _api_redoc_url(settings: Settings) -> str | None:
    return "/redoc" if settings.expose_api_docs else None


def _api_openapi_url(settings: Settings) -> str | None:
    return "/openapi.json" if settings.expose_api_docs else None


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    return str(getattr(route, "path", request.url.path))


def _request_settings(request: Request) -> Settings:
    return request.app.state.settings


def _client_identifier(request: Request, settings: Settings) -> str:
    if settings.rate_limit_trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for.strip():
            return forwarded_for.split(",", maxsplit=1)[0].strip()

    if request.client is None:
        return "unknown"
    return request.client.host


def _rate_limit_bucket(path: str, settings: Settings) -> tuple[str, int]:
    if path == "/health":
        return "health", settings.rate_limit_health_per_minute

    if path.startswith("/api/v1/search"):
        return "search", settings.rate_limit_search_per_minute

    return "default", settings.rate_limit_default_per_minute


def _rate_limit_response(request: Request, request_id: str) -> JSONResponse | None:
    settings = _request_settings(request)
    if not settings.rate_limit_enabled:
        return None

    bucket, limit = _rate_limit_bucket(request.url.path, settings)
    client_id = _client_identifier(request, settings)
    limiter: InMemoryRateLimiter = request.app.state.rate_limiter
    decision = limiter.check(
        key=f"{bucket}:{client_id}",
        limit=limit,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if decision.allowed:
        return None

    response = JSONResponse(
        status_code=429,
        content=error_payload(
            message="Too many requests.",
            code="RATE_LIMITED",
            status=429,
            details={
                "bucket": bucket,
                "limit": decision.limit,
                "windowSeconds": settings.rate_limit_window_seconds,
            },
            request_id=request_id,
        ),
    )
    response.headers["Retry-After"] = str(decision.retry_after_seconds)
    response.headers["X-RateLimit-Limit"] = str(decision.limit)
    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
    return response


async def request_logging_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id
    started_at = time.perf_counter()
    request_id_token, query_stats_token = begin_request_context(request_id)

    try:
        response = _rate_limit_response(request, request_id)
        if response is None:
            response = await call_next(request)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "request_failed method=%s path=%s route=%s request_id=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            _route_path(request),
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
                request_id=request_id,
            ),
        )

    response.headers["X-Request-Id"] = request_id
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    query_stats = get_query_stats()
    if response.status_code >= 500:
        logger.error(
            "request method=%s path=%s route=%s status=%s request_id=%s duration_ms=%.2f db_queries=%s db_duration_ms=%.2f",
            request.method,
            request.url.path,
            _route_path(request),
            response.status_code,
            request_id,
            elapsed_ms,
            query_stats.count,
            query_stats.duration_ms,
        )
    else:
        logger.info(
            "request method=%s path=%s route=%s status=%s request_id=%s duration_ms=%.2f db_queries=%s db_duration_ms=%.2f",
            request.method,
            request.url.path,
            _route_path(request),
            response.status_code,
            request_id,
            elapsed_ms,
            query_stats.count,
            query_stats.duration_ms,
        )
    reset_request_context(request_id_token, query_stats_token)
    return response


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
        content=error_payload(
            exc.message,
            exc.code,
            exc.status,
            exc.details,
            request_id=_request_id(request),
        ),
    )


def _sanitize_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for error in errors:
        location = tuple(str(part) for part in error.get("loc", ()))
        sanitized.append(
            {
                "location": list(location),
                "field": ".".join(location[1:]) if len(location) > 1 else "",
                "type": str(error.get("type", "validation_error")),
            },
        )
    return sanitized


def _validation_error_contract(errors: list[dict[str, Any]]) -> tuple[str, str]:
    locations = {str((error.get("loc") or ["request"])[0]) for error in errors}
    if "path" in locations:
        return "Invalid path parameters.", "INVALID_PATH_PARAM"
    if "body" in locations:
        return "Invalid request body.", "INVALID_REQUEST_BODY"
    if "header" in locations:
        return "Invalid request headers.", "INVALID_HEADER"
    if "cookie" in locations:
        return "Invalid request cookies.", "INVALID_COOKIE"
    return "Invalid query parameters.", "INVALID_QUERY_PARAM"


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:  # type: ignore[no-untyped-def]
    validation_errors = exc.errors()
    details = {"errors": _sanitize_validation_errors(validation_errors)}
    message, code = _validation_error_contract(validation_errors)
    return JSONResponse(
        status_code=400,
        content=error_payload(
            message=message,
            code=code,
            status=400,
            details=details,
            request_id=_request_id(request),
        ),
    )


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:  # type: ignore[no-untyped-def]
    code = "INTERNAL_ERROR" if exc.status_code >= 500 else "INVALID_QUERY_PARAM"
    message = str(exc.detail) if exc.detail else "HTTP error."
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            message=message,
            code=code,
            status=exc.status_code,
            request_id=_request_id(request),
        ),
    )


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
            request_id=_request_id(request),
        ),
    )


def _include_routers(application: FastAPI) -> None:
    application.include_router(health_router)
    application.include_router(competition_hub_router)
    application.include_router(home_router)
    application.include_router(coaches_router)
    application.include_router(market_router)
    application.include_router(players_router)
    application.include_router(teams_router)
    application.include_router(rankings_router)
    application.include_router(search_router)
    application.include_router(standings_router)
    application.include_router(matches_router)
    application.include_router(insights_router)
    application.include_router(world_cup_router)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    application = FastAPI(
        title=app_settings.app_name,
        version="1.0.0",
        docs_url=_api_docs_url(app_settings),
        redoc_url=_api_redoc_url(app_settings),
        openapi_url=_api_openapi_url(app_settings),
    )
    application.state.settings = app_settings
    application.state.rate_limiter = InMemoryRateLimiter()

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_allow_origins),
        allow_credentials=app_settings.cors_allow_credentials,
        allow_methods=list(app_settings.cors_allow_methods),
        allow_headers=list(app_settings.cors_allow_headers),
    )
    application.middleware("http")(request_logging_middleware)
    application.add_exception_handler(AppError, app_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(HTTPException, http_error_handler)
    application.add_exception_handler(Exception, unhandled_error_handler)
    _include_routers(application)
    return application


app = create_app()
