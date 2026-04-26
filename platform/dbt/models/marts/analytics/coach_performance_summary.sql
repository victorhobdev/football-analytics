with tenures as (
    select * from {{ ref('stg_team_coaches') }}
),
dim_coaches as (
    select * from {{ ref('dim_coach') }}
),
dim_teams as (
    select
        team_sk,
        team_id,
        team_name
    from {{ ref('dim_team') }}
),
team_match_rows as (
    select
        match_id,
        date_day,
        home_team_id as team_id,
        case
            when coalesce(home_goals, 0) > coalesce(away_goals, 0) then 'W'
            when coalesce(home_goals, 0) = coalesce(away_goals, 0) then 'D'
            else 'L'
        end as result,
        case
            when coalesce(home_goals, 0) > coalesce(away_goals, 0) then 3
            when coalesce(home_goals, 0) = coalesce(away_goals, 0) then 1
            else 0
        end as points
    from {{ ref('fact_matches') }}

    union all

    select
        match_id,
        date_day,
        away_team_id as team_id,
        case
            when coalesce(away_goals, 0) > coalesce(home_goals, 0) then 'W'
            when coalesce(away_goals, 0) = coalesce(home_goals, 0) then 'D'
            else 'L'
        end as result,
        case
            when coalesce(away_goals, 0) > coalesce(home_goals, 0) then 3
            when coalesce(away_goals, 0) = coalesce(home_goals, 0) then 1
            else 0
        end as points
    from {{ ref('fact_matches') }}
),
tenure_matches as (
    select
        t.provider,
        t.coach_tenure_id,
        t.coach_id,
        t.team_id,
        t.start_date,
        t.end_date,
        m.match_id,
        m.result,
        m.points
    from tenures t
    join team_match_rows m
      on m.team_id = t.team_id
     and m.date_day >= coalesce(t.start_date, date '1900-01-01')
     and m.date_day <= coalesce(t.end_date, date '2999-12-31')
)
select
    tm.provider,
    tm.coach_tenure_id,
    dc.coach_sk,
    tm.coach_id,
    coalesce(dc.coach_name, 'Nome indisponivel') as coach_name,
    dc.image_path,
    coalesce(dc.has_real_photo, false) as has_real_photo,
    coalesce(dc.is_placeholder_image, false) as is_placeholder_image,
    dt.team_sk,
    tm.team_id,
    coalesce(dt.team_name, 'Time indisponivel') as team_name,
    tm.start_date,
    tm.end_date,
    count(distinct tm.match_id) as matches,
    sum(case when tm.result = 'W' then 1 else 0 end) as wins,
    sum(case when tm.result = 'D' then 1 else 0 end) as draws,
    sum(case when tm.result = 'L' then 1 else 0 end) as losses,
    sum(tm.points) as points,
    case
        when count(distinct tm.match_id) > 0 then round(sum(tm.points)::numeric / count(distinct tm.match_id), 4)
        else null
    end as points_per_match
from tenure_matches tm
left join dim_coaches dc
  on dc.provider = tm.provider
 and dc.coach_id = tm.coach_id
left join dim_teams dt
  on dt.team_id = tm.team_id
group by
    tm.provider,
    tm.coach_tenure_id,
    dc.coach_sk,
    tm.coach_id,
    dc.coach_name,
    dc.image_path,
    dc.has_real_photo,
    dc.is_placeholder_image,
    dt.team_sk,
    tm.team_id,
    dt.team_name,
    tm.start_date,
    tm.end_date
