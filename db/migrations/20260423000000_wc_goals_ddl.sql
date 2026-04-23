-- migrate:up
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.wc_goals (
  wc_goal_pk              BIGSERIAL PRIMARY KEY,
  fixture_id              BIGINT NOT NULL,
  internal_match_id       TEXT NOT NULL,
  edition_key             TEXT NOT NULL,
  provider                TEXT NOT NULL,
  competition_key         TEXT NOT NULL,
  season_label            TEXT NOT NULL,
  source_name             TEXT NOT NULL,
  source_version          TEXT NOT NULL,
  source_match_id         TEXT NOT NULL,
  source_goal_id          TEXT NOT NULL,
  source_team_id          TEXT NOT NULL,
  source_player_id        TEXT NOT NULL,
  source_player_team_id   TEXT NOT NULL,
  team_internal_id        TEXT NOT NULL,
  player_internal_id      TEXT NOT NULL,
  player_team_internal_id TEXT NOT NULL,
  team_id                 BIGINT NOT NULL,
  player_id               BIGINT NOT NULL,
  player_team_id          BIGINT NOT NULL,
  team_name               TEXT NOT NULL,
  player_name             TEXT NOT NULL,
  player_team_name        TEXT NOT NULL,
  minute_regulation       INTEGER,
  minute_stoppage         INTEGER,
  match_period            TEXT,
  minute_label            TEXT,
  is_penalty              BOOLEAN NOT NULL DEFAULT FALSE,
  is_own_goal             BOOLEAN NOT NULL DEFAULT FALSE,
  payload                 JSONB NOT NULL,
  source_run_id           TEXT,
  ingested_run            TEXT,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_wc_goals_source_goal UNIQUE (source_name, edition_key, source_goal_id),
  CONSTRAINT chk_wc_goals_competition_key CHECK (competition_key = 'fifa_world_cup_mens'),
  CONSTRAINT chk_wc_goals_source_name_raw CHECK (source_name = 'fjelstul_worldcup')
);

CREATE INDEX IF NOT EXISTS idx_raw_wc_goals_edition
  ON raw.wc_goals (edition_key);

CREATE INDEX IF NOT EXISTS idx_raw_wc_goals_fixture
  ON raw.wc_goals (fixture_id);

CREATE INDEX IF NOT EXISTS idx_raw_wc_goals_player
  ON raw.wc_goals (player_id);

CREATE INDEX IF NOT EXISTS idx_raw_wc_goals_team
  ON raw.wc_goals (team_id);

COMMENT ON COLUMN raw.wc_goals.internal_match_id IS 'Identificador canonico da partida no dataset da Copa antes do fixture_id local.';
COMMENT ON COLUMN raw.wc_goals.source_goal_id IS 'Identificador bruto do gol no provedor de origem do dataset da Copa.';
COMMENT ON COLUMN raw.wc_goals.player_team_id IS 'Identificador canonico do time associado ao jogador no evento do gol.';
COMMENT ON COLUMN raw.wc_goals.minute_label IS 'Rotulo textual original do minuto, preservando acrescimos e anotacoes do dataset.';
COMMENT ON COLUMN raw.wc_goals.payload IS 'Payload bruto original do evento de gol para auditoria e replay.';

-- migrate:down
SELECT 1;
