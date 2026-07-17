with source_lineups as (
    select * from {{ source('postgres_raw', 'statsbomb_lineups') }}
)
select
    source_lineups.source_name,
    source_lineups.match_id as source_match_id,
    source_lineups.source_team_id,
    source_lineups.source_team_name,
    source_lineups.source_player_id,
    source_lineups.source_player_name,
    source_lineups.jersey_number,
    source_lineups.country_name,
    {% if var('canonical_snapshot_schema', '') %}
    match_identity.local_match_id,
    team_identity.canonical_id::bigint as local_team_id,
    {% else %}
    source_lineups.local_match_id,
    source_lineups.local_team_id,
    {% endif %}
    source_lineups.local_player_id,
    {% if var('canonical_snapshot_schema', '') %}
    match_identity.identity_status as match_identity_status,
    {% else %}
    source_lineups.match_identity_status,
    {% endif %}
    source_lineups.player_identity_status,
    source_lineups.player_identity_reason,
    source_lineups.player_identity_confidence,
    source_lineups.payload,
    source_lineups.updated_at
from source_lineups
{% if var('canonical_snapshot_schema', '') %}
left join {{ ref('bridge_statsbomb_match_identity') }} match_identity
  on match_identity.source_name = source_lineups.source_name
 and match_identity.source_match_id = source_lineups.match_id
left join raw.provider_entity_map team_identity
  on team_identity.provider = 'statsbomb_open_data'
 and team_identity.entity_type = 'team'
 and team_identity.source_team_key = 'statsbomb_open_data:' || source_lineups.source_team_id::text
 and team_identity.mapping_state = 'approved'
{% endif %}
