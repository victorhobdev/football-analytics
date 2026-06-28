-- migrate:up

CREATE SCHEMA IF NOT EXISTS mart;

DROP MATERIALIZED VIEW IF EXISTS mart.match_depth_profile;

CREATE MATERIALIZED VIEW mart.match_depth_profile AS
WITH match_base AS (
  SELECT
    match_id,
    max(competition_key) AS competition_key,
    max(season_label) AS season_label,
    max(date_day) AS match_date,
    max(home_team_id) AS home_team_id,
    max(away_team_id) AS away_team_id,
    max(home_goals) AS home_goals,
    max(away_goals) AS away_goals
  FROM mart.fact_matches
  WHERE match_id IS NOT NULL
    AND competition_key IS NOT NULL
  GROUP BY match_id
),
odds AS (
  SELECT
    match_id,
    count(*)::integer AS odds_rows,
    count(*) FILTER (
      WHERE odd_home IS NOT NULL
        AND odd_draw IS NOT NULL
        AND odd_away IS NOT NULL
    )::integer AS valid_1x2_rows,
    count(*) FILTER (
      WHERE over25 IS NOT NULL
        AND under25 IS NOT NULL
    )::integer AS valid_goal_line_rows,
    count(*) FILTER (
      WHERE handicap_size IS NOT NULL
        AND handicap_home IS NOT NULL
        AND handicap_away IS NOT NULL
    )::integer AS valid_handicap_rows
  FROM mart.fact_match_odds
  WHERE match_id IS NOT NULL
  GROUP BY match_id
),
team_stats AS (
  SELECT
    match_id,
    count(*)::integer AS team_stat_rows,
    count(DISTINCT side) FILTER (WHERE side IN ('home', 'away'))::integer AS valid_sides,
    count(*) FILTER (
      WHERE side IN ('home', 'away')
        AND (team_id IS NOT NULL OR nullif(trim(team_name), '') IS NOT NULL)
        AND (
          elo_rating IS NOT NULL
          OR form3 IS NOT NULL
          OR form5 IS NOT NULL
          OR shots IS NOT NULL
          OR shots_on_target IS NOT NULL
          OR fouls IS NOT NULL
          OR corners IS NOT NULL
          OR yellow_cards IS NOT NULL
          OR red_cards IS NOT NULL
          OR half_time_goals IS NOT NULL
          OR full_time_goals IS NOT NULL
        )
    )::integer AS valid_team_stat_rows
  FROM mart.fact_elo_match_team_stats
  WHERE match_id IS NOT NULL
  GROUP BY match_id
),
native_events AS (
  SELECT
    match_id,
    count(*)::integer AS native_event_rows,
    count(*) FILTER (
      WHERE event_type IS NOT NULL
        AND time_elapsed IS NOT NULL
        AND (team_id IS NOT NULL OR team_sk IS NOT NULL)
    )::integer AS valid_native_event_rows
  FROM mart.fact_match_events
  WHERE match_id IS NOT NULL
  GROUP BY match_id
),
tm_events AS (
  SELECT
    match_id,
    count(*)::integer AS transfermarkt_event_rows,
    count(*) FILTER (
      WHERE event_type IS NOT NULL
        AND minute IS NOT NULL
        AND (tm_club_id IS NOT NULL OR nullif(trim(club_name), '') IS NOT NULL)
    )::integer AS valid_transfermarkt_event_rows
  FROM mart.fact_transfermarkt_match_events
  WHERE match_id IS NOT NULL
  GROUP BY match_id
),
statsbomb_events AS (
  SELECT
    local_match_id AS match_id,
    count(*)::integer AS statsbomb_event_rows,
    count(*) FILTER (
      WHERE event_type IS NOT NULL
        AND minute IS NOT NULL
        AND (local_team_id IS NOT NULL OR nullif(trim(source_team_name), '') IS NOT NULL)
    )::integer AS valid_statsbomb_event_rows
  FROM mart.fact_statsbomb_match_event
  WHERE local_match_id IS NOT NULL
  GROUP BY local_match_id
),
tm_lineups AS (
  SELECT
    match_id,
    count(*)::integer AS transfermarkt_lineup_rows,
    count(*) FILTER (
      WHERE (tm_club_id IS NOT NULL OR player_id IS NOT NULL)
        AND (player_id IS NOT NULL OR tm_player_id IS NOT NULL OR nullif(trim(player_name), '') IS NOT NULL)
        AND nullif(trim(lineup_type), '') IS NOT NULL
    )::integer AS valid_transfermarkt_lineup_rows
  FROM mart.fact_transfermarkt_lineups
  WHERE match_id IS NOT NULL
  GROUP BY match_id
),
statsbomb_lineups AS (
  SELECT
    local_match_id AS match_id,
    count(*)::integer AS statsbomb_lineup_rows,
    count(*) FILTER (
      WHERE (local_team_id IS NOT NULL OR nullif(trim(source_team_name), '') IS NOT NULL)
        AND (local_player_id IS NOT NULL OR source_player_id IS NOT NULL OR nullif(trim(source_player_name), '') IS NOT NULL)
    )::integer AS valid_statsbomb_lineup_rows
  FROM mart.fact_statsbomb_lineup_slot
  WHERE local_match_id IS NOT NULL
  GROUP BY local_match_id
),
player_stats AS (
  SELECT
    match_id,
    count(*)::integer AS player_stat_rows,
    count(*) FILTER (
      WHERE (player_id IS NOT NULL OR nullif(trim(player_name), '') IS NOT NULL)
        AND (team_id IS NOT NULL OR nullif(trim(team_name), '') IS NOT NULL)
        AND (
          minutes_played IS NOT NULL
          OR goals IS NOT NULL
          OR assists IS NOT NULL
          OR shots_total IS NOT NULL
          OR shots_on_goal IS NOT NULL
          OR passes_total IS NOT NULL
          OR key_passes IS NOT NULL
          OR tackles IS NOT NULL
          OR interceptions IS NOT NULL
          OR duels IS NOT NULL
          OR fouls_committed IS NOT NULL
          OR yellow_cards IS NOT NULL
          OR red_cards IS NOT NULL
          OR goalkeeper_saves IS NOT NULL
          OR xg IS NOT NULL
          OR rating IS NOT NULL
        )
    )::integer AS valid_player_stat_rows
  FROM mart.player_match_summary
  WHERE match_id IS NOT NULL
  GROUP BY match_id
),
profile AS (
  SELECT
    b.match_id,
    b.competition_key,
    b.season_label,
    b.match_date,
    b.home_team_id,
    b.away_team_id,
    b.home_goals,
    b.away_goals,
    (b.match_date IS NOT NULL AND b.home_team_id IS NOT NULL AND b.away_team_id IS NOT NULL) AS has_match_context,
    (b.home_goals IS NOT NULL AND b.away_goals IS NOT NULL) AS has_score,
    coalesce(o.odds_rows, 0) AS odds_rows,
    coalesce(o.valid_1x2_rows, 0) AS valid_1x2_rows,
    coalesce(o.valid_goal_line_rows, 0) AS valid_goal_line_rows,
    coalesce(o.valid_handicap_rows, 0) AS valid_handicap_rows,
    coalesce(ts.team_stat_rows, 0) AS team_stat_rows,
    coalesce(ts.valid_team_stat_rows, 0) AS valid_team_stat_rows,
    coalesce(ne.native_event_rows, 0) AS native_event_rows,
    coalesce(ne.valid_native_event_rows, 0) AS valid_native_event_rows,
    coalesce(tme.transfermarkt_event_rows, 0) AS transfermarkt_event_rows,
    coalesce(tme.valid_transfermarkt_event_rows, 0) AS valid_transfermarkt_event_rows,
    coalesce(sbe.statsbomb_event_rows, 0) AS statsbomb_event_rows,
    coalesce(sbe.valid_statsbomb_event_rows, 0) AS valid_statsbomb_event_rows,
    coalesce(tml.transfermarkt_lineup_rows, 0) AS transfermarkt_lineup_rows,
    coalesce(tml.valid_transfermarkt_lineup_rows, 0) AS valid_transfermarkt_lineup_rows,
    coalesce(sbl.statsbomb_lineup_rows, 0) AS statsbomb_lineup_rows,
    coalesce(sbl.valid_statsbomb_lineup_rows, 0) AS valid_statsbomb_lineup_rows,
    coalesce(ps.player_stat_rows, 0) AS player_stat_rows,
    coalesce(ps.valid_player_stat_rows, 0) AS valid_player_stat_rows,
    coalesce(ts.valid_sides, 0) AS valid_team_stat_sides
  FROM match_base b
  LEFT JOIN odds o ON o.match_id = b.match_id
  LEFT JOIN team_stats ts ON ts.match_id = b.match_id
  LEFT JOIN native_events ne ON ne.match_id = b.match_id
  LEFT JOIN tm_events tme ON tme.match_id = b.match_id
  LEFT JOIN statsbomb_events sbe ON sbe.match_id = b.match_id
  LEFT JOIN tm_lineups tml ON tml.match_id = b.match_id
  LEFT JOIN statsbomb_lineups sbl ON sbl.match_id = b.match_id
  LEFT JOIN player_stats ps ON ps.match_id = b.match_id
),
flags AS (
  SELECT
    *,
    (valid_1x2_rows > 0) AS has_odds,
    (valid_team_stat_sides = 2 AND valid_team_stat_rows >= 2) AS has_team_stats,
    ((valid_native_event_rows + valid_transfermarkt_event_rows + valid_statsbomb_event_rows) > 0) AS has_events,
    ((valid_transfermarkt_lineup_rows + valid_statsbomb_lineup_rows) > 0) AS has_lineups,
    (valid_player_stat_rows > 0) AS has_player_stats,
    ((valid_transfermarkt_lineup_rows + valid_statsbomb_lineup_rows + valid_player_stat_rows) > 0) AS has_player_layer
  FROM profile
)
SELECT
  match_id,
  competition_key,
  season_label,
  match_date,
  home_team_id,
  away_team_id,
  home_goals,
  away_goals,
  has_match_context,
  has_score,
  has_odds,
  has_team_stats,
  has_events,
  has_lineups,
  has_player_stats,
  has_player_layer,
  (has_team_stats AND has_events AND has_player_layer) AS has_minimum_rich_depth,
  odds_rows,
  valid_1x2_rows,
  valid_goal_line_rows,
  valid_handicap_rows,
  team_stat_rows,
  valid_team_stat_rows,
  native_event_rows,
  valid_native_event_rows,
  transfermarkt_event_rows,
  valid_transfermarkt_event_rows,
  statsbomb_event_rows,
  valid_statsbomb_event_rows,
  transfermarkt_lineup_rows,
  valid_transfermarkt_lineup_rows,
  statsbomb_lineup_rows,
  valid_statsbomb_lineup_rows,
  player_stat_rows,
  valid_player_stat_rows,
  (valid_native_event_rows + valid_transfermarkt_event_rows + valid_statsbomb_event_rows) AS valid_event_rows,
  (valid_transfermarkt_lineup_rows + valid_statsbomb_lineup_rows) AS valid_lineup_rows,
  array_remove(ARRAY[
    CASE WHEN has_score THEN 'score' END,
    CASE WHEN has_odds THEN 'odds' END,
    CASE WHEN has_team_stats THEN 'team_stats' END,
    CASE WHEN has_events THEN 'events' END,
    CASE WHEN has_lineups THEN 'lineups' END,
    CASE WHEN has_player_stats THEN 'player_stats' END
  ], NULL) AS safe_sections,
  (
    CASE WHEN has_score THEN 1 ELSE 0 END
    + CASE WHEN has_odds THEN 1 ELSE 0 END
    + CASE WHEN has_team_stats THEN 1 ELSE 0 END
    + CASE WHEN has_events THEN 1 ELSE 0 END
    + CASE WHEN has_lineups THEN 1 ELSE 0 END
    + CASE WHEN has_player_stats THEN 1 ELSE 0 END
  ) AS depth_score,
  now() AS refreshed_at
FROM flags;

CREATE UNIQUE INDEX idx_match_depth_profile_match_id
  ON mart.match_depth_profile (match_id);

CREATE INDEX idx_match_depth_profile_competition_season
  ON mart.match_depth_profile (competition_key, season_label);

CREATE INDEX idx_match_depth_profile_depth_score
  ON mart.match_depth_profile (depth_score DESC, match_date DESC);

-- migrate:down

DROP MATERIALIZED VIEW IF EXISTS mart.match_depth_profile;
