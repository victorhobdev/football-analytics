{{ config(
    materialized='table',
    indexes=[
        {'columns': ['team_id'], 'unique': true, 'type': 'btree'},
        {'columns': ['points desc', 'team_id'], 'type': 'btree'},
        {'columns': ['goal_diff desc', 'team_id'], 'type': 'btree'},
        {'columns': ['wins desc', 'team_id'], 'type': 'btree'},
        {'columns': ['team_name', 'team_id'], 'type': 'btree'}
    ]
) }}

select
    tr.team_id,
    max(coalesce(dt.team_name, tr.team_id::text)) as team_name,
    count(*)::int as matches_played,
    sum(tr.wins)::int as wins,
    sum(tr.draws)::int as draws,
    sum(tr.losses)::int as losses,
    sum(tr.goals_for)::int as goals_for,
    sum(tr.goals_against)::int as goals_against,
    sum(tr.goals_for - tr.goals_against)::int as goal_diff,
    sum(tr.points_round)::int as points
from {{ ref('int_team_match_rows') }} tr
left join {{ ref('dim_team') }} dt on dt.team_id = tr.team_id
where tr.team_id is not null
group by tr.team_id
