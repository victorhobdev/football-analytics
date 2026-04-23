-- migrate:up
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.wc_match_events (
  wc_match_event_pk       BIGSERIAL PRIMARY KEY,
  internal_match_id       TEXT NOT NULL,
  edition_key             TEXT NOT NULL,
  source_name             TEXT NOT NULL,
  source_version          TEXT NOT NULL,
  source_match_id         TEXT NOT NULL,
  source_event_id         TEXT NOT NULL,
  event_index             INTEGER NOT NULL,
  team_internal_id        TEXT,
  player_internal_id      TEXT,
  event_type              TEXT NOT NULL,
  period                  INTEGER,
  minute                  INTEGER,
  second                  NUMERIC,
  location_x              NUMERIC,
  location_y              NUMERIC,
  outcome_label           TEXT,
  play_pattern_label      TEXT,
  is_three_sixty_backed   BOOLEAN NOT NULL DEFAULT FALSE,
  event_payload           JSONB NOT NULL,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  fixture_id              BIGINT,
  CONSTRAINT uq_wc_match_events_match_event_index UNIQUE (internal_match_id, source_name, event_index),
  CONSTRAINT uq_wc_match_events_source_event UNIQUE (source_name, source_match_id, source_event_id),
  CONSTRAINT chk_wc_match_events_source_name CHECK (
    source_name = ANY (
      ARRAY[
        'statsbomb_open_data',
        'fjelstul_worldcup',
        'openfootball_worldcup',
        'openfootball_worldcup_more'
      ]
    )
  )
);

CREATE INDEX IF NOT EXISTS idx_wc_match_events_edition_key
  ON raw.wc_match_events (edition_key);

CREATE INDEX IF NOT EXISTS idx_wc_match_events_fixture_id
  ON raw.wc_match_events (fixture_id);

CREATE INDEX IF NOT EXISTS idx_wc_match_events_internal_match_id
  ON raw.wc_match_events (internal_match_id);

CREATE INDEX IF NOT EXISTS idx_wc_match_events_player_internal_id
  ON raw.wc_match_events (player_internal_id);

CREATE INDEX IF NOT EXISTS idx_wc_match_events_team_internal_id
  ON raw.wc_match_events (team_internal_id);

COMMENT ON COLUMN raw.wc_match_events.internal_match_id IS 'Identificador canonico da partida no pipeline da Copa.';
COMMENT ON COLUMN raw.wc_match_events.source_event_id IS 'Identificador bruto do evento no dataset de origem.';
COMMENT ON COLUMN raw.wc_match_events.event_index IS 'Sequencia do evento dentro da partida para ordenacao deterministica.';
COMMENT ON COLUMN raw.wc_match_events.is_three_sixty_backed IS 'Sinaliza eventos enriquecidos por dados 360 do StatsBomb.';
COMMENT ON COLUMN raw.wc_match_events.event_payload IS 'Payload bruto completo do evento para auditoria e replay.';

-- migrate:down
SELECT 1;
