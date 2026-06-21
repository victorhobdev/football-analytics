with source_events as (
    select * from {{ source('postgres_raw', 'statsbomb_events') }}
)
select
    source_name,
    match_id as source_match_id,
    event_id as source_event_id,
    event_index,
    period,
    event_timestamp,
    minute,
    second,
    event_type,
    possession,
    possession_team_id as source_possession_team_id,
    possession_team_name as source_possession_team_name,
    play_pattern,
    source_team_id,
    source_team_name,
    source_player_id,
    source_player_name,
    local_match_id,
    local_team_id,
    local_player_id,
    match_identity_status,
    player_identity_status,
    payload,
    updated_at
from source_events
