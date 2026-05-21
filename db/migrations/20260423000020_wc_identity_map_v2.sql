-- migrate:up
ALTER TABLE raw.wc_player_identity_map
  ADD COLUMN IF NOT EXISTS match_score SMALLINT,
  ADD COLUMN IF NOT EXISTS match_method TEXT,
  ADD COLUMN IF NOT EXISTS audited_by TEXT,
  ADD COLUMN IF NOT EXISTS audit_notes TEXT,
  ADD COLUMN IF NOT EXISTS blocked_reason TEXT;

COMMENT ON COLUMN raw.wc_player_identity_map.match_score IS 'Score composto 0-100. NULL = não processado.';
COMMENT ON COLUMN raw.wc_player_identity_map.match_method IS 'exact_name | fuzzy_name | multi_signal | manual';
COMMENT ON COLUMN raw.wc_player_identity_map.audited_by IS 'human | script | NULL se não auditado';

-- migrate:down
ALTER TABLE raw.wc_player_identity_map
  DROP COLUMN IF EXISTS match_score,
  DROP COLUMN IF EXISTS match_method,
  DROP COLUMN IF EXISTS audited_by,
  DROP COLUMN IF EXISTS audit_notes,
  DROP COLUMN IF EXISTS blocked_reason;
