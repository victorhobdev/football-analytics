{{ config(
    materialized='incremental',
    unique_key='league_id',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['league_id'], 'type': 'btree'}
    ]
) }}

with fixtures as (
    select * from {{ ref('stg_matches') }}
),
ranked as (
    select
        league_id,
        league_name,
        row_number() over (
            partition by league_id
            order by fixture_timestamp desc nulls last, fixture_id desc
        ) as rn
    from fixtures
    where league_id is not null
      and league_name is not null
)
select
    md5(concat('competition:', league_id::text)) as competition_sk,
    league_id,
    league_name,
    cast(null as text) as country,
    now() as updated_at
from ranked
where rn = 1
