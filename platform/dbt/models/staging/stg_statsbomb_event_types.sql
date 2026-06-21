with base as (
    select * from {{ ref('stg_statsbomb_events') }}
)
select
    event_type,
    min(source_name) as source_name,
    count(*) as events_count,
    min(updated_at) as first_seen_at,
    max(updated_at) as last_seen_at
from base
where event_type is not null
group by event_type
