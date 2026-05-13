from __future__ import annotations

from src.config.settings import settings
from src.providers.apifootball import APIFootballProvider
from src.providers.base import BaseFootballProvider
from src.providers.sportmonks import SportMonksProvider


def get_provider() -> BaseFootballProvider:
    provider = settings.validate_active_provider()
    if provider == "apifootball":
        return APIFootballProvider(api_key=settings.API_FOOTBALL_KEY)
    if provider == "sportmonks":
        return SportMonksProvider()
    raise ValueError(f"Unsupported ACTIVE_PROVIDER='{settings.ACTIVE_PROVIDER}'")
