{{ config(
    indexes=[
        {'columns': ['competition_key', 'season_label', 'stage_id', 'tie_id'], 'type': 'btree'}
    ]
) }}

with tie_results as (
    select * from {{ ref('int_tie_results') }}
)
select
    tie_id,
    md5(concat('tie:', tie_id)) as tie_sk,
    provider,
    provider_league_id,
    competition_key,
    season_label,
    stage_id,
    stage_sk,
    stage_name,
    stage_format,
    tie_order,
    home_side_team_id,
    home_side_team_name,
    away_side_team_id,
    away_side_team_name,
    match_count,
    first_leg_at,
    last_leg_at,
    home_side_goals,
    away_side_goals,
    winner_team_id,
    resolution_type,
    has_extra_time_match,
    has_penalties_match,
    next_stage_id,
    next_stage_name,
    is_inferred
from tie_results
