{{ config(materialized='incremental', unique_key='event_id', on_schema_change='sync_all_columns') }}
{% set lookback_hours = var('fact_match_events_incremental_lookback_hours', 24) %}

with base as (
    select * from {{ ref('int_fact_match_events_base') }}
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
