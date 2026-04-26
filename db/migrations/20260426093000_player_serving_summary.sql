-- migrate:up
CREATE TABLE IF NOT EXISTS mart.player_serving_summary (
  player_id BIGINT PRIMARY KEY,
  player_name TEXT,
  team_id BIGINT,
  team_name TEXT,
  position_name TEXT,
  nationality TEXT,
  team_count INTEGER NOT NULL DEFAULT 0,
  recent_teams JSONB NOT NULL DEFAULT '[]'::jsonb,
  recent_teams_5 JSONB NOT NULL DEFAULT '[]'::jsonb,
  matches_played INTEGER NOT NULL DEFAULT 0,
  minutes_played NUMERIC NOT NULL DEFAULT 0,
  goals NUMERIC NOT NULL DEFAULT 0,
  assists NUMERIC NOT NULL DEFAULT 0,
  shots_total NUMERIC NOT NULL DEFAULT 0,
  shots_on_goal NUMERIC NOT NULL DEFAULT 0,
  yellow_cards NUMERIC NOT NULL DEFAULT 0,
  red_cards NUMERIC NOT NULL DEFAULT 0,
  cards_total NUMERIC NOT NULL DEFAULT 0,
  rating NUMERIC,
  data_updated_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DELETE FROM mart.player_serving_summary;

INSERT INTO mart.player_serving_summary (
  player_id,
  player_name,
  team_id,
  team_name,
  position_name,
  nationality,
  team_count,
  recent_teams,
  recent_teams_5,
  matches_played,
  minutes_played,
  goals,
  assists,
  shots_total,
  shots_on_goal,
  yellow_cards,
  red_cards,
  cards_total,
  rating,
  data_updated_at,
  updated_at
)
WITH base AS (
  SELECT
    pms.player_id,
    pms.player_name,
    pms.team_id,
    COALESCE(pms.team_name, dt.team_name) AS team_name,
    pms.position_name,
    pms.match_id,
    pms.match_date,
    COALESCE(pms.minutes_played, 0) AS minutes_played,
    COALESCE(pms.goals, 0) AS goals,
    COALESCE(pms.assists, 0) AS assists,
    COALESCE(pms.shots_total, 0) AS shots_total,
    COALESCE(pms.shots_on_goal, 0) AS shots_on_goal,
    COALESCE(pms.yellow_cards, 0) AS yellow_cards,
    COALESCE(pms.red_cards, 0) AS red_cards,
    pms.rating,
    pms.updated_at
  FROM mart.player_match_summary pms
  LEFT JOIN mart.dim_team dt
    ON dt.team_id = pms.team_id
),
aggregated AS (
  SELECT
    player_id,
    MAX(player_name) AS player_name,
    COUNT(DISTINCT match_id)::int AS matches_played,
    COUNT(DISTINCT team_id) FILTER (WHERE team_id IS NOT NULL)::int AS team_count,
    SUM(minutes_played)::numeric AS minutes_played,
    SUM(goals)::numeric AS goals,
    SUM(assists)::numeric AS assists,
    SUM(shots_total)::numeric AS shots_total,
    SUM(shots_on_goal)::numeric AS shots_on_goal,
    SUM(yellow_cards)::numeric AS yellow_cards,
    SUM(red_cards)::numeric AS red_cards,
    SUM(yellow_cards + red_cards)::numeric AS cards_total,
    AVG(rating)::numeric AS rating,
    MAX(updated_at) AS data_updated_at
  FROM base
  GROUP BY player_id
),
latest_context AS (
  SELECT DISTINCT ON (player_id)
    player_id,
    team_id,
    team_name,
    position_name
  FROM base
  ORDER BY player_id, match_date DESC NULLS LAST, match_id DESC
),
ranked_teams AS (
  SELECT
    team_context.player_id,
    team_context.team_id,
    team_context.team_name,
    team_context.last_match_date,
    team_context.last_match_id,
    ROW_NUMBER() OVER (
      PARTITION BY team_context.player_id
      ORDER BY team_context.last_match_date DESC NULLS LAST, team_context.last_match_id DESC
    ) AS recent_team_rank
  FROM (
    SELECT
      player_id,
      team_id,
      MAX(team_name) AS team_name,
      MAX(match_date) AS last_match_date,
      MAX(match_id) AS last_match_id
    FROM base
    WHERE team_id IS NOT NULL
    GROUP BY player_id, team_id
  ) team_context
),
recent_teams AS (
  SELECT
    player_id,
    JSONB_AGG(
      JSONB_BUILD_OBJECT(
        'teamId', team_id::text,
        'teamName', team_name
      )
      ORDER BY last_match_date DESC NULLS LAST, last_match_id DESC
    ) FILTER (WHERE recent_team_rank <= 3) AS recent_teams,
    JSONB_AGG(
      JSONB_BUILD_OBJECT(
        'teamId', team_id::text,
        'teamName', team_name
      )
      ORDER BY last_match_date DESC NULLS LAST, last_match_id DESC
    ) FILTER (WHERE recent_team_rank <= 5) AS recent_teams_5
  FROM ranked_teams
  GROUP BY player_id
)
SELECT
  a.player_id,
  a.player_name,
  lc.team_id,
  lc.team_name,
  lc.position_name,
  dp.nationality,
  a.team_count,
  COALESCE(rt.recent_teams, '[]'::jsonb) AS recent_teams,
  COALESCE(rt.recent_teams_5, '[]'::jsonb) AS recent_teams_5,
  a.matches_played,
  a.minutes_played,
  a.goals,
  a.assists,
  a.shots_total,
  a.shots_on_goal,
  a.yellow_cards,
  a.red_cards,
  a.cards_total,
  a.rating,
  a.data_updated_at,
  now() AS updated_at
FROM aggregated a
LEFT JOIN latest_context lc
  ON lc.player_id = a.player_id
LEFT JOIN recent_teams rt
  ON rt.player_id = a.player_id
LEFT JOIN mart.dim_player dp
  ON dp.player_id = a.player_id;

CREATE INDEX IF NOT EXISTS idx_mart_player_serving_summary_goals
  ON mart.player_serving_summary (goals DESC, player_id);
CREATE INDEX IF NOT EXISTS idx_mart_player_serving_summary_assists
  ON mart.player_serving_summary (assists DESC, player_id);
CREATE INDEX IF NOT EXISTS idx_mart_player_serving_summary_minutes
  ON mart.player_serving_summary (minutes_played DESC, player_id);
CREATE INDEX IF NOT EXISTS idx_mart_player_serving_summary_rating
  ON mart.player_serving_summary (rating DESC, player_id);
CREATE INDEX IF NOT EXISTS idx_mart_player_serving_summary_player_name
  ON mart.player_serving_summary (player_name, player_id);
CREATE INDEX IF NOT EXISTS idx_mart_player_serving_summary_team
  ON mart.player_serving_summary (team_id, player_id);

-- migrate:down
DROP TABLE IF EXISTS mart.player_serving_summary;
