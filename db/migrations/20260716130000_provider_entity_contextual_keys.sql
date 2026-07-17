-- migrate:up
ALTER TABLE raw.provider_entity_map
  ADD COLUMN IF NOT EXISTS source_team_key TEXT,
  ADD COLUMN IF NOT EXISTS valid_from DATE,
  ADD COLUMN IF NOT EXISTS valid_to DATE,
  ADD COLUMN IF NOT EXISTS mapping_state TEXT,
  ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE raw.provider_entity_map
SET source_team_key = source_id,
    mapping_state = CASE WHEN needs_manual_review THEN 'pending' ELSE 'approved' END
WHERE source_team_key IS NULL OR mapping_state IS NULL;

ALTER TABLE raw.provider_entity_map
  ALTER COLUMN source_team_key SET NOT NULL,
  ALTER COLUMN mapping_state SET NOT NULL;

ALTER TABLE raw.provider_entity_map DROP CONSTRAINT IF EXISTS pk_provider_entity_map;
ALTER TABLE raw.provider_entity_map
  ADD CONSTRAINT pk_provider_entity_map
  PRIMARY KEY (provider, entity_type, source_team_key);

CREATE INDEX IF NOT EXISTS idx_provider_entity_map_native_source
  ON raw.provider_entity_map (provider, entity_type, source_id);

-- migrate:down
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM raw.provider_entity_map
    GROUP BY provider, entity_type, source_id
    HAVING count(*) > 1
  ) THEN
    RAISE EXCEPTION 'cannot remove contextual keys while native source IDs have multiple mappings';
  END IF;
END $$;

ALTER TABLE raw.provider_entity_map DROP CONSTRAINT IF EXISTS pk_provider_entity_map;
ALTER TABLE raw.provider_entity_map
  ADD CONSTRAINT pk_provider_entity_map PRIMARY KEY (provider, entity_type, source_id);
DROP INDEX IF EXISTS raw.idx_provider_entity_map_native_source;
ALTER TABLE raw.provider_entity_map
  DROP COLUMN IF EXISTS source_team_key,
  DROP COLUMN IF EXISTS valid_from,
  DROP COLUMN IF EXISTS valid_to,
  DROP COLUMN IF EXISTS mapping_state,
  DROP COLUMN IF EXISTS evidence;
