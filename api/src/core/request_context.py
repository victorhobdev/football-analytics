from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass
class QueryStats:
    count: int = 0
    duration_ms: float = 0.0


_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_query_stats: ContextVar[QueryStats | None] = ContextVar("query_stats", default=None)


def begin_request_context(request_id: str) -> tuple[Token[str | None], Token[QueryStats | None]]:
    return _request_id.set(request_id), _query_stats.set(QueryStats())


def reset_request_context(
    request_id_token: Token[str | None],
    query_stats_token: Token[QueryStats | None],
) -> None:
    _query_stats.reset(query_stats_token)
    _request_id.reset(request_id_token)


def get_request_id() -> str | None:
    return _request_id.get()


def get_query_stats() -> QueryStats:
    stats = _query_stats.get()
    if stats is None:
        return QueryStats()
    return stats


def record_query(duration_ms: float) -> QueryStats:
    stats = _query_stats.get()
    if stats is None:
        return QueryStats(count=1, duration_ms=duration_ms)

    stats.count += 1
    stats.duration_ms += duration_ms
    return stats
