from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.main import app
from api.src.routers.rankings import RankingContextScope


class PlayerServingRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.src.routers.players.db_client.fetch_one")
    @patch("api.src.routers.players.db_client.fetch_all")
    def test_players_default_uses_serving_summary(self, fetch_all_mock, fetch_one_mock) -> None:
        fetch_all_mock.return_value = [
            {
                "player_id": 10,
                "player_name": "Jogador A",
                "team_id": 100,
                "team_name": "Clube A",
                "position_name": "Forward",
                "nationality": "BR",
                "team_count": 1,
                "recent_teams": [{"teamId": "100", "teamName": "Clube A"}],
                "matches_played": 12,
                "minutes_played": 900,
                "goals": 8,
                "assists": 3,
                "shots_total": 24,
                "yellow_cards": 1,
                "red_cards": 0,
                "rating": 7.5,
                "_total_count": 1,
            }
        ]
        fetch_one_mock.return_value = {"available_count": 12, "total_count": 12}

        response = self.client.get("/api/v1/players?pageSize=20")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        item = payload["data"]["items"][0]
        self.assertEqual(item["playerId"], "10")
        self.assertIsInstance(item["minutesPlayed"], int)
        self.assertIsInstance(item["goals"], int)
        self.assertIsInstance(item["assists"], int)
        self.assertIsInstance(item["yellowCards"], int)
        self.assertIsInstance(item["redCards"], int)
        query, _params = fetch_all_mock.call_args.args
        self.assertIn("mart.player_serving_summary", query)
        self.assertNotIn("mart.player_match_summary pms", query)

    @patch("api.src.routers.players.db_client.fetch_one")
    @patch("api.src.routers.players.db_client.fetch_all")
    def test_players_scoped_filters_keep_match_summary_query(self, fetch_all_mock, fetch_one_mock) -> None:
        fetch_all_mock.return_value = []
        fetch_one_mock.return_value = {"available_count": 0, "total_count": 0}

        response = self.client.get("/api/v1/players?competitionId=71&pageSize=20")

        self.assertEqual(response.status_code, 200)
        query, _params = fetch_all_mock.call_args.args
        self.assertIn("mart.player_match_summary pms", query)
        self.assertNotIn("mart.player_serving_summary", query)

    @patch("api.src.routers.rankings._player_ranking_coverage")
    @patch("api.src.routers.rankings._resolve_ranking_context_scope")
    @patch("api.src.routers.rankings.db_client.fetch_all")
    def test_player_ranking_default_uses_serving_summary(
        self,
        fetch_all_mock,
        resolve_scope_mock,
        ranking_coverage_mock,
    ) -> None:
        resolve_scope_mock.return_value = RankingContextScope(
            competition_id=None,
            competition_name=None,
            season_id=None,
            season_label=None,
        )
        ranking_coverage_mock.return_value = {"status": "complete", "label": "Player ranking coverage"}
        fetch_all_mock.return_value = [
            {
                "player_id": 10,
                "player_name": "Jogador A",
                "team_id": 100,
                "team_name": "Clube A",
                "team_count": 1,
                "recent_teams": [{"teamId": "100", "teamName": "Clube A"}],
                "matches_played": 12,
                "minutes_played": 900,
                "metric_value": 8,
                "metric_per90": 0.8,
                "rank": 1,
                "_total_count": 1,
                "_max_updated_at": None,
            }
        ]

        response = self.client.get("/api/v1/rankings/player-goals?pageSize=20")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["rows"][0]["entityId"], "10")
        query, _params = fetch_all_mock.call_args.args
        self.assertIn("mart.player_serving_summary", query)
        self.assertNotIn("mart.player_match_summary pms", query)

    @patch("api.src.routers.rankings._player_ranking_coverage")
    @patch("api.src.routers.rankings._resolve_ranking_context_scope")
    @patch("api.src.routers.rankings.db_client.fetch_all")
    def test_player_ranking_default_falls_back_to_match_summary_when_serving_is_empty(
        self,
        fetch_all_mock,
        resolve_scope_mock,
        ranking_coverage_mock,
    ) -> None:
        resolve_scope_mock.return_value = RankingContextScope(
            competition_id=None,
            competition_name=None,
            season_id=None,
            season_label=None,
        )
        ranking_coverage_mock.return_value = {"status": "complete", "label": "Player ranking coverage"}
        fetch_all_mock.side_effect = [
            [],
            [
                {
                    "player_id": 10,
                    "player_name": "Jogador A",
                    "team_id": 100,
                    "team_name": "Clube A",
                    "team_count": 1,
                    "recent_teams": [{"teamId": "100", "teamName": "Clube A"}],
                    "matches_played": 12,
                    "minutes_played": 900,
                    "metric_value": 8,
                    "metric_per90": 0.8,
                    "rank": 1,
                    "_total_count": 1,
                    "_max_updated_at": None,
                }
            ],
        ]

        response = self.client.get("/api/v1/rankings/player-goals?pageSize=20")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["rows"][0]["entityId"], "10")
        first_query, _first_params = fetch_all_mock.call_args_list[0].args
        second_query, _second_params = fetch_all_mock.call_args_list[1].args
        self.assertIn("mart.player_serving_summary", first_query)
        self.assertIn("mart.player_match_summary pms", second_query)

    @patch("api.src.routers.rankings._player_ranking_coverage")
    @patch("api.src.routers.rankings._resolve_ranking_context_scope")
    @patch("api.src.routers.rankings.db_client.fetch_all")
    def test_player_ranking_accepts_all_sentinel_values(
        self,
        fetch_all_mock,
        resolve_scope_mock,
        ranking_coverage_mock,
    ) -> None:
        resolve_scope_mock.return_value = RankingContextScope(
            competition_id=None,
            competition_name=None,
            season_id=None,
            season_label=None,
        )
        ranking_coverage_mock.return_value = {"status": "complete", "label": "Player ranking coverage"}
        fetch_all_mock.return_value = [
            {
                "player_id": 10,
                "player_name": "Jogador A",
                "team_id": 100,
                "team_name": "Clube A",
                "team_count": 1,
                "recent_teams": [{"teamId": "100", "teamName": "Clube A"}],
                "matches_played": 12,
                "minutes_played": 900,
                "metric_value": 8,
                "metric_per90": 0.8,
                "rank": 1,
                "_total_count": 1,
                "_max_updated_at": None,
            }
        ]

        response = self.client.get("/api/v1/rankings/player-goals?competitionId=all&seasonId=ALL&pageSize=20")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["rows"][0]["entityId"], "10")

    @patch("api.src.routers.players.db_client.fetch_one")
    @patch("api.src.routers.players.db_client.fetch_all")
    def test_players_default_falls_back_to_match_summary_when_serving_is_empty(
        self,
        fetch_all_mock,
        fetch_one_mock,
    ) -> None:
        fetch_all_mock.side_effect = [
            [],
            [
                {
                    "player_id": 10,
                    "player_name": "Jogador A",
                    "team_id": 100,
                    "team_name": "Clube A",
                    "position_name": "Forward",
                    "nationality": "BR",
                    "team_count": 1,
                    "recent_teams": [{"teamId": "100", "teamName": "Clube A"}],
                    "matches_played": 12,
                    "minutes_played": 900,
                    "goals": 8,
                    "assists": 3,
                    "shots_total": 24,
                    "yellow_cards": 1,
                    "red_cards": 0,
                    "rating": 7.5,
                    "_total_count": 1,
                }
            ],
        ]
        fetch_one_mock.return_value = {"available_count": 12, "total_count": 12}

        response = self.client.get("/api/v1/players?pageSize=20")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["items"][0]["playerId"], "10")
        first_query, _first_params = fetch_all_mock.call_args_list[0].args
        second_query, _second_params = fetch_all_mock.call_args_list[1].args
        self.assertIn("mart.player_serving_summary", first_query)
        self.assertIn("mart.player_match_summary pms", second_query)

    @patch("api.src.routers.players._profile_coverage")
    @patch("api.src.routers.players._fetch_player_profile_meta")
    @patch("api.src.routers.players.db_client.fetch_one")
    def test_player_profile_serializes_count_fields_as_int(
        self,
        fetch_one_mock,
        fetch_profile_meta_mock,
        profile_coverage_mock,
    ) -> None:
        fetch_profile_meta_mock.return_value = {"hasHistoricalStats": True}
        profile_coverage_mock.return_value = {"status": "complete", "label": "Player profile coverage"}
        fetch_one_mock.side_effect = [
            {"player_id": 10, "player_name": "Jogador A", "nationality": "BR"},
            {
                "team_id": 100,
                "team_name": "Clube A",
                "position_name": "Forward",
                "matches_played": 12,
                "last_match_date": None,
                "minutes_played": 900.0,
                "goals": 8.0,
                "assists": 3.0,
                "shots_total": 24.0,
                "shots_on_target": 12.0,
                "passes_attempted": 300.0,
                "yellow_cards": 1.0,
                "red_cards": 0.0,
                "rating": 7.5,
            },
        ]

        response = self.client.get(
            "/api/v1/players/10?includeRecentMatches=false&includeHistory=false&includeStats=false"
        )

        self.assertEqual(response.status_code, 200)
        summary = response.json()["data"]["summary"]
        for field in [
            "minutesPlayed",
            "goals",
            "assists",
            "shotsTotal",
            "shotsOnTarget",
            "passesAttempted",
            "yellowCards",
            "redCards",
        ]:
            self.assertIsInstance(summary[field], int)


if __name__ == "__main__":
    unittest.main()
