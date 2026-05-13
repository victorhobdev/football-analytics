from __future__ import annotations

from typing import Any

from common.http_client import ProviderHttpClient

from .base import ProviderAdapter
from .envelope import build_envelope


class APIFootballProvider(ProviderAdapter):
    name = "api_football"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        requests_per_minute: int | None = None,
    ):
        self._client = ProviderHttpClient.from_env(
            provider=self.name,
            base_url=base_url,
            default_headers={"x-apisports-key": api_key},
            requests_per_minute=requests_per_minute,
        )

    def _request(
        self,
        *,
        endpoint: str,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str]]:
        payload, headers = self._client.request_json(endpoint=endpoint, params=params)
        errors = payload.get("errors")
        if errors:
            raise RuntimeError(f"provider={self.name} endpoint={endpoint} errors={errors}")
        return payload, headers

    def get_fixtures(
        self,
        *,
        league_id: int,
        season: int,
        date_from: str,
        date_to: str,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        endpoint = "/fixtures"
        params = {
            "league": league_id,
            "season": season,
            "from": date_from,
            "to": date_to,
        }
        payload, headers = self._request(endpoint=endpoint, params=params)
        response_rows = payload.get("response", []) or []
        canonical = build_envelope(
            provider=self.name,
            entity_type="fixtures",
            response=response_rows,
            errors=payload.get("errors"),
            source_params=params,
            provider_meta={
                "endpoint": endpoint,
                "paging": payload.get("paging", {}),
                "rate_limit_headers": {
                    k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()
                },
            },
        )
        canonical["results"] = int(payload.get("results", len(response_rows)) or 0)
        return canonical, headers

    def get_fixture_statistics(
        self,
        *,
        fixture_id: int,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        endpoint = "/fixtures/statistics"
        params = {"fixture": fixture_id}
        payload, headers = self._request(endpoint=endpoint, params=params)
        response_rows = payload.get("response", []) or []
        canonical = build_envelope(
            provider=self.name,
            entity_type="statistics",
            response=response_rows,
            errors=payload.get("errors"),
            source_params=params,
            provider_meta={
                "endpoint": endpoint,
                "rate_limit_headers": {
                    k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()
                },
            },
        )
        canonical["results"] = int(payload.get("results", len(response_rows)) or 0)
        return canonical, headers

    def get_fixture_events(
        self,
        *,
        fixture_id: int,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        endpoint = "/fixtures/events"
        params = {"fixture": fixture_id}
        payload, headers = self._request(endpoint=endpoint, params=params)
        response_rows = payload.get("response", []) or []
        canonical = build_envelope(
            provider=self.name,
            entity_type="match_events",
            response=response_rows,
            errors=payload.get("errors"),
            source_params=params,
            provider_meta={
                "endpoint": endpoint,
                "rate_limit_headers": {
                    k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()
                },
            },
        )
        canonical["results"] = int(payload.get("results", len(response_rows)) or 0)
        return canonical, headers

    def get_standings(
        self,
        *,
        league_id: int,
        season: int,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        endpoint = "/standings"
        params = {"league": league_id, "season": season}
        payload, headers = self._request(endpoint=endpoint, params=params)
        response_rows = payload.get("response", []) or []
        canonical = build_envelope(
            provider=self.name,
            entity_type="standings",
            response=response_rows,
            errors=payload.get("errors"),
            source_params=params,
            provider_meta={
                "endpoint": endpoint,
                "paging": payload.get("paging", {}),
                "rate_limit_headers": {
                    k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()
                },
            },
        )
        canonical["results"] = int(payload.get("results", len(response_rows)) or 0)
        return canonical, headers
