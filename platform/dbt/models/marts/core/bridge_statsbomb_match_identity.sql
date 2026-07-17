{% if var('canonical_snapshot_schema', '') %}
select
    s.source_name,
    s.source_match_id,
    s.canonical_competition_key,
    s.season_label,
    s.match_date,
    s.source_home_team_id,
    s.source_home_team_name,
    s.source_away_team_id,
    s.source_away_team_name,
    s.source_home_score,
    s.source_away_score,
    s.identity_status,
    s.confidence,
    m.canonical_match_id as local_match_id,
    md5(concat(s.source_name, ':', s.source_match_id::text)) as bridge_match_identity_sk,
    s.resolution_reason,
    s.evidence,
    s.updated_at
from {{ source('postgres_mart', 'stg_statsbomb_match_identity') }} s
left join {{ adapter.quote(var('canonical_match_schema', 'shadow_match_dedup_20260715')) }}.match_group_member m
  on m.source_match_id = case
       when s.local_match_id is not null then s.local_match_id
       when s.identity_status = 'new_external_match' then 900000000000 + s.source_match_id
     end
{% else %}
select
    source_name,
    source_match_id,
    canonical_competition_key,
    season_label,
    match_date,
    source_home_team_id,
    source_home_team_name,
    source_away_team_id,
    source_away_team_name,
    source_home_score,
    source_away_score,
    identity_status,
    confidence,
    local_match_id,
    md5(concat(source_name, ':', source_match_id::text)) as bridge_match_identity_sk,
    resolution_reason,
    evidence,
    updated_at
from {{ source('postgres_mart', 'stg_statsbomb_match_identity') }}
{% endif %}
