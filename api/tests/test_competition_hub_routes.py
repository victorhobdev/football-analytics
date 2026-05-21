from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.main import app
from api.src.routers.competition_hub import CompetitionSeasonScope


class CompetitionHubAnalyticsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.src.routers.competition_hub._fetch_competition_season_average_goals")
    @patch("api.src.routers.competition_hub._fetch_competition_season_comparisons")
    @patch("api.src.routers.competition_hub._fetch_competition_stage_analytics")
    @patch("api.src.routers.competition_hub._resolve_competition_scope")
    def test_competition_analytics_normalizes_serie_a_italy_alias(
        self,
        resolve_scope_mock,
        fetch_stage_analytics_mock,
        fetch_season_comparisons_mock,
        fetch_season_average_goals_mock,
    ) -> None:
        resolve_scope_mock.return_value = CompetitionSeasonScope(
            competition_key="serie_a_it",
            competition_name="Serie A",
            competition_id=384,
            season_label="2024_25",
            season_id=23746,
            provider_season_id=23746,
            format_family="unknown",
            season_format_code="unconfigured",
            participant_scope="unknown",
            group_ranking_rule_code=None,
            tie_rule_code=None,
        )
        fetch_stage_analytics_mock.return_value = [
            {
                "stage_id": "77471748",
                "stage_name": "Regular Season",
                "stage_code": "regular_season",
                "stage_format": None,
                "sort_order": 1,
                "is_current": False,
                "match_count": 380,
                "team_count": 20,
                "group_count": 0,
                "average_goals": 2.56,
                "home_wins": 151,
                "draws": 108,
                "away_wins": 121,
                "tie_count": 0,
                "resolved_ties": 0,
                "inferred_ties": 0,
            }
        ]
        fetch_season_comparisons_mock.return_value = []
        fetch_season_average_goals_mock.return_value = 2.56

        response = self.client.get(
            "/api/v1/competition-analytics?competitionKey=serie_a_italy&seasonLabel=2024/2025"
        )

        self.assertEqual(response.status_code, 200)
        resolve_scope_mock.assert_called_once_with("serie_a_it", "2024_25")
        payload = response.json()
        self.assertEqual(payload["data"]["competition"]["competitionKey"], "serie_a_italy")
        self.assertEqual(payload["data"]["seasonSummary"]["averageGoals"], 2.56)

    @patch("api.src.routers.competition_hub._fetch_stage_scope_row")
    @patch("api.src.routers.competition_hub.db_client.fetch_one")
    @patch("api.src.routers.competition_hub._fetch_competition_season_average_goals")
    @patch("api.src.routers.competition_hub._fetch_competition_season_comparisons")
    @patch("api.src.routers.competition_hub._fetch_competition_stage_analytics")
    def test_competition_analytics_returns_season_average_goals_without_season_config(
        self,
        fetch_stage_analytics_mock,
        fetch_season_comparisons_mock,
        fetch_season_average_goals_mock,
        fetch_one_mock,
        fetch_stage_scope_row_mock,
    ) -> None:
        fetch_one_mock.return_value = None
        fetch_stage_analytics_mock.return_value = [
            {
                "stage_id": "77475702",
                "stage_name": "Temporada regular",
                "stage_code": "regular_season",
                "stage_format": "league_table",
                "sort_order": 1,
                "is_current": False,
                "match_count": 380,
                "team_count": 20,
                "group_count": 0,
                "average_goals": 2.52,
                "home_wins": 0,
                "draws": 0,
                "away_wins": 0,
                "tie_count": 0,
                "resolved_ties": 0,
                "inferred_ties": 0,
            }
        ]
        fetch_season_comparisons_mock.return_value = []
        fetch_season_average_goals_mock.return_value = 2.52
        fetch_stage_scope_row_mock.return_value = {
            "competition_key": "brasileirao_a",
            "competition_name": "Campeonato Brasileiro Série A",
            "competition_id": 71,
            "season_label": "2025",
            "season_id": 2025,
            "provider_season_id": 23628,
        }

        response = self.client.get(
            "/api/v1/competition-analytics?competitionKey=brasileirao_a&seasonLabel=2025"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["seasonSummary"]["averageGoals"], 2.52)
        self.assertEqual(payload["data"]["seasonComparisons"], [])
        self.assertEqual(payload["data"]["competition"]["competitionKey"], "brasileirao_a")


if __name__ == "__main__":
    unittest.main()
