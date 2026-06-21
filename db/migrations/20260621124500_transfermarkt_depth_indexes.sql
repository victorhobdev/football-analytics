-- migrate:up

CREATE INDEX IF NOT EXISTS idx_tm_appearances_game_player
  ON raw.tm_appearances (game_id, player_id);

CREATE INDEX IF NOT EXISTS idx_tm_game_lineups_game_player
  ON raw.tm_game_lineups (game_id, player_id);

CREATE INDEX IF NOT EXISTS idx_tm_game_events_game_player
  ON raw.tm_game_events (game_id, player_id);

CREATE INDEX IF NOT EXISTS idx_tm_game_events_player_in
  ON raw.tm_game_events (player_in_id);

CREATE INDEX IF NOT EXISTS idx_tm_game_events_player_assist
  ON raw.tm_game_events (player_assist_id);

-- migrate:down

DROP INDEX IF EXISTS raw.idx_tm_game_events_player_assist;
DROP INDEX IF EXISTS raw.idx_tm_game_events_player_in;
DROP INDEX IF EXISTS raw.idx_tm_game_events_game_player;
DROP INDEX IF EXISTS raw.idx_tm_game_lineups_game_player;
DROP INDEX IF EXISTS raw.idx_tm_appearances_game_player;
