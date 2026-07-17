{% if var('canonical_snapshot_schema', '') %}
select
    s.source_name,
    s.source_team_id,
    s.source_team_name,
    case when p.canonical_id is not null then 'approved_canonical' else s.identity_status end as identity_status,
    case when p.canonical_id is not null then 1.0000::numeric(5,4) else s.confidence end as confidence,
    case when p.canonical_id ~ '^[0-9]+$' then p.canonical_id::bigint end as local_team_id,
    md5(concat(s.source_name, ':', s.source_team_id::text)) as bridge_team_identity_sk,
    coalesce(p.resolution_method, s.resolution_reason) as resolution_reason,
    coalesce(p.evidence, s.evidence) as evidence,
    greatest(p.updated_at, s.updated_at) as updated_at
from {{ source('postgres_mart', 'stg_statsbomb_team_identity') }} s
left join raw.provider_entity_map p
  on p.provider = 'statsbomb_open_data'
 and p.entity_type = 'team'
 and p.source_team_key = 'statsbomb_open_data:' || s.source_team_id::text
 and p.mapping_state = 'approved'
{% else %}
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
{% endif %}
