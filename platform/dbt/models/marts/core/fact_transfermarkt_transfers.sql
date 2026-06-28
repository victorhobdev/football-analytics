{{ config(
    materialized='incremental',
    unique_key='transfer_event_id',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['transfer_event_id'], 'type': 'btree'},
        {'columns': ['player_id', 'transfer_date'], 'type': 'btree'}
    ]
) }}

with transfers as (
    select * from {{ ref('stg_tm_transfers') }}
),
players as (
    select
        player_id,
        player_sk
    from {{ ref('dim_player') }}
),
base as (
    select
        md5(concat('transfermarkt:', t.tm_transfer_id)) as transfer_event_id,
        t.tm_transfer_id as source_transfer_id,
        t.source_provider,
        t.player_id,
        p.player_sk,
        t.tm_player_id,
        t.player_name,
        t.transfer_date,
        t.transfer_season,
        t.from_club_id,
        t.from_club_name,
        t.to_club_id,
        t.to_club_name,
        t.transfer_fee_eur,
        t.market_value_eur,
        coalesce(t.ingested_at, now()) as updated_at
    from transfers t
    inner join players p
      on p.player_id = t.player_id
    where t.transfer_date is not null
),
filtered as (
    select *
    from base
    {% if is_incremental() %}
    where updated_at >= (
        select coalesce(max(updated_at) - interval '24 hour', timestamp '1900-01-01')
        from {{ this }}
    )
    {% endif %}
)
select * from filtered
