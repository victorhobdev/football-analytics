-- Resultado de referencia SQL para as medidas DAX de time.
-- Aplique os mesmos filtros de provider, competition_key, season_label e data usados no relatorio.
with valid_matches as (
    select provider, competition_key, season_label, match_id, date_day,
           home_team_id, away_team_id, home_goals, away_goals
    from mart.fact_matches
    where home_goals is not null and away_goals is not null
),
fact_team_match as (
    select provider, competition_key, season_label, match_id, date_day, home_team_id as team_id,
           'home'::text as venue, home_goals as goals_for, away_goals as goals_against
    from valid_matches
    union all
    select provider, competition_key, season_label, match_id, date_day, away_team_id,
           'away'::text, away_goals, home_goals
    from valid_matches
),
scored as (
    select *,
        case when goals_for > goals_against then 1 else 0 end as wins,
        case when goals_for = goals_against then 1 else 0 end as draws,
        case when goals_for < goals_against then 1 else 0 end as losses,
        case when goals_for > goals_against then 3 when goals_for = goals_against then 1 else 0 end as points
    from fact_team_match
)
select
    provider, competition_key, season_label, team_id,
    count(*)::int as matches,
    sum(wins)::int as wins,
    sum(draws)::int as draws,
    sum(losses)::int as losses,
    sum(points)::int as points,
    round(sum(points)::numeric / nullif(count(*), 0), 3) as points_per_game,
    sum(goals_for)::int as goals_for,
    sum(goals_against)::int as goals_against,
    sum(goals_for - goals_against)::int as goal_difference,
    round(avg(points) filter (where venue = 'home'), 3) as home_points_per_game,
    round(avg(points) filter (where venue = 'away'), 3) as away_points_per_game
from scored
group by provider, competition_key, season_label, team_id
order by provider, competition_key, season_label, points desc, goal_difference desc, goals_for desc, team_id;
