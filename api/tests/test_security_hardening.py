from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.core.config import get_settings
from api.src.main import create_app


class SecurityHardeningTests(unittest.TestCase):
    def test_default_cors_settings_are_explicit_and_do_not_allow_credentials(self) -> None:
        settings = get_settings()

        self.assertNotIn("*", settings.cors_allow_origins)
        self.assertEqual(settings.cors_allow_methods, ("GET", "HEAD", "OPTIONS"))
        self.assertFalse(settings.cors_allow_credentials)

    def test_cors_allows_known_local_origins_only(self) -> None:
        client = TestClient(create_app(replace(get_settings(), rate_limit_enabled=False)))

        allowed = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        blocked = client.options(
            "/health",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(allowed.headers["access-control-allow-origin"], "http://localhost:3000")
        self.assertNotIn("access-control-allow-credentials", allowed.headers)
        self.assertNotIn("access-control-allow-origin", blocked.headers)

    @patch("api.src.routers.health.db_client.fetch_val")
    def test_rate_limit_returns_429_with_retry_after(self, fetch_val_mock) -> None:
        fetch_val_mock.return_value = 1
        settings = replace(
            get_settings(),
            rate_limit_enabled=True,
            rate_limit_health_per_minute=2,
            rate_limit_window_seconds=60,
        )
        client = TestClient(create_app(settings))

        self.assertEqual(client.get("/health").status_code, 200)
        self.assertEqual(client.get("/health").status_code, 200)
        limited = client.get("/health")

        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["code"], "RATE_LIMITED")
        self.assertIn("Retry-After", limited.headers)


if __name__ == "__main__":
    unittest.main()
