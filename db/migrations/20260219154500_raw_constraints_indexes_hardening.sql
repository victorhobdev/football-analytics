-- migrate:up
-- P1.3 hardening: constraints e indices minimos em tabelas raw criticas.

-- IDs criticos usados em joins/filtros.
ALTER TABLE raw.fixtures
  ALTER COLUMN fixture_id SET NOT NULL,
  ALTER COLUMN league_id SET NOT NULL,
  ALTER COLUMN season SET NOT NULL;

ALTER TABLE raw.match_statistics
  ALTER COLUMN fixture_id SET NOT NULL,
  ALTER COLUMN team_id SET NOT NULL;

ALTER TABLE raw.match_events
  ALTER COLUMN event_id SET NOT NULL,
  ALTER COLUMN season SET NOT NULL,
  ALTER COLUMN fixture_id SET NOT NULL;

-- Garantia de PK no grao natural (somente se ausente).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'raw.fixtures'::regclass
      AND contype = 'p'
  ) THEN
    ALTER TABLE raw.fixtures
      ADD CONSTRAINT pk_raw_fixtures PRIMARY KEY (fixture_id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'raw.match_statistics'::regclass
      AND contype = 'p'
  ) THEN
    ALTER TABLE raw.match_statistics
      ADD CONSTRAINT pk_raw_match_statistics PRIMARY KEY (fixture_id, team_id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'raw.match_events'::regclass
      AND contype = 'p'
  ) THEN
    ALTER TABLE raw.match_events
      ADD CONSTRAINT pk_raw_match_events PRIMARY KEY (event_id, season);
  END IF;
END $$;

-- Indices para filtros e joins comuns.
CREATE INDEX IF NOT EXISTS idx_raw_fixtures_league_id
  ON raw.fixtures (league_id);

CREATE INDEX IF NOT EXISTS idx_raw_fixtures_season
  ON raw.fixtures (season);

CREATE INDEX IF NOT EXISTS idx_raw_fixtures_league_season
  ON raw.fixtures (league_id, season);

CREATE INDEX IF NOT EXISTS idx_raw_match_events_assist_id
  ON raw.match_events (assist_id);

-- migrate:down
DROP INDEX IF EXISTS idx_raw_match_events_assist_id;
DROP INDEX IF EXISTS idx_raw_fixtures_league_season;
DROP INDEX IF EXISTS idx_raw_fixtures_season;
DROP INDEX IF EXISTS idx_raw_fixtures_league_id;

ALTER TABLE raw.fixtures
  ALTER COLUMN league_id DROP NOT NULL,
  ALTER COLUMN season DROP NOT NULL;

ALTER TABLE raw.match_events DROP CONSTRAINT IF EXISTS pk_raw_match_events;
ALTER TABLE raw.match_statistics DROP CONSTRAINT IF EXISTS pk_raw_match_statistics;
ALTER TABLE raw.fixtures DROP CONSTRAINT IF EXISTS pk_raw_fixtures;
