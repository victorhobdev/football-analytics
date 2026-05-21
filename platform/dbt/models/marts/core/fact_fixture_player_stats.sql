{{ config(
    materialized='incremental',
    unique_key='fixture_player_stat_id',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['match_id', 'team_id'], 'type': 'btree'},
        {'columns': ['player_id', 'match_date desc', 'match_id desc'], 'type': 'btree'},
        {'columns': ['match_id', 'player_id'], 'type': 'btree'}
    ]
) }}
{% set lookback_hours = var('fact_fixture_player_stats_incremental_lookback_hours', 24) %}

with context as (
    select * from {{ ref('int_fixture_player_context') }}
),
fact_matches as (
    select
        match_id,
        competition_sk,
        season,
        date_day
    from {{ ref('fact_matches') }}
),
base as (
    select
        md5(concat(c.provider, ':', c.fixture_id::text, ':', c.team_id::text, ':', c.player_id::text)) as fixture_player_stat_id,
        c.provider,
        c.fixture_id as match_id,
        fm.competition_sk,
        fm.season,
        fm.date_day as match_date,
        md5(concat('team:', c.team_id::text)) as team_sk,
        md5(concat('player:', c.player_id::text)) as player_sk,
        c.team_id,
        c.player_id,
        c.team_name,
        c.player_name,
        c.position_name,
        c.is_starter,
        c.minutes_played,
        c.goals,
        c.assists,
        c.shots_total,
        c.shots_on_goal,
        c.passes_total,
        c.key_passes,
        c.tackles,
        c.interceptions,
        c.duels,
        c.fouls_committed,
        c.yellow_cards,
        c.red_cards,
        c.goalkeeper_saves,
        c.clean_sheets,
        c.xg,
        c.rating,
        c.statistics,
        c.ingested_run,
        coalesce(c.updated_at, now()) as updated_at
    from context c
    inner join fact_matches fm
      on fm.match_id = c.fixture_id
    where c.fixture_id is not null
      and c.team_id is not null
      and c.player_id is not null
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
