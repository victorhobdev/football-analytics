from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.main import app


class MatchCenterApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.src.routers.matches.db_client.fetch_all")
    @patch("api.src.routers.matches.db_client.fetch_one")
    def test_match_center_falls_back_to_external_depth_facts(self, fetch_one_mock, fetch_all_mock) -> None:
        fetch_one_mock.return_value = {
            "match_id": "930002718867",
            "fixture_id": "930002718867",
            "competition_id": "999",
            "competition_key": "la_liga",
            "competition_name": "La Liga",
            "competition_type": "domestic",
            "season_id": "2017",
            "season_label": "2017/18",
            "round_id": "1",
            "round_name": "Round 1",
            "stage_id": None,
            "stage_name": None,
            "stage_format": None,
            "group_id": None,
            "group_name": None,
            "tie_id": None,
            "tie_order": None,
            "tie_match_count": None,
            "leg_number": None,
            "is_knockout": False,
            "kickoff_at": "2018-02-01T00:00:00Z",
            "status": "FT",
            "venue_name": "Camp Nou",
            "home_team_id": "10",
            "home_team_name": "Home Club",
            "away_team_id": "20",
            "away_team_name": "Away Club",
            "home_score": 1,
            "away_score": 0,
        }
        fetch_all_mock.side_effect = [
            [],
            [
                {
                    "player_id": "186815",
                    "player_name": "Pablo Fornals",
                    "team_id": None,
                    "team_name": None,
                    "position": "Central Midfield",
                    "formation_field": None,
                    "formation_position": None,
                    "shirt_number": 8,
                    "is_starter": True,
                    "minutes_played": None,
                }
            ],
            [],
            [
                {
                    "team_id": "10",
                    "team_name": "Home Club",
                    "total_shots": 12,
                    "shots_on_goal": 5,
                    "ball_possession": None,
                    "total_passes": None,
                    "passes_accurate": None,
                    "passes_pct": None,
                    "corner_kicks": 4,
                    "fouls": 11,
                    "yellow_cards": 2,
                    "red_cards": 0,
                    "goalkeeper_saves": None,
                },
                {
                    "team_id": "20",
                    "team_name": "Away Club",
                    "total_shots": 9,
                    "shots_on_goal": 3,
                    "ball_possession": None,
                    "total_passes": None,
                    "passes_accurate": None,
                    "passes_pct": None,
                    "corner_kicks": 2,
                    "fouls": 13,
                    "yellow_cards": 1,
                    "red_cards": 0,
                    "goalkeeper_saves": None,
                },
            ],
            [],
            [
                {
                    "player_id": "186815",
                    "player_name": "Pablo Fornals",
                    "team_id": None,
                    "team_name": "Málaga CF",
                    "position_name": "Central Midfield",
                    "is_starter": True,
                    "minutes_played": 90,
                    "goals": 0,
                    "assists": 0,
                    "shots_total": None,
                    "shots_on_goal": None,
                    "passes_total": None,
                    "key_passes": None,
                    "tackles": None,
                    "interceptions": None,
                    "duels": None,
                    "fouls_committed": None,
                    "yellow_cards": 0,
                    "red_cards": 0,
                    "goalkeeper_saves": None,
                    "clean_sheets": None,
                    "xg": None,
                    "rating": None,
                }
            ],
        ]

        response = self.client.get(
            "/api/v1/matches/930002718867?includeTimeline=false&includeLineups=true&includeTeamStats=true&includePlayerStats=true"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(len(payload["lineups"]), 1)
        self.assertEqual(len(payload["teamStats"]), 2)
        self.assertEqual(len(payload["playerStats"]), 1)
        self.assertEqual(payload["playerStats"][0]["teamName"], "Málaga CF")
        self.assertEqual(payload["teamStats"][0]["teamId"], "10")
        self.assertEqual(payload["sectionCoverage"]["teamStats"]["status"], "partial")
        self.assertEqual(payload["sectionCoverage"]["playerStats"]["status"], "partial")


if __name__ == "__main__":
    unittest.main()
