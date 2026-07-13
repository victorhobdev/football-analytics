-- Contrato SQL da FactTeamMatch que o Power Query deriva de mart.fact_matches.
-- Exclui partidas sem placar; nao usa mart.int_team_match_rows, que coalesce placares nulos a zero.
with valid_matches as (
    select
        provider,
        competition_key,
        season_label,
        match_id,
        date_day,
        home_team_id,
        away_team_id,
        home_goals,
        away_goals
    from mart.fact_matches
    where home_goals is not null
      and away_goals is not null
      and home_team_id is not null
      and away_team_id is not null
),
fact_team_match as (
    select
        provider, competition_key, season_label, match_id, date_day,
        home_team_id as team_id,
        'home'::text as venue,
        home_goals as goals_for,
        away_goals as goals_against
    from valid_matches
    union all
    select
        provider, competition_key, season_label, match_id, date_day,
        away_team_id as team_id,
        'away'::text as venue,
        away_goals as goals_for,
        home_goals as goals_against
    from valid_matches
),
scored as (
    select
        *,
        case when goals_for > goals_against then 1 else 0 end as wins,
        case when goals_for = goals_against then 1 else 0 end as draws,
        case when goals_for < goals_against then 1 else 0 end as losses,
        case when goals_for > goals_against then 3 when goals_for = goals_against then 1 else 0 end as points
    from fact_team_match
)
select
    s.provider,
    s.competition_key,
    s.season_label,
    s.team_id,
    coalesce(dt.team_name, s.team_id::text) as team_name,
    count(*)::int as matches,
    sum(s.wins)::int as wins,
    sum(s.draws)::int as draws,
    sum(s.losses)::int as losses,
    sum(s.points)::int as points,
    round(sum(s.points)::numeric / nullif(count(*), 0), 3) as points_per_game,
    sum(s.goals_for)::int as goals_for,
    sum(s.goals_against)::int as goals_against,
    sum(s.goals_for - s.goals_against)::int as goal_difference,
    sum(s.points) filter (where s.venue = 'home')::int as home_points,
    sum(s.points) filter (where s.venue = 'away')::int as away_points,
    round(avg(s.points) filter (where s.venue = 'home'), 3) as home_points_per_game,
    round(avg(s.points) filter (where s.venue = 'away'), 3) as away_points_per_game
from scored s
left join mart.dim_team dt on dt.team_id = s.team_id
group by s.provider, s.competition_key, s.season_label, s.team_id, dt.team_name
order by s.provider, s.competition_key, s.season_label, points desc, goal_difference desc, goals_for desc, team_name;
