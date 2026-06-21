with source_events as (
    select * from {{ source('postgres_raw', 'match_events') }}
),
statsbomb_events as (
    select
        e.*,
        m.match_date
    from {{ source('postgres_raw', 'statsbomb_events') }} e
    left join {{ source('postgres_raw', 'statsbomb_matches') }} m
      on m.source_name = e.source_name
     and m.match_id = e.match_id
    where e.match_identity_status in ('new_external_match', 'linked_to_sportmonks')
      and (
          e.match_identity_status = 'linked_to_sportmonks'
          or m.match_date is not null
      )
)
select
    event_id,
    season,
    fixture_id,
    case
        when time_elapsed is not null and time_elapsed < 0 then null
        else time_elapsed
    end as time_elapsed,
    case
        when time_extra is not null and (time_extra < 0 or time_extra > 30) then null
        else time_extra
    end as time_extra,
    case
        when coalesce(is_time_elapsed_anomalous, false) then true
        when time_elapsed is not null and time_elapsed < 0 then true
        when time_extra is not null and (time_extra < 0 or time_extra > 30) then true
        else false
    end as is_time_elapsed_anomalous,
    team_id,
    team_name,
    player_id,
    player_name,
    assist_id as assist_player_id,
    assist_name as assist_player_name,
    type as event_type,
    detail as event_detail,
    comments,
    ingested_run,
    updated_at
from source_events

union all

select
    concat('statsbomb:', event_id) as event_id,
    extract(year from match_date)::int as season,
    case
        when match_identity_status = 'linked_to_sportmonks' then local_match_id
        else 900000000000 + match_id
    end as fixture_id,
    minute as time_elapsed,
    cast(null as int) as time_extra,
    false as is_time_elapsed_anomalous,
    case
        when match_identity_status = 'linked_to_sportmonks' and local_team_id is not null then local_team_id
        when source_team_id is not null then 910000000000 + source_team_id
        else null
    end as team_id,
    source_team_name as team_name,
    case
        when player_identity_status = 'linked_to_sportmonks' and local_player_id is not null then local_player_id
        when source_player_id is not null then 920000000000 + source_player_id
        else null
    end as player_id,
    source_player_name as player_name,
    cast(null as bigint) as assist_player_id,
    cast(null as text) as assist_player_name,
    case
        when event_type = 'Shot' and payload -> 'shot' -> 'outcome' ->> 'name' = 'Goal' then 'Goal'
        else event_type
    end as event_type,
    coalesce(
        payload -> 'shot' -> 'outcome' ->> 'name',
        payload -> 'pass' -> 'outcome' ->> 'name',
        event_type
    ) as event_detail,
    cast(null as text) as comments,
    coalesce(
        to_char(updated_at::timestamp at time zone 'UTC', 'YYYY-MM-DD"T"HH24MISS"Z"'),
        '2026-06-19T000000Z'
    ) as ingested_run,
    updated_at
from statsbomb_events
where event_id is not null
  and (
      (match_identity_status = 'linked_to_sportmonks' and local_match_id is not null)
      or match_identity_status = 'new_external_match'
  )
