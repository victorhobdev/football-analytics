{{ config(
    materialized='incremental',
    unique_key='player_valuation_id',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['player_valuation_id'], 'type': 'btree'},
        {'columns': ['player_id', 'valuation_date'], 'type': 'btree'}
    ]
) }}

with valuations as (
    select * from {{ ref('stg_tm_player_valuations') }}
),
players as (
    select
        player_id,
        player_sk
    from {{ ref('dim_player') }}
),
base as (
    select
        md5(concat('transfermarkt:', v.tm_valuation_id)) as player_valuation_id,
        v.tm_valuation_id as source_valuation_id,
        v.source_provider,
        v.player_id,
        p.player_sk,
        v.tm_player_id,
        v.valuation_date,
        v.market_value_eur,
        v.current_club_id,
        v.current_club_name,
        v.player_club_domestic_competition_id,
        coalesce(v.ingested_at, now()) as updated_at
    from valuations v
    inner join players p
      on p.player_id = v.player_id
    where v.valuation_date is not null
      and v.market_value_eur is not null
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
