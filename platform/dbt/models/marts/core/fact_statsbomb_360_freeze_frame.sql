{{ config(materialized='view') }}

with frames as (
    select * from {{ ref('stg_statsbomb_three_sixty_frames') }}
),
freeze_rows as (
    select * from {{ ref('stg_statsbomb_three_sixty_freeze_frame') }}
),
events as (
    select
        source_match_id,
        source_event_id,
        local_match_id,
        event_type,
        source_team_id,
        source_player_id,
        location_x as event_location_x,
        location_y as event_location_y
    from {{ ref('fact_statsbomb_match_event') }}
)
select
    md5(concat(f.source_name, ':', f.source_match_id::text, ':', f.event_uuid, ':', z.freeze_frame_index::text)) as statsbomb_360_freeze_frame_id,
    f.source_name as provider,
    f.source_match_id,
    coalesce(f.local_match_id, e.local_match_id) as local_match_id,
    f.event_uuid as source_event_id,
    z.freeze_frame_index,
    e.event_type,
    e.source_team_id,
    e.source_player_id,
    e.event_location_x,
    e.event_location_y,
    z.teammate,
    z.actor,
    z.keeper,
    z.location_x,
    z.location_y,
    f.visible_area,
    f.payload,
    greatest(f.updated_at, z.updated_at) as updated_at
from frames f
inner join freeze_rows z
  on z.source_name = f.source_name
 and z.source_match_id = f.source_match_id
 and z.event_uuid = f.event_uuid
left join events e
  on e.source_match_id = f.source_match_id
 and e.source_event_id = f.event_uuid
