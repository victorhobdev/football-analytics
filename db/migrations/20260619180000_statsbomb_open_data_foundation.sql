-- migrate:up
CREATE SCHEMA IF NOT EXISTS control;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS mart;

CREATE TABLE IF NOT EXISTS control.external_data_sources (
  source_name            TEXT PRIMARY KEY,
  source_kind            TEXT NOT NULL,
  source_root            TEXT,
  license_summary        TEXT,
  attribution_required   BOOLEAN NOT NULL DEFAULT false,
  usage_scope            TEXT NOT NULL DEFAULT 'research',
  terms_summary          TEXT,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS control.external_file_manifest (
  source_name         TEXT NOT NULL,
  relative_path       TEXT NOT NULL,
  detected_entity     TEXT NOT NULL,
  provider_match_id   BIGINT,
  file_size_bytes     BIGINT NOT NULL,
  sha256              TEXT NOT NULL,
  load_status         TEXT NOT NULL,
  parse_error         TEXT,
  ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_external_file_manifest PRIMARY KEY (source_name, relative_path)
);

CREATE INDEX IF NOT EXISTS idx_external_file_manifest_entity
  ON control.external_file_manifest (source_name, detected_entity, load_status);

CREATE TABLE IF NOT EXISTS raw.statsbomb_competition_seasons (
  source_name               TEXT NOT NULL DEFAULT 'statsbomb_open_data',
  competition_id            BIGINT NOT NULL,
  season_id                 BIGINT NOT NULL,
  competition_name          TEXT NOT NULL,
  country_name              TEXT,
  competition_gender        TEXT,
  competition_youth         BOOLEAN,
  competition_international BOOLEAN,
  season_name               TEXT NOT NULL,
  match_updated             TIMESTAMPTZ,
  match_updated_360         TIMESTAMPTZ,
  match_available           TIMESTAMPTZ,
  match_available_360       TIMESTAMPTZ,
  payload                   JSONB NOT NULL,
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_statsbomb_competition_seasons PRIMARY KEY (source_name, competition_id, season_id)
);

CREATE TABLE IF NOT EXISTS raw.statsbomb_matches (
  source_name                TEXT NOT NULL DEFAULT 'statsbomb_open_data',
  match_id                   BIGINT NOT NULL,
  competition_id             BIGINT NOT NULL,
  season_id                  BIGINT NOT NULL,
  canonical_competition_key  TEXT,
  season_label               TEXT,
  match_date                 DATE,
  kick_off                   TEXT,
  home_team_id               BIGINT,
  home_team_name             TEXT,
  away_team_id               BIGINT,
  away_team_name             TEXT,
  home_score                 INTEGER,
  away_score                 INTEGER,
  match_status               TEXT,
  match_status_360           TEXT,
  competition_stage_id       BIGINT,
  competition_stage_name     TEXT,
  match_week                 INTEGER,
  stadium_id                 BIGINT,
  stadium_name               TEXT,
  referee_id                 BIGINT,
  referee_name               TEXT,
  local_match_id             BIGINT,
  identity_status            TEXT NOT NULL,
  identity_confidence        NUMERIC(5,4),
  identity_reason            TEXT,
  metadata                   JSONB NOT NULL DEFAULT '{}'::jsonb,
  payload                    JSONB NOT NULL,
  updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_statsbomb_matches PRIMARY KEY (source_name, match_id)
);

CREATE INDEX IF NOT EXISTS idx_statsbomb_matches_local_match
  ON raw.statsbomb_matches (local_match_id);

CREATE INDEX IF NOT EXISTS idx_statsbomb_matches_identity_status
  ON raw.statsbomb_matches (identity_status, canonical_competition_key, season_label);

CREATE TABLE IF NOT EXISTS raw.statsbomb_lineups (
  source_name             TEXT NOT NULL DEFAULT 'statsbomb_open_data',
  match_id                BIGINT NOT NULL,
  source_team_id          BIGINT NOT NULL,
  source_team_name        TEXT,
  source_player_id        BIGINT NOT NULL,
  source_player_name      TEXT,
  jersey_number           INTEGER,
  country_name            TEXT,
  local_match_id          BIGINT,
  local_team_id           BIGINT,
  local_player_id         BIGINT,
  match_identity_status   TEXT,
  player_identity_status  TEXT,
  player_identity_reason  TEXT,
  player_identity_confidence NUMERIC(5,4),
  payload                 JSONB NOT NULL,
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_statsbomb_lineups PRIMARY KEY (source_name, match_id, source_team_id, source_player_id)
);

CREATE INDEX IF NOT EXISTS idx_statsbomb_lineups_local_match_team
  ON raw.statsbomb_lineups (local_match_id, local_team_id);

CREATE INDEX IF NOT EXISTS idx_statsbomb_lineups_local_player
  ON raw.statsbomb_lineups (local_player_id);

CREATE TABLE IF NOT EXISTS raw.statsbomb_events (
  source_name             TEXT NOT NULL DEFAULT 'statsbomb_open_data',
  match_id                BIGINT NOT NULL,
  event_id                TEXT NOT NULL,
  event_index             INTEGER NOT NULL,
  period                  INTEGER,
  event_timestamp         TEXT,
  minute                  INTEGER,
  second                  NUMERIC,
  event_type              TEXT,
  possession              INTEGER,
  possession_team_id      BIGINT,
  possession_team_name    TEXT,
  play_pattern            TEXT,
  source_team_id          BIGINT,
  source_team_name        TEXT,
  source_player_id        BIGINT,
  source_player_name      TEXT,
  local_match_id          BIGINT,
  local_team_id           BIGINT,
  local_player_id         BIGINT,
  match_identity_status   TEXT,
  player_identity_status  TEXT,
  payload                 JSONB NOT NULL,
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_statsbomb_events PRIMARY KEY (source_name, match_id, event_id),
  CONSTRAINT uq_statsbomb_events_event_index UNIQUE (source_name, match_id, event_index)
);

CREATE INDEX IF NOT EXISTS idx_statsbomb_events_local_match
  ON raw.statsbomb_events (local_match_id);

CREATE INDEX IF NOT EXISTS idx_statsbomb_events_local_team
  ON raw.statsbomb_events (local_team_id);

CREATE INDEX IF NOT EXISTS idx_statsbomb_events_local_player
  ON raw.statsbomb_events (local_player_id);

CREATE INDEX IF NOT EXISTS idx_statsbomb_events_event_type
  ON raw.statsbomb_events (event_type);

CREATE TABLE IF NOT EXISTS raw.statsbomb_three_sixty_frames (
  source_name            TEXT NOT NULL DEFAULT 'statsbomb_open_data',
  match_id               BIGINT NOT NULL,
  event_uuid             TEXT NOT NULL,
  local_match_id         BIGINT,
  visible_area           JSONB,
  payload                JSONB NOT NULL,
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_statsbomb_three_sixty_frames PRIMARY KEY (source_name, match_id, event_uuid)
);

CREATE INDEX IF NOT EXISTS idx_statsbomb_three_sixty_frames_local_match
  ON raw.statsbomb_three_sixty_frames (local_match_id);

CREATE TABLE IF NOT EXISTS raw.statsbomb_three_sixty_freeze_frame (
  source_name         TEXT NOT NULL DEFAULT 'statsbomb_open_data',
  match_id            BIGINT NOT NULL,
  event_uuid          TEXT NOT NULL,
  freeze_frame_index  INTEGER NOT NULL,
  teammate            BOOLEAN,
  actor               BOOLEAN,
  keeper              BOOLEAN,
  location_x          NUMERIC,
  location_y          NUMERIC,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_statsbomb_three_sixty_freeze_frame PRIMARY KEY (source_name, match_id, event_uuid, freeze_frame_index)
);

CREATE INDEX IF NOT EXISTS idx_statsbomb_three_sixty_freeze_frame_match
  ON raw.statsbomb_three_sixty_freeze_frame (match_id, event_uuid);

CREATE TABLE IF NOT EXISTS raw.statsbomb_quarantine_events (
  source_name         TEXT NOT NULL DEFAULT 'statsbomb_open_data',
  match_id            BIGINT NOT NULL,
  event_id            TEXT NOT NULL,
  quarantine_reason   TEXT NOT NULL,
  payload             JSONB NOT NULL,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_statsbomb_quarantine_events PRIMARY KEY (source_name, match_id, event_id)
);

CREATE TABLE IF NOT EXISTS raw.statsbomb_quarantine_lineups (
  source_name         TEXT NOT NULL DEFAULT 'statsbomb_open_data',
  match_id            BIGINT NOT NULL,
  source_team_id      BIGINT NOT NULL,
  source_player_id    BIGINT NOT NULL,
  quarantine_reason   TEXT NOT NULL,
  payload             JSONB NOT NULL,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_statsbomb_quarantine_lineups PRIMARY KEY (source_name, match_id, source_team_id, source_player_id)
);

CREATE TABLE IF NOT EXISTS mart.stg_statsbomb_match_identity (
  source_name               TEXT NOT NULL DEFAULT 'statsbomb_open_data',
  source_match_id           BIGINT NOT NULL,
  canonical_competition_key TEXT,
  season_label              TEXT,
  match_date                DATE,
  source_home_team_id       BIGINT,
  source_home_team_name     TEXT,
  source_away_team_id       BIGINT,
  source_away_team_name     TEXT,
  source_home_score         INTEGER,
  source_away_score         INTEGER,
  identity_status           TEXT NOT NULL,
  confidence                NUMERIC(5,4),
  local_match_id            BIGINT,
  resolution_reason         TEXT,
  evidence                  JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_stg_statsbomb_match_identity PRIMARY KEY (source_name, source_match_id)
);

CREATE INDEX IF NOT EXISTS idx_stg_statsbomb_match_identity_local
  ON mart.stg_statsbomb_match_identity (local_match_id, identity_status);

CREATE TABLE IF NOT EXISTS mart.stg_statsbomb_team_identity (
  source_name               TEXT NOT NULL DEFAULT 'statsbomb_open_data',
  source_team_id            BIGINT NOT NULL,
  source_team_name          TEXT,
  identity_status           TEXT NOT NULL,
  confidence                NUMERIC(5,4),
  local_team_id             BIGINT,
  resolution_reason         TEXT,
  evidence                  JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_stg_statsbomb_team_identity PRIMARY KEY (source_name, source_team_id)
);

CREATE INDEX IF NOT EXISTS idx_stg_statsbomb_team_identity_local
  ON mart.stg_statsbomb_team_identity (local_team_id, identity_status);

CREATE TABLE IF NOT EXISTS mart.stg_statsbomb_player_identity (
  source_name               TEXT NOT NULL DEFAULT 'statsbomb_open_data',
  source_player_id          BIGINT NOT NULL,
  source_player_name        TEXT,
  identity_status           TEXT NOT NULL,
  confidence                NUMERIC(5,4),
  local_player_id           BIGINT,
  resolution_reason         TEXT,
  evidence                  JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_stg_statsbomb_player_identity PRIMARY KEY (source_name, source_player_id)
);

CREATE INDEX IF NOT EXISTS idx_stg_statsbomb_player_identity_local
  ON mart.stg_statsbomb_player_identity (local_player_id, identity_status);

-- migrate:down
DROP TABLE IF EXISTS mart.stg_statsbomb_player_identity;
DROP TABLE IF EXISTS mart.stg_statsbomb_team_identity;
DROP TABLE IF EXISTS mart.stg_statsbomb_match_identity;
DROP TABLE IF EXISTS raw.statsbomb_quarantine_lineups;
DROP TABLE IF EXISTS raw.statsbomb_quarantine_events;
DROP TABLE IF EXISTS raw.statsbomb_three_sixty_freeze_frame;
DROP TABLE IF EXISTS raw.statsbomb_three_sixty_frames;
DROP TABLE IF EXISTS raw.statsbomb_events;
DROP TABLE IF EXISTS raw.statsbomb_lineups;
DROP TABLE IF EXISTS raw.statsbomb_matches;
DROP TABLE IF EXISTS raw.statsbomb_competition_seasons;
DROP TABLE IF EXISTS control.external_file_manifest;
DROP TABLE IF EXISTS control.external_data_sources;
