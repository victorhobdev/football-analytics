-- migrate:up
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.wc_player_identity_map (
  wc_player_id          BIGINT NOT NULL,
  sportmonks_player_id  BIGINT,
  match_confidence      TEXT NOT NULL CHECK (match_confidence IN ('confirmed', 'probable', 'ambiguous', 'none')),
  match_signals         JSONB,
  source_run_id         TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_wc_player_identity_map PRIMARY KEY (wc_player_id)
);

CREATE INDEX IF NOT EXISTS idx_wc_player_map_sm_id
  ON raw.wc_player_identity_map (sportmonks_player_id);

CREATE INDEX IF NOT EXISTS idx_wc_player_map_confidence
  ON raw.wc_player_identity_map (match_confidence);

CREATE TABLE IF NOT EXISTS raw.wc_team_identity_map (
  wc_team_id            BIGINT NOT NULL,
  wc_display_slug       TEXT,
  sportmonks_team_id    BIGINT,
  confidence            TEXT NOT NULL CHECK (confidence IN ('confirmed', 'probable', 'none')),
  status                TEXT NOT NULL CHECK (status IN ('active', 'extinct', 'ambiguous')),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_wc_team_identity_map PRIMARY KEY (wc_team_id)
);

CREATE INDEX IF NOT EXISTS idx_wc_team_map_sm_id
  ON raw.wc_team_identity_map (sportmonks_team_id);

CREATE INDEX IF NOT EXISTS idx_wc_team_map_confidence
  ON raw.wc_team_identity_map (confidence);

COMMENT ON COLUMN raw.wc_player_identity_map.wc_player_id IS 'Identificador canonico do jogador no dataset da Copa.';
COMMENT ON COLUMN raw.wc_player_identity_map.match_signals IS 'Evidencias usadas para reconciliar a identidade Copa -> Sportmonks.';
COMMENT ON COLUMN raw.wc_player_identity_map.source_run_id IS 'Identificador da execucao que gerou o match no crosswalk.';
COMMENT ON COLUMN raw.wc_team_identity_map.wc_display_slug IS 'Slug de exibicao legado da selecao na vertical Copa.';
COMMENT ON COLUMN raw.wc_team_identity_map.status IS 'Estado operacional do mapeamento do time no crosswalk.';

-- migrate:down
DROP TABLE IF EXISTS raw.wc_team_identity_map CASCADE;
DROP TABLE IF EXISTS raw.wc_player_identity_map CASCADE;
