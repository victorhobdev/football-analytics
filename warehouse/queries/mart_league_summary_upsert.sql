WITH aggregated AS (
    SELECT
        league_id,
        league_name,
        season,
        COUNT(*)::INT AS total_matches,
        SUM(COALESCE(home_goals, 0) + COALESCE(away_goals, 0))::INT AS total_goals,
        ROUND(
            SUM(COALESCE(home_goals, 0) + COALESCE(away_goals, 0))::NUMERIC
            / NULLIF(COUNT(*), 0),
            4
        ) AS avg_goals_per_match,
        MIN(date_utc::date) AS first_match_date,
        MAX(date_utc::date) AS last_match_date
    FROM raw.fixtures
    WHERE league_id = :league_id
      AND season = :season
    GROUP BY league_id, league_name, season
),
upserted AS (
    INSERT INTO mart.league_summary (
        league_id, league_name, season, total_matches, total_goals,
        avg_goals_per_match, first_match_date, last_match_date, updated_at
    )
    SELECT
        league_id, league_name, season, total_matches, total_goals,
        avg_goals_per_match, first_match_date, last_match_date, now()
    FROM aggregated
    ON CONFLICT (league_id, season) DO UPDATE
    SET
        league_name = EXCLUDED.league_name,
        total_matches = EXCLUDED.total_matches,
        total_goals = EXCLUDED.total_goals,
        avg_goals_per_match = EXCLUDED.avg_goals_per_match,
        first_match_date = EXCLUDED.first_match_date,
        last_match_date = EXCLUDED.last_match_date,
        updated_at = now()
    WHERE mart.league_summary.league_name IS DISTINCT FROM EXCLUDED.league_name
       OR mart.league_summary.total_matches IS DISTINCT FROM EXCLUDED.total_matches
       OR mart.league_summary.total_goals IS DISTINCT FROM EXCLUDED.total_goals
       OR mart.league_summary.avg_goals_per_match IS DISTINCT FROM EXCLUDED.avg_goals_per_match
       OR mart.league_summary.first_match_date IS DISTINCT FROM EXCLUDED.first_match_date
       OR mart.league_summary.last_match_date IS DISTINCT FROM EXCLUDED.last_match_date
    RETURNING (xmax = 0) AS inserted
)
SELECT
    COALESCE(SUM(CASE WHEN inserted THEN 1 ELSE 0 END), 0)::INT AS inserted,
    COALESCE(SUM(CASE WHEN NOT inserted THEN 1 ELSE 0 END), 0)::INT AS updated
FROM upserted;
