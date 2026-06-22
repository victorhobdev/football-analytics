-- Validation gate for the serving publication snapshot.
-- Run this against the candidate database before switching FOOTBALL_PG_DSN.

\set ON_ERROR_STOP on
\pset null '<null>'

with required_objects(object_name) as (
  values
    ('control.competitions'),
    ('control.historical_stat_definitions'),
    ('publication.serving_scope'),
    ('mart_control.competition_season_config'),
    ('mart.competition_historical_stats'),
    ('mart.competition_structure_hub'),
    ('mart.dim_coach'),
    ('mart.dim_competition'),
    ('mart.dim_date'),
    ('mart.dim_group'),
    ('mart.dim_player'),
    ('mart.dim_round'),
    ('mart.dim_stage'),
    ('mart.dim_team'),
    ('mart.dim_tie'),
    ('mart.dim_venue'),
    ('mart.fact_fixture_lineups'),
    ('mart.fact_fixture_player_stats'),
    ('mart.fact_group_standings'),
    ('mart.fact_match_events'),
    ('mart.fact_matches'),
    ('mart.fact_stage_progression'),
    ('mart.fact_tie_results'),
    ('mart.player_match_summary'),
    ('mart.stg_player_transfers'),
    ('mart.stg_team_coaches'),
    ('raw.coaches'),
    ('raw.competition_rounds'),
    ('raw.competition_stages'),
    ('raw.fixture_lineups'),
    ('raw.fixture_player_statistics'),
    ('raw.fixtures'),
    ('raw.match_events'),
    ('raw.match_statistics'),
    ('raw.player_transfers'),
    ('raw.standings_snapshots'),
    ('raw.team_coaches')
)
select
  object_name,
  to_regclass(object_name) is not null as exists_in_candidate
from required_objects
order by object_name;

with out_of_scope_matches as (
  select count(*)::bigint as rows_count
  from mart.fact_matches fm
  where not exists (
    select 1
    from publication.serving_scope s
    where s.source_competition_id = fm.league_id
      and s.season_query_id = fm.season
  )
),
future_matches as (
  select count(*)::bigint as rows_count
  from mart.fact_matches
  where season > 2025
),
raw_fixture_orphans as (
  select count(*)::bigint as rows_count
  from raw.fixtures rf
  where not exists (
    select 1 from mart.fact_matches fm where fm.match_id = rf.fixture_id
  )
),
event_orphans as (
  select count(*)::bigint as rows_count
  from mart.fact_match_events fme
  where not exists (
    select 1 from mart.fact_matches fm where fm.match_id = fme.match_id
  )
),
lineup_orphans as (
  select count(*)::bigint as rows_count
  from mart.fact_fixture_lineups fl
  where not exists (
    select 1 from mart.fact_matches fm where fm.match_id = fl.match_id
  )
),
player_stat_orphans as (
  select count(*)::bigint as rows_count
  from mart.fact_fixture_player_stats fps
  where not exists (
    select 1 from mart.fact_matches fm where fm.match_id = fps.match_id
  )
)
select 'out_of_scope_matches' as check_name, rows_count from out_of_scope_matches
union all
select 'future_matches_after_2025', rows_count from future_matches
union all
select 'raw_fixture_orphans', rows_count from raw_fixture_orphans
union all
select 'event_orphans', rows_count from event_orphans
union all
select 'lineup_orphans', rows_count from lineup_orphans
union all
select 'player_stat_orphans', rows_count from player_stat_orphans
order by check_name;

select
  'fdw_source_server_leftover' as check_name,
  count(*)::bigint as rows_count
from pg_foreign_server
where srvname = 'serving_snapshot_source'
union all
select
  'foreign_source_schemas_leftover',
  count(*)::bigint
from information_schema.schemata
where schema_name in ('source_control', 'source_mart_control', 'source_mart', 'source_raw')
order by check_name;

select
  s.competition_key,
  s.season_label,
  count(distinct fm.match_id)::bigint as matches,
  count(distinct fm.home_team_id) + count(distinct fm.away_team_id) as team_id_distinct_sum,
  count(distinct pms.player_id)::bigint as players_with_match_summary
from publication.serving_scope s
left join mart.fact_matches fm
  on fm.league_id = s.source_competition_id
 and fm.season = s.season_query_id
left join mart.player_match_summary pms
  on pms.match_id = fm.match_id
group by s.competition_key, s.season_label
order by s.competition_key, s.season_label;
