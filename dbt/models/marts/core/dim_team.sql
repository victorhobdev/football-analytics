with fixtures as (
    select * from {{ source('postgres_raw', 'fixtures') }}
),
home_teams as (
    select distinct
        home_team_id as team_id,
        home_team_name as team_name
    from fixtures
    where home_team_id is not null
      and home_team_name is not null
),
away_teams as (
    select distinct
        away_team_id as team_id,
        away_team_name as team_name
    from fixtures
    where away_team_id is not null
      and away_team_name is not null
),
teams as (
    select team_id, team_name from home_teams
    union
    select team_id, team_name from away_teams
)
select
    team_id,
    team_name,
    cast(null as text) as logo_url,
    now() as updated_at
from teams
