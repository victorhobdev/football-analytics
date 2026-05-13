CREATE TABLE IF NOT EXISTS mart.team_match_goals_monthly (
  season        INT NOT NULL,
  year          TEXT NOT NULL,
  month         TEXT NOT NULL,
  team_id       BIGINT,
  team_name     TEXT NOT NULL,
  goals_for     INT NOT NULL,
  goals_against INT NOT NULL,
  matches       INT NOT NULL,
  wins          INT NOT NULL,
  draws         INT NOT NULL,
  losses        INT NOT NULL,
  points        INT NOT NULL,
  goal_diff     INT NOT NULL,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_team_match_goals_monthly PRIMARY KEY (season, year, month, team_name)
);

ALTER TABLE IF EXISTS mart.team_match_goals_monthly
  ADD COLUMN IF NOT EXISTS points INT;

ALTER TABLE IF EXISTS mart.team_match_goals_monthly
  ADD COLUMN IF NOT EXISTS goal_diff INT;

UPDATE mart.team_match_goals_monthly
SET
  points = COALESCE(wins, 0) * 3 + COALESCE(draws, 0),
  goal_diff = COALESCE(goals_for, 0) - COALESCE(goals_against, 0)
WHERE points IS NULL OR goal_diff IS NULL;

ALTER TABLE IF EXISTS mart.team_match_goals_monthly
  ALTER COLUMN points SET NOT NULL;

ALTER TABLE IF EXISTS mart.team_match_goals_monthly
  ALTER COLUMN goal_diff SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_team_match_goals_monthly_period
  ON mart.team_match_goals_monthly (season, year, month);

CREATE INDEX IF NOT EXISTS idx_team_match_goals_monthly_team_name
  ON mart.team_match_goals_monthly (team_name);

CREATE TABLE IF NOT EXISTS mart.league_summary (
  league_id           BIGINT NOT NULL,
  league_name         TEXT NOT NULL,
  season              INT NOT NULL,
  total_matches       INT NOT NULL,
  total_goals         INT NOT NULL,
  avg_goals_per_match NUMERIC(10,4) NOT NULL,
  first_match_date    DATE,
  last_match_date     DATE,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_league_summary PRIMARY KEY (league_id, season)
);

CREATE INDEX IF NOT EXISTS idx_league_summary_season
  ON mart.league_summary (season);

CREATE TABLE IF NOT EXISTS mart.standings_evolution (
  season                    INT NOT NULL,
  round                     INT NOT NULL,
  team_id                   BIGINT NOT NULL,
  points_accumulated        INT NOT NULL,
  goals_for_accumulated     INT NOT NULL,
  goal_diff_accumulated     INT NOT NULL,
  position                  INT NOT NULL,
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_standings_evolution PRIMARY KEY (season, round, team_id)
);

CREATE INDEX IF NOT EXISTS idx_standings_evolution_season_round_position
  ON mart.standings_evolution (season, round, position);

CREATE INDEX IF NOT EXISTS idx_standings_evolution_team
  ON mart.standings_evolution (team_id);
