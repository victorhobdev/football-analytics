from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.main import app


class TeamsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.src.routers.teams.db_client.fetch_all")
    def test_team_search_filters_both_match_branches_before_aggregation(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = []

        response = self.client.get("/api/v1/teams?search=Flamengo")

        self.assertEqual(response.status_code, 200)
        query = fetch_all_mock.call_args.args[0]
        self.assertIn("home_team.team_name ilike", query)
        self.assertIn("away_team.team_name ilike", query)
        self.assertNotIn("a.team_name ilike", query)


if __name__ == "__main__":
    unittest.main()
