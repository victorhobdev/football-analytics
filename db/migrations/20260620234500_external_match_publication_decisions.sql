-- migrate:up
CREATE SCHEMA IF NOT EXISTS control;

CREATE TABLE IF NOT EXISTS control.external_match_publication_xref (
  source                         TEXT NOT NULL,
  source_entity_id               TEXT NOT NULL,
  canonical_external_match_id    BIGINT,
  publication_status             TEXT NOT NULL,
  duplicate_of_source            TEXT,
  duplicate_of_source_entity_id  TEXT,
  competition_key                TEXT NOT NULL,
  match_date                     DATE NOT NULL,
  source_priority                INTEGER NOT NULL,
  match_method                   TEXT,
  source_evidence                JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (source, source_entity_id),
  CONSTRAINT chk_external_match_publication_status
    CHECK (publication_status IN ('publishable', 'suppressed_duplicate', 'blocked'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_external_match_publication_canonical
  ON control.external_match_publication_xref (canonical_external_match_id)
  WHERE publication_status = 'publishable';

CREATE INDEX IF NOT EXISTS idx_external_match_publication_scope
  ON control.external_match_publication_xref (competition_key, match_date, publication_status);

-- migrate:down
DROP TABLE IF EXISTS control.external_match_publication_xref;
