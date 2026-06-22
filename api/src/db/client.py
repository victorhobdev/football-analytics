from __future__ import annotations

import atexit
import logging
import time
from contextlib import contextmanager
from decimal import Decimal
from datetime import date, datetime
from typing import Any, Iterator, Sequence

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ..core.config import get_settings
from ..core.request_context import get_request_id, record_query


logger = logging.getLogger("football_bff.db")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def _summarize_query(query: str) -> str:
    return " ".join(query.split())[:500]


class DatabaseClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._pool = ConnectionPool(
            conninfo=settings.pg_dsn,
            min_size=settings.pg_pool_min_size,
            max_size=settings.pg_pool_max_size,
            timeout=settings.pg_pool_timeout_s,
            kwargs={"row_factory": dict_row},
            open=True,
        )
        atexit.register(self.close)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        with self._pool.connection() as conn:
            yield conn

    def close(self) -> None:
        self._pool.close()

    def fetch_all(self, query: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        started_at = time.perf_counter()
        rows: list[Any] = []
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params or [])
                    rows = cursor.fetchall()
        finally:
            self._record_query_metric(query, started_at, row_count=len(rows))
        return [_json_safe(dict(row)) for row in rows]

    def fetch_one(self, query: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
        started_at = time.perf_counter()
        row: Any | None = None
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params or [])
                    row = cursor.fetchone()
        finally:
            self._record_query_metric(query, started_at, row_count=1 if row is not None else 0)
        if row is None:
            return None
        return _json_safe(dict(row))

    def fetch_val(self, query: str, params: Sequence[Any] | None = None) -> Any:
        started_at = time.perf_counter()
        row: Any | None = None
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params or [])
                    row = cursor.fetchone()
        finally:
            self._record_query_metric(query, started_at, row_count=1 if row is not None else 0)
        if row is None:
            return None
        value = next(iter(row.values()))
        return _json_safe(value)

    def _record_query_metric(self, query: str, started_at: float, *, row_count: int) -> None:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        record_query(elapsed_ms)

        settings = get_settings()
        if elapsed_ms < settings.pg_query_log_min_ms:
            return

        logger.info(
            "db_query request_id=%s duration_ms=%.2f rows=%s query=%s",
            get_request_id() or "-",
            elapsed_ms,
            row_count,
            _summarize_query(query),
        )


db_client = DatabaseClient()
