-- migrate:up

ALTER TABLE silver.wc_lineups
  DROP CONSTRAINT IF EXISTS chk_wc_lineups_source_name;

ALTER TABLE silver.wc_lineups
  ADD CONSTRAINT chk_wc_lineups_source_name
  CHECK (source_name IN ('statsbomb_open_data', 'fjelstul_worldcup'));

ALTER TABLE silver.wc_match_events
  DROP CONSTRAINT IF EXISTS chk_wc_match_events_source_name;

ALTER TABLE silver.wc_match_events
  ADD CONSTRAINT chk_wc_match_events_source_name
  CHECK (source_name IN ('statsbomb_open_data', 'fjelstul_worldcup'));

-- migrate:down

ALTER TABLE silver.wc_match_events
  DROP CONSTRAINT IF EXISTS chk_wc_match_events_source_name;

ALTER TABLE silver.wc_match_events
  ADD CONSTRAINT chk_wc_match_events_source_name
  CHECK (source_name = 'statsbomb_open_data');

ALTER TABLE silver.wc_lineups
  DROP CONSTRAINT IF EXISTS chk_wc_lineups_source_name;

ALTER TABLE silver.wc_lineups
  ADD CONSTRAINT chk_wc_lineups_source_name
  CHECK (source_name = 'statsbomb_open_data');
