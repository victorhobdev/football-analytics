from __future__ import annotations

import unittest
from unittest.mock import patch

from api.src.routers.home import _fetch_archive_summary, _fetch_competitions, _load_home_page_data


class HomeRouteTests(unittest.TestCase):
    def test_home_page_data_is_loaded_once_for_the_static_snapshot(self) -> None:
        competitions = [{"competitionKey": "champions_league"}]
        archive_summary = {"competitions": 0, "seasons": 0, "matches": 0, "players": 3}
        highlights = [{"id": "highlight-1"}]

        _load_home_page_data.cache_clear()
        with (
            patch("api.src.routers.home._fetch_competitions", return_value=competitions) as fetch_competitions,
            patch("api.src.routers.home._fetch_archive_summary", return_value=archive_summary) as fetch_archive,
            patch("api.src.routers.home._fetch_editorial_highlights", return_value=highlights) as fetch_highlights,
        ):
            first = _load_home_page_data()
            second = _load_home_page_data()

        self.assertIs(first, second)
        fetch_competitions.assert_called_once_with()
        fetch_archive.assert_called_once_with()
        fetch_highlights.assert_called_once_with()
        _load_home_page_data.cache_clear()

    def test_archive_summary_uses_small_serving_query(self) -> None:
        with patch("api.src.routers.home.db_client") as db_client:
            db_client.fetch_one.return_value = {"players": 3}

            result = _fetch_archive_summary()

        query = db_client.fetch_one.call_args.args[0]
        self.assertIn("mart.dim_player", query)
        self.assertNotIn("raw.fixtures", query)
        self.assertEqual(result, {"competitions": 0, "seasons": 0, "matches": 0, "players": 3})

    def test_competitions_read_from_serving_summary(self) -> None:
        serving_row = {
            "league_id": 2,
            "competition_key": "champions_league",
            "competition_name": "Champions League",
            "matches_count": 10,
            "seasons_count": 2,
            "min_season_label": "2024",
            "max_season_label": "2025",
            "match_statistics_count": 8,
            "lineups_count": 8,
            "events_count": 9,
            "player_statistics_count": 8,
        }

        with (
            patch("api.src.routers.home.db_client") as db_client,
            patch("api.src.routers.home._fetch_control_competition_catalog", return_value={}),
            patch("api.src.routers.home._fetch_external_competition_depth_by_key", return_value={}),
        ):
            db_client.fetch_all.return_value = [serving_row]

            result = _fetch_competitions()

        query = db_client.fetch_all.call_args.args[0]
        self.assertIn("mart.competition_serving_summary", query)
        self.assertIn("distinct on (lc.competition_key)", query.lower())
        self.assertNotIn("mart.fact_match_events", query)
        self.assertEqual(result[0]["competitionKey"], "champions_league")
        self.assertEqual(result[0]["matchesCount"], 10)


if __name__ == "__main__":
    unittest.main()
