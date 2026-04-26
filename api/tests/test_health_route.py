from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.main import app


class HealthRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.src.routers.health.db_client.fetch_val")
    def test_health_returns_ok_when_database_ping_succeeds(self, fetch_val_mock) -> None:
        fetch_val_mock.return_value = 1

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["checks"]["database"]["status"], "ok")
        fetch_val_mock.assert_called_once_with("select 1;")

    @patch("api.src.routers.health.db_client.fetch_val")
    def test_health_returns_degraded_when_database_ping_fails(self, fetch_val_mock) -> None:
        fetch_val_mock.side_effect = RuntimeError("database down")

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["checks"]["database"]["status"], "error")
        self.assertEqual(payload["checks"]["database"]["error"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
