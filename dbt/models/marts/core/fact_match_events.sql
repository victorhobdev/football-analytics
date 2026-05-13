with events as (
    select * from {{ source('postgres_raw', 'match_events') }}
),
matches as (
    select match_id from {{ ref('fact_matches') }}
),
cleaned as (
    select
        e.event_id,
        e.fixture_id as match_id,
        e.team_id,
        e.player_id,
        e.assist_id as assist_player_id,
        e.time_elapsed,
        e.time_extra,
        e.type as event_type,
        e.detail as event_detail,
        case when e.type = 'Goal' then true else false end as is_goal,
        now() as updated_at
    from events e
    inner join matches m
      on m.match_id = e.fixture_id
    where e.event_id is not null
      and e.fixture_id is not null
)
select * from cleaned
