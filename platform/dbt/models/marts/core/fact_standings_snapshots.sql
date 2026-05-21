{{ config(
    indexes=[
        {'columns': ['competition_key', 'season_label', 'stage_id', 'group_id', 'round_id', 'position'], 'type': 'btree'}
    ]
) }}

with snapshots as (
    select * from {{ ref('stg_standings_snapshots') }}
),
groups as (
    select
        provider,
        competition_key,
        season_label,
        stage_id,
        team_id,
        group_id,
        group_sk
    from {{ ref('int_group_memberships') }}
),
competition as (
    select
        league_id,
        competition_sk
    from {{ ref('dim_competition') }}
),
teams as (
    select
        team_id,
        team_sk
    from {{ ref('dim_team') }}
),
rounds as (
    select
        provider,
        round_id,
        round_sk,
        stage_sk,
        round_key
    from {{ ref('dim_round') }}
)
select
    md5(
        concat(
            s.provider,
            ':',
            s.season_id::text,
            ':',
            s.stage_id::text,
            ':',
            s.round_id::text,
            ':',
            s.team_id::text
        )
    ) as standings_snapshot_id,
    s.provider,
    s.provider_league_id,
    s.competition_key,
    s.season_label,
    s.provider_season_id,
    c.competition_sk,
    s.league_id,
    s.season_id,
    s.stage_id,
    r.stage_sk,
    s.round_id,
    r.round_sk,
    coalesce(r.round_key, 0) as round_key,
    g.group_id,
    g.group_sk,
    t.team_sk,
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
    coalesce(s.updated_at, now()) as updated_at
from snapshots s
left join groups g
  on g.provider = s.provider
 and g.competition_key = s.competition_key
 and g.season_label = s.season_label
 and g.stage_id = s.stage_id
 and g.team_id = s.team_id
left join competition c
  on c.league_id = s.league_id
left join teams t
  on t.team_id = s.team_id
left join rounds r
  on r.provider = s.provider
 and r.round_id = s.round_id
