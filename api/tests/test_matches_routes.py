from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.main import app


class MatchCenterApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def _match_row(self) -> dict[str, object]:
        return {
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

    def _depth_profile_row(self, **overrides: object) -> dict[str, object]:
        row: dict[str, object] = {
            "has_match_context": True,
            "has_score": True,
            "has_odds": False,
            "has_team_stats": False,
            "has_events": False,
            "has_lineups": False,
            "has_player_stats": False,
            "has_player_layer": False,
            "has_minimum_rich_depth": False,
            "valid_event_rows": 0,
            "valid_lineup_rows": 0,
            "valid_player_stat_rows": 0,
            "valid_team_stat_rows": 0,
            "valid_1x2_rows": 0,
            "safe_sections": ["score"],
            "depth_score": 1,
            "refreshed_at": None,
        }
        row.update(overrides)
        return row

    @patch("api.src.routers.matches.db_client.fetch_all")
    @patch("api.src.routers.matches.db_client.fetch_one")
    def test_match_center_falls_back_to_external_depth_facts(self, fetch_one_mock, fetch_all_mock) -> None:
        fetch_one_mock.side_effect = [
            self._match_row(),
            self._depth_profile_row(
                has_lineups=True,
                has_team_stats=True,
                has_player_stats=True,
                has_player_layer=True,
                valid_lineup_rows=1,
                valid_team_stat_rows=2,
                valid_player_stat_rows=1,
                safe_sections=["score", "lineups", "team_stats", "player_stats"],
                depth_score=4,
            ),
        ]
        fetch_all_mock.side_effect = [
            [],
            [
                {
                    "player_id": "186815",
                    "player_name": "Pablo Fornals",
                    "team_id": "1084",
                    "team_name": "Málaga CF",
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
        self.assertEqual(payload["lineups"][0]["teamId"], "1084")
        self.assertEqual(payload["lineups"][0]["teamName"], "Málaga CF")
        self.assertEqual(payload["playerStats"][0]["teamName"], "Málaga CF")
        self.assertEqual(payload["teamStats"][0]["teamId"], "10")
        self.assertTrue(payload["depthProfile"]["hasLineups"])
        self.assertTrue(payload["depthProfile"]["hasPlayerStats"])
        self.assertEqual(payload["depthProfile"]["counts"]["validPlayerStatRows"], 1)
        lineups_fallback_query = fetch_all_mock.call_args_list[1].args[0]
        self.assertIn("tml.tm_club_id::text as team_id", lineups_fallback_query)
        self.assertIn("left join raw.tm_clubs club", lineups_fallback_query)
        self.assertEqual(payload["sectionCoverage"]["teamStats"]["status"], "partial")
        self.assertEqual(payload["sectionCoverage"]["playerStats"]["status"], "partial")

    @patch("api.src.routers.matches.db_client.fetch_all")
    @patch("api.src.routers.matches.db_client.fetch_one")
    def test_match_center_hides_depth_sections_when_profile_marks_them_unsafe(self, fetch_one_mock, fetch_all_mock) -> None:
        fetch_one_mock.side_effect = [self._match_row(), self._depth_profile_row()]

        response = self.client.get(
            "/api/v1/matches/930002718867?includeTimeline=true&includeLineups=true&includeTeamStats=true&includePlayerStats=true"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["timeline"], [])
        self.assertEqual(payload["lineups"], [])
        self.assertEqual(payload["teamStats"], [])
        self.assertEqual(payload["playerStats"], [])
        self.assertFalse(payload["depthProfile"]["hasEvents"])
        self.assertFalse(payload["depthProfile"]["hasLineups"])
        self.assertNotIn("sectionCoverage", payload)
        fetch_all_mock.assert_not_called()

    @patch("api.src.routers.matches.db_client.fetch_all")
    @patch("api.src.routers.matches.db_client.fetch_one")
    def test_matches_list_includes_depth_profile(self, fetch_one_mock, fetch_all_mock) -> None:
        fetch_one_mock.return_value = {
            "total_matches": 4,
            "with_any_content": 3,
            "events_count": 1,
            "lineups_count": 2,
            "team_stats_count": 3,
            "player_stats_count": 0,
        }
        fetch_all_mock.return_value = [
            {
                **self._match_row(),
                **self._depth_profile_row(
                    has_events=True,
                    has_lineups=True,
                    has_team_stats=True,
                    valid_event_rows=3,
                    valid_lineup_rows=22,
                    valid_team_stat_rows=2,
                    safe_sections=["score", "events", "lineups", "team_stats"],
                    depth_score=4,
                ),
                "_total_count": 1,
            }
        ]

        response = self.client.get(
            "/api/v1/matches?hasContent=true&contentSection=events&sortBy=depthScore&page=1&pageSize=1"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        item = payload["items"][0]
        self.assertEqual(item["matchId"], "930002718867")
        self.assertTrue(item["depthProfile"]["hasEvents"])
        self.assertTrue(item["depthProfile"]["hasLineups"])
        self.assertEqual(item["depthProfile"]["counts"]["validEventRows"], 3)
        self.assertEqual(item["depthProfile"]["safeSections"], ["score", "events", "lineups", "team_stats"])
        self.assertEqual(payload["contentSummary"]["withAnyContent"], 3)
        self.assertEqual(payload["contentSummary"]["sections"]["teamStats"], 3)
        summary_query = fetch_one_mock.call_args.args[0]
        self.assertIn("count(*) filter (where coalesce(has_events, false))", summary_query)
        list_query = fetch_all_mock.call_args.args[0]
        self.assertIn("left join mart.match_depth_profile mdp", list_query)
        self.assertIn("or coalesce(e.has_events, false)", list_query)
        self.assertIn("or (%s = 'events' and coalesce(e.has_events, false))", list_query)
        self.assertIn("order by f.depth_score desc", list_query)
        self.assertIn(True, fetch_all_mock.call_args.args[1])
        self.assertIn("events", fetch_all_mock.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
