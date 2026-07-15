from unittest import TestCase
from unittest.mock import patch

from src.routers.standings import (
    StandingsRound,
    StandingsScope,
    StandingsStage,
    _fetch_standings_rows,
)


class StandingsFastPathTest(TestCase):
    def test_uses_materialized_snapshot_without_recomputing_matches(self) -> None:
        rows = [{"position": 1, "team_id": "1024", "team_name": "Flamengo"}]
        scope = StandingsScope(71, 2025, 25500, "Brasileirão", "brasileirao_a", "2025")
        stage = StandingsStage(77475702, "Regular Season", "league_table", 20)
        round_data = StandingsRound(367561, 367561, "38", "Rodada 38", None, None, True)

        with patch("src.routers.standings.db_client.fetch_all", return_value=rows) as fetch_all:
            self.assertEqual(_fetch_standings_rows(scope, stage, round_data), rows)

        self.assertEqual(fetch_all.call_count, 1)
        self.assertIn("mart.fact_standings_snapshots", fetch_all.call_args.args[0])
