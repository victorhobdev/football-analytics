from __future__ import annotations

from pathlib import Path

import pytest

from src.providers.apifootball import APIFootballProvider


class _SpyHttpClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get(self, url: str, headers: dict | None = None, params: dict | None = None) -> dict:
        self.calls.append({"url": url, "headers": headers, "params": params})
        return {"errors": {}, "response": []}


def test_apifootball_provider_uses_http_client(monkeypatch):
    monkeypatch.setenv("APIFOOTBALL_API_KEY", "test-key")
    spy = _SpyHttpClient()
    provider = APIFootballProvider(client=spy, base_url="https://api.test", league_id=71)

    provider.get_fixtures(2024)
    provider.get_standings(2024)
    provider.get_fixture_statistics(1234)
    provider.get_fixture_events(1234)

    assert len(spy.calls) == 4
    assert spy.calls[0]["url"] == "https://api.test/fixtures"
    assert spy.calls[1]["url"] == "https://api.test/standings"
    assert spy.calls[2]["url"] == "https://api.test/fixtures/statistics"
    assert spy.calls[3]["url"] == "https://api.test/fixtures/events"
    assert spy.calls[0]["headers"] == {"x-apisports-key": "test-key"}
    assert spy.calls[0]["params"] == {"league": 71, "season": 2024}
    assert spy.calls[2]["params"] == {"fixture": 1234}
    assert spy.calls[3]["params"] == {"fixture": 1234}


def test_apifootball_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("APIFOOTBALL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="APIFOOTBALL_API_KEY"):
        APIFootballProvider(base_url="https://api.test")


def test_no_requests_get_in_dags():
    dag_dir = Path("infra/airflow/dags")
    offenders: list[str] = []

    for py_file in dag_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if "requests.get" in content:
            offenders.append(str(py_file))

    assert not offenders, (
        "Encontrado requests.get nos DAGs (equivalente a grep -R \"requests.get\" infra/airflow/dags): "
        f"{offenders}"
    )
