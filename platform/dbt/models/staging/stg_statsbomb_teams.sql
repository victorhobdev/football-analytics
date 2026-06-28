with event_teams as (
    select
        source_team_id,
        source_team_name,
        local_team_id,
        local_match_id,
        updated_at
    from {{ ref('stg_statsbomb_events') }}
    where source_team_id is not null
),
lineup_teams as (
    select
        source_team_id,
        source_team_name,
        local_team_id,
        local_match_id,
        updated_at
    from {{ ref('stg_statsbomb_lineups') }}
    where source_team_id is not null
),
unioned as (
    select * from event_teams
    union all
    select * from lineup_teams
)
select
    source_team_id,
    max(source_team_name) as source_team_name,
    max(local_team_id) as local_team_id,
    count(distinct local_match_id) as matches_seen,
    max(updated_at) as updated_at
from unioned
group by source_team_id
