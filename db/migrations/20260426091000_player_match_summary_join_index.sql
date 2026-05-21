-- migrate:up
CREATE INDEX IF NOT EXISTS idx_mart_player_match_summary_match_date_player
  ON mart.player_match_summary (match_id, match_date DESC, player_id);

-- migrate:down
DROP INDEX IF EXISTS mart.idx_mart_player_match_summary_match_date_player;
