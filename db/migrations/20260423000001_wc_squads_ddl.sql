-- migrate:up
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.wc_squads (
  wc_squad_pk         BIGSERIAL PRIMARY KEY,
  edition_key         TEXT NOT NULL,
  provider            TEXT NOT NULL,
  competition_key     TEXT NOT NULL,
  season_label        TEXT NOT NULL,
  source_name         TEXT NOT NULL,
  source_version      TEXT NOT NULL,
  source_row_id       TEXT NOT NULL,
  source_team_id      TEXT NOT NULL,
  source_player_id    TEXT NOT NULL,
  team_internal_id    TEXT NOT NULL,
  player_internal_id  TEXT NOT NULL,
  team_id             BIGINT NOT NULL,
  player_id           BIGINT NOT NULL,
  team_name           TEXT NOT NULL,
  team_code           TEXT NOT NULL,
  player_name         TEXT NOT NULL,
  jersey_number       INTEGER,
  position_name       TEXT,
  position_code       TEXT,
  payload             JSONB NOT NULL,
  source_run_id       TEXT,
  ingested_run        TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_wc_squads_player UNIQUE (edition_key, team_internal_id, player_internal_id, source_name),
  CONSTRAINT uq_wc_squads_source_row UNIQUE (source_name, edition_key, source_row_id),
  CONSTRAINT chk_wc_squads_competition_key CHECK (competition_key = 'fifa_world_cup_mens'),
  CONSTRAINT chk_wc_squads_source_name_raw CHECK (source_name = 'fjelstul_worldcup')
);

CREATE INDEX IF NOT EXISTS idx_raw_wc_squads_edition
  ON raw.wc_squads (edition_key);

CREATE INDEX IF NOT EXISTS idx_raw_wc_squads_player
  ON raw.wc_squads (player_id);

CREATE INDEX IF NOT EXISTS idx_raw_wc_squads_team
  ON raw.wc_squads (team_id);

COMMENT ON COLUMN raw.wc_squads.source_row_id IS 'Chave bruta da linha de squad no dataset de origem da Copa.';
COMMENT ON COLUMN raw.wc_squads.team_internal_id IS 'Identificador canonico interno do time dentro do pipeline da Copa.';
COMMENT ON COLUMN raw.wc_squads.player_internal_id IS 'Identificador canonico interno do jogador dentro do pipeline da Copa.';
COMMENT ON COLUMN raw.wc_squads.team_code IS 'Codigo curto historico da selecao no dataset de origem.';
COMMENT ON COLUMN raw.wc_squads.payload IS 'Payload bruto da linha de elenco para auditoria e replay.';

-- migrate:down
SELECT 1;
