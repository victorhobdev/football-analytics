-- migrate:up
CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_match_id
  ON mart.fact_matches (match_id);

CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_scope_date
  ON mart.fact_matches (league_id, season, date_day DESC, match_id DESC);

CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_competition_stage
  ON mart.fact_matches (competition_key, season_label, stage_id, round_id);

CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_home_team_date
  ON mart.fact_matches (home_team_id, date_day DESC, match_id DESC);

CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_away_team_date
  ON mart.fact_matches (away_team_id, date_day DESC, match_id DESC);

CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_round_scope
  ON mart.fact_matches (league_id, season, round_number);

CREATE INDEX IF NOT EXISTS idx_mart_dim_competition_league
  ON mart.dim_competition (league_id);

CREATE INDEX IF NOT EXISTS idx_mart_dim_team_team
  ON mart.dim_team (team_id);

CREATE INDEX IF NOT EXISTS idx_mart_dim_player_player
  ON mart.dim_player (player_id);

CREATE INDEX IF NOT EXISTS idx_mart_dim_stage_scope
  ON mart.dim_stage (competition_key, season_label, stage_id);

CREATE INDEX IF NOT EXISTS idx_mart_dim_stage_provider_stage
  ON mart.dim_stage (provider, stage_id);

CREATE INDEX IF NOT EXISTS idx_mart_dim_round_scope
  ON mart.dim_round (league_id, season_id, stage_id, round_id);

CREATE INDEX IF NOT EXISTS idx_mart_player_match_summary_match
  ON mart.player_match_summary (match_id);

CREATE INDEX IF NOT EXISTS idx_mart_player_match_summary_team_date
  ON mart.player_match_summary (team_id, match_date DESC, match_id DESC);

CREATE INDEX IF NOT EXISTS idx_mart_fact_fixture_player_stats_player_date
  ON mart.fact_fixture_player_stats (player_id, match_date DESC, match_id DESC);

CREATE INDEX IF NOT EXISTS idx_mart_fact_fixture_player_stats_match_player
  ON mart.fact_fixture_player_stats (match_id, player_id);

CREATE INDEX IF NOT EXISTS idx_mart_fact_fixture_lineups_team_match
  ON mart.fact_fixture_lineups (team_id, match_id, player_id);

CREATE INDEX IF NOT EXISTS idx_mart_fact_coach_assignment_public_match
  ON mart.fact_coach_match_assignment (is_public_eligible, match_id, team_id);

CREATE INDEX IF NOT EXISTS idx_mart_fact_coach_assignment_team_match
  ON mart.fact_coach_match_assignment (team_id, match_id);

CREATE INDEX IF NOT EXISTS idx_mart_coach_tenure_coach
  ON mart.coach_tenure (coach_identity_id);

CREATE INDEX IF NOT EXISTS idx_raw_player_transfers_date_id
  ON raw.player_transfers (transfer_date DESC, transfer_id DESC);

CREATE INDEX IF NOT EXISTS idx_raw_player_transfers_type_date
  ON raw.player_transfers (type_id, transfer_date DESC);

CREATE INDEX IF NOT EXISTS idx_raw_player_transfers_from_team_date
  ON raw.player_transfers (from_team_id, transfer_date DESC);

CREATE INDEX IF NOT EXISTS idx_raw_player_transfers_to_team_date
  ON raw.player_transfers (to_team_id, transfer_date DESC);

CREATE INDEX IF NOT EXISTS idx_mart_fact_standings_snapshots_scope
  ON mart.fact_standings_snapshots (competition_key, season_label, stage_id, group_id, round_id, position);

CREATE INDEX IF NOT EXISTS idx_mart_fact_group_standings_scope
  ON mart.fact_group_standings (competition_key, season_label, stage_id, group_id, position);

CREATE INDEX IF NOT EXISTS idx_mart_fact_tie_results_scope
  ON mart.fact_tie_results (competition_key, season_label, stage_id, tie_id);

CREATE INDEX IF NOT EXISTS idx_mart_competition_structure_scope
  ON mart.competition_structure_hub (competition_key, season_label, from_stage_id);

-- migrate:down
DROP INDEX IF EXISTS mart.idx_mart_competition_structure_scope;
DROP INDEX IF EXISTS mart.idx_mart_fact_tie_results_scope;
DROP INDEX IF EXISTS mart.idx_mart_fact_group_standings_scope;
DROP INDEX IF EXISTS mart.idx_mart_fact_standings_snapshots_scope;
DROP INDEX IF EXISTS raw.idx_raw_player_transfers_to_team_date;
DROP INDEX IF EXISTS raw.idx_raw_player_transfers_from_team_date;
DROP INDEX IF EXISTS raw.idx_raw_player_transfers_type_date;
DROP INDEX IF EXISTS raw.idx_raw_player_transfers_date_id;
DROP INDEX IF EXISTS mart.idx_mart_coach_tenure_coach;
DROP INDEX IF EXISTS mart.idx_mart_fact_coach_assignment_team_match;
DROP INDEX IF EXISTS mart.idx_mart_fact_coach_assignment_public_match;
DROP INDEX IF EXISTS mart.idx_mart_fact_fixture_lineups_team_match;
DROP INDEX IF EXISTS mart.idx_mart_fact_fixture_player_stats_match_player;
DROP INDEX IF EXISTS mart.idx_mart_fact_fixture_player_stats_player_date;
DROP INDEX IF EXISTS mart.idx_mart_player_match_summary_team_date;
DROP INDEX IF EXISTS mart.idx_mart_player_match_summary_match;
DROP INDEX IF EXISTS mart.idx_mart_dim_round_scope;
DROP INDEX IF EXISTS mart.idx_mart_dim_stage_provider_stage;
DROP INDEX IF EXISTS mart.idx_mart_dim_stage_scope;
DROP INDEX IF EXISTS mart.idx_mart_dim_player_player;
DROP INDEX IF EXISTS mart.idx_mart_dim_team_team;
DROP INDEX IF EXISTS mart.idx_mart_dim_competition_league;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_round_scope;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_away_team_date;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_home_team_date;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_competition_stage;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_scope_date;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_match_id;
