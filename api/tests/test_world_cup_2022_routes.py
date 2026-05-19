from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.main import app


class WorldCup2022RoutesApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.src.routers.world_cup_2022.db_client.fetch_all")
    def test_competition_hub_returns_fixtures_and_grouped_standings(self, fetch_all_mock) -> None:
        fetch_all_mock.side_effect = [
            [
                {
                    "fixture_id": 1,
                    "date_utc": "2022-11-20T15:00:00Z",
                    "status_short": "FT",
                    "status_long": "Match Finished",
                    "stage_name": "Group Stage",
                    "group_name": "Group A",
                    "round_name": "Group A",
                    "venue_name": "Al Bayt Stadium",
                    "venue_city": "Al Khor",
                    "referee": "Daniele Orsato",
                    "home_team_id": 10,
                    "home_team_name": "Qatar",
                    "away_team_id": 20,
                    "away_team_name": "Ecuador",
                    "home_goals": 0,
                    "away_goals": 2,
                    "source_provider": "fjelstul_worldcup",
                }
            ],
            [
                {
                    "round_id": 101,
                    "stage_id": 201,
                    "team_id": 20,
                    "position": 1,
                    "points": 7,
                    "games_played": 3,
                    "won": 2,
                    "draw": 1,
                    "lost": 0,
                    "goals_for": 5,
                    "goals_against": 1,
                    "goal_diff": 4,
                    "stage_key": "group_stage_1",
                    "group_key": "A",
                    "team_name": "Ecuador",
                    "team_code": "ECU",
                    "advanced": "true",
                },
                {
                    "round_id": 101,
                    "stage_id": 201,
                    "team_id": 10,
                    "position": 4,
                    "points": 0,
                    "games_played": 3,
                    "won": 0,
                    "draw": 0,
                    "lost": 3,
                    "goals_for": 1,
                    "goals_against": 7,
                    "goal_diff": -6,
                    "stage_key": "group_stage_1",
                    "group_key": "A",
                    "team_name": "Qatar",
                    "team_code": "QAT",
                    "advanced": "false",
                },
            ],
        ]

        response = self.client.get("/api/v1/world-cup-2022/competition-hub")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["competition"]["editionKey"], "fifa_world_cup_mens__2022")
        self.assertEqual(payload["data"]["fixtures"][0]["fixtureId"], "1")
        self.assertEqual(payload["data"]["standings"]["groups"][0]["groupKey"], "A")
        self.assertEqual(payload["data"]["standings"]["groups"][0]["rows"][0]["teamCode"], "ECU")
        self.assertEqual(payload["meta"]["coverage"]["status"], "partial")

    @patch("api.src.routers.world_cup_2022.db_client.fetch_all")
    @patch("api.src.routers.world_cup_2022.db_client.fetch_one")
    def test_match_view_returns_fixture_lineups_and_events(
        self,
        fetch_one_mock,
        fetch_all_mock,
    ) -> None:
        fetch_one_mock.return_value = {
            "fixture_id": 1,
            "date_utc": "2022-11-20T15:00:00Z",
            "status_short": "FT",
            "status_long": "Match Finished",
            "stage_name": "Group Stage",
            "group_name": "Group A",
            "round_name": "Group A",
            "venue_name": "Al Bayt Stadium",
            "venue_city": "Al Khor",
            "referee": "Daniele Orsato",
            "home_team_id": 10,
            "home_team_name": "Qatar",
            "away_team_id": 20,
            "away_team_name": "Ecuador",
            "home_goals": 0,
            "away_goals": 2,
            "source_provider": "fjelstul_worldcup",
        }
        fetch_all_mock.side_effect = [
            [
                {
                    "fixture_id": 1,
                    "team_id": 10,
                    "team_name": "Qatar",
                    "player_id": 101,
                    "lineup_id": 1001,
                    "position_name": "Goalkeeper",
                    "lineup_type_id": 1,
                    "formation_field": "goalkeeper",
                    "formation_position": 1,
                    "jersey_number": 1,
                    "details": [],
                    "player_internal_id": "player__1",
                    "player_name": "Goalkeeper Qatar",
                    "player_nickname": "GK Qatar",
                    "source_name": "statsbomb_open_data",
                    "source_version": "statsbomb-sha",
                },
                {
                    "fixture_id": 1,
                    "team_id": 20,
                    "team_name": "Ecuador",
                    "player_id": 201,
                    "lineup_id": 2001,
                    "position_name": "Forward",
                    "lineup_type_id": 2,
                    "formation_field": "attack",
                    "formation_position": 9,
                    "jersey_number": 13,
                    "details": [],
                    "player_internal_id": "player__2",
                    "player_name": "Forward Ecuador",
                    "player_nickname": None,
                    "source_name": "statsbomb_open_data",
                    "source_version": "statsbomb-sha",
                },
            ],
            [
                {
                    "fixture_id": 1,
                    "internal_match_id": "match__wc__1",
                    "source_name": "statsbomb_open_data",
                    "source_version": "statsbomb-sha",
                    "source_match_id": "3857256",
                    "source_event_id": "evt-1",
                    "event_index": 1,
                    "event_type": "Starting XI",
                    "period": 1,
                    "minute": 0,
                    "second": 0,
                    "location_x": None,
                    "location_y": None,
                    "outcome_label": None,
                    "play_pattern_label": "Regular Play",
                    "is_three_sixty_backed": False,
                    "team_internal_id": "team__national_team__QAT",
                    "team_name": "Qatar",
                    "player_internal_id": None,
                    "player_name": None,
                    "event_payload": {"id": "evt-1"},
                }
            ],
        ]

        response = self.client.get("/api/v1/world-cup-2022/matches/1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["fixture"]["fixtureId"], "1")
        self.assertEqual(payload["data"]["lineups"][0]["teamName"], "Qatar")
        self.assertEqual(payload["data"]["lineups"][0]["starters"][0]["playerName"], "Goalkeeper Qatar")
        self.assertEqual(payload["data"]["events"][0]["sourceEventId"], "evt-1")
        self.assertEqual(payload["data"]["events"][0]["team"]["teamName"], "Qatar")
        self.assertEqual(payload["meta"]["coverage"]["status"], "partial")

    @patch("api.src.routers.world_cup_2022.db_client.fetch_all")
    @patch("api.src.routers.world_cup_2022.db_client.fetch_one")
    def test_team_view_returns_team_coach_and_fixtures_without_global_coach_identity(
        self,
        fetch_one_mock,
        fetch_all_mock,
    ) -> None:
        fetch_one_mock.side_effect = [
            {"team_id": 30, "team_name": "Argentina"},
            {
                "coach_tenure_id": 901,
                "team_id": 30,
                "coach_source_scoped_id": "M-383",
                "given_name": "Lionel",
                "family_name": "Scaloni",
                "country_name": "Argentina",
                "coach_identity_scope": "source_scoped_fjelstul_manager_id",
                "coach_tenure_scope": "edition_scoped_manager_appointment",
                "source_name": "fjelstul_worldcup",
                "source_version": "fjelstul-sha",
            },
        ]
        fetch_all_mock.return_value = [
            {
                "fixture_id": 77,
                "date_utc": "2022-12-18T15:00:00Z",
                "status_short": "FT",
                "status_long": "Match Finished",
                "stage_name": "Final",
                "group_name": None,
                "round_name": "Final",
                "venue_name": "Lusail Stadium",
                "venue_city": "Lusail",
                "referee": "Szymon Marciniak",
                "home_team_id": 30,
                "home_team_name": "Argentina",
                "away_team_id": 40,
                "away_team_name": "France",
                "home_goals": 3,
                "away_goals": 3,
                "source_provider": "fjelstul_worldcup",
                "venue_role": "home",
                "opponent_team_id": 40,
                "opponent_team_name": "France",
            }
        ]

        response = self.client.get("/api/v1/world-cup-2022/teams/30")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["team"]["teamId"], "30")
        self.assertEqual(payload["data"]["coach"]["coachTenureId"], "901")
        self.assertEqual(payload["data"]["coach"]["coachSourceScopedId"], "M-383")
        self.assertNotIn("coachId", payload["data"]["coach"])
        self.assertEqual(payload["data"]["fixtures"][0]["opponentTeamName"], "France")
        self.assertEqual(payload["meta"]["coverage"]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
