-- migrate:up
-- Copa do Mundo | Bloco B0
-- Fundacao multi-edicao para snapshot gate da Copa sem quebrar a wave 2022.

ALTER TABLE control.wc_source_snapshots
  DROP CONSTRAINT IF EXISTS uq_wc_source_snapshots_source_version;

DROP INDEX IF EXISTS control.uq_wc_source_snapshots_active_source;

CREATE UNIQUE INDEX IF NOT EXISTS uq_wc_source_snapshots_source_version_scope
  ON control.wc_source_snapshots (source_name, source_commit_or_release, edition_scope);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wc_source_snapshots_active_source_scope
  ON control.wc_source_snapshots (source_name, edition_scope)
  WHERE is_active;

-- migrate:down
SELECT 1;
