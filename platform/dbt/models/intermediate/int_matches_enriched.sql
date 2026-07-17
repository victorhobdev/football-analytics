{% if var('canonical_snapshot_schema', '') %}
select
    match_id,
    provider,
    provider as source_provider,
    provider_league_id,
    competition_key,
    competition_type,
    league_id,
    season,
    season_label,
    provider_season_id,
    cast(null as text) as season_name,
    cast(null as date) as season_start_date,
    cast(null as date) as season_end_date,
    date_day,
    match_ingested_run,
    match_ingested_at,
    round,
    round_name,
    stage_id,
    stage_name,
    round_id,
    group_id as group_name,
    leg_number,
    home_team_id,
    away_team_id,
    venue_id,
    home_goals,
    away_goals,
    total_goals,
    result
from {{ adapter.quote(var('canonical_snapshot_schema')) }}.fact_matches
{% else %}
with matches as (
    select * from {{ ref('stg_matches') }}
)
select
    fixture_id as match_id,
    provider,
    source_provider,
    provider_league_id,
    competition_key,
    competition_type,
    league_id,
    season,
    season_label,
    provider_season_id,
    season_name,
    season_start_date,
    season_end_date,
    date_utc::date as date_day,
    ingested_run as match_ingested_run,
    ingested_at as match_ingested_at,
    round,
    round_name,
    stage_id,
    stage_name,
    round_id,
    group_name,
    case
        when leg_number is not null and leg_number > 0 then leg_number
        else null
    end as leg_number,
    home_team_id,
    away_team_id,
    venue_id,
    home_goals,
    away_goals,
    coalesce(home_goals, 0) + coalesce(away_goals, 0) as total_goals,
    case
        when coalesce(home_goals, 0) > coalesce(away_goals, 0) then 'Home Win'
        when coalesce(home_goals, 0) < coalesce(away_goals, 0) then 'Away Win'
        else 'Draw'
    end as result
from matches
where fixture_id is not null
  and date_utc is not null
  and home_team_id is not null
  and away_team_id is not null
{% endif %}
