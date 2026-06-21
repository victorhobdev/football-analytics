{{ config(
    materialized='incremental',
    unique_key='transfermarkt_event_id',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['transfermarkt_event_id'], 'type': 'btree'},
        {'columns': ['match_id', 'minute'], 'type': 'btree'}
    ]
) }}

with events as (
    select * from {{ ref('stg_tm_game_events') }}
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
        md5(concat('transfermarkt:', e.tm_event_id)) as transfermarkt_event_id,
        e.tm_event_id as source_event_hash,
        e.source_event_id,
        e.source_provider,
        e.match_id,
        m.competition_sk,
        m.competition_key,
        coalesce(e.match_date, m.date_day) as match_date,
        e.player_id,
        p.player_sk,
        e.player_in_id,
        e.player_in_sk,
        e.assist_player_id,
        e.assist_player_sk,
        e.tm_player_id,
        e.tm_club_id,
        e.club_name,
        e.minute,
        e.event_type,
        e.description,
        coalesce(e.ingested_at, now()) as updated_at
    from events e
    inner join matches m
      on m.match_id = e.match_id
    inner join players p
      on p.player_id = e.player_id
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
