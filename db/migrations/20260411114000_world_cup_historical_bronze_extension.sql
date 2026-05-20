-- migrate:up
CREATE TABLE IF NOT EXISTS bronze.fjelstul_wc_tournament_stages (
  source_name                TEXT NOT NULL,
  source_version             TEXT NOT NULL,
  edition_key                TEXT NOT NULL,
  snapshot_path              TEXT NOT NULL,
  snapshot_checksum_sha256   TEXT NOT NULL,
  source_file                TEXT NOT NULL,
  key_id                     TEXT NOT NULL,
  tournament_id              TEXT NOT NULL,
  stage_number               TEXT,
  stage_name                 TEXT,
  group_stage                TEXT,
  knockout_stage             TEXT,
  start_date                 TEXT,
  end_date                   TEXT,
  count_matches              TEXT,
  count_teams                TEXT,
  payload                    JSONB NOT NULL,
  ingested_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_fjelstul_wc_tournament_stages PRIMARY KEY (source_version, key_id),
  CONSTRAINT chk_fjelstul_wc_tournament_stages_source_name
    CHECK (source_name = 'fjelstul_worldcup')
);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_tournament_stages_edition
  ON bronze.fjelstul_wc_tournament_stages (edition_key);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_tournament_stages_tournament
  ON bronze.fjelstul_wc_tournament_stages (tournament_id);

CREATE TABLE IF NOT EXISTS bronze.fjelstul_wc_squads (
  source_name                TEXT NOT NULL,
  source_version             TEXT NOT NULL,
  edition_key                TEXT NOT NULL,
  snapshot_path              TEXT NOT NULL,
  snapshot_checksum_sha256   TEXT NOT NULL,
  source_file                TEXT NOT NULL,
  key_id                     TEXT NOT NULL,
  tournament_id              TEXT NOT NULL,
  team_id                    TEXT,
  team_name                  TEXT,
  team_code                  TEXT,
  player_id                  TEXT,
  family_name                TEXT,
  given_name                 TEXT,
  shirt_number               TEXT,
  position_name              TEXT,
  position_code              TEXT,
  payload                    JSONB NOT NULL,
  ingested_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_fjelstul_wc_squads PRIMARY KEY (source_version, key_id),
  CONSTRAINT chk_fjelstul_wc_squads_source_name
    CHECK (source_name = 'fjelstul_worldcup')
);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_squads_edition
  ON bronze.fjelstul_wc_squads (edition_key);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_squads_tournament
  ON bronze.fjelstul_wc_squads (tournament_id);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_squads_team_id
  ON bronze.fjelstul_wc_squads (team_id);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_squads_player_id
  ON bronze.fjelstul_wc_squads (player_id);

CREATE TABLE IF NOT EXISTS bronze.fjelstul_wc_player_appearances (
  source_name                TEXT NOT NULL,
  source_version             TEXT NOT NULL,
  edition_key                TEXT NOT NULL,
  snapshot_path              TEXT NOT NULL,
  snapshot_checksum_sha256   TEXT NOT NULL,
  source_file                TEXT NOT NULL,
  key_id                     TEXT NOT NULL,
  tournament_id              TEXT NOT NULL,
  match_id                   TEXT NOT NULL,
  match_date                 TEXT,
  stage_name                 TEXT,
  group_name                 TEXT,
  team_id                    TEXT,
  team_name                  TEXT,
  team_code                  TEXT,
  player_id                  TEXT,
  family_name                TEXT,
  given_name                 TEXT,
  shirt_number               TEXT,
  position_name              TEXT,
  position_code              TEXT,
  starter                    TEXT,
  substitute                 TEXT,
  payload                    JSONB NOT NULL,
  ingested_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_fjelstul_wc_player_appearances PRIMARY KEY (source_version, key_id),
  CONSTRAINT chk_fjelstul_wc_player_appearances_source_name
    CHECK (source_name = 'fjelstul_worldcup')
);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_player_appearances_edition
  ON bronze.fjelstul_wc_player_appearances (edition_key);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_player_appearances_tournament
  ON bronze.fjelstul_wc_player_appearances (tournament_id);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_player_appearances_match_id
  ON bronze.fjelstul_wc_player_appearances (match_id);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_player_appearances_team_id
  ON bronze.fjelstul_wc_player_appearances (team_id);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_player_appearances_player_id
  ON bronze.fjelstul_wc_player_appearances (player_id);

CREATE TABLE IF NOT EXISTS bronze.fjelstul_wc_goals (
  source_name                TEXT NOT NULL,
  source_version             TEXT NOT NULL,
  edition_key                TEXT NOT NULL,
  snapshot_path              TEXT NOT NULL,
  snapshot_checksum_sha256   TEXT NOT NULL,
  source_file                TEXT NOT NULL,
  key_id                     TEXT NOT NULL,
  goal_id                    TEXT,
  tournament_id              TEXT NOT NULL,
  match_id                   TEXT NOT NULL,
  match_date                 TEXT,
  stage_name                 TEXT,
  group_name                 TEXT,
  team_id                    TEXT,
  team_name                  TEXT,
  team_code                  TEXT,
  player_id                  TEXT,
  player_team_id             TEXT,
  minute_regulation          TEXT,
  minute_stoppage            TEXT,
  own_goal                   TEXT,
  penalty                    TEXT,
  payload                    JSONB NOT NULL,
  ingested_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_fjelstul_wc_goals PRIMARY KEY (source_version, key_id),
  CONSTRAINT chk_fjelstul_wc_goals_source_name
    CHECK (source_name = 'fjelstul_worldcup')
);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_goals_edition
  ON bronze.fjelstul_wc_goals (edition_key);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_goals_tournament
  ON bronze.fjelstul_wc_goals (tournament_id);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_goals_match_id
  ON bronze.fjelstul_wc_goals (match_id);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_goals_player_id
  ON bronze.fjelstul_wc_goals (player_id);

CREATE TABLE IF NOT EXISTS bronze.fjelstul_wc_bookings (
  source_name                TEXT NOT NULL,
  source_version             TEXT NOT NULL,
  edition_key                TEXT NOT NULL,
  snapshot_path              TEXT NOT NULL,
  snapshot_checksum_sha256   TEXT NOT NULL,
  source_file                TEXT NOT NULL,
  key_id                     TEXT NOT NULL,
  booking_id                 TEXT,
  tournament_id              TEXT NOT NULL,
  match_id                   TEXT NOT NULL,
  match_date                 TEXT,
  stage_name                 TEXT,
  group_name                 TEXT,
  team_id                    TEXT,
  team_name                  TEXT,
  team_code                  TEXT,
  player_id                  TEXT,
  minute_regulation          TEXT,
  minute_stoppage            TEXT,
  yellow_card                TEXT,
  red_card                   TEXT,
  second_yellow_card         TEXT,
  sending_off                TEXT,
  payload                    JSONB NOT NULL,
  ingested_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_fjelstul_wc_bookings PRIMARY KEY (source_version, key_id),
  CONSTRAINT chk_fjelstul_wc_bookings_source_name
    CHECK (source_name = 'fjelstul_worldcup')
);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_bookings_edition
  ON bronze.fjelstul_wc_bookings (edition_key);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_bookings_tournament
  ON bronze.fjelstul_wc_bookings (tournament_id);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_bookings_match_id
  ON bronze.fjelstul_wc_bookings (match_id);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_bookings_player_id
  ON bronze.fjelstul_wc_bookings (player_id);

CREATE TABLE IF NOT EXISTS bronze.fjelstul_wc_substitutions (
  source_name                TEXT NOT NULL,
  source_version             TEXT NOT NULL,
  edition_key                TEXT NOT NULL,
  snapshot_path              TEXT NOT NULL,
  snapshot_checksum_sha256   TEXT NOT NULL,
  source_file                TEXT NOT NULL,
  key_id                     TEXT NOT NULL,
  substitution_id            TEXT,
  tournament_id              TEXT NOT NULL,
  match_id                   TEXT NOT NULL,
  match_date                 TEXT,
  stage_name                 TEXT,
  group_name                 TEXT,
  team_id                    TEXT,
  team_name                  TEXT,
  team_code                  TEXT,
  player_id                  TEXT,
  minute_regulation          TEXT,
  minute_stoppage            TEXT,
  going_off                  TEXT,
  coming_on                  TEXT,
  payload                    JSONB NOT NULL,
  ingested_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_fjelstul_wc_substitutions PRIMARY KEY (source_version, key_id),
  CONSTRAINT chk_fjelstul_wc_substitutions_source_name
    CHECK (source_name = 'fjelstul_worldcup')
);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_substitutions_edition
  ON bronze.fjelstul_wc_substitutions (edition_key);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_substitutions_tournament
  ON bronze.fjelstul_wc_substitutions (tournament_id);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_substitutions_match_id
  ON bronze.fjelstul_wc_substitutions (match_id);

CREATE INDEX IF NOT EXISTS idx_fjelstul_wc_substitutions_player_id
  ON bronze.fjelstul_wc_substitutions (player_id);

-- migrate:down
SELECT 1;
