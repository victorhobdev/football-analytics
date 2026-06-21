{{ config(materialized='view') }}

with source_transfers as (
    select * from {{ source('postgres_raw', 'tm_transfers') }}
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
    st.record_hash as tm_transfer_id,
    lp.local_player_id as player_id,
    md5(concat('player:', lp.local_player_id::text)) as player_sk,
    nullif(trim(st.player_id), '') as tm_player_id,
    nullif(trim(st.player_name), '') as player_name,
    case
        when nullif(trim(st.transfer_date_raw), '') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            then trim(st.transfer_date_raw)::date
        else null
    end as transfer_date,
    nullif(trim(st.transfer_season), '') as transfer_season,
    nullif(trim(st.from_club_id), '') as from_club_id,
    nullif(trim(st.to_club_id), '') as to_club_id,
    nullif(trim(st.from_club_name), '') as from_club_name,
    nullif(trim(st.to_club_name), '') as to_club_name,
    case
        when nullif(trim(st.transfer_fee), '') ~ '^-?[0-9]+(\.[0-9]+)?$'
            then trim(st.transfer_fee)::numeric
        else null
    end as transfer_fee_eur,
    case
        when nullif(trim(st.market_value_in_eur), '') ~ '^-?[0-9]+(\.[0-9]+)?$'
            then trim(st.market_value_in_eur)::numeric
        else null
    end as market_value_eur,
    st.ingested_at,
    'transfermarkt' as source_provider
from source_transfers st
inner join linked_players lp
  on lp.tm_player_id = st.player_id
where nullif(trim(st.player_id), '') is not null
