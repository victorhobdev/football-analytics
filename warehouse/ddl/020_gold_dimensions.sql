CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.dim_team (
  team_id      BIGINT PRIMARY KEY,
  team_name    TEXT NOT NULL,
  logo_url     TEXT,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.dim_venue (
  venue_id     BIGINT PRIMARY KEY,
  venue_name   TEXT NOT NULL,
  venue_city   TEXT,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.dim_competition (
  league_id    BIGINT PRIMARY KEY,
  league_name  TEXT NOT NULL,
  country      TEXT,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.dim_player (
  player_id    BIGINT PRIMARY KEY,
  player_name  TEXT NOT NULL,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.dim_date (
  date_day          DATE PRIMARY KEY,
  year              INT NOT NULL,
  month             INT NOT NULL,
  day               INT NOT NULL,
  day_of_week_name  TEXT NOT NULL,
  is_weekend        BOOLEAN NOT NULL
);
