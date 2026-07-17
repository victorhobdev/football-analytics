from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.main import app


class SearchApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.src.routers.search.db_client.fetch_all")
    def test_match_search_uses_indexable_candidates(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = []

        response = self.client.get("/api/v1/search?q=flamengo&types=match")

        self.assertEqual(response.status_code, 200)
        query = fetch_all_mock.call_args.args[0]
        self.assertIn("candidate_matches as", query)
        self.assertIn("fm.home_team_id = mt.team_id", query)
        self.assertIn("fm.away_team_id = mt.team_id", query)
        self.assertIn("cross join lateral", query)
        self.assertNotIn("fm.match_id::text", query)


if __name__ == "__main__":
    unittest.main()
