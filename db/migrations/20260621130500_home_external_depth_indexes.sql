-- migrate:up

CREATE INDEX IF NOT EXISTS idx_tm_games_game_id
  ON raw.tm_games (game_id);

CREATE INDEX IF NOT EXISTS idx_tm_games_competition_season_game
  ON raw.tm_games (competition_id, season, game_id);

CREATE INDEX IF NOT EXISTS idx_elo_matches_division_date_hash
  ON raw.elo_matches (division, match_date_raw, record_hash);

CREATE INDEX IF NOT EXISTS idx_tm_clubs_club_id
  ON raw.tm_clubs (club_id);

-- migrate:down

DROP INDEX IF EXISTS raw.idx_tm_clubs_club_id;
DROP INDEX IF EXISTS raw.idx_elo_matches_division_date_hash;
DROP INDEX IF EXISTS raw.idx_tm_games_competition_season_game;
DROP INDEX IF EXISTS raw.idx_tm_games_game_id;
