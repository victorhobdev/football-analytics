with source_standings as (
    select * from {{ source('postgres_raw', 'standings_snapshots') }}
)
select
    source_standings.provider,
    source_standings.league_id,
    source_standings.provider_league_id,
    nullif(trim(source_standings.competition_key), '') as competition_key,
    source_standings.season_id,
    nullif(trim(source_standings.season_label), '') as season_label,
    source_standings.provider_season_id,
    source_standings.stage_id,
    source_standings.round_id,
    {% if var('canonical_snapshot_schema', '') %}
    identity.canonical_id::bigint as team_id,
    {% else %}
    source_standings.team_id,
    {% endif %}
    source_standings.position,
    source_standings.points,
    source_standings.games_played,
    source_standings.won,
    source_standings.draw,
    source_standings.lost,
    source_standings.goals_for,
    source_standings.goals_against,
    source_standings.goal_diff,
    nullif(trim(source_standings.payload ->> 'group_id'), '') as raw_group_id,
    source_standings.payload,
    source_standings.ingested_run,
    source_standings.ingested_at,
    source_standings.source_run_id,
    source_standings.updated_at
from source_standings
{% if var('canonical_snapshot_schema', '') %}
join raw.provider_entity_map identity
  on identity.provider = 'legacy_dim_team'
 and identity.entity_type = 'team'
 and identity.source_id = source_standings.team_id::text
 and identity.mapping_state = 'approved'
 and (
      identity.valid_from is null
      or (
        nullif(trim(source_standings.season_label), '') ~ '^[0-9]{4}$'
        and identity.valid_from <= make_date(trim(source_standings.season_label)::int, 7, 1)
      )
 )
 and (
      identity.valid_to is null
      or (
        nullif(trim(source_standings.season_label), '') ~ '^[0-9]{4}$'
        and make_date(trim(source_standings.season_label)::int, 7, 1) < identity.valid_to
      )
 )
{% endif %}
