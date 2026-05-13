from __future__ import annotations

from pathlib import Path
import sys

import pytest


DAGS_DIR = Path("infra/airflow/dags").resolve()
if str(DAGS_DIR) not in sys.path:
    sys.path.insert(0, str(DAGS_DIR))

from common.providers.registry import get_default_provider, normalize_provider_name, provider_env_prefix


def test_normalize_provider_name_accepts_aliases():
    assert normalize_provider_name("sportmonks") == "sportmonks"
    assert normalize_provider_name("api_football") == "api_football"
    assert normalize_provider_name("api-football") == "api_football"
    assert normalize_provider_name("apifootball") == "api_football"


def test_get_default_provider_reads_and_normalizes_active_provider(monkeypatch):
    monkeypatch.setenv("ACTIVE_PROVIDER", "api-football")
    assert get_default_provider() == "api_football"


def test_provider_env_prefix_uses_canonical_names():
    assert provider_env_prefix("sportmonks") == "SPORTMONKS"
    assert provider_env_prefix("api-football") == "APIFOOTBALL"


def test_normalize_provider_name_rejects_invalid_value():
    with pytest.raises(RuntimeError, match="Provider nao suportado"):
        normalize_provider_name("invalid-provider")
