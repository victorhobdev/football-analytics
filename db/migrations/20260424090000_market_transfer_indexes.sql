-- migrate:up
CREATE INDEX IF NOT EXISTS idx_player_transfers_type
  ON raw.player_transfers (type_id);

CREATE INDEX IF NOT EXISTS idx_player_transfers_from_team
  ON raw.player_transfers (from_team_id);

CREATE INDEX IF NOT EXISTS idx_player_transfers_to_team
  ON raw.player_transfers (to_team_id);

-- migrate:down
DROP INDEX IF EXISTS raw.idx_player_transfers_to_team;
DROP INDEX IF EXISTS raw.idx_player_transfers_from_team;
DROP INDEX IF EXISTS raw.idx_player_transfers_type;
