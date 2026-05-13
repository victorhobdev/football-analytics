from __future__ import annotations

from src.providers.base import BaseFootballProvider


class SportMonksProvider(BaseFootballProvider):
    def get_fixtures(self, season: int) -> dict:
        raise NotImplementedError("SportMonksProvider not implemented yet")

    def get_standings(self, season: int) -> dict:
        raise NotImplementedError("SportMonksProvider not implemented yet")

    def get_fixture_statistics(self, fixture_id: int) -> dict:
        raise NotImplementedError("SportMonksProvider not implemented yet")

    def get_fixture_events(self, fixture_id: int) -> dict:
        raise NotImplementedError("SportMonksProvider not implemented yet")
