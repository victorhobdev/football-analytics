-- migrate:up
CREATE TABLE IF NOT EXISTS raw.sportmonks_coaches (
  provider        TEXT NOT NULL DEFAULT 'sportmonks',
  coach_id        BIGINT NOT NULL,
  coach_name      TEXT,
  display_name    TEXT,
  common_name     TEXT,
  firstname       TEXT,
  lastname        TEXT,
  image_path      TEXT,
  payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingested_run    TEXT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_sportmonks_coaches PRIMARY KEY (provider, coach_id)
);

CREATE TABLE IF NOT EXISTS raw.sportmonks_fixture_coaches (
  provider        TEXT NOT NULL DEFAULT 'sportmonks',
  fixture_id      BIGINT NOT NULL,
  team_id         BIGINT NOT NULL,
  coach_id        BIGINT NOT NULL,
  fixture_date    DATE,
  league_id       BIGINT,
  season_id       BIGINT,
  state_id        BIGINT,
  coach_payload   JSONB NOT NULL DEFAULT '{}'::jsonb,
  fixture_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingested_run    TEXT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_sportmonks_fixture_coaches PRIMARY KEY (provider, fixture_id, team_id, coach_id)
);

CREATE TABLE IF NOT EXISTS raw.sportmonks_transfer_events (
  provider        TEXT NOT NULL DEFAULT 'sportmonks',
  transfer_id     BIGINT NOT NULL,
  player_id       BIGINT NOT NULL,
  from_team_id    BIGINT,
  to_team_id      BIGINT,
  transfer_date   DATE,
  completed       BOOLEAN,
  career_ended    BOOLEAN,
  type_id         BIGINT,
  position_id     BIGINT,
  amount          TEXT,
  payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingested_run    TEXT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_sportmonks_transfer_events PRIMARY KEY (provider, transfer_id)
);

CREATE TABLE IF NOT EXISTS mart.stg_sportmonks_fixture_coach_assignments (
  provider                  TEXT NOT NULL DEFAULT 'sportmonks',
  fixture_id                BIGINT NOT NULL,
  local_match_id            BIGINT,
  provider_team_id          BIGINT NOT NULL,
  team_id                   BIGINT,
  provider_coach_id         BIGINT NOT NULL,
  coach_name                TEXT,
  display_name              TEXT,
  fixture_date              DATE,
  assignment_method         TEXT NOT NULL,
  source_confidence         NUMERIC(5,4),
  is_local_match            BOOLEAN NOT NULL DEFAULT false,
  is_public_cutoff_eligible BOOLEAN NOT NULL DEFAULT false,
  source_payload            JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingested_run              TEXT,
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_stg_sportmonks_fixture_coach_assignments PRIMARY KEY (provider, fixture_id, provider_team_id, provider_coach_id)
);

CREATE TABLE IF NOT EXISTS mart.stg_sportmonks_transfer_events (
  provider        TEXT NOT NULL DEFAULT 'sportmonks',
  transfer_id     BIGINT NOT NULL,
  player_id       BIGINT NOT NULL,
  player_name     TEXT,
  from_team_id    BIGINT,
  from_team_name  TEXT,
  to_team_id      BIGINT,
  to_team_name    TEXT,
  transfer_date   DATE,
  completed       BOOLEAN,
  career_ended    BOOLEAN,
  type_id         BIGINT,
  type_name       TEXT,
  position_id     BIGINT,
  amount          TEXT,
  payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingested_run    TEXT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_stg_sportmonks_transfer_events PRIMARY KEY (provider, transfer_id)
);

CREATE INDEX IF NOT EXISTS idx_sportmonks_fixture_coaches_fixture_team
  ON raw.sportmonks_fixture_coaches (fixture_id, team_id);

CREATE INDEX IF NOT EXISTS idx_stg_sportmonks_fixture_coach_assignments_local
  ON mart.stg_sportmonks_fixture_coach_assignments (local_match_id, team_id, is_public_cutoff_eligible);

CREATE INDEX IF NOT EXISTS idx_sportmonks_transfer_events_date
  ON raw.sportmonks_transfer_events (transfer_date);

CREATE INDEX IF NOT EXISTS idx_stg_sportmonks_transfer_events_player
  ON mart.stg_sportmonks_transfer_events (player_id);

-- migrate:down
DROP TABLE IF EXISTS mart.stg_sportmonks_transfer_events;
DROP TABLE IF EXISTS mart.stg_sportmonks_fixture_coach_assignments;
DROP TABLE IF EXISTS raw.sportmonks_transfer_events;
DROP TABLE IF EXISTS raw.sportmonks_fixture_coaches;
DROP TABLE IF EXISTS raw.sportmonks_coaches;
