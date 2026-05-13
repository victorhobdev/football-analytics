from __future__ import annotations

from src.core.http_client import HttpClient


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict, headers: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


def test_http_client_retries_on_429(monkeypatch):
    responses = [
        _FakeResponse(429, {"error": "rate_limit"}, headers={"Retry-After": "0"}),
        _FakeResponse(200, {"ok": True}),
    ]
    client = HttpClient(max_retries=2, backoff_factor=0.0)

    def fake_get(url, headers=None, params=None, timeout=None):
        return responses.pop(0)

    sleeps: list[float] = []
    monkeypatch.setattr(client.session, "get", fake_get)
    monkeypatch.setattr("src.core.http_client.time.sleep", lambda value: sleeps.append(value))

    payload = client.get("https://example.com/fixtures")
    assert payload == {"ok": True}
    assert len(sleeps) == 1


def test_http_client_retries_on_500(monkeypatch):
    responses = [
        _FakeResponse(500, {"error": "temporary"}, text="temporary error"),
        _FakeResponse(200, {"ok": True}),
    ]
    client = HttpClient(max_retries=2, backoff_factor=0.0)

    def fake_get(url, headers=None, params=None, timeout=None):
        return responses.pop(0)

    sleeps: list[float] = []
    monkeypatch.setattr(client.session, "get", fake_get)
    monkeypatch.setattr("src.core.http_client.time.sleep", lambda value: sleeps.append(value))

    payload = client.get("https://example.com/standings")
    assert payload == {"ok": True}
    assert len(sleeps) == 1

