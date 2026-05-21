-- migrate:up
CREATE TABLE IF NOT EXISTS mart.stg_coach_sources (
  stg_coach_source_id BIGSERIAL PRIMARY KEY,
  source              TEXT NOT NULL,
  source_record_id    TEXT NOT NULL,
  provider            TEXT,
  provider_coach_id   BIGINT,
  team_id             BIGINT,
  role                TEXT,
  source_payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_updated_at   TIMESTAMPTZ,
  ingested_run        TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_stg_coach_sources UNIQUE (source, source_record_id)
);

CREATE TABLE IF NOT EXISTS mart.stg_coach_identity_candidates (
  stg_coach_identity_candidate_id BIGSERIAL PRIMARY KEY,
  source                          TEXT NOT NULL,
  source_record_id                TEXT NOT NULL,
  provider                        TEXT,
  provider_coach_id               BIGINT,
  coach_name                      TEXT,
  display_name_candidate          TEXT,
  aliases                         JSONB NOT NULL DEFAULT '[]'::jsonb,
  image_url                       TEXT,
  source_confidence               NUMERIC(5,4),
  source_payload                  JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_updated_at               TIMESTAMPTZ,
  ingested_run                    TEXT,
  created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_stg_coach_identity_candidates UNIQUE (source, source_record_id)
);

CREATE TABLE IF NOT EXISTS mart.stg_coach_tenures (
  stg_coach_tenure_id     BIGSERIAL PRIMARY KEY,
  source                  TEXT NOT NULL,
  source_record_id        TEXT NOT NULL,
  provider                TEXT,
  provider_coach_id       BIGINT,
  team_id                 BIGINT NOT NULL,
  role                    TEXT NOT NULL,
  start_date              DATE,
  end_date                DATE,
  is_date_estimated       BOOLEAN NOT NULL DEFAULT false,
  is_current_as_of_source BOOLEAN NOT NULL DEFAULT false,
  source_confidence       NUMERIC(5,4),
  source_payload          JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_updated_at       TIMESTAMPTZ,
  ingested_run            TEXT,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_stg_coach_tenures UNIQUE (source, source_record_id)
);

CREATE TABLE IF NOT EXISTS mart.stg_coach_lineup_assignments (
  stg_coach_lineup_assignment_id BIGSERIAL PRIMARY KEY,
  source                         TEXT NOT NULL,
  source_record_id               TEXT NOT NULL,
  match_id                       BIGINT NOT NULL,
  team_id                        BIGINT NOT NULL,
  provider                       TEXT,
  provider_coach_id              BIGINT,
  role                           TEXT NOT NULL,
  assignment_method              TEXT,
  source_confidence              NUMERIC(5,4),
  source_payload                 JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_updated_at              TIMESTAMPTZ,
  ingested_run                   TEXT,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_stg_coach_lineup_assignments UNIQUE (source, source_record_id)
);

CREATE TABLE IF NOT EXISTS mart.coach_identity (
  coach_identity_id   BIGSERIAL PRIMARY KEY,
  provider            TEXT NOT NULL,
  provider_coach_id   BIGINT NOT NULL,
  canonical_name      TEXT,
  display_name        TEXT,
  aliases             JSONB NOT NULL DEFAULT '[]'::jsonb,
  image_url           TEXT,
  identity_confidence NUMERIC(5,4),
  source_refs         JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_coach_identity_provider UNIQUE (provider, provider_coach_id)
);

CREATE TABLE IF NOT EXISTS mart.coach_tenure (
  coach_tenure_id         BIGSERIAL PRIMARY KEY,
  coach_identity_id       BIGINT NOT NULL REFERENCES mart.coach_identity(coach_identity_id),
  team_id                 BIGINT NOT NULL,
  role                    TEXT NOT NULL,
  start_date              DATE,
  end_date                DATE,
  source                  TEXT NOT NULL,
  source_confidence       NUMERIC(5,4),
  is_date_estimated       BOOLEAN NOT NULL DEFAULT false,
  is_current_as_of_source BOOLEAN NOT NULL DEFAULT false,
  source_updated_at       TIMESTAMPTZ,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_coach_tenure_role CHECK (role IN ('head_coach', 'interim_head_coach', 'assistant', 'unknown')),
  CONSTRAINT uq_coach_tenure_natural UNIQUE (coach_identity_id, team_id, role, start_date, source)
);

CREATE TABLE IF NOT EXISTS mart.fact_coach_match_assignment (
  match_id               BIGINT NOT NULL,
  team_id                BIGINT NOT NULL,
  coach_identity_id      BIGINT REFERENCES mart.coach_identity(coach_identity_id),
  coach_tenure_id        BIGINT REFERENCES mart.coach_tenure(coach_tenure_id),
  assignment_method      TEXT NOT NULL,
  assignment_confidence  NUMERIC(5,4),
  conflict_reason        TEXT,
  is_public_eligible     BOOLEAN NOT NULL DEFAULT false,
  source                 TEXT,
  source_record_id       TEXT,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_fact_coach_match_assignment PRIMARY KEY (match_id, team_id),
  CONSTRAINT ck_fact_coach_match_assignment_method CHECK (
    assignment_method IN (
      'lineup_source',
      'single_head_coach_tenure',
      'interim_head_coach_tenure',
      'manual_override',
      'inferred_low_confidence',
      'blocked_conflict'
    )
  )
);

CREATE INDEX IF NOT EXISTS idx_stg_coach_identity_candidates_provider
  ON mart.stg_coach_identity_candidates (provider, provider_coach_id);

CREATE INDEX IF NOT EXISTS idx_stg_coach_tenures_provider_team
  ON mart.stg_coach_tenures (provider, provider_coach_id, team_id);

CREATE INDEX IF NOT EXISTS idx_stg_coach_lineup_assignments_match_team
  ON mart.stg_coach_lineup_assignments (match_id, team_id);

CREATE INDEX IF NOT EXISTS idx_coach_tenure_team_dates
  ON mart.coach_tenure (team_id, start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_fact_coach_match_assignment_coach
  ON mart.fact_coach_match_assignment (coach_identity_id, is_public_eligible);

-- migrate:down
DROP TABLE IF EXISTS mart.fact_coach_match_assignment;
DROP TABLE IF EXISTS mart.coach_tenure;
DROP TABLE IF EXISTS mart.coach_identity;
DROP TABLE IF EXISTS mart.stg_coach_lineup_assignments;
DROP TABLE IF EXISTS mart.stg_coach_tenures;
DROP TABLE IF EXISTS mart.stg_coach_identity_candidates;
DROP TABLE IF EXISTS mart.stg_coach_sources;
