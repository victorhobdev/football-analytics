{{ config(
    materialized='incremental',
    unique_key='transfermarkt_appearance_id',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['transfermarkt_appearance_id'], 'type': 'btree'},
        {'columns': ['match_id', 'player_id'], 'type': 'btree'}
    ]
) }}

with appearances as (
    select * from {{ ref('stg_tm_appearances') }}
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
        md5(concat('transfermarkt:', a.tm_appearance_id)) as transfermarkt_appearance_id,
        a.tm_appearance_id as source_appearance_hash,
        a.source_appearance_id,
        a.source_provider,
        a.match_id,
        m.competition_sk,
        m.competition_key,
        coalesce(a.match_date, m.date_day) as match_date,
        a.player_id,
        p.player_sk,
        a.tm_player_id,
        a.player_name,
        a.player_club_id,
        a.player_current_club_id,
        a.tm_competition_id,
        a.minutes_played,
        a.goals,
        a.assists,
        a.yellow_cards,
        a.red_cards,
        coalesce(a.ingested_at, now()) as updated_at
    from appearances a
    inner join matches m
      on m.match_id = a.match_id
    inner join players p
      on p.player_id = a.player_id
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
