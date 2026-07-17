-- migrate:up
CREATE INDEX IF NOT EXISTS idx_wc_match_events_shootout_penalties
  ON raw.wc_match_events (fixture_id)
  WHERE event_type = 'Shot'
    AND event_payload->'shot'->'type'->>'name' = 'Penalty'
    AND coalesce((event_payload->>'period')::int, 0) = 5;

ANALYZE raw.wc_match_events;

-- migrate:down
DROP INDEX IF EXISTS raw.idx_wc_match_events_shootout_penalties;
