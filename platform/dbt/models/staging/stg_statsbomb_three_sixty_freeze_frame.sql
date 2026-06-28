with source_freeze_frame as (
    select * from {{ source('postgres_raw', 'statsbomb_three_sixty_freeze_frame') }}
)
select
    source_name,
    match_id as source_match_id,
    event_uuid,
    freeze_frame_index,
    teammate,
    actor,
    keeper,
    location_x,
    location_y,
    updated_at
from source_freeze_frame
