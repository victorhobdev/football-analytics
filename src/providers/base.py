from __future__ import annotations

from abc import ABC, abstractmethod


class BaseFootballProvider(ABC):
    @abstractmethod
    def get_fixtures(self, season: int) -> dict:
        pass

    @abstractmethod
    def get_standings(self, season: int) -> dict:
        pass

    def get_fixture_statistics(self, fixture_id: int) -> dict:
        raise NotImplementedError(f"{self.__class__.__name__} does not implement get_fixture_statistics")

    def get_fixture_events(self, fixture_id: int) -> dict:
        raise NotImplementedError(f"{self.__class__.__name__} does not implement get_fixture_events")
