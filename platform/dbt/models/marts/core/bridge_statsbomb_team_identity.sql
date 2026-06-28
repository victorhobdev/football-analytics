select
    source_name,
    source_team_id,
    source_team_name,
    identity_status,
    confidence,
    local_team_id,
    md5(concat(source_name, ':', source_team_id::text)) as bridge_team_identity_sk,
    resolution_reason,
    evidence,
    updated_at
from {{ source('postgres_mart', 'stg_statsbomb_team_identity') }}
