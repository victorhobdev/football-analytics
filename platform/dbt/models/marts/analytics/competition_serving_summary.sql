{{ config(
    materialized='table',
    indexes=[
        {'columns': ['league_id'], 'type': 'btree'}
    ]
) }}

with match_totals as (
    select
        fm.league_id,
        count(distinct fm.match_id)::int as matches_count,
        count(distinct fm.season)::int as seasons_count,
        min(fm.season)::int as min_season,
        max(fm.season)::int as max_season
    from {{ ref('fact_matches') }} fm
    group by fm.league_id
),
match_statistics as (
    select
        rf.league_id,
        count(distinct ms.fixture_id)::int as available_count
    from {{ source('postgres_raw', 'match_statistics') }} ms
    inner join {{ source('postgres_raw', 'fixtures') }} rf
      on rf.fixture_id = ms.fixture_id
    group by rf.league_id
),
fixture_lineups as (
    select
        rf.league_id,
        count(distinct fl.fixture_id)::int as available_count
    from {{ source('postgres_raw', 'fixture_lineups') }} fl
    inner join {{ source('postgres_raw', 'fixtures') }} rf
      on rf.fixture_id = fl.fixture_id
    group by rf.league_id
),
match_events as (
    select
        rf.league_id,
        count(distinct me.fixture_id)::int as available_count
    from {{ source('postgres_raw', 'match_events') }} me
    inner join {{ source('postgres_raw', 'fixtures') }} rf
      on rf.fixture_id = me.fixture_id
    group by rf.league_id
),
fixture_player_statistics as (
    select
        rf.league_id,
        count(distinct fps.fixture_id)::int as available_count
    from {{ source('postgres_raw', 'fixture_player_statistics') }} fps
    inner join {{ source('postgres_raw', 'fixtures') }} rf
      on rf.fixture_id = fps.fixture_id
    group by rf.league_id
),
competition_names as (
    select distinct on (dc.league_id)
        dc.league_id,
        dc.league_name
    from {{ ref('dim_competition') }} dc
    order by dc.league_id, dc.updated_at desc nulls last
)
select
    mt.league_id,
    cn.league_name,
    mt.matches_count,
    mt.seasons_count,
    mt.min_season,
    mt.max_season,
    coalesce(ms.available_count, 0) as match_statistics_count,
    coalesce(fl.available_count, 0) as lineups_count,
    coalesce(me.available_count, 0) as events_count,
    coalesce(fps.available_count, 0) as player_statistics_count,
    now() as updated_at
from match_totals mt
left join competition_names cn
  on cn.league_id = mt.league_id
left join match_statistics ms
  on ms.league_id = mt.league_id
left join fixture_lineups fl
  on fl.league_id = mt.league_id
left join match_events me
  on me.league_id = mt.league_id
left join fixture_player_statistics fps
  on fps.league_id = mt.league_id
