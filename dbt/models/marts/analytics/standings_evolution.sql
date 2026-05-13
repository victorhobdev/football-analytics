with fixtures as (
    select * from {{ source('postgres_raw', 'fixtures') }}
),
matches as (
    select * from {{ ref('fact_matches') }}
),
match_rows as (
    select
        m.season,
        coalesce((regexp_match(f.round, '([0-9]+)'))[1]::int, 0) as round,
        m.date_day,
        m.match_id,
        m.home_team_id as team_id,
        coalesce(m.home_goals, 0) as goals_for,
        coalesce(m.away_goals, 0) as goals_against,
        case
            when coalesce(m.home_goals, 0) > coalesce(m.away_goals, 0) then 3
            when coalesce(m.home_goals, 0) = coalesce(m.away_goals, 0) then 1
            else 0
        end as points_round,
        case when coalesce(m.home_goals, 0) > coalesce(m.away_goals, 0) then 1 else 0 end as wins_round
    from matches m
    inner join fixtures f
      on f.fixture_id = m.match_id

    union all

    select
        m.season,
        coalesce((regexp_match(f.round, '([0-9]+)'))[1]::int, 0) as round,
        m.date_day,
        m.match_id,
        m.away_team_id as team_id,
        coalesce(m.away_goals, 0) as goals_for,
        coalesce(m.home_goals, 0) as goals_against,
        case
            when coalesce(m.away_goals, 0) > coalesce(m.home_goals, 0) then 3
            when coalesce(m.away_goals, 0) = coalesce(m.home_goals, 0) then 1
            else 0
        end as points_round,
        case when coalesce(m.away_goals, 0) > coalesce(m.home_goals, 0) then 1 else 0 end as wins_round
    from matches m
    inner join fixtures f
      on f.fixture_id = m.match_id
),
per_round as (
    select
        season,
        round,
        team_id,
        min(date_day) as round_date,
        min(match_id) as round_match_id,
        sum(points_round)::int as points_round,
        sum(goals_for)::int as goals_for_round,
        sum(goals_for - goals_against)::int as goal_diff_round,
        sum(wins_round)::int as wins_round
    from match_rows
    group by season, round, team_id
),
accumulated as (
    select
        season,
        round,
        team_id,
        sum(points_round) over (
            partition by season, team_id
            order by round_date, round, round_match_id
            rows between unbounded preceding and current row
        )::int as points_accumulated,
        sum(goals_for_round) over (
            partition by season, team_id
            order by round_date, round, round_match_id
            rows between unbounded preceding and current row
        )::int as goals_for_accumulated,
        sum(goal_diff_round) over (
            partition by season, team_id
            order by round_date, round, round_match_id
            rows between unbounded preceding and current row
        )::int as goal_diff_accumulated,
        sum(wins_round) over (
            partition by season, team_id
            order by round_date, round, round_match_id
            rows between unbounded preceding and current row
        )::int as wins_accumulated
    from per_round
),
ranked as (
    select
        season,
        round,
        team_id,
        points_accumulated,
        goals_for_accumulated,
        goal_diff_accumulated,
        dense_rank() over (
            partition by season, round
            order by
                points_accumulated desc,
                wins_accumulated desc,
                goal_diff_accumulated desc,
                goals_for_accumulated desc,
                team_id asc
        )::int as position
    from accumulated
)
select * from ranked
