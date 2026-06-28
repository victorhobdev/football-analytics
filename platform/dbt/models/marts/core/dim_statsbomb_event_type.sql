select
    md5(concat('statsbomb:event_type:', event_type)) as event_type_sk,
    source_name,
    event_type,
    events_count,
    first_seen_at,
    last_seen_at
from {{ ref('stg_statsbomb_event_types') }}
