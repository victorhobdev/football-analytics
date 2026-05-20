-- migrate:up
-- Copa do Mundo | Dominios adicionais Fjelstul
-- Foundation para squads/rosters e registries discretos de goals, bookings e substitutions.

CREATE TABLE IF NOT EXISTS silver.wc_squads (
  edition_key         TEXT NOT NULL,
  team_internal_id    TEXT NOT NULL,
  player_internal_id  TEXT NOT NULL,
  source_name         TEXT NOT NULL,
  source_version      TEXT NOT NULL,
  source_row_id       TEXT NOT NULL,
  source_team_id      TEXT NOT NULL,
  source_player_id    TEXT NOT NULL,
  team_name           TEXT NOT NULL,
  team_code           TEXT NOT NULL,
  player_name         TEXT NOT NULL,
  jersey_number       INTEGER,
  position_name       TEXT,
  position_code       TEXT,
  payload             JSONB NOT NULL,
  materialized_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_wc_squads PRIMARY KEY (edition_key, team_internal_id, player_internal_id, source_name),
  CONSTRAINT uq_wc_squads_source_row UNIQUE (source_name, edition_key, source_row_id),
  CONSTRAINT chk_wc_squads_source_name
    CHECK (source_name = 'fjelstul_worldcup')
);

CREATE INDEX IF NOT EXISTS idx_wc_squads_team
  ON silver.wc_squads (edition_key, team_internal_id);

CREATE INDEX IF NOT EXISTS idx_wc_squads_player
  ON silver.wc_squads (player_internal_id);

CREATE TABLE IF NOT EXISTS silver.wc_goals (
  edition_key               TEXT NOT NULL,
  internal_match_id         TEXT NOT NULL,
  team_internal_id          TEXT NOT NULL,
  player_internal_id        TEXT NOT NULL,
  player_team_internal_id   TEXT NOT NULL,
  source_name               TEXT NOT NULL,
  source_version            TEXT NOT NULL,
  source_match_id           TEXT NOT NULL,
  source_goal_id            TEXT NOT NULL,
  source_team_id            TEXT NOT NULL,
  source_player_id          TEXT NOT NULL,
  source_player_team_id     TEXT NOT NULL,
  team_name                 TEXT NOT NULL,
  team_code                 TEXT NOT NULL,
  player_name               TEXT NOT NULL,
  player_team_name          TEXT NOT NULL,
  player_team_code          TEXT NOT NULL,
  minute_regulation         INTEGER,
  minute_stoppage           INTEGER,
  match_period              TEXT,
  minute_label              TEXT,
  is_penalty                BOOLEAN NOT NULL DEFAULT FALSE,
  is_own_goal               BOOLEAN NOT NULL DEFAULT FALSE,
  payload                   JSONB NOT NULL,
  materialized_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_wc_goals PRIMARY KEY (source_name, edition_key, source_goal_id),
  CONSTRAINT uq_wc_goals_match_goal UNIQUE (edition_key, internal_match_id, source_goal_id),
  CONSTRAINT chk_wc_goals_source_name
    CHECK (source_name = 'fjelstul_worldcup')
);

CREATE INDEX IF NOT EXISTS idx_wc_goals_match
  ON silver.wc_goals (edition_key, internal_match_id);

CREATE INDEX IF NOT EXISTS idx_wc_goals_team
  ON silver.wc_goals (team_internal_id);

CREATE INDEX IF NOT EXISTS idx_wc_goals_player
  ON silver.wc_goals (player_internal_id);

CREATE TABLE IF NOT EXISTS silver.wc_bookings (
  edition_key               TEXT NOT NULL,
  internal_match_id         TEXT NOT NULL,
  team_internal_id          TEXT NOT NULL,
  player_internal_id        TEXT NOT NULL,
  source_name               TEXT NOT NULL,
  source_version            TEXT NOT NULL,
  source_match_id           TEXT NOT NULL,
  source_booking_id         TEXT NOT NULL,
  source_team_id            TEXT NOT NULL,
  source_player_id          TEXT NOT NULL,
  team_name                 TEXT NOT NULL,
  team_code                 TEXT NOT NULL,
  player_name               TEXT NOT NULL,
  minute_regulation         INTEGER,
  minute_stoppage           INTEGER,
  match_period              TEXT,
  minute_label              TEXT,
  is_yellow_card            BOOLEAN NOT NULL DEFAULT FALSE,
  is_red_card               BOOLEAN NOT NULL DEFAULT FALSE,
  is_second_yellow_card     BOOLEAN NOT NULL DEFAULT FALSE,
  is_sending_off            BOOLEAN NOT NULL DEFAULT FALSE,
  payload                   JSONB NOT NULL,
  materialized_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_wc_bookings PRIMARY KEY (source_name, edition_key, source_booking_id),
  CONSTRAINT uq_wc_bookings_match_booking UNIQUE (edition_key, internal_match_id, source_booking_id),
  CONSTRAINT chk_wc_bookings_source_name
    CHECK (source_name = 'fjelstul_worldcup')
);

CREATE INDEX IF NOT EXISTS idx_wc_bookings_match
  ON silver.wc_bookings (edition_key, internal_match_id);

CREATE INDEX IF NOT EXISTS idx_wc_bookings_team
  ON silver.wc_bookings (team_internal_id);

CREATE INDEX IF NOT EXISTS idx_wc_bookings_player
  ON silver.wc_bookings (player_internal_id);

CREATE TABLE IF NOT EXISTS silver.wc_substitutions (
  edition_key               TEXT NOT NULL,
  internal_match_id         TEXT NOT NULL,
  team_internal_id          TEXT NOT NULL,
  player_internal_id        TEXT NOT NULL,
  source_name               TEXT NOT NULL,
  source_version            TEXT NOT NULL,
  source_match_id           TEXT NOT NULL,
  source_substitution_id    TEXT NOT NULL,
  source_team_id            TEXT NOT NULL,
  source_player_id          TEXT NOT NULL,
  team_name                 TEXT NOT NULL,
  team_code                 TEXT NOT NULL,
  player_name               TEXT NOT NULL,
  minute_regulation         INTEGER,
  minute_stoppage           INTEGER,
  match_period              TEXT,
  minute_label              TEXT,
  is_going_off              BOOLEAN NOT NULL DEFAULT FALSE,
  is_coming_on              BOOLEAN NOT NULL DEFAULT FALSE,
  substitution_role         TEXT NOT NULL,
  payload                   JSONB NOT NULL,
  materialized_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_wc_substitutions PRIMARY KEY (source_name, edition_key, source_substitution_id),
  CONSTRAINT uq_wc_substitutions_match_substitution UNIQUE (edition_key, internal_match_id, source_substitution_id),
  CONSTRAINT chk_wc_substitutions_source_name
    CHECK (source_name = 'fjelstul_worldcup'),
  CONSTRAINT chk_wc_substitutions_role
    CHECK (substitution_role IN ('going_off', 'coming_on')),
  CONSTRAINT chk_wc_substitutions_flags
    CHECK (
      (CASE WHEN is_going_off THEN 1 ELSE 0 END) +
      (CASE WHEN is_coming_on THEN 1 ELSE 0 END) = 1
    )
);

CREATE INDEX IF NOT EXISTS idx_wc_substitutions_match
  ON silver.wc_substitutions (edition_key, internal_match_id);

CREATE INDEX IF NOT EXISTS idx_wc_substitutions_team
  ON silver.wc_substitutions (team_internal_id);

CREATE INDEX IF NOT EXISTS idx_wc_substitutions_player
  ON silver.wc_substitutions (player_internal_id);

CREATE TABLE IF NOT EXISTS raw.wc_squads (
  wc_squad_pk          BIGSERIAL PRIMARY KEY,
  edition_key          TEXT NOT NULL,
  provider             TEXT NOT NULL,
  competition_key      TEXT NOT NULL,
  season_label         TEXT NOT NULL,
  source_name          TEXT NOT NULL,
  source_version       TEXT NOT NULL,
  source_row_id        TEXT NOT NULL,
  source_team_id       TEXT NOT NULL,
  source_player_id     TEXT NOT NULL,
  team_internal_id     TEXT NOT NULL,
  player_internal_id   TEXT NOT NULL,
  team_id              BIGINT NOT NULL,
  player_id            BIGINT NOT NULL,
  team_name            TEXT NOT NULL,
  team_code            TEXT NOT NULL,
  player_name          TEXT NOT NULL,
  jersey_number        INTEGER,
  position_name        TEXT,
  position_code        TEXT,
  payload              JSONB NOT NULL,
  source_run_id        TEXT,
  ingested_run         TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_wc_squads_source_row
    UNIQUE (source_name, edition_key, source_row_id),
  CONSTRAINT uq_wc_squads_player
    UNIQUE (edition_key, team_internal_id, player_internal_id, source_name),
  CONSTRAINT chk_wc_squads_source_name_raw
    CHECK (source_name = 'fjelstul_worldcup'),
  CONSTRAINT chk_wc_squads_competition_key
    CHECK (competition_key = 'fifa_world_cup_mens')
);

CREATE INDEX IF NOT EXISTS idx_raw_wc_squads_edition
  ON raw.wc_squads (edition_key);

CREATE INDEX IF NOT EXISTS idx_raw_wc_squads_team
  ON raw.wc_squads (team_id);

CREATE INDEX IF NOT EXISTS idx_raw_wc_squads_player
  ON raw.wc_squads (player_id);

CREATE TABLE IF NOT EXISTS raw.wc_goals (
  wc_goal_pk                BIGSERIAL PRIMARY KEY,
  fixture_id                BIGINT NOT NULL,
  internal_match_id         TEXT NOT NULL,
  edition_key               TEXT NOT NULL,
  provider                  TEXT NOT NULL,
  competition_key           TEXT NOT NULL,
  season_label              TEXT NOT NULL,
  source_name               TEXT NOT NULL,
  source_version            TEXT NOT NULL,
  source_match_id           TEXT NOT NULL,
  source_goal_id            TEXT NOT NULL,
  source_team_id            TEXT NOT NULL,
  source_player_id          TEXT NOT NULL,
  source_player_team_id     TEXT NOT NULL,
  team_internal_id          TEXT NOT NULL,
  player_internal_id        TEXT NOT NULL,
  player_team_internal_id   TEXT NOT NULL,
  team_id                   BIGINT NOT NULL,
  player_id                 BIGINT NOT NULL,
  player_team_id            BIGINT NOT NULL,
  team_name                 TEXT NOT NULL,
  player_name               TEXT NOT NULL,
  player_team_name          TEXT NOT NULL,
  minute_regulation         INTEGER,
  minute_stoppage           INTEGER,
  match_period              TEXT,
  minute_label              TEXT,
  is_penalty                BOOLEAN NOT NULL DEFAULT FALSE,
  is_own_goal               BOOLEAN NOT NULL DEFAULT FALSE,
  payload                   JSONB NOT NULL,
  source_run_id             TEXT,
  ingested_run              TEXT,
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_wc_goals_source_goal
    UNIQUE (source_name, edition_key, source_goal_id),
  CONSTRAINT chk_wc_goals_source_name_raw
    CHECK (source_name = 'fjelstul_worldcup'),
  CONSTRAINT chk_wc_goals_competition_key
    CHECK (competition_key = 'fifa_world_cup_mens')
);

CREATE INDEX IF NOT EXISTS idx_raw_wc_goals_fixture
  ON raw.wc_goals (fixture_id);

CREATE INDEX IF NOT EXISTS idx_raw_wc_goals_edition
  ON raw.wc_goals (edition_key);

CREATE INDEX IF NOT EXISTS idx_raw_wc_goals_team
  ON raw.wc_goals (team_id);

CREATE INDEX IF NOT EXISTS idx_raw_wc_goals_player
  ON raw.wc_goals (player_id);

CREATE TABLE IF NOT EXISTS raw.wc_bookings (
  wc_booking_pk             BIGSERIAL PRIMARY KEY,
  fixture_id                BIGINT NOT NULL,
  internal_match_id         TEXT NOT NULL,
  edition_key               TEXT NOT NULL,
  provider                  TEXT NOT NULL,
  competition_key           TEXT NOT NULL,
  season_label              TEXT NOT NULL,
  source_name               TEXT NOT NULL,
  source_version            TEXT NOT NULL,
  source_match_id           TEXT NOT NULL,
  source_booking_id         TEXT NOT NULL,
  source_team_id            TEXT NOT NULL,
  source_player_id          TEXT NOT NULL,
  team_internal_id          TEXT NOT NULL,
  player_internal_id        TEXT NOT NULL,
  team_id                   BIGINT NOT NULL,
  player_id                 BIGINT NOT NULL,
  team_name                 TEXT NOT NULL,
  player_name               TEXT NOT NULL,
  minute_regulation         INTEGER,
  minute_stoppage           INTEGER,
  match_period              TEXT,
  minute_label              TEXT,
  is_yellow_card            BOOLEAN NOT NULL DEFAULT FALSE,
  is_red_card               BOOLEAN NOT NULL DEFAULT FALSE,
  is_second_yellow_card     BOOLEAN NOT NULL DEFAULT FALSE,
  is_sending_off            BOOLEAN NOT NULL DEFAULT FALSE,
  payload                   JSONB NOT NULL,
  source_run_id             TEXT,
  ingested_run              TEXT,
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_wc_bookings_source_booking
    UNIQUE (source_name, edition_key, source_booking_id),
  CONSTRAINT chk_wc_bookings_source_name_raw
    CHECK (source_name = 'fjelstul_worldcup'),
  CONSTRAINT chk_wc_bookings_competition_key
    CHECK (competition_key = 'fifa_world_cup_mens')
);

CREATE INDEX IF NOT EXISTS idx_raw_wc_bookings_fixture
  ON raw.wc_bookings (fixture_id);

CREATE INDEX IF NOT EXISTS idx_raw_wc_bookings_edition
  ON raw.wc_bookings (edition_key);

CREATE INDEX IF NOT EXISTS idx_raw_wc_bookings_team
  ON raw.wc_bookings (team_id);

CREATE INDEX IF NOT EXISTS idx_raw_wc_bookings_player
  ON raw.wc_bookings (player_id);

CREATE TABLE IF NOT EXISTS raw.wc_substitutions (
  wc_substitution_pk        BIGSERIAL PRIMARY KEY,
  fixture_id                BIGINT NOT NULL,
  internal_match_id         TEXT NOT NULL,
  edition_key               TEXT NOT NULL,
  provider                  TEXT NOT NULL,
  competition_key           TEXT NOT NULL,
  season_label              TEXT NOT NULL,
  source_name               TEXT NOT NULL,
  source_version            TEXT NOT NULL,
  source_match_id           TEXT NOT NULL,
  source_substitution_id    TEXT NOT NULL,
  source_team_id            TEXT NOT NULL,
  source_player_id          TEXT NOT NULL,
  team_internal_id          TEXT NOT NULL,
  player_internal_id        TEXT NOT NULL,
  team_id                   BIGINT NOT NULL,
  player_id                 BIGINT NOT NULL,
  team_name                 TEXT NOT NULL,
  player_name               TEXT NOT NULL,
  minute_regulation         INTEGER,
  minute_stoppage           INTEGER,
  match_period              TEXT,
  minute_label              TEXT,
  is_going_off              BOOLEAN NOT NULL DEFAULT FALSE,
  is_coming_on              BOOLEAN NOT NULL DEFAULT FALSE,
  substitution_role         TEXT NOT NULL,
  payload                   JSONB NOT NULL,
  source_run_id             TEXT,
  ingested_run              TEXT,
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_wc_substitutions_source_substitution
    UNIQUE (source_name, edition_key, source_substitution_id),
  CONSTRAINT chk_wc_substitutions_source_name_raw
    CHECK (source_name = 'fjelstul_worldcup'),
  CONSTRAINT chk_wc_substitutions_competition_key
    CHECK (competition_key = 'fifa_world_cup_mens'),
  CONSTRAINT chk_wc_substitutions_role_raw
    CHECK (substitution_role IN ('going_off', 'coming_on')),
  CONSTRAINT chk_wc_substitutions_flags_raw
    CHECK (
      (CASE WHEN is_going_off THEN 1 ELSE 0 END) +
      (CASE WHEN is_coming_on THEN 1 ELSE 0 END) = 1
    )
);

CREATE INDEX IF NOT EXISTS idx_raw_wc_substitutions_fixture
  ON raw.wc_substitutions (fixture_id);

CREATE INDEX IF NOT EXISTS idx_raw_wc_substitutions_edition
  ON raw.wc_substitutions (edition_key);

CREATE INDEX IF NOT EXISTS idx_raw_wc_substitutions_team
  ON raw.wc_substitutions (team_id);

CREATE INDEX IF NOT EXISTS idx_raw_wc_substitutions_player
  ON raw.wc_substitutions (player_id);

-- migrate:down
SELECT 1;
