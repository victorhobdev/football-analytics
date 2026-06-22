from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.main import app


class AnalyticsRouteContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.src.routers.analytics.db_client.fetch_all")
    def test_overview_returns_data(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = [
            {
                "competition_key": "bra_serie_a",
                "season": 2025,
                "season_label": "2025",
                "total_matches": 380,
                "total_goals": 987,
                "avg_goals_per_match": 2.6,
                "home_wins": 152,
                "away_wins": 114,
                "draws": 114,
                "home_win_rate": 40.0,
                "away_win_rate": 30.0,
                "draw_rate": 30.0,
                "total_teams": 20,
                "total_coaches": 34,
                "total_players": 612,
                "top_scorer_team_id": 123,
                "top_scorer_team_name": "Flamengo",
                "top_scorer_goals": 72,
                "best_defense_team_id": 456,
                "best_defense_team_name": "Palmeiras",
                "best_defense_goals_against": 28,
                "best_ppm_coach_id": "789",
                "best_ppm_coach_name": "Abel Ferreira",
                "best_ppm_coach_points_per_match": 2.18,
                "best_ppm_coach_matches": 38,
            }
        ]

        response = self.client.get("/api/v1/analytics/overview")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["summary"]["totalMatches"], 380)
        self.assertEqual(data["summary"]["totalGoals"], 987)
        self.assertEqual(data["summary"]["avgGoalsPerMatch"], 2.6)
        self.assertEqual(data["summary"]["totalCoaches"], 34)
        self.assertEqual(data["summary"]["totalPlayers"], 612)
        self.assertEqual(data["topScorerTeam"]["teamId"], "123")
        self.assertEqual(data["bestDefenseTeam"]["teamName"], "Palmeiras")
        self.assertEqual(data["bestPpmCoach"]["coachName"], "Abel Ferreira")
        executed_query = fetch_all_mock.call_args.args[0]
        self.assertIn("where 1=1", executed_query)

    @patch("api.src.routers.analytics.db_client.fetch_all")
    def test_overview_empty_returns_not_available(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = []

        response = self.client.get("/api/v1/analytics/overview?competitionId=999")

        self.assertEqual(response.status_code, 200)
        meta = response.json()["meta"]
        self.assertEqual(meta["coverage"]["status"], "not_available")
        self.assertEqual(response.json()["data"]["summary"]["totalMatches"], 0)

    @patch("api.src.routers.analytics.db_client.fetch_all")
    def test_trends_returns_series(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = [
            {"period": "1", "period_label": "Rodada 1", "value": 28, "sample_size": 10},
            {"period": "2", "period_label": "Rodada 2", "value": 25, "sample_size": 10},
            {"period": "3", "period_label": "Rodada 3", "value": 30, "sample_size": 10},
        ]

        response = self.client.get("/api/v1/analytics/trends?metric=goals&periodType=round")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["metric"], "goals")
        self.assertEqual(len(data["series"]), 3)
        self.assertEqual(data["series"][0]["period"], "1")

    @patch("api.src.routers.analytics.db_client.fetch_all")
    def test_trends_invalid_metric_returns_400(self, fetch_all_mock) -> None:
        response = self.client.get("/api/v1/analytics/trends?metric=invalid_metric&periodType=round")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_METRIC")

    @patch("api.src.routers.analytics.db_client.fetch_all")
    def test_olap_invalid_metric_returns_400(self, fetch_all_mock) -> None:
        response = self.client.get(
            "/api/v1/analytics/olap?metric=bad_metric&dimension=team&grain=competition_season_team"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_METRIC")

    @patch("api.src.routers.analytics.db_client.fetch_all")
    def test_olap_incompatible_combination_returns_400(self, fetch_all_mock) -> None:
        response = self.client.get(
            "/api/v1/analytics/olap?metric=matches&dimension=round&grain=competition_season"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INCOMPATIBLE_COMBINATION")

    @patch("api.src.routers.analytics.db_client.fetch_all")
    def test_olap_returns_rows(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = [
            {
                "dimension_key": "1",
                "dimension_label": "Rodada 1",
                "value": 28,
                "sample_size": 10,
            },
            {
                "dimension_key": "2",
                "dimension_label": "Rodada 2",
                "value": 25,
                "sample_size": 10,
            },
        ]

        response = self.client.get(
            "/api/v1/analytics/olap?metric=goals&dimension=round&grain=competition_season_round"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data["rows"]), 2)
        self.assertTrue(data["drillThroughAvailable"])

    @patch("api.src.routers.analytics.db_client.fetch_all")
    def test_comparisons_team_vs_team(self, fetch_all_mock) -> None:
        def side_effect(query, params=None):
            if "team_name from mart.dim_team" in query:
                return [{"team_name": "Flamengo"}] if "123" in str(params) else [{"team_name": "Palmeiras"}]
            return [
                {
                    "entity_id": "123",
                    "entity_label": "Flamengo",
                    "matches": 38,
                    "wins": 24,
                    "draws": 8,
                    "losses": 6,
                    "points": 80,
                    "goals_for": 72,
                    "goals_against": 38,
                    "goal_diff": 34,
                    "avg_goals_per_match": 1.89,
                    "points_per_match": 2.11,
                },
            ]

        fetch_all_mock.side_effect = side_effect

        response = self.client.get("/api/v1/analytics/comparisons?type=team_vs_team&entityA=123&entityB=456")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["type"], "team_vs_team")
        self.assertIn("entityA", data)
        self.assertIn("entityB", data)
        first_query = fetch_all_mock.call_args_list[0].args[0]
        self.assertIn("tr.team_id::text as entity_id", first_query)
        self.assertIn("coalesce(dt.team_name, 'Time indisponivel') as entity_label", first_query)

    @patch("api.src.routers.analytics.db_client.fetch_all")
    def test_superlatives_returns_records(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = [
            {
                "entity_id": "match_1",
                "entity_label": "Match 1",
                "value": 7,
                "scope": "bra_serie_a/2025",
                "sample_size": 380,
            },
        ]

        response = self.client.get("/api/v1/analytics/superlatives?category=most_goals_match&limit=5")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["category"], "most_goals_match")
        self.assertEqual(len(data["records"]), 1)
        self.assertEqual(data["records"][0]["value"], 7)

    @patch("api.src.routers.analytics.db_client.fetch_all")
    def test_superlatives_invalid_category_returns_400(self, fetch_all_mock) -> None:
        response = self.client.get("/api/v1/analytics/superlatives?category=bad_category")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_SUPERLATIVE_CATEGORY")

    @patch("api.src.routers.analytics.db_client.fetch_all")
    def test_coverage_returns_metrics(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = [
            {
                "total_matches": 380,
                "matches_with_events": 320,
                "matches_with_lineups": 280,
                "matches_with_player_stats": 200,
                "matches_with_team_stats": 380,
                "matches_with_coach_assignment": 250,
            }
        ]

        response = self.client.get("/api/v1/analytics/coverage")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["totalMatches"], 380)
        self.assertIn("scores", data["metrics"])
        self.assertIn("events", data["metrics"])
        self.assertEqual(data["metrics"]["teamStats"]["count"], 380)
        self.assertEqual(data["metrics"]["coachAssignment"]["count"], 250)
        self.assertIn("points", data["enabledMetrics"])
        self.assertIn("coach_best_ppm", data["enabledMetrics"])
        self.assertIn("enabledMetrics", data)
        executed_query = fetch_all_mock.call_args.args[0]
        self.assertIn("with match_scope as", executed_query)
        self.assertEqual(fetch_all_mock.call_args.args[1], [])

    @patch("api.src.routers.analytics.db_client.fetch_all")
    def test_coverage_empty_returns_not_available(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = []

        response = self.client.get("/api/v1/analytics/coverage?competitionId=999")

        self.assertEqual(response.status_code, 200)
        meta = response.json()["meta"]
        self.assertEqual(meta["coverage"]["status"], "not_available")
        self.assertEqual(response.json()["data"]["totalMatches"], 0)


if __name__ == "__main__":
    unittest.main()
