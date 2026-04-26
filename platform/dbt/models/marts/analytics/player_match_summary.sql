{{ config(
    indexes=[
        {'columns': ['player_id', 'match_date desc', 'match_id desc'], 'type': 'btree'},
        {'columns': ['match_id'], 'type': 'btree'},
        {'columns': ['match_id', 'match_date desc', 'player_id'], 'type': 'btree'},
        {'columns': ['team_id', 'match_date desc', 'match_id desc'], 'type': 'btree'}
    ]
) }}

with fact_player_stats as (
    select * from {{ ref('fact_fixture_player_stats') }}
),
dim_players as (
    select
        player_sk,
        player_id,
        player_name
    from {{ ref('dim_player') }}
),
dim_teams as (
    select
        team_sk,
        team_id,
        team_name
    from {{ ref('dim_team') }}
)
select
    fps.fixture_player_stat_id,
    fps.match_id,
    fps.match_date,
    fps.competition_sk,
    fps.season,
    fps.player_sk,
    coalesce(dp.player_id, fps.player_id) as player_id,
    coalesce(dp.player_name, fps.player_name) as player_name,
    fps.team_sk,
    coalesce(dt.team_id, fps.team_id) as team_id,
    coalesce(dt.team_name, fps.team_name) as team_name,
    fps.position_name,
    fps.is_starter,
    fps.minutes_played,
    fps.goals,
    fps.assists,
    fps.shots_total,
    fps.shots_on_goal,
    fps.passes_total,
    fps.key_passes,
    fps.tackles,
    fps.interceptions,
    fps.duels,
    fps.fouls_committed,
    fps.yellow_cards,
    fps.red_cards,
    fps.goalkeeper_saves,
    fps.clean_sheets,
    fps.xg,
    fps.rating,
    fps.updated_at
from fact_player_stats fps
left join dim_players dp
  on dp.player_sk = fps.player_sk
left join dim_teams dt
  on dt.team_sk = fps.team_sk
