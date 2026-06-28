with source_frames as (
    select * from {{ source('postgres_raw', 'statsbomb_three_sixty_frames') }}
)
select
    source_name,
    match_id as source_match_id,
    event_uuid,
    local_match_id,
    visible_area,
    payload,
    updated_at
from source_frames
