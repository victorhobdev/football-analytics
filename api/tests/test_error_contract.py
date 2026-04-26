from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api.src.main import app


class ErrorContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_app_error_payload_keeps_legacy_fields_and_adds_meta(self) -> None:
        response = self.client.get("/api/v1/standings")

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        request_id = response.headers["X-Request-Id"]
        self.assertEqual(payload["message"], "Canonical standings require 'competitionId' and 'seasonId'.")
        self.assertEqual(payload["code"], "INVALID_QUERY_PARAM")
        self.assertEqual(payload["status"], 400)
        self.assertIsNone(payload["data"])
        self.assertEqual(payload["error"]["code"], "INVALID_QUERY_PARAM")
        self.assertEqual(payload["error"]["details"], payload["details"])
        self.assertEqual(payload["meta"]["requestId"], request_id)
        self.assertIn("generatedAt", payload["meta"])

    def test_validation_error_payload_includes_request_id(self) -> None:
        response = self.client.get("/api/v1/players?page=0")

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], "INVALID_QUERY_PARAM")
        self.assertEqual(payload["error"]["code"], "INVALID_QUERY_PARAM")
        self.assertEqual(payload["meta"]["requestId"], response.headers["X-Request-Id"])
        self.assertIn("errors", payload["details"])
        self.assertEqual(payload["details"]["errors"][0]["field"], "page")
        self.assertEqual(payload["details"]["errors"][0]["location"], ["query", "page"])
        self.assertNotIn("input", payload["details"]["errors"][0])
        self.assertNotIn("ctx", payload["details"]["errors"][0])


if __name__ == "__main__":
    unittest.main()
