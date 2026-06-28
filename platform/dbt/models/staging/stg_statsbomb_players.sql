with event_players as (
    select
        source_player_id,
        source_player_name,
        local_player_id,
        local_team_id,
        local_match_id,
        updated_at
    from {{ ref('stg_statsbomb_events') }}
    where source_player_id is not null
),
lineup_players as (
    select
        source_player_id,
        source_player_name,
        local_player_id,
        local_team_id,
        local_match_id,
        updated_at
    from {{ ref('stg_statsbomb_lineups') }}
    where source_player_id is not null
),
unioned as (
    select * from event_players
    union all
    select * from lineup_players
)
select
    source_player_id,
    max(source_player_name) as source_player_name,
    max(local_player_id) as local_player_id,
    max(local_team_id) as local_team_id,
    count(distinct local_match_id) as matches_seen,
    max(updated_at) as updated_at
from unioned
group by source_player_id
