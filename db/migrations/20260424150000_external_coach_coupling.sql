-- migrate:up
CREATE TABLE IF NOT EXISTS raw.external_coach_source_facts (
  source               TEXT NOT NULL,
  source_record_id     TEXT NOT NULL,
  source_url           TEXT,
  external_person_id   TEXT,
  external_team_id     TEXT,
  coach_name           TEXT,
  team_name            TEXT,
  source_role          TEXT,
  start_date_original  DATE,
  end_date_original    DATE,
  source_confidence    NUMERIC(5,4),
  payload              JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingested_run         TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_external_coach_source_facts PRIMARY KEY (source, source_record_id)
);

CREATE TABLE IF NOT EXISTS mart.coach_identity_source_ref (
  coach_identity_source_ref_id BIGSERIAL PRIMARY KEY,
  coach_identity_id            BIGINT NOT NULL REFERENCES mart.coach_identity(coach_identity_id),
  source                       TEXT NOT NULL,
  external_person_id           TEXT NOT NULL,
  external_person_url          TEXT,
  confidence                   NUMERIC(5,4),
  payload                      JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_coach_identity_source_ref UNIQUE (source, external_person_id)
);

CREATE TABLE IF NOT EXISTS mart.stg_external_coach_candidate_resolution (
  source                              TEXT NOT NULL,
  source_record_id                    TEXT NOT NULL,
  source_url                          TEXT,
  external_person_id                  TEXT,
  external_team_id                    TEXT,
  team_id                             BIGINT,
  local_team_name                     TEXT,
  team_match_method                   TEXT,
  team_match_score                    NUMERIC(5,4),
  coach_identity_id                   BIGINT REFERENCES mart.coach_identity(coach_identity_id),
  identity_match_method               TEXT,
  identity_match_score                NUMERIC(5,4),
  candidate_coach_key                 TEXT,
  coach_name                          TEXT,
  coach_name_normalized               TEXT,
  team_name                           TEXT,
  source_role                         TEXT,
  role_candidate                      TEXT NOT NULL,
  start_date_original                 DATE,
  end_date_original                   DATE,
  clipped_start_date                  DATE,
  clipped_end_date                    DATE,
  is_date_estimated                   BOOLEAN NOT NULL DEFAULT false,
  source_tier                         TEXT NOT NULL,
  source_confidence                   NUMERIC(5,4),
  candidate_confidence                NUMERIC(5,4),
  canonical_missing_matches_covered   INTEGER NOT NULL DEFAULT 0,
  canonical_assigned_matches_covered  INTEGER NOT NULL DEFAULT 0,
  existing_same_coach_overlap_matches INTEGER NOT NULL DEFAULT 0,
  best_existing_coach_similarity      NUMERIC(5,4),
  classification                      TEXT NOT NULL,
  block_reason                        TEXT,
  payload                             JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingested_run                        TEXT,
  created_at                          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_stg_external_coach_candidate_resolution PRIMARY KEY (source, source_record_id)
);

CREATE TABLE IF NOT EXISTS mart.stg_external_coach_assignment_candidates (
  source                         TEXT NOT NULL,
  source_record_id               TEXT NOT NULL,
  match_id                       BIGINT NOT NULL,
  team_id                        BIGINT NOT NULL,
  source_url                     TEXT,
  external_person_id             TEXT,
  coach_identity_id              BIGINT REFERENCES mart.coach_identity(coach_identity_id),
  candidate_coach_key            TEXT,
  coach_name                     TEXT,
  role_candidate                 TEXT NOT NULL,
  assignment_method              TEXT NOT NULL,
  assignment_confidence          NUMERIC(5,4),
  match_date                     DATE NOT NULL,
  competition_key                TEXT,
  season                         INTEGER,
  is_existing_public_assignment  BOOLEAN NOT NULL DEFAULT false,
  existing_coach_identity_id     BIGINT,
  existing_coach_name            TEXT,
  conflict_candidate_count       INTEGER NOT NULL DEFAULT 0,
  promotion_status               TEXT NOT NULL,
  block_reason                   TEXT,
  payload                        JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingested_run                   TEXT,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_stg_external_coach_assignment_candidates PRIMARY KEY (source, source_record_id, match_id, team_id)
);

CREATE INDEX IF NOT EXISTS idx_external_coach_source_facts_person
  ON raw.external_coach_source_facts (external_person_id);

CREATE INDEX IF NOT EXISTS idx_external_coach_source_facts_team
  ON raw.external_coach_source_facts (external_team_id);

CREATE INDEX IF NOT EXISTS idx_stg_external_coach_candidate_resolution_team
  ON mart.stg_external_coach_candidate_resolution (team_id, clipped_start_date, clipped_end_date);

CREATE INDEX IF NOT EXISTS idx_stg_external_coach_candidate_resolution_class
  ON mart.stg_external_coach_candidate_resolution (classification, source_tier);

CREATE INDEX IF NOT EXISTS idx_stg_external_coach_assignment_candidates_match_team
  ON mart.stg_external_coach_assignment_candidates (match_id, team_id, promotion_status);

CREATE INDEX IF NOT EXISTS idx_stg_external_coach_assignment_candidates_team_date
  ON mart.stg_external_coach_assignment_candidates (team_id, match_date);

-- migrate:down
DROP TABLE IF EXISTS mart.stg_external_coach_assignment_candidates;
DROP TABLE IF EXISTS mart.stg_external_coach_candidate_resolution;
DROP TABLE IF EXISTS mart.coach_identity_source_ref;
DROP TABLE IF EXISTS raw.external_coach_source_facts;
