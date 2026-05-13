from __future__ import annotations

import pytest

from src.providers.apifootball import APIFootballProvider
from src.providers.factory import get_provider
from src.providers.sportmonks import SportMonksProvider


def test_provider_factory_defaults_to_apifootball(monkeypatch):
    monkeypatch.delenv("ACTIVE_PROVIDER", raising=False)
    monkeypatch.setenv("API_FOOTBALL_KEY", "test-key")
    monkeypatch.delenv("APIFOOTBALL_API_KEY", raising=False)

    provider = get_provider()

    assert isinstance(provider, APIFootballProvider)


def test_provider_factory_returns_sportmonks(monkeypatch):
    monkeypatch.setenv("ACTIVE_PROVIDER", "sportmonks")

    provider = get_provider()

    assert isinstance(provider, SportMonksProvider)


def test_provider_factory_rejects_invalid_provider(monkeypatch):
    monkeypatch.setenv("ACTIVE_PROVIDER", "invalid-provider")

    with pytest.raises(ValueError, match="Unsupported ACTIVE_PROVIDER"):
        get_provider()
