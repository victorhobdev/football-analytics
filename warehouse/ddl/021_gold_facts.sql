CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.fact_matches (
  match_id               BIGINT PRIMARY KEY,
  league_id              BIGINT NOT NULL,
  season                 INT NOT NULL,
  date_day               DATE NOT NULL,
  home_team_id           BIGINT NOT NULL,
  away_team_id           BIGINT NOT NULL,
  venue_id               BIGINT,
  home_goals             INT,
  away_goals             INT,
  total_goals            INT,
  result                 TEXT,
  home_shots             INT,
  home_shots_on_target   INT,
  home_possession        INT,
  home_corners           INT,
  home_fouls             INT,
  away_shots             INT,
  away_shots_on_target   INT,
  away_possession        INT,
  away_corners           INT,
  away_fouls             INT,
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_fact_matches_competition
    FOREIGN KEY (league_id) REFERENCES gold.dim_competition (league_id),
  CONSTRAINT fk_fact_matches_date
    FOREIGN KEY (date_day) REFERENCES gold.dim_date (date_day),
  CONSTRAINT fk_fact_matches_home_team
    FOREIGN KEY (home_team_id) REFERENCES gold.dim_team (team_id),
  CONSTRAINT fk_fact_matches_away_team
    FOREIGN KEY (away_team_id) REFERENCES gold.dim_team (team_id),
  CONSTRAINT fk_fact_matches_venue
    FOREIGN KEY (venue_id) REFERENCES gold.dim_venue (venue_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_matches_league_id
  ON gold.fact_matches (league_id);

CREATE INDEX IF NOT EXISTS idx_fact_matches_season
  ON gold.fact_matches (season);

CREATE INDEX IF NOT EXISTS idx_fact_matches_date_day
  ON gold.fact_matches (date_day);

CREATE INDEX IF NOT EXISTS idx_fact_matches_home_team_id
  ON gold.fact_matches (home_team_id);

CREATE INDEX IF NOT EXISTS idx_fact_matches_away_team_id
  ON gold.fact_matches (away_team_id);

CREATE INDEX IF NOT EXISTS idx_fact_matches_venue_id
  ON gold.fact_matches (venue_id);

CREATE TABLE IF NOT EXISTS gold.fact_match_events (
  event_id            TEXT PRIMARY KEY,
  match_id            BIGINT NOT NULL,
  team_id             BIGINT,
  player_id           BIGINT,
  assist_player_id    BIGINT,
  time_elapsed        INT,
  time_extra          INT,
  event_type          TEXT,
  event_detail        TEXT,
  is_goal             BOOLEAN NOT NULL DEFAULT false,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_fact_match_events_match
    FOREIGN KEY (match_id) REFERENCES gold.fact_matches (match_id),
  CONSTRAINT fk_fact_match_events_team
    FOREIGN KEY (team_id) REFERENCES gold.dim_team (team_id),
  CONSTRAINT fk_fact_match_events_player
    FOREIGN KEY (player_id) REFERENCES gold.dim_player (player_id),
  CONSTRAINT fk_fact_match_events_assist_player
    FOREIGN KEY (assist_player_id) REFERENCES gold.dim_player (player_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_match_events_match_id
  ON gold.fact_match_events (match_id);

CREATE INDEX IF NOT EXISTS idx_fact_match_events_team_id
  ON gold.fact_match_events (team_id);

CREATE INDEX IF NOT EXISTS idx_fact_match_events_player_id
  ON gold.fact_match_events (player_id);

CREATE INDEX IF NOT EXISTS idx_fact_match_events_assist_player_id
  ON gold.fact_match_events (assist_player_id);
