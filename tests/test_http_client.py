from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
import requests

from common.http_client import ProviderHttpClient


def _response(status_code: int, *, headers: dict[str, str] | None = None, payload: dict | None = None):
    response = Mock()
    response.status_code = status_code
    response.headers = headers or {}
    response.text = "retryable failure"
    response.json.return_value = payload or {"data": []}
    return response


def test_retries_retryable_status_and_returns_success_payload():
    client = ProviderHttpClient(provider="test", base_url="https://example.test", max_retries=1)
    retry_response = _response(503)
    success_response = _response(200, headers={"X-Request-Id": "run-1"}, payload={"data": [1]})

    with patch.object(client._session, "request", side_effect=[retry_response, success_response]) as request, patch(
        "common.http_client.time.sleep"
    ) as sleep:
        payload, headers = client.request_json(endpoint="/fixtures", params={"api_key": "secret", "page": 1})

    assert payload == {"data": [1]}
    assert headers == {"X-Request-Id": "run-1"}
    assert request.call_count == 2
    sleep.assert_called_once_with(2.0)


def test_honors_retry_after_header():
    client = ProviderHttpClient(provider="test", base_url="https://example.test", max_retries=1, backoff_seconds=99)
    retry_response = _response(429, headers={"Retry-After": "3"})
    success_response = _response(200)

    with patch.object(client._session, "request", side_effect=[retry_response, success_response]), patch(
        "common.http_client.time.sleep"
    ) as sleep:
        client.request_json(endpoint="/fixtures")

    sleep.assert_called_once_with(3.0)


def test_raises_after_connection_retries_are_exhausted():
    client = ProviderHttpClient(provider="test", base_url="https://example.test", max_retries=1)

    with patch.object(
        client._session, "request", side_effect=requests.ConnectionError("offline")
    ) as request, patch("common.http_client.time.sleep") as sleep:
        with pytest.raises(RuntimeError, match="erro_rede=ConnectionError"):
            client.request_json(endpoint="/fixtures")

    assert request.call_count == 2
    sleep.assert_called_once_with(2.0)
