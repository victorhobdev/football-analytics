{{ config(
    materialized='table',
    indexes=[
        {'columns': ['goals desc', 'player_id'], 'type': 'btree'},
        {'columns': ['assists desc', 'player_id'], 'type': 'btree'},
        {'columns': ['minutes_played desc', 'player_id'], 'type': 'btree'},
        {'columns': ['rating desc', 'player_id'], 'type': 'btree'},
        {'columns': ['player_name', 'player_id'], 'type': 'btree'},
        {'columns': ['team_id', 'player_id'], 'type': 'btree'}
    ]
) }}

with base as (
    select
        pms.player_id,
        pms.player_name,
        pms.team_id,
        coalesce(pms.team_name, dt.team_name) as team_name,
        pms.position_name,
        pms.match_id,
        pms.match_date,
        coalesce(pms.minutes_played, 0) as minutes_played,
        coalesce(pms.goals, 0) as goals,
        coalesce(pms.assists, 0) as assists,
        coalesce(pms.shots_total, 0) as shots_total,
        coalesce(pms.shots_on_goal, 0) as shots_on_goal,
        coalesce(pms.yellow_cards, 0) as yellow_cards,
        coalesce(pms.red_cards, 0) as red_cards,
        pms.rating,
        pms.updated_at
    from {{ ref('player_match_summary') }} pms
    left join {{ ref('dim_team') }} dt
      on dt.team_id = pms.team_id
),
aggregated as (
    select
        player_id,
        max(player_name) as player_name,
        count(distinct match_id)::int as matches_played,
        count(distinct team_id) filter (where team_id is not null)::int as team_count,
        sum(minutes_played)::numeric as minutes_played,
        sum(goals)::numeric as goals,
        sum(assists)::numeric as assists,
        sum(shots_total)::numeric as shots_total,
        sum(shots_on_goal)::numeric as shots_on_goal,
        sum(yellow_cards)::numeric as yellow_cards,
        sum(red_cards)::numeric as red_cards,
        sum(yellow_cards + red_cards)::numeric as cards_total,
        avg(rating)::numeric as rating,
        max(updated_at) as data_updated_at
    from base
    group by player_id
),
latest_context as (
    select distinct on (player_id)
        player_id,
        team_id,
        team_name,
        position_name
    from base
    order by player_id, match_date desc nulls last, match_id desc
),
ranked_teams as (
    select
        team_context.player_id,
        team_context.team_id,
        team_context.team_name,
        team_context.last_match_date,
        team_context.last_match_id,
        row_number() over (
            partition by team_context.player_id
            order by team_context.last_match_date desc nulls last, team_context.last_match_id desc
        ) as recent_team_rank
    from (
        select
            player_id,
            team_id,
            max(team_name) as team_name,
            max(match_date) as last_match_date,
            max(match_id) as last_match_id
        from base
        where team_id is not null
        group by player_id, team_id
    ) team_context
),
recent_teams as (
    select
        player_id,
        jsonb_agg(
            jsonb_build_object(
                'teamId', team_id::text,
                'teamName', team_name
            )
            order by last_match_date desc nulls last, last_match_id desc
        ) filter (where recent_team_rank <= 3) as recent_teams,
        jsonb_agg(
            jsonb_build_object(
                'teamId', team_id::text,
                'teamName', team_name
            )
            order by last_match_date desc nulls last, last_match_id desc
        ) filter (where recent_team_rank <= 5) as recent_teams_5
    from ranked_teams
    group by player_id
)
select
    a.player_id,
    a.player_name,
    lc.team_id,
    lc.team_name,
    lc.position_name,
    dp.nationality,
    a.team_count,
    coalesce(rt.recent_teams, '[]'::jsonb) as recent_teams,
    coalesce(rt.recent_teams_5, '[]'::jsonb) as recent_teams_5,
    a.matches_played,
    a.minutes_played,
    a.goals,
    a.assists,
    a.shots_total,
    a.shots_on_goal,
    a.yellow_cards,
    a.red_cards,
    a.cards_total,
    a.rating,
    a.data_updated_at,
    now() as updated_at
from aggregated a
left join latest_context lc
  on lc.player_id = a.player_id
left join recent_teams rt
  on rt.player_id = a.player_id
left join {{ ref('dim_player') }} dp
  on dp.player_id = a.player_id
