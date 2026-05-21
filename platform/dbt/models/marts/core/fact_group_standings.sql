{{ config(
    indexes=[
        {'columns': ['competition_key', 'season_label', 'stage_id', 'group_id', 'position'], 'type': 'btree'}
    ]
) }}

with standings as (
    select * from {{ ref('fact_standings_snapshots') }}
),
groups as (
    select
        group_id,
        group_sk,
        source_group_id,
        group_name,
        group_order
    from {{ ref('dim_group') }}
)
select
    s.standings_snapshot_id,
    s.provider,
    s.provider_league_id,
    s.competition_key,
    s.season_label,
    s.provider_season_id,
    s.competition_sk,
    s.league_id,
    s.season_id,
    s.stage_id,
    s.stage_sk,
    s.round_id,
    s.round_sk,
    s.round_key,
    s.group_id,
    g.group_sk,
    g.source_group_id,
    g.group_name,
    g.group_order,
    s.team_sk,
    s.team_id,
    s.position,
    s.points,
    s.games_played,
    s.won,
    s.draw,
    s.lost,
    s.goals_for,
    s.goals_against,
    s.goal_diff,
    s.payload,
    s.ingested_run,
    s.updated_at
from standings s
inner join groups g
  on g.group_id = s.group_id
