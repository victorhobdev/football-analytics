from __future__ import annotations

import os

from src.config.settings import settings
from src.core.http_client import HttpClient
from src.providers.base import BaseFootballProvider


class APIFootballProvider(BaseFootballProvider):
    def __init__(
        self,
        *,
        client: HttpClient | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        league_id: int | None = None,
    ) -> None:
        self.client = client or HttpClient()
        self.api_key = api_key or settings.API_FOOTBALL_KEY
        if not self.api_key:
            raise RuntimeError(
                "Variavel de ambiente obrigatoria ausente: API_FOOTBALL_KEY (ou APIFOOTBALL_API_KEY)"
            )
        self.base_url = (base_url or os.getenv("APIFOOTBALL_BASE_URL", "https://v3.football.api-sports.io")).rstrip("/")
        self.league_id = league_id or int(os.getenv("APIFOOTBALL_LEAGUE_ID", "71"))

    def get_fixtures(self, season: int) -> dict:
        payload = self.client.get(
            f"{self.base_url}/fixtures",
            headers=self._headers(),
            params={"league": self.league_id, "season": season},
        )
        self._raise_if_api_errors(payload, endpoint="/fixtures")
        return payload

    def get_standings(self, season: int) -> dict:
        payload = self.client.get(
            f"{self.base_url}/standings",
            headers=self._headers(),
            params={"league": self.league_id, "season": season},
        )
        self._raise_if_api_errors(payload, endpoint="/standings")
        return payload

    def get_fixture_statistics(self, fixture_id: int) -> dict:
        payload = self.client.get(
            f"{self.base_url}/fixtures/statistics",
            headers=self._headers(),
            params={"fixture": fixture_id},
        )
        self._raise_if_api_errors(payload, endpoint="/fixtures/statistics")
        return payload

    def get_fixture_events(self, fixture_id: int) -> dict:
        payload = self.client.get(
            f"{self.base_url}/fixtures/events",
            headers=self._headers(),
            params={"fixture": fixture_id},
        )
        self._raise_if_api_errors(payload, endpoint="/fixtures/events")
        return payload

    def _headers(self) -> dict[str, str]:
        return {"x-apisports-key": self.api_key}

    def _raise_if_api_errors(self, payload: dict, *, endpoint: str) -> None:
        errors = payload.get("errors")
        if errors:
            raise RuntimeError(f"API-Football returned errors endpoint={endpoint}: {errors}")
