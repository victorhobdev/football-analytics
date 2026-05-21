from __future__ import annotations

import unittest
from unittest.mock import patch

from api.src.routers.world_cup import (
    _build_world_cup_edition_rankings,
    _build_world_cup_squad_appearance_rankings,
    _build_world_cup_team_stat_rankings,
    _build_world_cup_team_catalog,
    _filter_scorer_list_by_minimum_goals,
)
from api.src.routers.world_cup_labels import serialize_world_cup_display_team


class WorldCupRouteHelpersTests(unittest.TestCase):
    def test_serialize_world_cup_display_team_merges_germany_lineage(self) -> None:
        brazil = serialize_world_cup_display_team(7030456752538593319, "Brazil")
        germany = serialize_world_cup_display_team(7030167035104799597, "Germany")
        west_germany = serialize_world_cup_display_team(7030069810056421591, "West Germany")
        east_germany = serialize_world_cup_display_team(7030661052346191578, "East Germany")

        self.assertEqual(brazil, {"teamId": "world-cup-brazil", "teamName": "Brasil"})
        self.assertEqual(germany, {"teamId": "world-cup-germany", "teamName": "Alemanha"})
        self.assertEqual(west_germany, {"teamId": "world-cup-germany", "teamName": "Alemanha"})
        self.assertEqual(east_germany, {"teamId": "world-cup-east-germany", "teamName": "Alemanha Oriental"})

    @patch("api.src.routers.world_cup._fetch_team_top_scorers_by_season")
    @patch("api.src.routers.world_cup._fetch_team_knockout_presence_rows")
    @patch("api.src.routers.world_cup._fetch_team_stage_presence_rows")
    @patch("api.src.routers.world_cup._fetch_team_match_rows")
    @patch("api.src.routers.world_cup._build_world_cup_hub_payload")
    def test_team_catalog_merges_germany_and_west_germany_in_single_display_entity(
        self,
        build_hub_payload_mock,
        fetch_team_match_rows_mock,
        fetch_team_stage_presence_rows_mock,
        fetch_team_knockout_presence_rows_mock,
        fetch_team_top_scorers_by_season_mock,
    ) -> None:
        build_hub_payload_mock.return_value = (
            {
                "summary": {},
                "editions": [
                    {
                        "seasonLabel": "1954",
                        "year": 1954,
                        "editionName": "Copa do Mundo FIFA 1954",
                        "champion": {"teamId": "world-cup-germany", "teamName": "Alemanha"},
                        "runnerUp": {"teamId": "900", "teamName": "Hungria"},
                    },
                    {
                        "seasonLabel": "2014",
                        "year": 2014,
                        "editionName": "Copa do Mundo FIFA 2014",
                        "champion": {"teamId": "world-cup-germany", "teamName": "Alemanha"},
                        "runnerUp": {"teamId": "901", "teamName": "Argentina"},
                    },
                ],
            },
            {"status": "complete", "label": "Cobertura completa", "percentage": 100},
        )
        fetch_team_match_rows_mock.return_value = [
            {
                "season_label": "1954",
                "team_id": 7030069810056421591,
                "team_name": "West Germany",
                "matches_count": 6,
            },
            {
                "season_label": "2014",
                "team_id": 7030167035104799597,
                "team_name": "Germany",
                "matches_count": 7,
            },
        ]
        fetch_team_stage_presence_rows_mock.return_value = []
        fetch_team_knockout_presence_rows_mock.return_value = []
        fetch_team_top_scorers_by_season_mock.return_value = []

        teams_payload, team_index = _build_world_cup_team_catalog()

        self.assertEqual(len(teams_payload), 1)
        self.assertEqual(teams_payload[0]["teamId"], "world-cup-germany")
        self.assertEqual(teams_payload[0]["teamName"], "Alemanha")
        self.assertEqual(teams_payload[0]["titlesCount"], 2)
        self.assertEqual(teams_payload[0]["participationsCount"], 2)
        self.assertEqual([item["year"] for item in teams_payload[0]["participations"]], [1954, 2014])
        self.assertEqual(team_index["7030069810056421591"]["teamId"], "world-cup-germany")
        self.assertEqual(team_index["7030167035104799597"]["teamId"], "world-cup-germany")

    def test_filter_scorer_list_by_minimum_goals_removes_low_value_rows(self) -> None:
        rows = [
            {"playerName": "Jogador A", "goals": 5},
            {"playerName": "Jogador B", "goals": 3},
            {"playerName": "Jogador C", "goals": 2},
            {"playerName": "Jogador D", "goals": 1},
        ]

        filtered_rows = _filter_scorer_list_by_minimum_goals(rows)

        self.assertEqual(filtered_rows, rows[:2])

    def test_team_stat_rankings_merge_germany_lineage_for_fixture_aggregates(self) -> None:
        teams_payload = [
            {
                "teamId": "world-cup-germany",
                "teamName": "Alemanha",
                "titlesCount": 4,
                "participationsCount": 20,
                "participations": [
                    {"resultRank": 1},
                    {"resultRank": 1},
                    {"resultRank": 1},
                    {"resultRank": 1},
                    {"resultRank": 2},
                    {"resultRank": 4},
                ],
            },
            {
                "teamId": "1",
                "teamName": "Brasil",
                "titlesCount": 5,
                "participationsCount": 22,
                "participations": [
                    {"resultRank": 1},
                    {"resultRank": 1},
                    {"resultRank": 1},
                    {"resultRank": 1},
                    {"resultRank": 1},
                ],
            },
        ]
        fixture_rows = [
            {
                "home_team_id": 7030069810056421591,
                "home_team_name": "West Germany",
                "away_team_id": 1,
                "away_team_name": "Brasil",
                "home_goals": 3,
                "away_goals": 2,
            },
            {
                "home_team_id": 7030167035104799597,
                "home_team_name": "Germany",
                "away_team_id": 1,
                "away_team_name": "Brasil",
                "home_goals": 2,
                "away_goals": 0,
            },
        ]

        rankings = _build_world_cup_team_stat_rankings(teams_payload, fixture_rows)

        self.assertEqual(rankings["wins"]["items"][0]["teamId"], "world-cup-germany")
        self.assertEqual(rankings["wins"]["items"][0]["wins"], 2)
        self.assertEqual(rankings["matches"]["items"][0]["teamId"], "world-cup-germany")
        self.assertEqual(rankings["matches"]["items"][0]["matches"], 2)
        self.assertEqual(rankings["goalsScored"]["items"][0]["teamId"], "world-cup-germany")
        self.assertEqual(rankings["goalsScored"]["items"][0]["goalsScored"], 5)
        self.assertEqual(rankings["topFourAppearances"]["items"][0]["teamId"], "world-cup-germany")
        self.assertEqual(rankings["topFourAppearances"]["items"][0]["topFourCount"], 6)

    def test_edition_rankings_measure_goals_and_average_from_fixtures(self) -> None:
        editions = [
            {"seasonLabel": "1954", "year": 1954, "editionName": "Copa do Mundo FIFA 1954"},
            {"seasonLabel": "1982", "year": 1982, "editionName": "Copa do Mundo FIFA 1982"},
        ]
        fixture_rows = [
            {"season_label": "1954", "home_goals": 4, "away_goals": 1},
            {"season_label": "1954", "home_goals": 3, "away_goals": 2},
            {"season_label": "1982", "home_goals": 1, "away_goals": 0},
            {"season_label": "1982", "home_goals": 1, "away_goals": 0},
            {"season_label": "1982", "home_goals": 1, "away_goals": 0},
        ]

        rankings = _build_world_cup_edition_rankings(editions, fixture_rows)

        self.assertEqual(rankings["goals"]["items"][0]["seasonLabel"], "1954")
        self.assertEqual(rankings["goals"]["items"][0]["goalsCount"], 10)
        self.assertEqual(rankings["goalsPerMatch"]["items"][0]["seasonLabel"], "1954")
        self.assertEqual(rankings["goalsPerMatch"]["items"][0]["goalsPerMatch"], 5.0)

    def test_squad_appearance_rankings_group_players_by_distinct_editions(self) -> None:
        squad_rows = [
            {
                "player_id": 10,
                "player_name": "Lothar Matthäus",
                "season_label": "1982",
                "team_id": 7030069810056421591,
                "team_name": "West Germany",
            },
            {
                "player_id": 10,
                "player_name": "Lothar Matthäus",
                "season_label": "1986",
                "team_id": 7030069810056421591,
                "team_name": "West Germany",
            },
            {
                "player_id": 10,
                "player_name": "Lothar Matthäus",
                "season_label": "1990",
                "team_id": 7030069810056421591,
                "team_name": "West Germany",
            },
            {
                "player_id": 10,
                "player_name": "Lothar Matthäus",
                "season_label": "1994",
                "team_id": 7030167035104799597,
                "team_name": "Germany",
            },
            {
                "player_id": 20,
                "player_name": "Jogador B",
                "season_label": "1998",
                "team_id": 1,
                "team_name": "Brasil",
            },
        ]

        rankings = _build_world_cup_squad_appearance_rankings(squad_rows)

        self.assertEqual(rankings["squadAppearances"]["items"][0]["playerId"], "10")
        self.assertEqual(rankings["squadAppearances"]["items"][0]["teamId"], "world-cup-germany")
        self.assertEqual(rankings["squadAppearances"]["items"][0]["teamName"], "Alemanha")
        self.assertEqual(rankings["squadAppearances"]["items"][0]["appearancesCount"], 4)
        self.assertEqual(
            [edition["year"] for edition in rankings["squadAppearances"]["items"][0]["editions"]],
            [1982, 1986, 1990, 1994],
        )


if __name__ == "__main__":
    unittest.main()
