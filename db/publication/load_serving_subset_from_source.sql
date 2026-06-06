-- Build the read-only serving subset in a fresh candidate database.
--
-- Preconditions:
-- 1. The candidate database was created in parallel and received schema-only DDL
--    from the current source database.
-- 2. This script runs against the empty candidate database, never against the
--    currently published production database.
-- 3. psql variables are provided:
--    source_host, source_port, source_db, source_user, source_password.
--
-- Example:
-- psql "$CANDIDATE_DSN" `
--   -v source_host=127.0.0.1 `
--   -v source_port=5432 `
--   -v source_db=football_dw `
--   -v source_user=football `
--   -v source_password=... `
--   -f db/publication/load_serving_subset_from_source.sql

\set ON_ERROR_STOP on

create extension if not exists postgres_fdw;

drop schema if exists source_control cascade;
drop schema if exists source_mart_control cascade;
drop schema if exists source_mart cascade;
drop schema if exists source_raw cascade;

create schema source_control;
create schema source_mart_control;
create schema source_mart;
create schema source_raw;
create schema if not exists publication;

drop server if exists serving_snapshot_source cascade;
create server serving_snapshot_source
  foreign data wrapper postgres_fdw
  options (
    host :'source_host',
    port :'source_port',
    dbname :'source_db'
  );

create user mapping for current_user
  server serving_snapshot_source
  options (
    user :'source_user',
    password :'source_password'
  );

import foreign schema control
  limit to (
    competitions,
    historical_stat_definitions
  )
  from server serving_snapshot_source
  into source_control;

import foreign schema mart_control
  limit to (
    competition_season_config
  )
  from server serving_snapshot_source
  into source_mart_control;

import foreign schema mart
  limit to (
    competition_historical_stats,
    competition_structure_hub,
    dim_coach,
    dim_competition,
    dim_date,
    dim_group,
    dim_player,
    dim_round,
    dim_stage,
    dim_team,
    dim_tie,
    dim_venue,
    fact_fixture_lineups,
    fact_fixture_player_stats,
    fact_group_standings,
    fact_match_events,
    fact_matches,
    fact_stage_progression,
    fact_tie_results,
    player_match_summary,
    stg_player_transfers,
    stg_team_coaches
  )
  from server serving_snapshot_source
  into source_mart;

import foreign schema raw
  limit to (
    coaches,
    competition_rounds,
    competition_stages,
    fixture_lineups,
    fixture_player_statistics,
    fixtures,
    match_events,
    match_statistics,
    player_transfers,
    standings_snapshots,
    team_coaches
  )
  from server serving_snapshot_source
  into source_raw;

drop table if exists publication.serving_scope;
create table publication.serving_scope (
  competition_key text not null,
  canonical_competition_id bigint not null,
  source_competition_id bigint not null,
  season_query_id int not null,
  season_label text not null,
  primary key (source_competition_id, season_query_id, season_label)
);

insert into publication.serving_scope (
  competition_key,
  canonical_competition_id,
  source_competition_id,
  season_query_id,
  season_label
)
values
  ('brasileirao_a', 71, 71, 2021, '2021'),
  ('brasileirao_a', 71, 71, 2022, '2022'),
  ('brasileirao_a', 71, 71, 2023, '2023'),
  ('brasileirao_a', 71, 71, 2024, '2024'),
  ('brasileirao_a', 71, 71, 2025, '2025'),
  ('brasileirao_a', 71, 648, 2021, '2021'),
  ('brasileirao_a', 71, 648, 2022, '2022'),
  ('brasileirao_a', 71, 648, 2023, '2023'),
  ('brasileirao_a', 71, 648, 2024, '2024'),
  ('brasileirao_a', 71, 648, 2025, '2025'),
  ('brasileirao_b', 651, 651, 2021, '2021'),
  ('brasileirao_b', 651, 651, 2022, '2022'),
  ('brasileirao_b', 651, 651, 2023, '2023'),
  ('brasileirao_b', 651, 651, 2024, '2024'),
  ('brasileirao_b', 651, 651, 2025, '2025'),
  ('libertadores', 390, 390, 2021, '2021'),
  ('libertadores', 390, 390, 2022, '2022'),
  ('libertadores', 390, 390, 2023, '2023'),
  ('libertadores', 390, 390, 2024, '2024'),
  ('libertadores', 390, 390, 2025, '2025'),
  ('libertadores', 390, 1122, 2021, '2021'),
  ('libertadores', 390, 1122, 2022, '2022'),
  ('libertadores', 390, 1122, 2023, '2023'),
  ('libertadores', 390, 1122, 2024, '2024'),
  ('libertadores', 390, 1122, 2025, '2025'),
  ('sudamericana', 1116, 1116, 2024, '2024'),
  ('sudamericana', 1116, 1116, 2025, '2025'),
  ('copa_do_brasil', 732, 732, 2021, '2021'),
  ('copa_do_brasil', 732, 732, 2022, '2022'),
  ('copa_do_brasil', 732, 732, 2023, '2023'),
  ('copa_do_brasil', 732, 732, 2024, '2024'),
  ('copa_do_brasil', 732, 732, 2025, '2025'),
  ('copa_do_brasil', 732, 654, 2021, '2021'),
  ('copa_do_brasil', 732, 654, 2022, '2022'),
  ('copa_do_brasil', 732, 654, 2023, '2023'),
  ('copa_do_brasil', 732, 654, 2024, '2024'),
  ('copa_do_brasil', 732, 654, 2025, '2025'),
  ('supercopa_do_brasil', 1798, 1798, 2025, '2025'),
  ('fifa_intercontinental_cup', 1452, 1452, 2024, '2024'),
  ('premier_league', 8, 8, 2021, '2021_22'),
  ('premier_league', 8, 8, 2022, '2022_23'),
  ('premier_league', 8, 8, 2023, '2023_24'),
  ('premier_league', 8, 8, 2024, '2024_25'),
  ('champions_league', 2, 2, 2021, '2021_22'),
  ('champions_league', 2, 2, 2022, '2022_23'),
  ('champions_league', 2, 2, 2023, '2023_24'),
  ('champions_league', 2, 2, 2024, '2024_25'),
  ('la_liga', 564, 564, 2021, '2021_22'),
  ('la_liga', 564, 564, 2022, '2022_23'),
  ('la_liga', 564, 564, 2023, '2023_24'),
  ('la_liga', 564, 564, 2024, '2024_25'),
  ('serie_a_it', 384, 384, 2021, '2021_22'),
  ('serie_a_it', 384, 384, 2022, '2022_23'),
  ('serie_a_it', 384, 384, 2023, '2023_24'),
  ('serie_a_it', 384, 384, 2024, '2024_25'),
  ('bundesliga', 82, 82, 2021, '2021_22'),
  ('bundesliga', 82, 82, 2022, '2022_23'),
  ('bundesliga', 82, 82, 2023, '2023_24'),
  ('bundesliga', 82, 82, 2024, '2024_25'),
  ('ligue_1', 301, 301, 2021, '2021_22'),
  ('ligue_1', 301, 301, 2022, '2022_23'),
  ('ligue_1', 301, 301, 2023, '2023_24'),
  ('ligue_1', 301, 301, 2024, '2024_25'),
  ('primeira_liga', 462, 462, 2023, '2023_24'),
  ('primeira_liga', 462, 462, 2024, '2024_25');

create temporary table scoped_matches as
select fm.*
from source_mart.fact_matches fm
where exists (
  select 1
  from publication.serving_scope s
  where s.source_competition_id = fm.league_id
    and s.season_query_id = fm.season
);

create temporary table provider_season_scope as
select distinct
  rf.league_id,
  rf.season,
  rf.provider_season_id
from source_raw.fixtures rf
join scoped_matches sm
  on sm.match_id = rf.fixture_id
where rf.provider_season_id is not null;

create temporary table scoped_teams as
select distinct team_id
from (
  select home_team_id as team_id from scoped_matches where home_team_id is not null
  union all
  select away_team_id from scoped_matches where away_team_id is not null
  union all
  select team_id from source_mart.fact_group_standings fgs
  where exists (
    select 1 from publication.serving_scope s
    where s.competition_key = fgs.competition_key
      and s.season_label = fgs.season_label
  )
  union all
  select team_id from source_mart.fact_stage_progression sp
  where exists (
    select 1 from publication.serving_scope s
    where s.competition_key = sp.competition_key
      and s.season_label = sp.season_label
  )
  union all
  select winner_team_id from source_mart.fact_tie_results ftr
  where winner_team_id is not null
    and exists (
      select 1 from publication.serving_scope s
      where s.competition_key = ftr.competition_key
        and s.season_label = ftr.season_label
    )
  union all
  select home_side_team_id from source_mart.fact_tie_results ftr
  where home_side_team_id is not null
    and exists (
      select 1 from publication.serving_scope s
      where s.competition_key = ftr.competition_key
        and s.season_label = ftr.season_label
    )
  union all
  select away_side_team_id from source_mart.fact_tie_results ftr
  where away_side_team_id is not null
    and exists (
      select 1 from publication.serving_scope s
      where s.competition_key = ftr.competition_key
        and s.season_label = ftr.season_label
    )
  union all
  select team_id from source_mart.player_match_summary pms
  where exists (select 1 from scoped_matches sm where sm.match_id = pms.match_id)
  union all
  select team_id from source_mart.fact_fixture_lineups fl
  where exists (select 1 from scoped_matches sm where sm.match_id = fl.match_id)
  union all
  select team_id from source_mart.fact_fixture_player_stats fps
  where exists (select 1 from scoped_matches sm where sm.match_id = fps.match_id)
) candidates
where team_id is not null;

create temporary table scoped_transfers as
select spt.*
from source_mart.stg_player_transfers spt
where exists (
  select 1 from scoped_teams st
  where st.team_id in (spt.from_team_id, spt.to_team_id)
);

create temporary table scoped_players as
select distinct player_id
from (
  select player_id from source_mart.player_match_summary pms
  where exists (select 1 from scoped_matches sm where sm.match_id = pms.match_id)
  union all
  select player_id from source_mart.fact_match_events fme
  where exists (select 1 from scoped_matches sm where sm.match_id = fme.match_id)
  union all
  select assist_player_id from source_mart.fact_match_events fme
  where assist_player_id is not null
    and exists (select 1 from scoped_matches sm where sm.match_id = fme.match_id)
  union all
  select player_id from source_mart.fact_fixture_lineups fl
  where exists (select 1 from scoped_matches sm where sm.match_id = fl.match_id)
  union all
  select player_id from source_mart.fact_fixture_player_stats fps
  where exists (select 1 from scoped_matches sm where sm.match_id = fps.match_id)
  union all
  select player_id from source_raw.fixture_lineups rl
  where exists (select 1 from scoped_matches sm where sm.match_id = rl.fixture_id)
  union all
  select player_id from source_raw.fixture_player_statistics rps
  where exists (select 1 from scoped_matches sm where sm.match_id = rps.fixture_id)
  union all
  select player_id from scoped_transfers
) candidates
where player_id is not null;

create temporary table supporting_transfer_teams as
select distinct team_id
from (
  select from_team_id as team_id from scoped_transfers where from_team_id is not null
  union all
  select to_team_id from scoped_transfers where to_team_id is not null
) candidates
where team_id is not null;

create temporary table scoped_stages as
select distinct stage_id
from (
  select stage_id from scoped_matches where stage_id is not null
  union all
  select stage_id from source_mart.dim_stage ds
  where exists (
    select 1 from publication.serving_scope s
    where s.competition_key = ds.competition_key
      and s.season_label = ds.season_label
  )
  union all
  select stage_id from source_mart.fact_group_standings fgs
  where exists (
    select 1 from publication.serving_scope s
    where s.competition_key = fgs.competition_key
      and s.season_label = fgs.season_label
  )
  union all
  select stage_id from source_mart.fact_tie_results ftr
  where exists (
    select 1 from publication.serving_scope s
    where s.competition_key = ftr.competition_key
      and s.season_label = ftr.season_label
  )
  union all
  select from_stage_id from source_mart.competition_structure_hub csh
  where exists (
    select 1 from publication.serving_scope s
    where s.competition_key = csh.competition_key
      and s.season_label = csh.season_label
  )
  union all
  select to_stage_id from source_mart.competition_structure_hub csh
  where to_stage_id is not null
    and exists (
      select 1 from publication.serving_scope s
      where s.competition_key = csh.competition_key
        and s.season_label = csh.season_label
    )
) candidates
where stage_id is not null;

insert into control.competitions
select c.*
from source_control.competitions c
where exists (
  select 1 from publication.serving_scope s
  where s.competition_key = c.competition_key
);

insert into control.historical_stat_definitions
select * from source_control.historical_stat_definitions;

insert into mart_control.competition_season_config
select csc.*
from source_mart_control.competition_season_config csc
where exists (
  select 1 from publication.serving_scope s
  where s.competition_key = csc.competition_key
    and s.season_label = csc.season_label
);

insert into mart.dim_competition
select dc.*
from source_mart.dim_competition dc
where exists (
  select 1 from publication.serving_scope s
  where s.source_competition_id = dc.league_id
     or s.canonical_competition_id = dc.league_id
);

insert into mart.dim_date
select dd.*
from source_mart.dim_date dd
where exists (
  select 1 from scoped_matches sm
  where sm.date_sk = dd.date_sk
);

insert into mart.dim_team
select dt.*
from source_mart.dim_team dt
where exists (
  select 1 from scoped_teams st
  where st.team_id = dt.team_id
)
or exists (
  select 1 from supporting_transfer_teams st
  where st.team_id = dt.team_id
);

insert into mart.dim_player
select dp.*
from source_mart.dim_player dp
where exists (
  select 1 from scoped_players sp
  where sp.player_id = dp.player_id
);

insert into mart.dim_venue
select dv.*
from source_mart.dim_venue dv
where exists (
  select 1
  from source_raw.fixtures rf
  join scoped_matches sm
    on sm.match_id = rf.fixture_id
  where rf.venue_id = dv.venue_id
);

insert into mart.dim_stage
select ds.*
from source_mart.dim_stage ds
where exists (
  select 1 from scoped_stages ss
  where ss.stage_id = ds.stage_id
)
or exists (
  select 1 from publication.serving_scope s
  where s.competition_key = ds.competition_key
    and s.season_label = ds.season_label
);

insert into mart.dim_round
select dr.*
from source_mart.dim_round dr
where exists (
  select 1 from scoped_stages ss
  where ss.stage_id = dr.stage_id
)
or exists (
  select 1 from scoped_matches sm
  where sm.round_id = dr.round_id
);

insert into mart.dim_group
select dg.*
from source_mart.dim_group dg
where exists (
  select 1 from publication.serving_scope s
  where s.competition_key = dg.competition_key
    and s.season_label = dg.season_label
);

insert into mart.dim_tie
select dt.*
from source_mart.dim_tie dt
where exists (
  select 1 from publication.serving_scope s
  where s.competition_key = dt.competition_key
    and s.season_label = dt.season_label
);

insert into mart.dim_coach
select dc.*
from source_mart.dim_coach dc
where exists (
  select 1
  from source_mart.stg_team_coaches tc
  join scoped_teams st
    on st.team_id = tc.team_id
  where tc.coach_id = dc.coach_id
);

insert into raw.fixtures
select rf.*
from source_raw.fixtures rf
where exists (
  select 1 from scoped_matches sm
  where sm.match_id = rf.fixture_id
);

insert into raw.match_statistics
select ms.*
from source_raw.match_statistics ms
where exists (
  select 1 from scoped_matches sm
  where sm.match_id = ms.fixture_id
);

insert into raw.fixture_lineups
select fl.*
from source_raw.fixture_lineups fl
where exists (
  select 1 from scoped_matches sm
  where sm.match_id = fl.fixture_id
);

insert into raw.fixture_player_statistics
select fps.*
from source_raw.fixture_player_statistics fps
where exists (
  select 1 from scoped_matches sm
  where sm.match_id = fps.fixture_id
);

insert into raw.match_events
select me.*
from source_raw.match_events me
where exists (
  select 1 from scoped_matches sm
  where sm.match_id = me.fixture_id
);

insert into raw.player_transfers
select rpt.*
from source_raw.player_transfers rpt
where exists (
  select 1
  from scoped_transfers st
  where st.provider = rpt.provider
    and st.transfer_id = rpt.transfer_id
);

insert into raw.team_coaches
select tc.*
from source_raw.team_coaches tc
where exists (
  select 1 from scoped_teams st
  where st.team_id = tc.team_id
);

insert into raw.coaches
select rc.*
from source_raw.coaches rc
where exists (
  select 1
  from source_raw.team_coaches tc
  join scoped_teams st
    on st.team_id = tc.team_id
  where tc.provider = rc.provider
    and tc.coach_id = rc.coach_id
);

insert into raw.standings_snapshots
select ss.*
from source_raw.standings_snapshots ss
where exists (
  select 1 from provider_season_scope pss
  where pss.league_id = ss.league_id
    and pss.provider_season_id = ss.season_id
);

insert into raw.competition_stages
select cs.*
from source_raw.competition_stages cs
where exists (
  select 1 from provider_season_scope pss
  where pss.league_id = cs.league_id
    and pss.provider_season_id = cs.season_id
);

insert into raw.competition_rounds
select cr.*
from source_raw.competition_rounds cr
where exists (
  select 1 from provider_season_scope pss
  where pss.league_id = cr.league_id
    and pss.provider_season_id = cr.season_id
);

insert into mart.fact_matches
select * from scoped_matches;

insert into mart.fact_match_events
select fme.*
from source_mart.fact_match_events fme
where exists (
  select 1 from scoped_matches sm
  where sm.match_id = fme.match_id
);

insert into mart.fact_fixture_lineups
select fl.*
from source_mart.fact_fixture_lineups fl
where exists (
  select 1 from scoped_matches sm
  where sm.match_id = fl.match_id
);

insert into mart.fact_fixture_player_stats
select fps.*
from source_mart.fact_fixture_player_stats fps
where exists (
  select 1 from scoped_matches sm
  where sm.match_id = fps.match_id
);

insert into mart.fact_group_standings
select fgs.*
from source_mart.fact_group_standings fgs
where exists (
  select 1 from publication.serving_scope s
  where s.competition_key = fgs.competition_key
    and s.season_label = fgs.season_label
);

insert into mart.fact_tie_results
select ftr.*
from source_mart.fact_tie_results ftr
where exists (
  select 1 from publication.serving_scope s
  where s.competition_key = ftr.competition_key
    and s.season_label = ftr.season_label
);

insert into mart.fact_stage_progression
select sp.*
from source_mart.fact_stage_progression sp
where exists (
  select 1 from publication.serving_scope s
  where s.competition_key = sp.competition_key
    and s.season_label = sp.season_label
);

insert into mart.competition_structure_hub
select csh.*
from source_mart.competition_structure_hub csh
where exists (
  select 1 from publication.serving_scope s
  where s.competition_key = csh.competition_key
    and s.season_label = csh.season_label
);

insert into mart.player_match_summary
select pms.*
from source_mart.player_match_summary pms
where exists (
  select 1 from scoped_matches sm
  where sm.match_id = pms.match_id
);

insert into mart.competition_historical_stats
select h.*
from source_mart.competition_historical_stats h
where h.as_of_year <= 2025
  and exists (
    select 1 from publication.serving_scope s
    where s.competition_key = h.competition_key
  );

create table if not exists mart.competition_serving_summary (
  league_id bigint primary key,
  league_name text,
  matches_count integer not null default 0,
  seasons_count integer not null default 0,
  min_season integer,
  max_season integer,
  match_statistics_count integer not null default 0,
  lineups_count integer not null default 0,
  events_count integer not null default 0,
  player_statistics_count integer not null default 0,
  updated_at timestamptz not null default now()
);

delete from mart.competition_serving_summary;

insert into mart.competition_serving_summary (
  league_id,
  league_name,
  matches_count,
  seasons_count,
  min_season,
  max_season,
  match_statistics_count,
  lineups_count,
  events_count,
  player_statistics_count,
  updated_at
)
with match_totals as (
  select
    fm.league_id,
    count(distinct fm.match_id)::int as matches_count,
    count(distinct fm.season)::int as seasons_count,
    min(fm.season)::int as min_season,
    max(fm.season)::int as max_season
  from mart.fact_matches fm
  group by fm.league_id
),
match_statistics as (
  select
    rf.league_id,
    count(distinct ms.fixture_id)::int as available_count
  from raw.match_statistics ms
  inner join raw.fixtures rf
    on rf.fixture_id = ms.fixture_id
  group by rf.league_id
),
fixture_lineups as (
  select
    rf.league_id,
    count(distinct fl.fixture_id)::int as available_count
  from raw.fixture_lineups fl
  inner join raw.fixtures rf
    on rf.fixture_id = fl.fixture_id
  group by rf.league_id
),
match_events as (
  select
    rf.league_id,
    count(distinct me.fixture_id)::int as available_count
  from raw.match_events me
  inner join raw.fixtures rf
    on rf.fixture_id = me.fixture_id
  group by rf.league_id
),
fixture_player_statistics as (
  select
    rf.league_id,
    count(distinct fps.fixture_id)::int as available_count
  from raw.fixture_player_statistics fps
  inner join raw.fixtures rf
    on rf.fixture_id = fps.fixture_id
  group by rf.league_id
),
competition_names as (
  select distinct on (dc.league_id)
    dc.league_id,
    dc.league_name
  from mart.dim_competition dc
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
  on fps.league_id = mt.league_id;

drop schema if exists source_control cascade;
drop schema if exists source_mart_control cascade;
drop schema if exists source_mart cascade;
drop schema if exists source_raw cascade;
drop server if exists serving_snapshot_source cascade;

analyze;
