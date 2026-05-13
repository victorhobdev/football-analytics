from __future__ import annotations

from typing import Any
import os

from common.providers import get_default_provider, normalize_provider_name, provider_env_prefix


DEFAULT_LEAGUE_ID = 71
DEFAULT_SEASON = 2024
DEFAULT_PROVIDER = get_default_provider()

DEFAULT_FIXTURE_WINDOWS_BY_SEASON: dict[int, list[tuple[str, str]]] = {
    2024: [
        ("2024-04-13", "2024-06-30"),
        ("2024-07-01", "2024-09-30"),
        ("2024-10-01", "2024-12-08"),
    ]
}


def _safe_int(value: Any, default_value: int, field_name: str) -> int:
    if value is None:
        return default_value
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Parametro invalido para {field_name}: {value}") from exc


def _raw_runtime_inputs(context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    params = context.get("params") or {}
    dag_run = context.get("dag_run")
    conf = dag_run.conf if dag_run and dag_run.conf else {}
    return params, conf


def resolve_runtime_params(context: dict[str, Any]) -> dict[str, Any]:
    params, conf = _raw_runtime_inputs(context)
    raw_provider = conf.get("provider", params.get("provider", DEFAULT_PROVIDER))
    provider_value = str(raw_provider or "").strip()
    provider = normalize_provider_name(provider_value) if provider_value else DEFAULT_PROVIDER
    env_prefix = provider_env_prefix(provider)
    default_league = _safe_int(
        os.getenv(f"{env_prefix}_DEFAULT_LEAGUE_ID", str(DEFAULT_LEAGUE_ID)),
        DEFAULT_LEAGUE_ID,
        "default_league_id",
    )
    default_season = _safe_int(
        os.getenv(f"{env_prefix}_DEFAULT_SEASON", str(DEFAULT_SEASON)),
        DEFAULT_SEASON,
        "default_season",
    )
    league_id = _safe_int(
        conf.get("league_id", params.get("league_id", default_league)),
        default_league,
        "league_id",
    )
    season = _safe_int(
        conf.get("season", params.get("season", default_season)),
        default_season,
        "season",
    )
    return {
        "league_id": league_id,
        "season": season,
        "provider": provider,
    }


def resolve_fixture_windows(context: dict[str, Any], season: int) -> list[tuple[str, str]]:
    params, conf = _raw_runtime_inputs(context)
    if season < 1900 or season > 2100:
        raise ValueError(
            f"Parametro season invalido para janelas de fixtures: {season}. "
            "Use o ano da temporada (ex.: 2024), nao o season_id numerico do provider."
        )
    configured = conf.get("fixture_windows", params.get("fixture_windows"))
    if configured:
        windows: list[tuple[str, str]] = []
        for item in configured:
            if isinstance(item, dict):
                date_from = str(item.get("from", "")).strip()
                date_to = str(item.get("to", "")).strip()
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                date_from = str(item[0]).strip()
                date_to = str(item[1]).strip()
            else:
                raise ValueError(f"Formato invalido em fixture_windows: {item}")
            if not date_from or not date_to:
                raise ValueError(f"Janela invalida em fixture_windows: {item}")
            windows.append((date_from, date_to))
        if windows:
            return windows

    if season in DEFAULT_FIXTURE_WINDOWS_BY_SEASON:
        return DEFAULT_FIXTURE_WINDOWS_BY_SEASON[season]
    return [(f"{season}-01-01", f"{season}-12-31")]
