from __future__ import annotations

import os


_PROVIDER_ALIASES = {
    "apifootball": "apifootball",
    "api_football": "apifootball",
    "api-football": "apifootball",
    "sportmonks": "sportmonks",
}


def _optional_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None:
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def normalize_provider_name(provider: str) -> str:
    normalized = provider.strip().lower()
    canonical = _PROVIDER_ALIASES.get(normalized)
    if canonical is None:
        supported = ", ".join(sorted(_PROVIDER_ALIASES.keys()))
        raise ValueError(f"Unsupported ACTIVE_PROVIDER='{provider}'. Supported values: {supported}")
    return canonical


class Settings:
    @property
    def ACTIVE_PROVIDER(self) -> str:
        return (os.getenv("ACTIVE_PROVIDER") or "apifootball").strip().lower()

    @property
    def API_FOOTBALL_KEY(self) -> str | None:
        return _optional_env("API_FOOTBALL_KEY", "APIFOOTBALL_API_KEY")

    @property
    def SPORTMONKS_KEY(self) -> str | None:
        return _optional_env("SPORTMONKS_KEY", "API_KEY_SPORTMONKS")

    @property
    def HTTP_TIMEOUT_SECONDS(self) -> float:
        return _float_env("HTTP_TIMEOUT_SECONDS", 30.0)

    @property
    def HTTP_MAX_RETRIES(self) -> int:
        return _int_env("HTTP_MAX_RETRIES", 3)

    @property
    def HTTP_BACKOFF_FACTOR(self) -> float:
        return _float_env("HTTP_BACKOFF_FACTOR", 1.0)

    def active_provider(self) -> str:
        return normalize_provider_name(self.ACTIVE_PROVIDER)

    def validate_active_provider(self) -> str:
        provider = self.active_provider()
        if provider == "apifootball" and not self.API_FOOTBALL_KEY:
            raise RuntimeError(
                "ACTIVE_PROVIDER=apifootball requires API_FOOTBALL_KEY (or APIFOOTBALL_API_KEY)."
            )
        return provider


settings = Settings()
