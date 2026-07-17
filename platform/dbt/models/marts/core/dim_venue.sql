{% if var('canonical_snapshot_schema', '') %}
{{ config(materialized='table', indexes=[{'columns': ['venue_id'], 'type': 'btree'}]) }}

select
    f.venue_sk,
    f.venue_id,
    coalesce(max(v.venue_name), concat('Unknown Venue #', f.venue_id::text)) as venue_name,
    max(v.venue_city) as venue_city,
    max(v.venue_country) as venue_country,
    now() as updated_at
from {{ adapter.quote(var('canonical_snapshot_schema')) }}.fact_matches f
left join mart.dim_venue v on v.venue_id = f.venue_id
where f.venue_id is not null
group by f.venue_sk, f.venue_id
{% else %}
{{ config(
    materialized='incremental',
    unique_key='venue_sk',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['venue_id'], 'type': 'btree'}
    ]
) }}

with fixtures as (
    select * from {{ ref('stg_matches') }}
),
base as (
    select
        venue_id,
        venue_name,
        venue_city,
        venue_country,
        date_utc,
        ingested_run,
        fixture_id
    from fixtures
    where venue_id is not null
),
normalized as (
    select
        venue_id,
        nullif(trim(venue_name), '') as venue_name,
        nullif(trim(venue_city), '') as venue_city,
        nullif(trim(venue_country), '') as venue_country,
        date_utc,
        ingested_run,
        fixture_id
    from base
),
ranked as (
    select
        venue_id,
        venue_name,
        venue_city,
        venue_country,
        row_number() over (
            partition by venue_id
            order by
                case when venue_name is null then 1 else 0 end,
                date_utc desc nulls last,
                ingested_run desc nulls last,
                fixture_id desc nulls last
        ) as row_num
    from normalized
)
select
    md5(concat('venue:', venue_id::text)) as venue_sk,
    venue_id,
    coalesce(venue_name, concat('Unknown Venue #', venue_id::text)) as venue_name,
    venue_city,
    venue_country,
    now() as updated_at
from ranked
where row_num = 1
  and venue_id is not null
{% endif %}
