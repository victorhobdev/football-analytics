from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import time
from typing import Any

import requests

from src.config.settings import settings


class HttpClient:
    def __init__(
        self,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
        backoff_factor: float | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = settings.HTTP_TIMEOUT_SECONDS if timeout is None else timeout
        self.max_retries = settings.HTTP_MAX_RETRIES if max_retries is None else max_retries
        self.backoff_factor = settings.HTTP_BACKOFF_FACTOR if backoff_factor is None else backoff_factor
        self.session = session or requests.Session()
        self.logger = logging.getLogger(self.__class__.__name__)

    def get(self, url: str, headers: dict | None = None, params: dict | None = None) -> dict:
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            started = time.perf_counter()
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout,
                )
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                self._log(
                    event="http_get",
                    url=url,
                    status_code=response.status_code,
                    attempt=attempt,
                    duration_ms=elapsed_ms,
                    params=params,
                )

                if response.status_code == 429 and attempt < self.max_retries:
                    sleep_seconds = self._retry_after_seconds(response.headers.get("Retry-After"), attempt)
                    time.sleep(sleep_seconds)
                    continue

                if 500 <= response.status_code <= 599 and attempt < self.max_retries:
                    sleep_seconds = self.backoff_factor * (2**attempt)
                    time.sleep(sleep_seconds)
                    continue

                if response.status_code >= 400:
                    body_preview = (response.text or "")[:500]
                    raise RuntimeError(
                        f"HTTP GET failed status={response.status_code} url={url} body={body_preview}"
                    )

                payload = response.json()
                if not isinstance(payload, dict):
                    raise RuntimeError(f"HTTP GET expected dict payload for url={url}")
                return payload
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                self._log(
                    event="http_get_error",
                    url=url,
                    status_code=None,
                    attempt=attempt,
                    duration_ms=elapsed_ms,
                    params=params,
                    error=type(exc).__name__,
                )
                if attempt >= self.max_retries:
                    raise RuntimeError(f"HTTP GET network failure url={url}: {exc}") from exc
                time.sleep(self.backoff_factor * (2**attempt))

        raise RuntimeError(f"HTTP GET exhausted retries url={url} error={last_error}")

    def _retry_after_seconds(self, retry_after: str | None, attempt: int) -> float:
        if retry_after and retry_after.isdigit():
            return float(retry_after)
        return self.backoff_factor * (2**attempt)

    def _log(
        self,
        *,
        event: str,
        url: str,
        status_code: int | None,
        attempt: int,
        duration_ms: int,
        params: dict[str, Any] | None,
        error: str | None = None,
    ) -> None:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "url": url,
            "status_code": status_code,
            "attempt": attempt,
            "duration_ms": duration_ms,
            "params": params or {},
            "error": error,
        }
        self.logger.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
