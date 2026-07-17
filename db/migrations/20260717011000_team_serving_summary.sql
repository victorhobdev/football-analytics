-- migrate:up
DROP TABLE IF EXISTS mart.team_serving_summary;

CREATE TABLE mart.team_serving_summary AS
SELECT
  tr.team_id,
  max(coalesce(dt.team_name, tr.team_id::text)) AS team_name,
  count(*)::int AS matches_played,
  sum(tr.wins)::int AS wins,
  sum(tr.draws)::int AS draws,
  sum(tr.losses)::int AS losses,
  sum(tr.goals_for)::int AS goals_for,
  sum(tr.goals_against)::int AS goals_against,
  sum(tr.goals_for - tr.goals_against)::int AS goal_diff,
  sum(tr.points_round)::int AS points
FROM mart.int_team_match_rows tr
LEFT JOIN mart.dim_team dt ON dt.team_id = tr.team_id
WHERE tr.team_id IS NOT NULL
GROUP BY tr.team_id;

CREATE UNIQUE INDEX idx_mart_team_serving_summary_team
  ON mart.team_serving_summary (team_id);
CREATE INDEX idx_mart_team_serving_summary_points
  ON mart.team_serving_summary (points DESC, team_id);
CREATE INDEX idx_mart_team_serving_summary_goal_diff
  ON mart.team_serving_summary (goal_diff DESC, team_id);
CREATE INDEX idx_mart_team_serving_summary_wins
  ON mart.team_serving_summary (wins DESC, team_id);
CREATE INDEX idx_mart_team_serving_summary_name
  ON mart.team_serving_summary (team_name, team_id);

ANALYZE mart.team_serving_summary;

-- migrate:down
DROP TABLE IF EXISTS mart.team_serving_summary;
