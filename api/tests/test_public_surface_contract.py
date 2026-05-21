from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.core.config import get_settings
from api.src.main import app, create_app


class PublicSurfaceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_insights_placeholder_returns_explicit_not_implemented(self) -> None:
        response = self.client.get("/api/v1/insights?entityType=global")

        self.assertEqual(response.status_code, 501)
        payload = response.json()
        self.assertEqual(payload["code"], "FEATURE_NOT_IMPLEMENTED")
        self.assertEqual(payload["details"]["entityType"], "global")

    @patch("api.src.routers.rankings.db_client.fetch_one")
    @patch("api.src.routers.rankings.db_client.fetch_all")
    def test_unsupported_ranking_returns_explicit_not_implemented(
        self,
        fetch_all_mock,
        fetch_one_mock,
    ) -> None:
        response = self.client.get("/api/v1/rankings/player-pass-accuracy")

        self.assertEqual(response.status_code, 501)
        payload = response.json()
        self.assertEqual(payload["code"], "RANKING_NOT_IMPLEMENTED")
        self.assertEqual(payload["details"]["rankingType"], "player-pass-accuracy")
        fetch_all_mock.assert_not_called()
        fetch_one_mock.assert_not_called()

    def test_compatibility_routes_are_marked_deprecated_in_openapi(self) -> None:
        response = self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        self.assertTrue(paths["/api/v1/group-standings"]["get"]["deprecated"])
        self.assertTrue(paths["/api/v1/team-progression"]["get"]["deprecated"])
        self.assertTrue(paths["/api/v1/insights"]["get"]["deprecated"])

    def test_api_docs_can_be_disabled_for_non_local_runtime(self) -> None:
        settings = replace(get_settings(), environment="production", expose_api_docs=False)
        client = TestClient(create_app(settings))

        self.assertEqual(client.get("/docs").status_code, 404)
        self.assertEqual(client.get("/redoc").status_code, 404)
        self.assertEqual(client.get("/openapi.json").status_code, 404)


if __name__ == "__main__":
    unittest.main()
