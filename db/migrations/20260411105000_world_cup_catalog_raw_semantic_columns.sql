-- migrate:up
-- Alinha o schema raw das tabelas de catalogo com o contrato semantico
-- assumido pelos seeds World Cup introduzidos em 20260411110000.

ALTER TABLE raw.competition_leagues
  ADD COLUMN IF NOT EXISTS provider_league_id BIGINT,
  ADD COLUMN IF NOT EXISTS competition_key TEXT,
  ADD COLUMN IF NOT EXISTS competition_type TEXT,
  ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS source_run_id TEXT;

ALTER TABLE raw.competition_seasons
  ADD COLUMN IF NOT EXISTS provider_league_id BIGINT,
  ADD COLUMN IF NOT EXISTS competition_key TEXT,
  ADD COLUMN IF NOT EXISTS season_label TEXT,
  ADD COLUMN IF NOT EXISTS provider_season_id BIGINT,
  ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS source_run_id TEXT;

-- migrate:down
SELECT 1;
