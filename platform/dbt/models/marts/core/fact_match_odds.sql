{{ config(
    materialized='incremental',
    unique_key='match_id',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['match_id'], 'type': 'btree'},
        {'columns': ['competition_key', 'match_date'], 'type': 'btree'}
    ]
) }}

with elo as (
    select * from {{ ref('stg_elo_matches') }}
),
published_matches as (
    select
        match_id,
        competition_sk,
        competition_key,
        date_day as match_date
    from {{ ref('fact_matches') }}
),
base as (
    select
        pm.match_id,
        pm.competition_sk,
        pm.competition_key,
        pm.match_date,
        elo.odd_home,
        elo.odd_draw,
        elo.odd_away,
        elo.max_home,
        elo.max_draw,
        elo.max_away,
        elo.over25,
        elo.under25,
        elo.max_over25,
        elo.max_under25,
        elo.handicap_size,
        elo.handicap_home,
        elo.handicap_away,
        'eloratings' as source_provider,
        elo.elo_match_hash as source_match_id,
        coalesce(elo.ingested_at, now()) as updated_at
    from elo
    inner join published_matches pm
      on pm.match_id = elo.match_id
    where elo.odd_home is not null
       or elo.odd_draw is not null
       or elo.odd_away is not null
       or elo.max_home is not null
       or elo.max_draw is not null
       or elo.max_away is not null
       or elo.over25 is not null
       or elo.under25 is not null
       or elo.max_over25 is not null
       or elo.max_under25 is not null
       or elo.handicap_home is not null
       or elo.handicap_away is not null
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
