-- migrate:up
CREATE TABLE IF NOT EXISTS raw.provider_entity_map (
  provider      TEXT NOT NULL,
  entity_type   TEXT NOT NULL,
  source_id     TEXT NOT NULL,
  canonical_id  TEXT NOT NULL,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_provider_entity_map PRIMARY KEY (provider, entity_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_provider_entity_map_canonical_id
  ON raw.provider_entity_map (canonical_id);

CREATE TABLE IF NOT EXISTS raw.provider_sync_state (
  provider                 TEXT NOT NULL,
  entity_type              TEXT NOT NULL,
  scope_key                TEXT NOT NULL DEFAULT 'global',
  league_id                BIGINT,
  season                   INT,
  last_successful_sync     TIMESTAMPTZ,
  last_provider_updated_at TIMESTAMPTZ,
  cursor                   TEXT,
  status                   TEXT NOT NULL DEFAULT 'idle',
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_provider_sync_state PRIMARY KEY (provider, entity_type, scope_key)
);

CREATE INDEX IF NOT EXISTS idx_provider_sync_state_scope
  ON raw.provider_sync_state (provider, entity_type, league_id, season);

-- migrate:down
SELECT 1;
