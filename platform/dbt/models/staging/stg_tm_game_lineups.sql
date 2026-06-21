{{ config(materialized='view') }}

with source_lineups as (
    select * from {{ source('postgres_raw', 'tm_game_lineups') }}
)
select
    l.record_hash as tm_lineup_id,
    nullif(trim(l.game_lineups_id), '') as source_lineup_id,
    mi.match_id,
    pi.player_id,
    pi.player_sk,
    nullif(trim(l.game_id), '') as tm_game_id,
    nullif(trim(l.player_id), '') as tm_player_id,
    nullif(trim(l.club_id), '') as tm_club_id,
    nullif(trim(l.player_name), '') as player_name,
    nullif(trim(l.lineup_type), '') as lineup_type,
    nullif(trim(l.position), '') as position_name,
    case when nullif(trim(l.shirt_number), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(l.shirt_number)::numeric::int else null end as shirt_number,
    case
        when lower(nullif(trim(l.team_captain), '')) in ('1', 'true', 't', 'yes') then true
        when lower(nullif(trim(l.team_captain), '')) in ('0', 'false', 'f', 'no') then false
        else null
    end as is_captain,
    case when nullif(trim(l.match_date_raw), '') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then trim(l.match_date_raw)::date else null end as match_date,
    l.ingested_at,
    'transfermarkt' as source_provider
from source_lineups l
inner join {{ ref('stg_tm_match_identity') }} mi
  on mi.tm_game_id = l.game_id
inner join {{ ref('stg_tm_player_identity') }} pi
  on pi.tm_player_id = l.player_id
where mi.match_id is not null
