from __future__ import annotations

import os

from .api_football import APIFootballProvider
from .base import ProviderAdapter
from .sportmonks import SportMonksProvider


DEFAULT_ACTIVE_PROVIDER = "sportmonks"
PROVIDER_ENV_PREFIX = {
    "sportmonks": "SPORTMONKS",
    "api_football": "APIFOOTBALL",
}

PROVIDER_ALIASES = {
    "sportmonks": "sportmonks",
    "api-football": "api_football",
    "api_football": "api_football",
    "apifootball": "api_football",
}


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def normalize_provider_name(name: str) -> str:
    normalized = name.strip().lower()
    canonical = PROVIDER_ALIASES.get(normalized)
    if not canonical:
        supported = ", ".join(sorted(PROVIDER_ALIASES.keys()))
        raise RuntimeError(f"Provider nao suportado: {name}. Valores aceitos: {supported}")
    return canonical


def get_default_provider() -> str:
    selected = os.getenv("ACTIVE_PROVIDER", DEFAULT_ACTIVE_PROVIDER)
    return normalize_provider_name(selected)


def provider_env_prefix(provider_name: str) -> str:
    canonical = normalize_provider_name(provider_name)
    return PROVIDER_ENV_PREFIX.get(canonical, canonical.upper())


def get_provider(provider_name: str | None = None, *, requests_per_minute: int | None = None) -> ProviderAdapter:
    canonical = get_default_provider() if provider_name is None else normalize_provider_name(provider_name)
    if canonical == "sportmonks":
        return SportMonksProvider(
            api_key=_required_env("API_KEY_SPORTMONKS"),
            base_url=os.getenv("SPORTMONKS_BASE_URL", "https://api.sportmonks.com/v3/football"),
            requests_per_minute=requests_per_minute,
        )
    if canonical == "api_football":
        return APIFootballProvider(
            api_key=_required_env("APIFOOTBALL_API_KEY"),
            base_url=os.getenv("APIFOOTBALL_BASE_URL", "https://v3.football.api-sports.io"),
            requests_per_minute=requests_per_minute,
        )
    raise RuntimeError(f"Provider sem implementacao: {canonical}")
