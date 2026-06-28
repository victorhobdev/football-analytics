{{ config(materialized='view') }}

with source_valuations as (
    select * from {{ source('postgres_raw', 'tm_player_valuations') }}
),
linked_players as (
    select
        tm_player_id,
        local_player_id
    from control.tm_player_xref
    where identity_status = 'linked_to_local_player'
      and review_status = 'auto_approved'
      and local_player_id is not null
)
select
    sv.record_hash as tm_valuation_id,
    lp.local_player_id as player_id,
    md5(concat('player:', lp.local_player_id::text)) as player_sk,
    nullif(trim(sv.player_id), '') as tm_player_id,
    case
        when nullif(trim(sv.valuation_date_raw), '') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            then trim(sv.valuation_date_raw)::date
        else null
    end as valuation_date,
    case
        when nullif(trim(sv.market_value_in_eur), '') ~ '^-?[0-9]+(\.[0-9]+)?$'
            then trim(sv.market_value_in_eur)::numeric
        else null
    end as market_value_eur,
    nullif(trim(sv.current_club_id), '') as current_club_id,
    nullif(trim(sv.current_club_name), '') as current_club_name,
    nullif(trim(sv.player_club_domestic_competition_id), '') as player_club_domestic_competition_id,
    sv.ingested_at,
    'transfermarkt' as source_provider
from source_valuations sv
inner join linked_players lp
  on lp.tm_player_id = sv.player_id
where nullif(trim(sv.player_id), '') is not null
