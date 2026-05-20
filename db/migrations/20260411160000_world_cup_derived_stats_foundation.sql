-- migrate:up

CREATE TABLE IF NOT EXISTS silver.wc_match_stats (
  edition_key text NOT NULL,
  internal_match_id text NOT NULL,
  team_internal_id text NOT NULL,
  source_name text NOT NULL,
  source_version text NOT NULL,
  source_match_id text,
  team_name text,
  shots_on_goal integer,
  shots_off_goal integer,
  total_shots integer,
  blocked_shots integer,
  shots_inside_box integer,
  shots_outside_box integer,
  fouls integer,
  corner_kicks integer,
  offsides integer,
  ball_possession integer,
  yellow_cards integer,
  red_cards integer,
  goalkeeper_saves integer,
  total_passes integer,
  passes_accurate integer,
  passes_pct numeric,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  materialized_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_wc_match_stats PRIMARY KEY (edition_key, internal_match_id, team_internal_id, source_name),
  CONSTRAINT chk_wc_match_stats_source_name CHECK (source_name = 'statsbomb_open_data'),
  CONSTRAINT chk_wc_match_stats_ball_possession CHECK (ball_possession IS NULL OR (ball_possession BETWEEN 0 AND 100))
);

CREATE INDEX IF NOT EXISTS idx_wc_match_stats_match
  ON silver.wc_match_stats (edition_key, internal_match_id);

CREATE INDEX IF NOT EXISTS idx_wc_match_stats_team
  ON silver.wc_match_stats (team_internal_id);

CREATE TABLE IF NOT EXISTS silver.wc_player_match_stats (
  edition_key text NOT NULL,
  internal_match_id text NOT NULL,
  team_internal_id text NOT NULL,
  player_internal_id text NOT NULL,
  source_name text NOT NULL,
  source_version text NOT NULL,
  source_match_id text,
  source_team_id text,
  source_player_id text,
  team_name text,
  player_name text,
  player_nickname text,
  jersey_number integer,
  is_starter boolean,
  minutes_played integer,
  statistics jsonb NOT NULL DEFAULT '[]'::jsonb,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  materialized_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_wc_player_match_stats PRIMARY KEY (
    edition_key,
    internal_match_id,
    team_internal_id,
    player_internal_id,
    source_name
  ),
  CONSTRAINT chk_wc_player_match_stats_source_name CHECK (source_name = 'statsbomb_open_data'),
  CONSTRAINT chk_wc_player_match_stats_minutes_played CHECK (minutes_played IS NULL OR minutes_played >= 0)
);

CREATE INDEX IF NOT EXISTS idx_wc_player_match_stats_match
  ON silver.wc_player_match_stats (edition_key, internal_match_id);

CREATE INDEX IF NOT EXISTS idx_wc_player_match_stats_player
  ON silver.wc_player_match_stats (player_internal_id);

CREATE INDEX IF NOT EXISTS idx_wc_player_match_stats_team
  ON silver.wc_player_match_stats (team_internal_id);

-- migrate:down

DROP TABLE IF EXISTS silver.wc_player_match_stats;
DROP TABLE IF EXISTS silver.wc_match_stats;
