with source_events as (
    select * from {{ source('postgres_raw', 'statsbomb_events') }}
)
select
    source_events.source_name,
    source_events.match_id as source_match_id,
    source_events.event_id as source_event_id,
    source_events.event_index,
    source_events.period,
    source_events.event_timestamp,
    source_events.minute,
    source_events.second,
    source_events.event_type,
    source_events.possession,
    source_events.possession_team_id as source_possession_team_id,
    source_events.possession_team_name as source_possession_team_name,
    source_events.play_pattern,
    source_events.source_team_id,
    source_events.source_team_name,
    source_events.source_player_id,
    source_events.source_player_name,
    {% if var('canonical_snapshot_schema', '') %}
    match_identity.local_match_id,
    team_identity.canonical_id::bigint as local_team_id,
    {% else %}
    source_events.local_match_id,
    source_events.local_team_id,
    {% endif %}
    source_events.local_player_id,
    {% if var('canonical_snapshot_schema', '') %}
    match_identity.identity_status as match_identity_status,
    {% else %}
    source_events.match_identity_status,
    {% endif %}
    source_events.player_identity_status,
    source_events.payload,
    source_events.updated_at
from source_events
{% if var('canonical_snapshot_schema', '') %}
left join {{ ref('bridge_statsbomb_match_identity') }} match_identity
  on match_identity.source_name = source_events.source_name
 and match_identity.source_match_id = source_events.match_id
left join raw.provider_entity_map team_identity
  on team_identity.provider = 'statsbomb_open_data'
 and team_identity.entity_type = 'team'
 and team_identity.source_team_key = 'statsbomb_open_data:' || source_events.source_team_id::text
 and team_identity.mapping_state = 'approved'
{% endif %}
