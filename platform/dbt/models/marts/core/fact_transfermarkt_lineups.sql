{{ config(
    materialized='incremental',
    unique_key='transfermarkt_lineup_id',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['transfermarkt_lineup_id'], 'type': 'btree'},
        {'columns': ['match_id', 'player_id'], 'type': 'btree'}
    ]
) }}

with lineups as (
    select * from {{ ref('stg_tm_game_lineups') }}
),
matches as (
    select match_id, competition_sk, competition_key, date_day
    from {{ ref('fact_matches') }}
),
players as (
    select player_id, player_sk
    from {{ ref('dim_player') }}
),
base as (
    select
        md5(concat('transfermarkt:', l.tm_lineup_id)) as transfermarkt_lineup_id,
        l.tm_lineup_id as source_lineup_hash,
        l.source_lineup_id,
        l.source_provider,
        l.match_id,
        m.competition_sk,
        m.competition_key,
        coalesce(l.match_date, m.date_day) as match_date,
        l.player_id,
        p.player_sk,
        l.tm_player_id,
        l.tm_club_id,
        l.player_name,
        l.lineup_type,
        l.position_name,
        l.shirt_number,
        l.is_captain,
        coalesce(l.ingested_at, now()) as updated_at
    from lineups l
    inner join matches m
      on m.match_id = l.match_id
    inner join players p
      on p.player_id = l.player_id
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
