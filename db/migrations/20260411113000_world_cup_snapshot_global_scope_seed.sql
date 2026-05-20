-- migrate:up
WITH source_scope_seed AS (
  SELECT
    source_name,
    source_url,
    source_version,
    source_commit_or_release,
    accessed_at,
    checksum_sha256,
    local_path,
    license_code,
    attribution_note,
    'GLOBAL'::text AS edition_scope,
    usage_decision,
    TRUE AS is_active
  FROM control.wc_source_snapshots
  WHERE is_active = TRUE
    AND source_name IN ('statsbomb_open_data', 'fjelstul_worldcup')
    AND edition_scope = 'fifa_world_cup_mens__2022'
),
global_upsert AS (
  INSERT INTO control.wc_source_snapshots (
    source_name,
    source_url,
    source_version,
    source_commit_or_release,
    edition_scope,
    accessed_at,
    checksum_sha256,
    local_path,
    license_code,
    attribution_note,
    usage_decision,
    is_active
  )
  SELECT
    source_name,
    source_url,
    source_version,
    source_commit_or_release,
    edition_scope,
    accessed_at,
    checksum_sha256,
    local_path,
    license_code,
    attribution_note,
    usage_decision,
    is_active
  FROM source_scope_seed
  ON CONFLICT (source_name, source_commit_or_release, edition_scope) DO UPDATE
  SET
    source_url = EXCLUDED.source_url,
    source_version = EXCLUDED.source_version,
    accessed_at = EXCLUDED.accessed_at,
    checksum_sha256 = EXCLUDED.checksum_sha256,
    local_path = EXCLUDED.local_path,
    license_code = EXCLUDED.license_code,
    attribution_note = EXCLUDED.attribution_note,
    usage_decision = EXCLUDED.usage_decision,
    is_active = EXCLUDED.is_active
  WHERE
    control.wc_source_snapshots.source_url IS DISTINCT FROM EXCLUDED.source_url
    OR control.wc_source_snapshots.source_version IS DISTINCT FROM EXCLUDED.source_version
    OR control.wc_source_snapshots.accessed_at IS DISTINCT FROM EXCLUDED.accessed_at
    OR control.wc_source_snapshots.checksum_sha256 IS DISTINCT FROM EXCLUDED.checksum_sha256
    OR control.wc_source_snapshots.local_path IS DISTINCT FROM EXCLUDED.local_path
    OR control.wc_source_snapshots.license_code IS DISTINCT FROM EXCLUDED.license_code
    OR control.wc_source_snapshots.attribution_note IS DISTINCT FROM EXCLUDED.attribution_note
    OR control.wc_source_snapshots.usage_decision IS DISTINCT FROM EXCLUDED.usage_decision
    OR control.wc_source_snapshots.is_active IS DISTINCT FROM EXCLUDED.is_active
  RETURNING 1
)
SELECT count(*) FROM global_upsert;

-- migrate:down
DELETE FROM control.wc_source_snapshots
WHERE edition_scope = 'GLOBAL'
  AND source_name IN ('statsbomb_open_data', 'fjelstul_worldcup');
