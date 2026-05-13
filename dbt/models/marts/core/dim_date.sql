with fixtures as (
    select * from {{ source('postgres_raw', 'fixtures') }}
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
    date_day,
    extract(year from date_day)::int as year,
    extract(month from date_day)::int as month,
    extract(day from date_day)::int as day,
    trim(to_char(date_day, 'Day')) as day_of_week_name,
    (extract(isodow from date_day) in (6, 7)) as is_weekend
from calendar
