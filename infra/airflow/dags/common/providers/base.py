from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

JsonDict = dict[str, Any]


class ProviderAdapter(ABC):
    name: str

    @abstractmethod
    def get_fixtures(
        self,
        *,
        league_id: int,
        season: int,
        date_from: str,
        date_to: str,
    ) -> tuple[JsonDict, dict[str, str]]:
        """Fetch fixtures for a date window and return canonical bronze payload."""

    @abstractmethod
    def get_fixture_statistics(
        self,
        *,
        fixture_id: int,
    ) -> tuple[JsonDict, dict[str, str]]:
        """Fetch fixture statistics and return canonical bronze payload."""

    @abstractmethod
    def get_fixture_events(
        self,
        *,
        fixture_id: int,
    ) -> tuple[JsonDict, dict[str, str]]:
        """Fetch fixture events and return canonical bronze payload."""

    @abstractmethod
    def get_standings(
        self,
        *,
        league_id: int,
        season: int,
    ) -> tuple[JsonDict, dict[str, str]]:
        """Fetch standings in canonical envelope format."""

    # Backward-compatible aliases
    def fetch_fixtures(
        self,
        *,
        league_id: int,
        season: int,
        date_from: str,
        date_to: str,
    ) -> tuple[JsonDict, dict[str, str]]:
        return self.get_fixtures(
            league_id=league_id,
            season=season,
            date_from=date_from,
            date_to=date_to,
        )

    def fetch_fixture_statistics(
        self,
        *,
        fixture_id: int,
    ) -> tuple[JsonDict, dict[str, str]]:
        return self.get_fixture_statistics(fixture_id=fixture_id)

    def fetch_fixture_events(
        self,
        *,
        fixture_id: int,
    ) -> tuple[JsonDict, dict[str, str]]:
        return self.get_fixture_events(fixture_id=fixture_id)
