with source_lineups as (
    select * from {{ source('postgres_raw', 'statsbomb_lineups') }}
)
select
    source_name,
    match_id as source_match_id,
    source_team_id,
    source_team_name,
    source_player_id,
    source_player_name,
    jersey_number,
    country_name,
    local_match_id,
    local_team_id,
    local_player_id,
    match_identity_status,
    player_identity_status,
    player_identity_reason,
    player_identity_confidence,
    payload,
    updated_at
from source_lineups
