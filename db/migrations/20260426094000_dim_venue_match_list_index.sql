-- migrate:up
CREATE INDEX IF NOT EXISTS idx_mart_dim_venue_venue
  ON mart.dim_venue (venue_id);

-- migrate:down
DROP INDEX IF EXISTS mart.idx_mart_dim_venue_venue;
