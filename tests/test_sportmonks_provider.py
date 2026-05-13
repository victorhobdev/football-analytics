from __future__ import annotations

import pytest

from src.providers.sportmonks import SportMonksProvider


def test_sportmonks_provider_stub_methods_raise_not_implemented():
    provider = SportMonksProvider()
    with pytest.raises(NotImplementedError, match="not implemented yet"):
        provider.get_fixtures(2024)
    with pytest.raises(NotImplementedError, match="not implemented yet"):
        provider.get_standings(2024)
    with pytest.raises(NotImplementedError, match="not implemented yet"):
        provider.get_fixture_statistics(1)
    with pytest.raises(NotImplementedError, match="not implemented yet"):
        provider.get_fixture_events(1)
