-- migrate:up

CREATE INDEX IF NOT EXISTS idx_fact_match_events_match_time
  ON mart.fact_match_events (match_id, time_elapsed);

-- migrate:down

DROP INDEX IF EXISTS mart.idx_fact_match_events_match_time;
