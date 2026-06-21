select
    source_name,
    source_player_id,
    source_player_name,
    identity_status,
    confidence,
    local_player_id,
    md5(concat(source_name, ':', source_player_id::text)) as bridge_player_identity_sk,
    resolution_reason,
    evidence,
    updated_at
from {{ source('postgres_mart', 'stg_statsbomb_player_identity') }}
