{{ config(
    materialized='incremental',
    unique_key='team_sk',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['team_id'], 'type': 'btree'}
    ]
) }}

with fixtures as (
    select * from {{ ref('stg_matches') }}
),
events as (
    select * from {{ ref('stg_match_events') }}
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
event_teams as (
    select distinct
        team_id,
        team_name
    from events
    where team_id is not null
      and team_name is not null
),
teams as (
    select team_id, team_name from home_teams
    union
    select team_id, team_name from away_teams
    union
    select team_id, team_name from event_teams
),
ranked as (
    select
        team_id,
        team_name,
        row_number() over (
            partition by team_id
            order by team_name
        ) as row_num
    from teams
)
select
    md5(concat('team:', team_id::text)) as team_sk,
    team_id,
    team_name,
    cast(null as text) as logo_url,
    now() as updated_at
from ranked
where row_num = 1
