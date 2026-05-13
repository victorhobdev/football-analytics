with matches as (
    select * from {{ ref('fact_matches') }}
),
teams as (
    select team_id, team_name from {{ ref('dim_team') }}
),
team_rows as (
    select
        m.season,
        extract(year from m.date_day)::int as year,
        lpad(extract(month from m.date_day)::int::text, 2, '0') as month,
        m.home_team_id as team_id,
        coalesce(m.home_goals, 0) as goals_for,
        coalesce(m.away_goals, 0) as goals_against,
        case when coalesce(m.home_goals, 0) > coalesce(m.away_goals, 0) then 1 else 0 end as wins,
        case when coalesce(m.home_goals, 0) = coalesce(m.away_goals, 0) then 1 else 0 end as draws,
        case when coalesce(m.home_goals, 0) < coalesce(m.away_goals, 0) then 1 else 0 end as losses
    from matches m

    union all

    select
        m.season,
        extract(year from m.date_day)::int as year,
        lpad(extract(month from m.date_day)::int::text, 2, '0') as month,
        m.away_team_id as team_id,
        coalesce(m.away_goals, 0) as goals_for,
        coalesce(m.home_goals, 0) as goals_against,
        case when coalesce(m.away_goals, 0) > coalesce(m.home_goals, 0) then 1 else 0 end as wins,
        case when coalesce(m.away_goals, 0) = coalesce(m.home_goals, 0) then 1 else 0 end as draws,
        case when coalesce(m.away_goals, 0) < coalesce(m.home_goals, 0) then 1 else 0 end as losses
    from matches m
),
aggregated as (
    select
        tr.season,
        tr.year,
        tr.month,
        tr.team_id,
        t.team_name,
        sum(tr.goals_for)::int as goals_for,
        sum(tr.goals_against)::int as goals_against,
        count(*)::int as matches,
        sum(tr.wins)::int as wins,
        sum(tr.draws)::int as draws,
        sum(tr.losses)::int as losses,
        (sum(tr.wins) * 3 + sum(tr.draws))::int as points,
        (sum(tr.goals_for) - sum(tr.goals_against))::int as goal_diff
    from team_rows tr
    left join teams t
      on t.team_id = tr.team_id
    group by tr.season, tr.year, tr.month, tr.team_id, t.team_name
)
select * from aggregated
