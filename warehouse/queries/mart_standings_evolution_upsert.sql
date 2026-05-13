WITH match_rows AS (
  SELECT
    f.season,
    COALESCE((regexp_match(f.round, '([0-9]+)'))[1]::INT, 0) AS round,
    f.date_utc,
    f.fixture_id,
    f.home_team_id AS team_id,
    COALESCE(f.home_goals, 0) AS goals_for,
    COALESCE(f.away_goals, 0) AS goals_against,
    CASE
      WHEN COALESCE(f.home_goals, 0) > COALESCE(f.away_goals, 0) THEN 3
      WHEN COALESCE(f.home_goals, 0) = COALESCE(f.away_goals, 0) THEN 1
      ELSE 0
    END AS points_round,
    CASE WHEN COALESCE(f.home_goals, 0) > COALESCE(f.away_goals, 0) THEN 1 ELSE 0 END AS wins_round
  FROM raw.fixtures f
  WHERE f.home_team_id IS NOT NULL
    AND f.league_id = :league_id
    AND f.season = :season

  UNION ALL

  SELECT
    f.season,
    COALESCE((regexp_match(f.round, '([0-9]+)'))[1]::INT, 0) AS round,
    f.date_utc,
    f.fixture_id,
    f.away_team_id AS team_id,
    COALESCE(f.away_goals, 0) AS goals_for,
    COALESCE(f.home_goals, 0) AS goals_against,
    CASE
      WHEN COALESCE(f.away_goals, 0) > COALESCE(f.home_goals, 0) THEN 3
      WHEN COALESCE(f.away_goals, 0) = COALESCE(f.home_goals, 0) THEN 1
      ELSE 0
    END AS points_round,
    CASE WHEN COALESCE(f.away_goals, 0) > COALESCE(f.home_goals, 0) THEN 1 ELSE 0 END AS wins_round
  FROM raw.fixtures f
  WHERE f.away_team_id IS NOT NULL
    AND f.league_id = :league_id
    AND f.season = :season
),
per_round AS (
  SELECT
    season,
    round,
    team_id,
    MIN(date_utc) AS round_date_utc,
    MIN(fixture_id) AS round_fixture_id,
    SUM(points_round)::INT AS points_round,
    SUM(goals_for)::INT AS goals_for_round,
    SUM(goals_for - goals_against)::INT AS goal_diff_round,
    SUM(wins_round)::INT AS wins_round
  FROM match_rows
  GROUP BY season, round, team_id
),
accumulated AS (
  SELECT
    season,
    round,
    team_id,
    SUM(points_round) OVER (
      PARTITION BY season, team_id
      ORDER BY round_date_utc, round, round_fixture_id
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )::INT AS points_accumulated,
    SUM(goals_for_round) OVER (
      PARTITION BY season, team_id
      ORDER BY round_date_utc, round, round_fixture_id
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )::INT AS goals_for_accumulated,
    SUM(goal_diff_round) OVER (
      PARTITION BY season, team_id
      ORDER BY round_date_utc, round, round_fixture_id
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )::INT AS goal_diff_accumulated,
    SUM(wins_round) OVER (
      PARTITION BY season, team_id
      ORDER BY round_date_utc, round, round_fixture_id
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )::INT AS wins_accumulated
  FROM per_round
),
ranked AS (
  SELECT
    season,
    round,
    team_id,
    points_accumulated,
    goals_for_accumulated,
    goal_diff_accumulated,
    DENSE_RANK() OVER (
      PARTITION BY season, round
      ORDER BY
        points_accumulated DESC,
        wins_accumulated DESC,
        goal_diff_accumulated DESC,
        goals_for_accumulated DESC,
        team_id ASC
    )::INT AS position
  FROM accumulated
)
INSERT INTO mart.standings_evolution (
  season,
  round,
  team_id,
  points_accumulated,
  goals_for_accumulated,
  goal_diff_accumulated,
  position,
  updated_at
)
SELECT
  season,
  round,
  team_id,
  points_accumulated,
  goals_for_accumulated,
  goal_diff_accumulated,
  position,
  now()
FROM ranked
ON CONFLICT (season, round, team_id) DO UPDATE
SET
  points_accumulated = EXCLUDED.points_accumulated,
  goals_for_accumulated = EXCLUDED.goals_for_accumulated,
  goal_diff_accumulated = EXCLUDED.goal_diff_accumulated,
  position = EXCLUDED.position,
  updated_at = now()
WHERE mart.standings_evolution.points_accumulated IS DISTINCT FROM EXCLUDED.points_accumulated
   OR mart.standings_evolution.goals_for_accumulated IS DISTINCT FROM EXCLUDED.goals_for_accumulated
   OR mart.standings_evolution.goal_diff_accumulated IS DISTINCT FROM EXCLUDED.goal_diff_accumulated
   OR mart.standings_evolution.position IS DISTINCT FROM EXCLUDED.position;
