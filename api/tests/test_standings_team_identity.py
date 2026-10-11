from datetime import date
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.core.team_identity import resolve_legacy_team_ids
from api.src.main import app
from api.src.routers import standings, teams


class StandingsTeamIdentityTests(TestCase):
    def test_resolves_public_standings_ids_to_canonical_profiles(self):
        with patch('api.src.core.team_identity.db_client.fetch_all', return_value=[
            {'source_id': '2864', 'canonical_id': '3000000000848'},
            {'source_id': '3422', 'canonical_id': '3000000001504'},
        ]) as fetch_all:
            resolved = resolve_legacy_team_ids(['2864', '3422'], '2024')

        self.assertEqual(resolved, {'2864': '3000000000848', '3422': '3000000001504'})
        query, params = fetch_all.call_args.args
        self.assertIn("mapping_state = 'approved'", query)
        self.assertIn('mart.dim_team', query)
        self.assertIn('valid_from', query)
        self.assertIn('valid_to', query)
        self.assertEqual(params, [['2864', '3422'], date(2024, 7, 1), date(2024, 7, 1)])

    def test_does_not_choose_between_conflicting_identities(self):
        with patch('api.src.core.team_identity.db_client.fetch_all', return_value=[
            {'source_id': '2864', 'canonical_id': '100'},
            {'source_id': '2864', 'canonical_id': '200'},
        ]):
            self.assertEqual(resolve_legacy_team_ids(['2864'], '2024'), {})

    def test_unmapped_ids_remain_unresolved(self):
        with patch('api.src.core.team_identity.db_client.fetch_all', return_value=[]):
            self.assertEqual(resolve_legacy_team_ids(['9999'], '2024'), {})

    def test_split_year_season_uses_its_start_year(self):
        with patch('api.src.core.team_identity.db_client.fetch_all', return_value=[]) as fetch_all:
            resolve_legacy_team_ids(['715'], '2024/2025')
        self.assertEqual(fetch_all.call_args.args[1][1:], [date(2024, 7, 1)] * 2)

    def test_empty_input_does_not_query_the_database(self):
        with patch('api.src.core.team_identity.db_client.fetch_all') as fetch_all:
            self.assertEqual(resolve_legacy_team_ids([], '2024'), {})
        fetch_all.assert_not_called()

    def test_standings_links_use_profile_ids_without_changing_the_table(self):
        scope = standings.StandingsScope(71, 2024, 23628, 'Brasileirão', 'brasileirao_a', '2024')
        stage = standings.StandingsStage(1, 'Regular Season', 'league_table', 20)
        round_data = standings.StandingsRound(38, 38, '38', 'Rodada 38', None, None, True)
        snapshot = [
            {'position': 1, 'team_id': '2864', 'team_name': 'Botafogo', 'points': 79, 'matches_played': 38},
            {'position': 2, 'team_id': '3422', 'team_name': 'Palmeiras', 'points': 73, 'matches_played': 38},
        ]
        with (
            patch.object(standings, '_resolve_standings_scope', return_value=scope),
            patch.object(standings, '_resolve_standings_stage', return_value=stage),
            patch.object(standings, '_fetch_stage_rounds', return_value=[round_data]),
            patch.object(standings, '_fetch_standings_rows', return_value=snapshot),
            patch('api.src.core.team_identity.db_client.fetch_all', return_value=[
                {'source_id': '2864', 'canonical_id': '3000000000848'},
                {'source_id': '3422', 'canonical_id': '3000000001504'},
            ]),
        ):
            response = TestClient(app).get('/api/v1/standings?competitionId=71&seasonId=2024')
        self.assertEqual(response.status_code, 200)
        rows = response.json()['data']['rows']
        self.assertEqual([row['teamId'] for row in rows], ['3000000000848', '3000000001504'])
        self.assertEqual([row['points'] for row in rows], [79, 73])
        self.assertEqual([row['matchesPlayed'] for row in rows], [38, 38])
        self.assertEqual([row['position'] for row in rows], [1, 2])
        self.assertEqual([row['team_id'] for row in snapshot], ['2864', '3422'])

    def test_old_profile_links_load_the_canonical_team_and_its_statistics(self):
        for old_id, canonical_id, name in [
            ('2864', '3000000000848', 'Botafogo'),
            ('3422', '3000000001504', 'Palmeiras'),
        ]:
            with (
                self.subTest(team=name),
                patch.object(teams, '_fetch_team_profile_foundation', return_value={
                    'identity': {'teamType': 'club', 'officialName': name},
                    'archive': {},
                    'identityCoverage': {'status': 'complete', 'percentage': 100},
                    'archiveCoverage': {'status': 'complete', 'percentage': 100},
                }) as foundation,
                patch.object(teams, '_load_team_honors', return_value=None),
                patch.object(teams.db_client, 'fetch_one', side_effect=[
                    None,
                    {'team_id': int(canonical_id), 'team_name': name},
                    {'league_name': 'Brasileirão'},
                    {'matches_played': 38, 'wins': 23, 'points': 79},
                    {'position': 1, 'total_teams': 20},
                ]) as fetch_one,
                patch('api.src.core.team_identity.db_client.fetch_all', return_value=[
                    {'source_id': old_id, 'canonical_id': canonical_id},
                ]),
            ):
                response = TestClient(app).get(
                    f'/api/v1/teams/{old_id}?competitionId=71&seasonId=2024'
                    '&includeRecentMatches=false&includeSquad=false&includeStats=false'
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['data']['team']['teamId'], canonical_id)
                foundation.assert_called_once_with(int(canonical_id), name)
                self.assertIn(int(canonical_id), fetch_one.call_args_list[3].args[1])

    def test_unknown_profile_still_returns_not_found(self):
        with (
            patch.object(teams.db_client, 'fetch_one', return_value=None),
            patch('api.src.core.team_identity.db_client.fetch_all', return_value=[]),
        ):
            response = TestClient(app).get('/api/v1/teams/9999?competitionId=71&seasonId=2024')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], 'TEAM_NOT_FOUND')

    def test_old_context_links_query_matches_with_the_canonical_id(self):
        with (
            patch.object(teams.db_client, 'fetch_one', side_effect=[
                None, {'team_id': 3000000000848, 'team_name': 'Botafogo'},
            ]),
            patch.object(teams.db_client, 'fetch_all', side_effect=[
                [{'source_id': '2864', 'canonical_id': '3000000000848'}],
                [{'league_id': 71, 'competition_name': 'Brasileirão', 'season_id': 2024}],
            ]) as fetch_all,
        ):
            response = TestClient(app).get('/api/v1/teams/2864/contexts?competitionId=71&seasonId=2024')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(fetch_all.call_args.args[1], [3000000000848, 3000000000848])
