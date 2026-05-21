{{ config(
    materialized='incremental',
    unique_key='fixture_lineup_id',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['match_id', 'team_id'], 'type': 'btree'},
        {'columns': ['team_id', 'match_id', 'player_id'], 'type': 'btree'}
    ]
) }}
{% set lookback_hours = var('fact_fixture_lineups_incremental_lookback_hours', 24) %}

with lineups as (
    select * from {{ ref('stg_fixture_lineups') }}
),
valid_matches as (
    select match_id from {{ ref('fact_matches') }}
),
base as (
    select
        md5(concat(l.provider, ':', l.fixture_id::text, ':', l.team_id::text, ':', l.lineup_id::text)) as fixture_lineup_id,
        l.provider,
        l.fixture_id as match_id,
        md5(concat('team:', l.team_id::text)) as team_sk,
        md5(concat('player:', l.player_id::text)) as player_sk,
        l.team_id,
        l.player_id,
        l.player_name,
        l.lineup_id,
        l.position_id,
        l.position_name,
        l.lineup_type_id,
        l.is_starter,
        l.formation_field,
        l.formation_position,
        l.jersey_number,
        l.minutes_played,
        l.details,
        l.ingested_run,
        coalesce(l.updated_at, now()) as updated_at
    from lineups l
    inner join valid_matches m
      on m.match_id = l.fixture_id
    where l.fixture_id is not null
      and l.team_id is not null
      and l.lineup_id is not null
      and l.player_id is not null
),
filtered as (
    select *
    from base
    {% if is_incremental() %}
    where coalesce(updated_at, now()) >= (
        select coalesce(max(updated_at) - interval '{{ lookback_hours }} hour', timestamp '1900-01-01')
        from {{ this }}
    )
    {% endif %}
)
select * from filtered
