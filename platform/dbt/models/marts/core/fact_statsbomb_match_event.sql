{{ config(materialized='view') }}

with events as (
    select * from {{ ref('stg_statsbomb_events') }}
),
frames as (
    select distinct source_match_id, event_uuid
    from {{ ref('stg_statsbomb_three_sixty_frames') }}
),
event_types as (
    select event_type, event_type_sk
    from {{ ref('dim_statsbomb_event_type') }}
),
base as (
    select
        md5(concat(e.source_name, ':', e.source_match_id::text, ':', e.source_event_id)) as statsbomb_match_event_id,
        e.source_name as provider,
        e.source_match_id,
        e.local_match_id,
        e.source_event_id,
        e.event_index as source_event_index,
        et.event_type_sk,
        e.event_type,
        (f.event_uuid is not null) as is_three_sixty_backed,
        e.period,
        e.event_timestamp,
        e.minute,
        e.second,
        e.possession,
        e.source_possession_team_id,
        e.source_possession_team_name,
        e.play_pattern,
        e.source_team_id,
        e.source_team_name,
        e.source_player_id,
        e.source_player_name,
        e.local_team_id,
        e.local_player_id,
        payload -> 'type' ->> 'name' as event_type_label,
        payload -> 'position' ->> 'name' as player_position_name,
        payload -> 'position' ->> 'id' as player_position_id,
        payload -> 'pass' -> 'recipient' ->> 'id' as source_recipient_player_id,
        payload -> 'pass' -> 'recipient' ->> 'name' as source_recipient_player_name,
        payload -> 'pass' -> 'height' ->> 'name' as pass_height_name,
        payload -> 'pass' -> 'body_part' ->> 'name' as body_part_name,
        payload -> 'pass' -> 'outcome' ->> 'name' as outcome_name,
        payload -> 'shot' -> 'outcome' ->> 'name' as shot_outcome_name,
        payload -> 'shot' -> 'body_part' ->> 'name' as shot_body_part_name,
        payload -> 'shot' -> 'technique' ->> 'name' as shot_technique_name,
        payload -> 'shot' -> 'type' ->> 'name' as shot_type_name,
        payload -> 'goalkeeper' -> 'outcome' ->> 'name' as goalkeeper_outcome_name,
        (payload -> 'location' ->> 0)::numeric as location_x,
        (payload -> 'location' ->> 1)::numeric as location_y,
        coalesce(
            (payload -> 'pass' -> 'end_location' ->> 0)::numeric,
            (payload -> 'carry' -> 'end_location' ->> 0)::numeric,
            (payload -> 'shot' -> 'end_location' ->> 0)::numeric
        ) as end_location_x,
        coalesce(
            (payload -> 'pass' -> 'end_location' ->> 1)::numeric,
            (payload -> 'carry' -> 'end_location' ->> 1)::numeric,
            (payload -> 'shot' -> 'end_location' ->> 1)::numeric
        ) as end_location_y,
        (payload ->> 'duration')::numeric as duration_seconds,
        e.match_identity_status,
        e.player_identity_status,
        e.payload,
        e.updated_at
    from events e
    left join frames f
      on f.source_match_id = e.source_match_id
     and f.event_uuid = e.source_event_id
    left join event_types et
      on et.event_type = e.event_type
)
select * from base
