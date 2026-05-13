WITH raw_scope AS (
    SELECT
        season,
        year,
        month,
        home_team_id,
        home_team_name,
        away_team_id,
        away_team_name,
        COALESCE(home_goals, 0) AS home_goals,
        COALESCE(away_goals, 0) AS away_goals
    FROM raw.fixtures
    WHERE league_id = :league_id
      AND season = :season
),
team_rows AS (
    SELECT
        season,
        year,
        month,
        home_team_id AS team_id,
        home_team_name AS team_name,
        home_goals AS goals_for,
        away_goals AS goals_against,
        CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END AS wins,
        CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END AS draws,
        CASE WHEN home_goals < away_goals THEN 1 ELSE 0 END AS losses
    FROM raw_scope
    WHERE home_team_name IS NOT NULL

    UNION ALL

    SELECT
        season,
        year,
        month,
        away_team_id AS team_id,
        away_team_name AS team_name,
        away_goals AS goals_for,
        home_goals AS goals_against,
        CASE WHEN away_goals > home_goals THEN 1 ELSE 0 END AS wins,
        CASE WHEN away_goals = home_goals THEN 1 ELSE 0 END AS draws,
        CASE WHEN away_goals < home_goals THEN 1 ELSE 0 END AS losses
    FROM raw_scope
    WHERE away_team_name IS NOT NULL
),
aggregated AS (
    SELECT
        season,
        year,
        month,
        team_id,
        team_name,
        SUM(goals_for)::INT AS goals_for,
        SUM(goals_against)::INT AS goals_against,
        COUNT(*)::INT AS matches,
        SUM(wins)::INT AS wins,
        SUM(draws)::INT AS draws,
        SUM(losses)::INT AS losses,
        (SUM(wins) * 3 + SUM(draws))::INT AS points,
        (SUM(goals_for) - SUM(goals_against))::INT AS goal_diff
    FROM team_rows
    GROUP BY season, year, month, team_id, team_name
),
upserted AS (
    INSERT INTO mart.team_match_goals_monthly (
        season, year, month, team_id, team_name,
        goals_for, goals_against, matches, wins, draws, losses, points, goal_diff, updated_at
    )
    SELECT
        season, year, month, team_id, team_name,
        goals_for, goals_against, matches, wins, draws, losses, points, goal_diff, now()
    FROM aggregated
    ON CONFLICT (season, year, month, team_name) DO UPDATE
    SET
        team_id = EXCLUDED.team_id,
        goals_for = EXCLUDED.goals_for,
        goals_against = EXCLUDED.goals_against,
        matches = EXCLUDED.matches,
        wins = EXCLUDED.wins,
        draws = EXCLUDED.draws,
        losses = EXCLUDED.losses,
        points = EXCLUDED.points,
        goal_diff = EXCLUDED.goal_diff,
        updated_at = now()
    WHERE mart.team_match_goals_monthly.team_id IS DISTINCT FROM EXCLUDED.team_id
       OR mart.team_match_goals_monthly.goals_for IS DISTINCT FROM EXCLUDED.goals_for
       OR mart.team_match_goals_monthly.goals_against IS DISTINCT FROM EXCLUDED.goals_against
       OR mart.team_match_goals_monthly.matches IS DISTINCT FROM EXCLUDED.matches
       OR mart.team_match_goals_monthly.wins IS DISTINCT FROM EXCLUDED.wins
       OR mart.team_match_goals_monthly.draws IS DISTINCT FROM EXCLUDED.draws
       OR mart.team_match_goals_monthly.losses IS DISTINCT FROM EXCLUDED.losses
       OR mart.team_match_goals_monthly.points IS DISTINCT FROM EXCLUDED.points
       OR mart.team_match_goals_monthly.goal_diff IS DISTINCT FROM EXCLUDED.goal_diff
    RETURNING (xmax = 0) AS inserted
)
SELECT
    COALESCE(SUM(CASE WHEN inserted THEN 1 ELSE 0 END), 0)::INT AS inserted,
    COALESCE(SUM(CASE WHEN NOT inserted THEN 1 ELSE 0 END), 0)::INT AS updated
FROM upserted;
