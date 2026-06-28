{{ config(materialized='view') }}

select
    statsbomb_match_event_id,
    provider,
    source_match_id,
    local_match_id,
    source_event_id,
    source_event_index,
    event_type_sk,
    source_team_id,
    source_team_name,
    source_player_id,
    source_player_name,
    local_team_id,
    local_player_id,
    minute,
    second,
    possession,
    play_pattern,
    location_x,
    location_y,
    duration_seconds,
    is_three_sixty_backed,
    payload,
    updated_at
from {{ ref('fact_statsbomb_match_event') }}
where event_type = 'Pressure'
