-- migrate:up
CREATE TABLE IF NOT EXISTS mart.competition_serving_summary (
  league_id BIGINT PRIMARY KEY,
  league_name TEXT,
  matches_count INTEGER NOT NULL DEFAULT 0,
  seasons_count INTEGER NOT NULL DEFAULT 0,
  min_season INTEGER,
  max_season INTEGER,
  match_statistics_count INTEGER NOT NULL DEFAULT 0,
  lineups_count INTEGER NOT NULL DEFAULT 0,
  events_count INTEGER NOT NULL DEFAULT 0,
  player_statistics_count INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DELETE FROM mart.competition_serving_summary;

INSERT INTO mart.competition_serving_summary (
  league_id,
  league_name,
  matches_count,
  seasons_count,
  min_season,
  max_season,
  match_statistics_count,
  lineups_count,
  events_count,
  player_statistics_count,
  updated_at
)
WITH match_totals AS (
  SELECT
    fm.league_id,
    COUNT(DISTINCT fm.match_id)::int AS matches_count,
    COUNT(DISTINCT fm.season)::int AS seasons_count,
    MIN(fm.season)::int AS min_season,
    MAX(fm.season)::int AS max_season
  FROM mart.fact_matches fm
  GROUP BY fm.league_id
),
match_statistics AS (
  SELECT
    rf.league_id,
    COUNT(DISTINCT ms.fixture_id)::int AS available_count
  FROM raw.match_statistics ms
  INNER JOIN raw.fixtures rf
    ON rf.fixture_id = ms.fixture_id
  GROUP BY rf.league_id
),
fixture_lineups AS (
  SELECT
    rf.league_id,
    COUNT(DISTINCT fl.fixture_id)::int AS available_count
  FROM raw.fixture_lineups fl
  INNER JOIN raw.fixtures rf
    ON rf.fixture_id = fl.fixture_id
  GROUP BY rf.league_id
),
match_events AS (
  SELECT
    rf.league_id,
    COUNT(DISTINCT me.fixture_id)::int AS available_count
  FROM raw.match_events me
  INNER JOIN raw.fixtures rf
    ON rf.fixture_id = me.fixture_id
  GROUP BY rf.league_id
),
fixture_player_statistics AS (
  SELECT
    rf.league_id,
    COUNT(DISTINCT fps.fixture_id)::int AS available_count
  FROM raw.fixture_player_statistics fps
  INNER JOIN raw.fixtures rf
    ON rf.fixture_id = fps.fixture_id
  GROUP BY rf.league_id
),
competition_names AS (
  SELECT DISTINCT ON (dc.league_id)
    dc.league_id,
    dc.league_name
  FROM mart.dim_competition dc
  ORDER BY dc.league_id, dc.updated_at DESC NULLS LAST
)
SELECT
  mt.league_id,
  cn.league_name,
  mt.matches_count,
  mt.seasons_count,
  mt.min_season,
  mt.max_season,
  COALESCE(ms.available_count, 0) AS match_statistics_count,
  COALESCE(fl.available_count, 0) AS lineups_count,
  COALESCE(me.available_count, 0) AS events_count,
  COALESCE(fps.available_count, 0) AS player_statistics_count,
  now() AS updated_at
FROM match_totals mt
LEFT JOIN competition_names cn
  ON cn.league_id = mt.league_id
LEFT JOIN match_statistics ms
  ON ms.league_id = mt.league_id
LEFT JOIN fixture_lineups fl
  ON fl.league_id = mt.league_id
LEFT JOIN match_events me
  ON me.league_id = mt.league_id
LEFT JOIN fixture_player_statistics fps
  ON fps.league_id = mt.league_id;

-- migrate:down
DROP TABLE IF EXISTS mart.competition_serving_summary;
