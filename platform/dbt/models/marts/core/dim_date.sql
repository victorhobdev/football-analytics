{% if var('canonical_snapshot_schema', '') %}
{{ config(materialized='table') }}

with bounds as (
    select min(date_day) as min_day, max(date_day) as max_day
    from {{ adapter.quote(var('canonical_snapshot_schema')) }}.fact_matches
),
calendar as (
    select generate_series(min_day, max_day, interval '1 day')::date as date_day
    from bounds
)
select
    md5(concat('date:', date_day::text)) as date_sk,
    date_day,
    extract(year from date_day)::int as year,
    extract(month from date_day)::int as month,
    extract(day from date_day)::int as day,
    trim(to_char(date_day, 'Day')) as day_of_week_name,
    (extract(isodow from date_day) in (6, 7)) as is_weekend
from calendar
{% else %}
{{ config(materialized='incremental', unique_key='date_sk', on_schema_change='sync_all_columns') }}

with fixtures as (
    select * from {{ ref('stg_matches') }}
),
bounds as (
    select
        coalesce(min(date_utc::date), date '2023-01-01') as min_day,
        coalesce(max(date_utc::date), date '2025-12-31') as max_day
    from fixtures
),
calendar as (
    select
        generate_series(min_day, max_day, interval '1 day')::date as date_day
    from bounds
)
select
    md5(concat('date:', date_day::text)) as date_sk,
    date_day,
    extract(year from date_day)::int as year,
    extract(month from date_day)::int as month,
    extract(day from date_day)::int as day,
    trim(to_char(date_day, 'Day')) as day_of_week_name,
    (extract(isodow from date_day) in (6, 7)) as is_weekend
from calendar
{% endif %}
