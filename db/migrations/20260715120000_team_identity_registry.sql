-- migrate:up
CREATE SCHEMA IF NOT EXISTS control;

-- Keep the internal identity namespace disjoint from legacy/provider team IDs.
CREATE SEQUENCE IF NOT EXISTS control.team_identity_id_seq START WITH 2000000000000;

CREATE TABLE IF NOT EXISTS control.team_identity (
  canonical_team_id    BIGINT NOT NULL DEFAULT nextval('control.team_identity_id_seq'),
  team_name            TEXT NOT NULL,
  country_or_territory TEXT,
  team_type            TEXT NOT NULL DEFAULT 'club',
  gender               TEXT NOT NULL DEFAULT 'unknown',
  category             TEXT NOT NULL DEFAULT 'senior',
  identity_state       TEXT NOT NULL DEFAULT 'active',
  merged_into_team_id  BIGINT,
  decision_method      TEXT,
  decision_confidence  NUMERIC(5,4),
  decision_evidence    JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_team_identity PRIMARY KEY (canonical_team_id),
  CONSTRAINT fk_team_identity_merged_into
    FOREIGN KEY (merged_into_team_id) REFERENCES control.team_identity(canonical_team_id),
  CONSTRAINT chk_team_identity_type
    CHECK (team_type IN ('club', 'national_team', 'representative', 'other')),
  CONSTRAINT chk_team_identity_gender
    CHECK (gender IN ('male', 'female', 'mixed', 'unknown')),
  CONSTRAINT chk_team_identity_category
    CHECK (category IN ('senior', 'u20', 'u17', 'youth', 'reserve', 'unknown')),
  CONSTRAINT chk_team_identity_state
    CHECK (identity_state IN ('active', 'merged', 'retired')),
  CONSTRAINT chk_team_identity_merge_state
    CHECK (
      (identity_state = 'merged' and merged_into_team_id is not null)
      or (identity_state <> 'merged' and merged_into_team_id is null)
    ),
  CONSTRAINT chk_team_identity_not_self_merged
    CHECK (merged_into_team_id is null or merged_into_team_id <> canonical_team_id)
);

CREATE INDEX IF NOT EXISTS idx_team_identity_state
  ON control.team_identity (identity_state, merged_into_team_id);

-- No UNIQUE constraint is placed on team_name: homonyms are valid identities.
-- raw.provider_entity_map remains the only source-to-canonical crosswalk.

-- migrate:down
DROP TABLE IF EXISTS control.team_identity;
DROP SEQUENCE IF EXISTS control.team_identity_id_seq;
