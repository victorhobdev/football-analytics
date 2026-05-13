with fixtures as (
    select * from {{ source('postgres_raw', 'fixtures') }}
),
stats as (
    select * from {{ source('postgres_raw', 'match_statistics') }}
),
joined as (
    select
        f.fixture_id as match_id,
        f.league_id,
        f.season,
        f.date_utc::date as date_day,
        f.home_team_id,
        f.away_team_id,
        f.venue_id,
        f.home_goals,
        f.away_goals,
        coalesce(f.home_goals, 0) + coalesce(f.away_goals, 0) as total_goals,
        case
            when coalesce(f.home_goals, 0) > coalesce(f.away_goals, 0) then 'Home Win'
            when coalesce(f.home_goals, 0) < coalesce(f.away_goals, 0) then 'Away Win'
            else 'Draw'
        end as result,
        s_home.total_shots as home_shots,
        s_home.shots_on_goal as home_shots_on_target,
        s_home.ball_possession as home_possession,
        s_home.corner_kicks as home_corners,
        s_home.fouls as home_fouls,
        s_away.total_shots as away_shots,
        s_away.shots_on_goal as away_shots_on_target,
        s_away.ball_possession as away_possession,
        s_away.corner_kicks as away_corners,
        s_away.fouls as away_fouls,
        now() as updated_at
    from fixtures f
    left join stats s_home
      on f.fixture_id = s_home.fixture_id
     and f.home_team_id = s_home.team_id
    left join stats s_away
      on f.fixture_id = s_away.fixture_id
     and f.away_team_id = s_away.team_id
    where f.fixture_id is not null
      and f.date_utc is not null
      and f.home_team_id is not null
      and f.away_team_id is not null
)
select * from joined
