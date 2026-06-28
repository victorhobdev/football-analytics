{{ config(materialized='view') }}

with source_appearances as (
    select * from {{ source('postgres_raw', 'tm_appearances') }}
)
select
    a.record_hash as tm_appearance_id,
    nullif(trim(a.appearance_id), '') as source_appearance_id,
    mi.match_id,
    pi.player_id,
    pi.player_sk,
    nullif(trim(a.game_id), '') as tm_game_id,
    nullif(trim(a.player_id), '') as tm_player_id,
    nullif(trim(a.player_name), '') as player_name,
    nullif(trim(a.player_club_id), '') as player_club_id,
    nullif(trim(a.player_current_club_id), '') as player_current_club_id,
    nullif(trim(a.competition_id), '') as tm_competition_id,
    case when nullif(trim(a.match_date_raw), '') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then trim(a.match_date_raw)::date else null end as match_date,
    case when nullif(trim(a.yellow_cards), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(a.yellow_cards)::numeric::int else null end as yellow_cards,
    case when nullif(trim(a.red_cards), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(a.red_cards)::numeric::int else null end as red_cards,
    case when nullif(trim(a.goals), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(a.goals)::numeric::int else null end as goals,
    case when nullif(trim(a.assists), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(a.assists)::numeric::int else null end as assists,
    case when nullif(trim(a.minutes_played), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(a.minutes_played)::numeric::int else null end as minutes_played,
    a.ingested_at,
    'transfermarkt' as source_provider
from source_appearances a
inner join {{ ref('stg_tm_match_identity') }} mi
  on mi.tm_game_id = a.game_id
inner join {{ ref('stg_tm_player_identity') }} pi
  on pi.tm_player_id = a.player_id
where mi.match_id is not null
