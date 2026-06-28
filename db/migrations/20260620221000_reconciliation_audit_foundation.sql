-- migrate:up
CREATE SCHEMA IF NOT EXISTS control;

ALTER TABLE control.brasileirao_fixture_xref
  ADD COLUMN IF NOT EXISTS match_method TEXT,
  ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS source_evidence JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE control.tm_game_fixture_xref
  ADD COLUMN IF NOT EXISTS match_method TEXT,
  ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS source_evidence JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE control.tm_player_xref
  ADD COLUMN IF NOT EXISTS match_method TEXT,
  ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS source_evidence JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_brasileirao_fixture_xref_review_status'
      AND conrelid = 'control.brasileirao_fixture_xref'::regclass
  ) THEN
    ALTER TABLE control.brasileirao_fixture_xref
      ADD CONSTRAINT chk_brasileirao_fixture_xref_review_status
      CHECK (review_status IN ('pending', 'auto_approved', 'manual_review', 'blocked', 'rejected'));
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_tm_game_fixture_xref_review_status'
      AND conrelid = 'control.tm_game_fixture_xref'::regclass
  ) THEN
    ALTER TABLE control.tm_game_fixture_xref
      ADD CONSTRAINT chk_tm_game_fixture_xref_review_status
      CHECK (review_status IN ('pending', 'auto_approved', 'manual_review', 'blocked', 'rejected'));
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_tm_player_xref_review_status'
      AND conrelid = 'control.tm_player_xref'::regclass
  ) THEN
    ALTER TABLE control.tm_player_xref
      ADD CONSTRAINT chk_tm_player_xref_review_status
      CHECK (review_status IN ('pending', 'auto_approved', 'manual_review', 'blocked', 'rejected'));
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS control.entity_reconciliation_review_queue (
  review_queue_id         BIGSERIAL PRIMARY KEY,
  entity_type             TEXT NOT NULL,
  source                  TEXT NOT NULL,
  source_entity_id        TEXT NOT NULL,
  candidate_canonical_id  BIGINT,
  candidate_competition_key TEXT,
  status                  TEXT NOT NULL DEFAULT 'pending',
  reason                  TEXT,
  source_label            TEXT,
  evidence                JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_entity_reconciliation_review_queue_entity_type
    CHECK (entity_type IN ('match', 'player', 'team', 'coach', 'competition', 'season')),
  CONSTRAINT chk_entity_reconciliation_review_queue_status
    CHECK (status IN ('pending', 'approved', 'rejected', 'blocked'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_reconciliation_review_queue_candidate
  ON control.entity_reconciliation_review_queue (
    entity_type,
    source,
    source_entity_id,
    COALESCE(candidate_canonical_id, -1)
  );

CREATE INDEX IF NOT EXISTS idx_entity_reconciliation_review_queue_status
  ON control.entity_reconciliation_review_queue (entity_type, status, source);

CREATE OR REPLACE VIEW control.v_match_reconciliation_audit AS
select
  'dataset_brasileirao'::text as source,
  brasileirao_match_id::text as source_entity_id,
  local_fixture_id as canonical_match_id,
  match_date,
  home_team_name_raw,
  away_team_name_raw,
  identity_status,
  confidence,
  coalesce(match_method, 'unspecified') as match_method,
  review_status,
  source_evidence,
  resolved_at,
  created_at,
  updated_at
from control.brasileirao_fixture_xref
union all
select
  'transfermarkt'::text as source,
  tm_game_id::text as source_entity_id,
  local_fixture_id as canonical_match_id,
  match_date,
  home_team_name_raw,
  away_team_name_raw,
  identity_status,
  confidence,
  coalesce(match_method, 'unspecified') as match_method,
  review_status,
  source_evidence,
  resolved_at,
  created_at,
  updated_at
from control.tm_game_fixture_xref
union all
select
  source_name as source,
  source_match_id::text as source_entity_id,
  local_match_id as canonical_match_id,
  match_date,
  source_home_team_name as home_team_name_raw,
  source_away_team_name as away_team_name_raw,
  identity_status,
  confidence,
  coalesce(resolution_reason, 'unspecified') as match_method,
  case
    when identity_status in ('linked_to_sportmonks', 'new_external_match') then 'auto_approved'
    when identity_status in ('ambiguous', 'manual_review', 'blocked') then 'manual_review'
    else 'pending'
  end as review_status,
  coalesce(evidence, '{}'::jsonb) as source_evidence,
  null::timestamptz as resolved_at,
  updated_at as created_at,
  updated_at
from mart.stg_statsbomb_match_identity;

CREATE OR REPLACE VIEW control.v_player_reconciliation_audit AS
select
  'transfermarkt'::text as source,
  tm_player_id::text as source_entity_id,
  local_player_id as canonical_player_id,
  player_name_raw,
  date_of_birth_raw,
  identity_status,
  confidence,
  coalesce(match_method, 'unspecified') as match_method,
  review_status,
  source_evidence,
  resolved_at,
  created_at,
  updated_at
from control.tm_player_xref
union all
select
  source_name as source,
  source_player_id::text as source_entity_id,
  local_player_id as canonical_player_id,
  source_player_name as player_name_raw,
  null::text as date_of_birth_raw,
  identity_status,
  confidence,
  coalesce(resolution_reason, 'unspecified') as match_method,
  case
    when identity_status = 'linked_to_sportmonks' then 'auto_approved'
    when identity_status in ('ambiguous', 'manual_review', 'blocked') then 'manual_review'
    else 'pending'
  end as review_status,
  coalesce(evidence, '{}'::jsonb) as source_evidence,
  null::timestamptz as resolved_at,
  updated_at as created_at,
  updated_at
from mart.stg_statsbomb_player_identity;

-- migrate:down
DROP VIEW IF EXISTS control.v_player_reconciliation_audit;
DROP VIEW IF EXISTS control.v_match_reconciliation_audit;
DROP INDEX IF EXISTS idx_entity_reconciliation_review_queue_status;
DROP INDEX IF EXISTS uq_entity_reconciliation_review_queue_candidate;
DROP TABLE IF EXISTS control.entity_reconciliation_review_queue;

ALTER TABLE control.tm_player_xref
  DROP CONSTRAINT IF EXISTS chk_tm_player_xref_review_status;
ALTER TABLE control.tm_game_fixture_xref
  DROP CONSTRAINT IF EXISTS chk_tm_game_fixture_xref_review_status;
ALTER TABLE control.brasileirao_fixture_xref
  DROP CONSTRAINT IF EXISTS chk_brasileirao_fixture_xref_review_status;

ALTER TABLE control.tm_player_xref
  DROP COLUMN IF EXISTS source_evidence,
  DROP COLUMN IF EXISTS review_status,
  DROP COLUMN IF EXISTS match_method;

ALTER TABLE control.tm_game_fixture_xref
  DROP COLUMN IF EXISTS source_evidence,
  DROP COLUMN IF EXISTS review_status,
  DROP COLUMN IF EXISTS match_method;

ALTER TABLE control.brasileirao_fixture_xref
  DROP COLUMN IF EXISTS source_evidence,
  DROP COLUMN IF EXISTS review_status,
  DROP COLUMN IF EXISTS match_method;
