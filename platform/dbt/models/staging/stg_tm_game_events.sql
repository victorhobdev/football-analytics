{{ config(materialized='view') }}

with source_events as (
    select * from {{ source('postgres_raw', 'tm_game_events') }}
)
select
    e.record_hash as tm_event_id,
    nullif(trim(e.game_event_id), '') as source_event_id,
    mi.match_id,
    pi.player_id,
    pi.player_sk,
    player_in.player_id as player_in_id,
    player_in.player_sk as player_in_sk,
    player_assist.player_id as assist_player_id,
    player_assist.player_sk as assist_player_sk,
    nullif(trim(e.game_id), '') as tm_game_id,
    nullif(trim(e.player_id), '') as tm_player_id,
    nullif(trim(e.club_id), '') as tm_club_id,
    nullif(trim(e.club_name), '') as club_name,
    case when nullif(trim(e.match_date_raw), '') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then trim(e.match_date_raw)::date else null end as match_date,
    case when nullif(trim(e.minute), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(e.minute)::numeric::int else null end as minute,
    nullif(trim(e.type), '') as event_type,
    nullif(trim(e.description), '') as description,
    e.ingested_at,
    'transfermarkt' as source_provider
from source_events e
inner join {{ ref('stg_tm_match_identity') }} mi
  on mi.tm_game_id = e.game_id
inner join {{ ref('stg_tm_player_identity') }} pi
  on pi.tm_player_id = e.player_id
left join {{ ref('stg_tm_player_identity') }} player_in
  on player_in.tm_player_id = e.player_in_id
left join {{ ref('stg_tm_player_identity') }} player_assist
  on player_assist.tm_player_id = e.player_assist_id
where mi.match_id is not null
