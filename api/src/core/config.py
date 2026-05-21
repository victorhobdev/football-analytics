from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache


DEFAULT_CORS_ALLOW_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
)
DEFAULT_CORS_ALLOW_METHODS = ("GET", "HEAD", "OPTIONS")
DEFAULT_CORS_ALLOW_HEADERS = (
    "Accept",
    "Accept-Language",
    "Authorization",
    "Content-Language",
    "Content-Type",
    "X-Request-Id",
)
LOCAL_ENVIRONMENTS = {"local", "dev", "development", "test"}


def _build_default_pg_dsn() -> str:
    user = os.getenv("POSTGRES_USER", "football")
    password = os.getenv("POSTGRES_PASSWORD", "football")
    database = os.getenv("POSTGRES_DB", "football_dw")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    log_level: str
    expose_api_docs: bool
    cors_allow_origins: tuple[str, ...]
    cors_allow_credentials: bool
    cors_allow_methods: tuple[str, ...]
    cors_allow_headers: tuple[str, ...]
    rate_limit_enabled: bool
    rate_limit_default_per_minute: int
    rate_limit_search_per_minute: int
    rate_limit_health_per_minute: int
    rate_limit_window_seconds: int
    rate_limit_trust_proxy_headers: bool
    pg_dsn: str
    pg_pool_min_size: int
    pg_pool_max_size: int
    pg_pool_timeout_s: float
    pg_query_log_min_ms: float
    product_data_cutoff: date


def _parse_csv_env(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None or not value.strip():
        return default

    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


def _parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False

    raise ValueError(f"{name} must be a boolean value.")


def _parse_int_env(name: str, default: int, *, minimum: int = 0) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default

    parsed = int(value)
    if parsed < minimum:
        raise ValueError(f"{name} must be >= {minimum}.")
    return parsed


def _is_local_environment(environment: str) -> bool:
    return environment.strip().lower() in LOCAL_ENVIRONMENTS


def _validate_cors_settings(
    *,
    allow_credentials: bool,
    allow_headers: tuple[str, ...],
    allow_methods: tuple[str, ...],
    allow_origins: tuple[str, ...],
    environment: str,
) -> None:
    if allow_credentials and (
        "*" in allow_origins or "*" in allow_methods or "*" in allow_headers
    ):
        raise ValueError("CORS credentials require explicit origins, methods and headers.")

    if not _is_local_environment(environment) and "*" in allow_origins:
        raise ValueError("BFF_CORS_ALLOW_ORIGINS must be explicit outside local environments.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = os.getenv("ENVIRONMENT", "local").strip().lower()
    pg_dsn = os.getenv("FOOTBALL_PG_DSN") or os.getenv("DATABASE_URL") or _build_default_pg_dsn()
    cors_allow_origins = _parse_csv_env(
        os.getenv("BFF_CORS_ALLOW_ORIGINS"),
        DEFAULT_CORS_ALLOW_ORIGINS,
    )
    cors_allow_credentials = _parse_bool_env("BFF_CORS_ALLOW_CREDENTIALS", False)
    cors_allow_methods = _parse_csv_env(
        os.getenv("BFF_CORS_ALLOW_METHODS"),
        DEFAULT_CORS_ALLOW_METHODS,
    )
    cors_allow_headers = _parse_csv_env(
        os.getenv("BFF_CORS_ALLOW_HEADERS"),
        DEFAULT_CORS_ALLOW_HEADERS,
    )
    _validate_cors_settings(
        allow_credentials=cors_allow_credentials,
        allow_headers=cors_allow_headers,
        allow_methods=cors_allow_methods,
        allow_origins=cors_allow_origins,
        environment=environment,
    )

    return Settings(
        app_name=os.getenv("BFF_APP_NAME", "football-analytics-bff"),
        environment=environment,
        log_level=os.getenv("BFF_LOG_LEVEL", "INFO").upper(),
        expose_api_docs=_parse_bool_env("BFF_EXPOSE_API_DOCS", _is_local_environment(environment)),
        cors_allow_origins=cors_allow_origins,
        cors_allow_credentials=cors_allow_credentials,
        cors_allow_methods=cors_allow_methods,
        cors_allow_headers=cors_allow_headers,
        rate_limit_enabled=_parse_bool_env("BFF_RATE_LIMIT_ENABLED", True),
        rate_limit_default_per_minute=_parse_int_env("BFF_RATE_LIMIT_DEFAULT_PER_MINUTE", 300, minimum=1),
        rate_limit_search_per_minute=_parse_int_env("BFF_RATE_LIMIT_SEARCH_PER_MINUTE", 60, minimum=1),
        rate_limit_health_per_minute=_parse_int_env("BFF_RATE_LIMIT_HEALTH_PER_MINUTE", 600, minimum=1),
        rate_limit_window_seconds=_parse_int_env("BFF_RATE_LIMIT_WINDOW_SECONDS", 60, minimum=1),
        rate_limit_trust_proxy_headers=_parse_bool_env("BFF_RATE_LIMIT_TRUST_PROXY_HEADERS", False),
        pg_dsn=pg_dsn,
        pg_pool_min_size=int(os.getenv("FOOTBALL_PG_POOL_MIN_SIZE", "1")),
        pg_pool_max_size=int(os.getenv("FOOTBALL_PG_POOL_MAX_SIZE", "10")),
        pg_pool_timeout_s=float(os.getenv("FOOTBALL_PG_POOL_TIMEOUT_S", "10")),
        pg_query_log_min_ms=float(os.getenv("FOOTBALL_PG_QUERY_LOG_MIN_MS", "250")),
        product_data_cutoff=date.fromisoformat(os.getenv("PRODUCT_DATA_CUTOFF", "2025-12-31")),
    )
