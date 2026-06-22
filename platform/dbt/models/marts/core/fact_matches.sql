-- depends_on: {{ ref('competition_season_config') }}
-- depends_on: {{ ref('dim_stage') }}
{{ config(
    materialized='incremental',
    unique_key='match_id',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['match_id'], 'type': 'btree'},
        {'columns': ['league_id', 'season', 'date_day desc', 'match_id desc'], 'type': 'btree'},
        {'columns': ['competition_key', 'season_label', 'stage_id', 'round_id'], 'type': 'btree'},
        {'columns': ['home_team_id', 'date_day desc', 'match_id desc'], 'type': 'btree'},
        {'columns': ['away_team_id', 'date_day desc', 'match_id desc'], 'type': 'btree'},
        {'columns': ['league_id', 'season', 'round_number'], 'type': 'btree'}
    ]
) }}
{% set lookback_hours = var('fact_matches_incremental_lookback_hours', 24) %}

with base as (
    select * from {{ ref('int_fact_matches_base') }}
),
stage_context as (
    select
        provider,
        stage_id,
        stage_format
    from {{ ref('dim_stage') }}
),
target_needs_context_backfill as (
    {% if is_incremental() %}
    select exists (
        select 1
        from {{ this }} t
        left join {{ ref('competition_season_config') }} c
          on c.competition_key = t.competition_key
         and c.season_label = t.season_label
        left join stage_context s
          on s.provider = t.provider
         and s.stage_id = t.stage_id
        where t.provider is null
           or t.competition_key is null
           or t.season_label is null
           or (
                s.stage_format = 'group_table'
            and t.group_id is null
           )
           or (
                c.format_family = 'knockout'
            and (
                t.tie_id is null
                or t.leg_number is null
            )
           )
    ) as needs_backfill
    {% else %}
    select false as needs_backfill
    {% endif %}
),
filtered as (
    select
        base.*,
        now() as updated_at
    from base
    {% if is_incremental() %}
    where base.source_watermark >= (
        select coalesce(max(updated_at) - interval '{{ lookback_hours }} hour', timestamptz '1900-01-01 00:00:00+00')
        from {{ this }}
    )
       or (select needs_backfill from target_needs_context_backfill)
    {% endif %}
)
select * from filtered
