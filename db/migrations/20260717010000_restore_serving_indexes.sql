-- migrate:up
-- The canonical mart cutover replaced fact_matches and dropped its serving indexes.
CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_match_id
  ON mart.fact_matches (match_id);

CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_scope_date
  ON mart.fact_matches (league_id, season, date_day DESC, match_id DESC);

CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_league_date
  ON mart.fact_matches (league_id, date_day DESC, match_id DESC);

CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_competition_stage
  ON mart.fact_matches (competition_key, season_label, stage_id, round_id);

CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_home_team_date
  ON mart.fact_matches (home_team_id, date_day DESC, match_id DESC);

CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_away_team_date
  ON mart.fact_matches (away_team_id, date_day DESC, match_id DESC);

CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_round_scope
  ON mart.fact_matches (league_id, season, round_number);

CREATE INDEX IF NOT EXISTS idx_mart_fact_matches_competition_date
  ON mart.fact_matches (competition_key, date_day, season_label, provider);

CREATE INDEX IF NOT EXISTS idx_mart_dim_team_team
  ON mart.dim_team (team_id);

ANALYZE mart.fact_matches;
ANALYZE mart.dim_team;

-- migrate:down
DROP INDEX IF EXISTS mart.idx_mart_dim_team_team;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_competition_date;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_round_scope;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_away_team_date;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_home_team_date;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_competition_stage;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_league_date;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_scope_date;
DROP INDEX IF EXISTS mart.idx_mart_fact_matches_match_id;
