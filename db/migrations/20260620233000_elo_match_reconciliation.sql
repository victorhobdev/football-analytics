-- migrate:up
CREATE SCHEMA IF NOT EXISTS control;

CREATE TABLE IF NOT EXISTS control.elo_match_xref (
  elo_match_hash          TEXT PRIMARY KEY,
  local_fixture_id        BIGINT,
  match_date              DATE,
  competition_key         TEXT,
  division                TEXT,
  home_team_name_raw      TEXT NOT NULL,
  away_team_name_raw      TEXT NOT NULL,
  identity_status         TEXT NOT NULL DEFAULT 'unmatched',
  confidence              NUMERIC(5,4),
  resolved_at             TIMESTAMPTZ,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  match_method            TEXT,
  review_status           TEXT NOT NULL DEFAULT 'pending',
  source_evidence         JSONB NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT chk_elo_match_xref_review_status
    CHECK (review_status IN ('pending', 'auto_approved', 'manual_review', 'blocked', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_elo_match_xref_status
  ON control.elo_match_xref (identity_status, review_status, competition_key, match_date);

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
  'eloratings'::text as source,
  elo_match_hash::text as source_entity_id,
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
from control.elo_match_xref
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

-- migrate:down
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

DROP TABLE IF EXISTS control.elo_match_xref;
