-- migrate:up
CREATE SCHEMA IF NOT EXISTS control;
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS control.brasileirao_fixture_xref (
  brasileirao_match_id   TEXT PRIMARY KEY,
  local_fixture_id       BIGINT,
  match_date             DATE,
  home_team_name_raw     TEXT NOT NULL,
  away_team_name_raw     TEXT NOT NULL,
  identity_status        TEXT NOT NULL DEFAULT 'unmatched',
  confidence             NUMERIC(5,4),
  resolved_at            TIMESTAMPTZ,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS control.tm_game_fixture_xref (
  tm_game_id             TEXT PRIMARY KEY,
  local_fixture_id       BIGINT,
  match_date             DATE,
  home_team_name_raw     TEXT NOT NULL,
  away_team_name_raw     TEXT NOT NULL,
  identity_status        TEXT NOT NULL DEFAULT 'unmatched',
  confidence             NUMERIC(5,4),
  resolved_at            TIMESTAMPTZ,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS control.tm_player_xref (
  tm_player_id           TEXT PRIMARY KEY,
  local_player_id        BIGINT,
  player_name_raw        TEXT NOT NULL,
  date_of_birth_raw      TEXT,
  identity_status        TEXT NOT NULL DEFAULT 'unmatched',
  confidence             NUMERIC(5,4),
  resolved_at            TIMESTAMPTZ,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.brasileirao_matches (
  record_hash            TEXT PRIMARY KEY,
  source_name            TEXT NOT NULL DEFAULT 'dataset_brasileirao',
  match_id               TEXT,
  rodada                 TEXT,
  match_date_raw         TEXT,
  match_time_raw         TEXT,
  home_team_name         TEXT,
  away_team_name         TEXT,
  home_formation         TEXT,
  away_formation         TEXT,
  home_coach_name        TEXT,
  away_coach_name        TEXT,
  winner_name            TEXT,
  venue_name             TEXT,
  home_score             TEXT,
  away_score             TEXT,
  home_state             TEXT,
  away_state             TEXT,
  revenue_raw            TEXT,
  source_file            TEXT NOT NULL,
  ingested_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.brasileirao_stats (
  record_hash            TEXT PRIMARY KEY,
  source_name            TEXT NOT NULL DEFAULT 'dataset_brasileirao',
  partida_id             TEXT,
  rodada                 TEXT,
  clube                  TEXT,
  chutes                 TEXT,
  chutes_no_alvo         TEXT,
  posse_de_bola          TEXT,
  passes                 TEXT,
  precisao_passes        TEXT,
  faltas                 TEXT,
  cartao_amarelo         TEXT,
  cartao_vermelho        TEXT,
  impedimentos           TEXT,
  escanteios             TEXT,
  source_file            TEXT NOT NULL,
  ingested_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.brasileirao_goals (
  record_hash            TEXT PRIMARY KEY,
  source_name            TEXT NOT NULL DEFAULT 'dataset_brasileirao',
  partida_id             TEXT,
  rodada                 TEXT,
  clube                  TEXT,
  atleta                 TEXT,
  minuto                 TEXT,
  tipo_de_gol            TEXT,
  source_file            TEXT NOT NULL,
  ingested_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.brasileirao_cards (
  record_hash            TEXT PRIMARY KEY,
  source_name            TEXT NOT NULL DEFAULT 'dataset_brasileirao',
  partida_id             TEXT,
  rodada                 TEXT,
  clube                  TEXT,
  cartao                 TEXT,
  atleta                 TEXT,
  num_camisa             TEXT,
  posicao                TEXT,
  minuto                 TEXT,
  source_file            TEXT NOT NULL,
  ingested_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.elo_ratings (
  record_hash            TEXT PRIMARY KEY,
  source_name            TEXT NOT NULL DEFAULT 'dataset_elo_matches',
  rating_date_raw        TEXT,
  club_name              TEXT,
  country_code           TEXT,
  elo_rating_raw         TEXT,
  source_file            TEXT NOT NULL,
  ingested_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.elo_matches (
  record_hash            TEXT PRIMARY KEY,
  source_name            TEXT NOT NULL DEFAULT 'dataset_elo_matches',
  division               TEXT,
  match_date_raw         TEXT,
  match_time_raw         TEXT,
  home_team_name         TEXT,
  away_team_name         TEXT,
  home_elo_raw           TEXT,
  away_elo_raw           TEXT,
  form3_home_raw         TEXT,
  form5_home_raw         TEXT,
  form3_away_raw         TEXT,
  form5_away_raw         TEXT,
  ft_home_raw            TEXT,
  ft_away_raw            TEXT,
  ft_result              TEXT,
  ht_home_raw            TEXT,
  ht_away_raw            TEXT,
  ht_result              TEXT,
  home_shots_raw         TEXT,
  away_shots_raw         TEXT,
  home_target_raw        TEXT,
  away_target_raw        TEXT,
  home_fouls_raw         TEXT,
  away_fouls_raw         TEXT,
  home_corners_raw       TEXT,
  away_corners_raw       TEXT,
  home_yellow_raw        TEXT,
  away_yellow_raw        TEXT,
  home_red_raw           TEXT,
  away_red_raw           TEXT,
  odd_home_raw           TEXT,
  odd_draw_raw           TEXT,
  odd_away_raw           TEXT,
  max_home_raw           TEXT,
  max_draw_raw           TEXT,
  max_away_raw           TEXT,
  over25_raw             TEXT,
  under25_raw            TEXT,
  max_over25_raw         TEXT,
  max_under25_raw        TEXT,
  handi_size_raw         TEXT,
  handi_home_raw         TEXT,
  handi_away_raw         TEXT,
  c_lth_raw              TEXT,
  c_lta_raw              TEXT,
  c_vhd_raw              TEXT,
  c_vad_raw              TEXT,
  c_htb_raw              TEXT,
  c_phb_raw              TEXT,
  source_file            TEXT NOT NULL,
  ingested_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.tm_competitions (
  record_hash                 TEXT PRIMARY KEY,
  source_name                 TEXT NOT NULL DEFAULT 'dataset_transfermarket',
  competition_id              TEXT,
  competition_code            TEXT,
  name                        TEXT,
  sub_type                    TEXT,
  type                        TEXT,
  country_id                  TEXT,
  country_name                TEXT,
  domestic_league_code        TEXT,
  confederation               TEXT,
  total_clubs                 TEXT,
  url                         TEXT,
  source_file                 TEXT NOT NULL,
  ingested_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.tm_countries (
  record_hash                 TEXT PRIMARY KEY,
  source_name                 TEXT NOT NULL DEFAULT 'dataset_transfermarket',
  country_id                  TEXT,
  country_name                TEXT,
  country_code                TEXT,
  confederation               TEXT,
  total_clubs                 TEXT,
  total_players               TEXT,
  average_age                 TEXT,
  url                         TEXT,
  source_file                 TEXT NOT NULL,
  ingested_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.tm_national_teams (
  record_hash                 TEXT PRIMARY KEY,
  source_name                 TEXT NOT NULL DEFAULT 'dataset_transfermarket',
  national_team_id            TEXT,
  name                        TEXT,
  team_code                   TEXT,
  country_id                  TEXT,
  country_name                TEXT,
  country_code                TEXT,
  confederation               TEXT,
  team_image_url              TEXT,
  squad_size                  TEXT,
  average_age                 TEXT,
  foreigners_number           TEXT,
  foreigners_percentage       TEXT,
  total_market_value          TEXT,
  coach_name                  TEXT,
  fifa_ranking                TEXT,
  last_season                 TEXT,
  url                         TEXT,
  source_file                 TEXT NOT NULL,
  ingested_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.tm_clubs (
  record_hash                 TEXT PRIMARY KEY,
  source_name                 TEXT NOT NULL DEFAULT 'dataset_transfermarket',
  club_id                     TEXT,
  club_code                   TEXT,
  name                        TEXT,
  domestic_competition_id     TEXT,
  total_market_value          TEXT,
  squad_size                  TEXT,
  average_age                 TEXT,
  foreigners_number           TEXT,
  foreigners_percentage       TEXT,
  national_team_players       TEXT,
  stadium_name                TEXT,
  stadium_seats               TEXT,
  net_transfer_record         TEXT,
  coach_name                  TEXT,
  last_season                 TEXT,
  filename                    TEXT,
  url                         TEXT,
  source_file                 TEXT NOT NULL,
  ingested_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.tm_players (
  record_hash                     TEXT PRIMARY KEY,
  source_name                     TEXT NOT NULL DEFAULT 'dataset_transfermarket',
  player_id                       TEXT,
  first_name                      TEXT,
  last_name                       TEXT,
  name                            TEXT,
  last_season                     TEXT,
  current_club_id                 TEXT,
  player_code                     TEXT,
  country_of_birth                TEXT,
  city_of_birth                   TEXT,
  country_of_citizenship          TEXT,
  date_of_birth_raw               TEXT,
  sub_position                    TEXT,
  position                        TEXT,
  foot                            TEXT,
  height_in_cm                    TEXT,
  contract_expiration_date_raw    TEXT,
  agent_name                      TEXT,
  image_url                       TEXT,
  international_caps              TEXT,
  international_goals             TEXT,
  current_national_team_id        TEXT,
  url                             TEXT,
  current_club_domestic_competition_id TEXT,
  current_club_name               TEXT,
  market_value_in_eur             TEXT,
  highest_market_value_in_eur     TEXT,
  source_file                     TEXT NOT NULL,
  ingested_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.tm_games (
  record_hash                     TEXT PRIMARY KEY,
  source_name                     TEXT NOT NULL DEFAULT 'dataset_transfermarket',
  game_id                         TEXT,
  competition_id                  TEXT,
  season                          TEXT,
  round                           TEXT,
  match_date_raw                  TEXT,
  home_club_id                    TEXT,
  away_club_id                    TEXT,
  home_club_goals                 TEXT,
  away_club_goals                 TEXT,
  home_club_position              TEXT,
  away_club_position              TEXT,
  home_club_manager_name          TEXT,
  away_club_manager_name          TEXT,
  stadium                         TEXT,
  attendance                      TEXT,
  referee                         TEXT,
  url                             TEXT,
  home_club_formation             TEXT,
  away_club_formation             TEXT,
  home_club_name                  TEXT,
  away_club_name                  TEXT,
  aggregate                       TEXT,
  competition_type                TEXT,
  source_file                     TEXT NOT NULL,
  ingested_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.tm_club_games (
  record_hash                     TEXT PRIMARY KEY,
  source_name                     TEXT NOT NULL DEFAULT 'dataset_transfermarket',
  game_id                         TEXT,
  club_id                         TEXT,
  own_goals                       TEXT,
  own_position                    TEXT,
  own_manager_name                TEXT,
  opponent_id                     TEXT,
  opponent_goals                  TEXT,
  opponent_position               TEXT,
  opponent_manager_name           TEXT,
  hosting                         TEXT,
  is_win                          TEXT,
  source_file                     TEXT NOT NULL,
  ingested_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.tm_player_valuations (
  record_hash                     TEXT PRIMARY KEY,
  source_name                     TEXT NOT NULL DEFAULT 'dataset_transfermarket',
  player_id                       TEXT,
  valuation_date_raw              TEXT,
  market_value_in_eur             TEXT,
  current_club_name               TEXT,
  current_club_id                 TEXT,
  player_club_domestic_competition_id TEXT,
  source_file                     TEXT NOT NULL,
  ingested_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.tm_transfers (
  record_hash                     TEXT PRIMARY KEY,
  source_name                     TEXT NOT NULL DEFAULT 'dataset_transfermarket',
  player_id                       TEXT,
  transfer_date_raw               TEXT,
  transfer_season                 TEXT,
  from_club_id                    TEXT,
  to_club_id                      TEXT,
  from_club_name                  TEXT,
  to_club_name                    TEXT,
  transfer_fee                    TEXT,
  market_value_in_eur             TEXT,
  player_name                     TEXT,
  source_file                     TEXT NOT NULL,
  ingested_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.tm_appearances (
  record_hash                     TEXT PRIMARY KEY,
  source_name                     TEXT NOT NULL DEFAULT 'dataset_transfermarket',
  appearance_id                   TEXT,
  game_id                         TEXT,
  player_id                       TEXT,
  player_club_id                  TEXT,
  player_current_club_id          TEXT,
  match_date_raw                  TEXT,
  player_name                     TEXT,
  competition_id                  TEXT,
  yellow_cards                    TEXT,
  red_cards                       TEXT,
  goals                           TEXT,
  assists                         TEXT,
  minutes_played                  TEXT,
  source_file                     TEXT NOT NULL,
  ingested_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.tm_game_events (
  record_hash                     TEXT PRIMARY KEY,
  source_name                     TEXT NOT NULL DEFAULT 'dataset_transfermarket',
  game_event_id                   TEXT,
  match_date_raw                  TEXT,
  game_id                         TEXT,
  minute                          TEXT,
  type                            TEXT,
  club_id                         TEXT,
  club_name                       TEXT,
  player_id                       TEXT,
  description                     TEXT,
  player_in_id                    TEXT,
  player_assist_id                TEXT,
  source_file                     TEXT NOT NULL,
  ingested_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.tm_game_lineups (
  record_hash                     TEXT PRIMARY KEY,
  source_name                     TEXT NOT NULL DEFAULT 'dataset_transfermarket',
  game_lineups_id                 TEXT,
  match_date_raw                  TEXT,
  game_id                         TEXT,
  player_id                       TEXT,
  club_id                         TEXT,
  player_name                     TEXT,
  lineup_type                     TEXT,
  position                        TEXT,
  shirt_number                    TEXT,
  team_captain                    TEXT,
  source_file                     TEXT NOT NULL,
  ingested_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- migrate:down
DROP TABLE IF EXISTS raw.tm_game_lineups;
DROP TABLE IF EXISTS raw.tm_game_events;
DROP TABLE IF EXISTS raw.tm_appearances;
DROP TABLE IF EXISTS raw.tm_transfers;
DROP TABLE IF EXISTS raw.tm_player_valuations;
DROP TABLE IF EXISTS raw.tm_club_games;
DROP TABLE IF EXISTS raw.tm_games;
DROP TABLE IF EXISTS raw.tm_players;
DROP TABLE IF EXISTS raw.tm_clubs;
DROP TABLE IF EXISTS raw.tm_national_teams;
DROP TABLE IF EXISTS raw.tm_countries;
DROP TABLE IF EXISTS raw.tm_competitions;
DROP TABLE IF EXISTS raw.elo_matches;
DROP TABLE IF EXISTS raw.elo_ratings;
DROP TABLE IF EXISTS raw.brasileirao_cards;
DROP TABLE IF EXISTS raw.brasileirao_goals;
DROP TABLE IF EXISTS raw.brasileirao_stats;
DROP TABLE IF EXISTS raw.brasileirao_matches;
DROP TABLE IF EXISTS control.tm_player_xref;
DROP TABLE IF EXISTS control.tm_game_fixture_xref;
DROP TABLE IF EXISTS control.brasileirao_fixture_xref;
