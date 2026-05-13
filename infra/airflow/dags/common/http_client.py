from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any

import requests


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_params(params: dict[str, Any] | None) -> dict[str, Any]:
    if not params:
        return {}
    safe: dict[str, Any] = {}
    for key, value in params.items():
        lowered = key.lower()
        if "token" in lowered or "key" in lowered or "secret" in lowered or "password" in lowered:
            safe[key] = "***"
        else:
            safe[key] = value
    return safe


def _http_logger() -> logging.Logger:
    return logging.getLogger("football_http_client")


class ProviderHttpClient:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        default_headers: dict[str, str] | None = None,
        timeout_seconds: float = 45.0,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
        requests_per_minute: int | None = None,
    ):
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.default_headers = default_headers or {}
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.requests_per_minute = requests_per_minute
        self._session = requests.Session()
        self._next_allowed_at = 0.0
        self._request_interval = 0.0
        if requests_per_minute and requests_per_minute > 0:
            self._request_interval = 60.0 / float(requests_per_minute)

    @classmethod
    def from_env(
        cls,
        *,
        provider: str,
        base_url: str,
        default_headers: dict[str, str] | None = None,
        requests_per_minute: int | None = None,
    ) -> "ProviderHttpClient":
        timeout_seconds = float(os.getenv("INGEST_HTTP_TIMEOUT_SECONDS", "45"))
        max_retries = int(os.getenv("INGEST_HTTP_MAX_RETRIES", "3"))
        backoff_seconds = float(os.getenv("INGEST_HTTP_BACKOFF_SECONDS", "2"))
        rpm_env = os.getenv("INGEST_HTTP_REQUESTS_PER_MINUTE")
        rpm = requests_per_minute
        if rpm is None and rpm_env:
            rpm = int(rpm_env)
        return cls(
            provider=provider,
            base_url=base_url,
            default_headers=default_headers,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            requests_per_minute=rpm,
        )

    def _log_event(
        self,
        *,
        endpoint: str,
        params: dict[str, Any] | None,
        status_code: int | None,
        duration_ms: int,
        attempt: int,
        final: bool,
        error: str | None = None,
    ):
        payload = {
            "ts": _utc_now(),
            "component": "http_client",
            "provider": self.provider,
            "endpoint": endpoint,
            "params": _safe_params(params),
            "status_code": status_code,
            "duration_ms": duration_ms,
            "attempt": attempt,
            "final": final,
            "error": error,
        }
        _http_logger().info(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    def _throttle(self):
        if self._request_interval <= 0:
            return
        now = time.monotonic()
        wait_seconds = self._next_allowed_at - now
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        self._next_allowed_at = time.monotonic() + self._request_interval

    def request_json(
        self,
        *,
        endpoint: str,
        params: dict[str, Any] | None = None,
        method: str = "GET",
        headers: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        url = f"{self.base_url}{endpoint}"
        merged_headers = {**self.default_headers, **(headers or {})}
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            self._throttle()
            started = time.perf_counter()
            try:
                response = self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=merged_headers,
                    timeout=self.timeout_seconds,
                )
                duration_ms = int((time.perf_counter() - started) * 1000)
                status_code = response.status_code

                if status_code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        sleep_seconds = float(retry_after)
                    else:
                        sleep_seconds = self.backoff_seconds * (2**attempt)
                    self._log_event(
                        endpoint=endpoint,
                        params=params,
                        status_code=status_code,
                        duration_ms=duration_ms,
                        attempt=attempt,
                        final=False,
                        error=f"retryable_status={status_code}",
                    )
                    time.sleep(sleep_seconds)
                    continue

                if status_code >= 400:
                    body = (response.text or "")[:600]
                    self._log_event(
                        endpoint=endpoint,
                        params=params,
                        status_code=status_code,
                        duration_ms=duration_ms,
                        attempt=attempt,
                        final=True,
                        error=f"http_error status={status_code}",
                    )
                    raise RuntimeError(
                        f"provider={self.provider} endpoint={endpoint} status={status_code} body={body}"
                    )

                payload = response.json()
                self._log_event(
                    endpoint=endpoint,
                    params=params,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    attempt=attempt,
                    final=True,
                )
                return payload, {k: v for k, v in response.headers.items()}
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                duration_ms = int((time.perf_counter() - started) * 1000)
                if attempt < self.max_retries:
                    self._log_event(
                        endpoint=endpoint,
                        params=params,
                        status_code=None,
                        duration_ms=duration_ms,
                        attempt=attempt,
                        final=False,
                        error=type(exc).__name__,
                    )
                    time.sleep(self.backoff_seconds * (2**attempt))
                    continue
                self._log_event(
                    endpoint=endpoint,
                    params=params,
                    status_code=None,
                    duration_ms=duration_ms,
                    attempt=attempt,
                    final=True,
                    error=type(exc).__name__,
                )
                raise RuntimeError(
                    f"provider={self.provider} endpoint={endpoint} erro_rede={type(exc).__name__}: {exc}"
                ) from exc

        raise RuntimeError(
            f"provider={self.provider} endpoint={endpoint} retries_excedidos error={last_error}"
        )
