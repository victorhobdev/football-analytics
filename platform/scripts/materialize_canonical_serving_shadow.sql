-- Materializes the approved team/match result and every persisted match child.
-- The active mart and raw schemas remain untouched.

\set ON_ERROR_STOP on

begin;

create schema if not exists shadow_serving_20260716;

drop table if exists shadow_serving_20260716.dim_team cascade;
create table shadow_serving_20260716.dim_team
  (like mart.dim_team including all);

insert into shadow_serving_20260716.dim_team (
  team_sk, team_id, team_name, logo_url, updated_at
)
select
  md5(concat('team:', c.canonical_team_id::text)),
  c.canonical_team_id,
  c.team_name,
  (array_agg(d.logo_url order by
     case when d.logo_url is not null then 0 else 1 end,
     d.updated_at desc nulls last,
     d.team_id
   ))[1],
  max(d.updated_at)
from shadow_team_identity_20260715.canonical_team c
left join shadow_team_identity_20260715.provider_entity_map p
  on p.canonical_team_id = c.canonical_team_id
 and p.provider = 'legacy_dim_team'
 and p.entity_type = 'team'
left join mart.dim_team d on d.team_id::text = p.source_id
group by c.canonical_team_id, c.team_name;

drop table if exists shadow_serving_20260716.fact_matches cascade;
create table shadow_serving_20260716.fact_matches
  (like mart.fact_matches including all);

with ranked_source as (
  select
    m.match_group_key,
    m.canonical_match_id,
    m.source_match_id,
    row_number() over (
      partition by m.match_group_key
      order by s.source_priority desc, m.source_match_id
    ) as source_rank
  from shadow_match_dedup_20260715.match_group_member m
  join shadow_match_dedup_20260715.source_match s
    on s.source_match_id = m.source_match_id
), survivor as (
  select * from ranked_source where source_rank = 1
)
insert into shadow_serving_20260716.fact_matches (
  match_id, competition_sk, date_sk, home_team_sk, away_team_sk, venue_sk,
  provider, provider_league_id, competition_key, competition_type, league_id,
  season, season_label, provider_season_id, date_day, match_ingested_run,
  match_ingested_at, source_watermark, round, round_name, stage_id, stage_sk,
  stage_name, round_id, round_sk, group_id, tie_id, leg_number, round_number,
  is_knockout, home_team_id, away_team_id, venue_id, home_goals, away_goals,
  total_goals, result, home_shots, home_shots_on_target, home_possession,
  home_corners, home_fouls, away_shots, away_shots_on_target, away_possession,
  away_corners, away_fouls, updated_at
)
select
  u.canonical_match_id,
  f.competition_sk,
  f.date_sk,
  md5(concat('team:', u.canonical_home_team_id::text)),
  md5(concat('team:', u.canonical_away_team_id::text)),
  f.venue_sk,
  f.provider,
  f.provider_league_id,
  u.competition_key,
  f.competition_type,
  f.league_id,
  f.season,
  u.season_label,
  f.provider_season_id,
  u.date_day,
  f.match_ingested_run,
  f.match_ingested_at,
  f.source_watermark,
  f.round,
  f.round_name,
  f.stage_id,
  f.stage_sk,
  f.stage_name,
  f.round_id,
  f.round_sk,
  f.group_id,
  f.tie_id,
  f.leg_number,
  f.round_number,
  f.is_knockout,
  u.canonical_home_team_id,
  u.canonical_away_team_id,
  f.venue_id,
  u.home_goals,
  u.away_goals,
  coalesce(u.home_goals, 0) + coalesce(u.away_goals, 0),
  coalesce(case
    when u.home_goals > u.away_goals then 'Home Win'
    when u.home_goals < u.away_goals then 'Away Win'
    when u.home_goals = u.away_goals then 'Draw'
  end, f.result),
  u.home_shots,
  u.home_shots_on_target,
  u.home_possession,
  u.home_corners,
  u.home_fouls,
  u.away_shots,
  u.away_shots_on_target,
  u.away_possession,
  u.away_corners,
  u.away_fouls,
  f.updated_at
from shadow_match_dedup_20260715.fused_fact_matches u
join survivor s on s.match_group_key = u.match_group_key
join mart.fact_matches f on f.match_id = s.source_match_id;

drop table if exists shadow_serving_20260716.fact_match_events cascade;
create table shadow_serving_20260716.fact_match_events
  (like mart.fact_match_events including all);
insert into shadow_serving_20260716.fact_match_events
select
  e.event_id,
  m.canonical_match_id,
  case
    when sb.canonical_team_id is not null then md5(concat('team:', sb.canonical_team_id::text))
    when lm.canonical_team_id is not null then md5(concat('team:', lm.canonical_team_id::text))
    when e.team_id = f.home_team_id then md5(concat('team:', g.canonical_home_team_id::text))
    when e.team_id = f.away_team_id then md5(concat('team:', g.canonical_away_team_id::text))
    else null
  end,
  e.player_sk,
  e.assist_player_sk,
  case
    when sb.canonical_team_id is not null then sb.canonical_team_id
    when lm.canonical_team_id is not null then lm.canonical_team_id
    when e.team_id = f.home_team_id then g.canonical_home_team_id
    when e.team_id = f.away_team_id then g.canonical_away_team_id
    else null
  end,
  e.player_id, e.assist_player_id, e.time_elapsed, e.time_extra,
  e.is_time_elapsed_anomalous, e.event_type, e.event_detail, e.is_goal, e.updated_at
from mart.fact_match_events e
join mart.fact_matches f on f.match_id = e.match_id
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
join shadow_match_dedup_20260715.match_group g on g.match_group_key = m.match_group_key
left join shadow_team_identity_20260715.provider_entity_map sb
  on sb.provider = 'statsbomb_open_data'
 and sb.entity_type = 'team'
 and e.team_id between 910000000000 and 919999999999
 and sb.source_id = (e.team_id - 910000000000)::text
left join shadow_team_identity_20260715.provider_entity_map lm
  on lm.provider = 'legacy_dim_team'
 and lm.entity_type = 'team'
 and lm.source_id = e.team_id::text
 and (lm.valid_from is null or lm.valid_from <= f.date_day)
 and (lm.valid_to is null or f.date_day < lm.valid_to);

drop table if exists shadow_serving_20260716.fact_fixture_lineups cascade;
create table shadow_serving_20260716.fact_fixture_lineups
  (like mart.fact_fixture_lineups including all);
insert into shadow_serving_20260716.fact_fixture_lineups
select
  e.fixture_lineup_id, e.provider, m.canonical_match_id,
  case when e.team_id = f.home_team_id then md5(concat('team:', g.canonical_home_team_id::text))
       when e.team_id = f.away_team_id then md5(concat('team:', g.canonical_away_team_id::text)) end,
  e.player_sk,
  case when e.team_id = f.home_team_id then g.canonical_home_team_id
       when e.team_id = f.away_team_id then g.canonical_away_team_id end,
  e.player_id, e.player_name, e.lineup_id, e.position_id, e.position_name,
  e.lineup_type_id, e.is_starter, e.formation_field, e.formation_position,
  e.jersey_number, e.minutes_played, e.details, e.ingested_run, e.updated_at
from mart.fact_fixture_lineups e
join mart.fact_matches f on f.match_id = e.match_id
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
join shadow_match_dedup_20260715.match_group g on g.match_group_key = m.match_group_key;

drop table if exists shadow_serving_20260716.fact_fixture_player_stats cascade;
create table shadow_serving_20260716.fact_fixture_player_stats
  (like mart.fact_fixture_player_stats including all);
insert into shadow_serving_20260716.fact_fixture_player_stats
select
  e.fixture_player_stat_id, e.provider, m.canonical_match_id, e.competition_sk,
  e.season, e.match_date,
  case when e.team_id = f.home_team_id then md5(concat('team:', g.canonical_home_team_id::text))
       when e.team_id = f.away_team_id then md5(concat('team:', g.canonical_away_team_id::text)) end,
  e.player_sk,
  case when e.team_id = f.home_team_id then g.canonical_home_team_id
       when e.team_id = f.away_team_id then g.canonical_away_team_id end,
  e.player_id, c.team_name, e.player_name, e.position_name, e.is_starter,
  e.minutes_played, e.goals, e.assists, e.shots_total, e.shots_on_goal,
  e.passes_total, e.key_passes, e.tackles, e.interceptions, e.duels,
  e.fouls_committed, e.yellow_cards, e.red_cards, e.goalkeeper_saves,
  e.clean_sheets, e.xg, e.rating, e.statistics, e.ingested_run, e.updated_at
from mart.fact_fixture_player_stats e
join mart.fact_matches f on f.match_id = e.match_id
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
join shadow_match_dedup_20260715.match_group g on g.match_group_key = m.match_group_key
left join shadow_team_identity_20260715.canonical_team c
  on c.canonical_team_id = case
    when e.team_id = f.home_team_id then g.canonical_home_team_id
    when e.team_id = f.away_team_id then g.canonical_away_team_id
  end;

drop table if exists shadow_serving_20260716.fact_elo_match_team_stats cascade;
create table shadow_serving_20260716.fact_elo_match_team_stats
  (like mart.fact_elo_match_team_stats including all);
insert into shadow_serving_20260716.fact_elo_match_team_stats
select
  e.elo_match_team_stat_id, m.canonical_match_id, e.competition_sk,
  e.competition_key, e.match_date, e.side,
  case when e.side = 'home' then g.canonical_home_team_id
       when e.side = 'away' then g.canonical_away_team_id end,
  md5(concat('team:', (case when e.side = 'home' then g.canonical_home_team_id
                            when e.side = 'away' then g.canonical_away_team_id end)::text)),
  c.team_name, e.elo_rating, e.form3, e.form5, e.shots, e.shots_on_target,
  e.fouls, e.corners, e.yellow_cards, e.red_cards, e.half_time_goals,
  e.full_time_goals, e.ft_result, e.ht_result, e.source_provider,
  e.source_match_id, e.updated_at
from mart.fact_elo_match_team_stats e
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
join shadow_match_dedup_20260715.match_group g on g.match_group_key = m.match_group_key
left join shadow_team_identity_20260715.canonical_team c
  on c.canonical_team_id = case when e.side = 'home' then g.canonical_home_team_id
                                when e.side = 'away' then g.canonical_away_team_id end;

drop table if exists shadow_serving_20260716.fact_transfermarkt_match_events cascade;
create table shadow_serving_20260716.fact_transfermarkt_match_events
  (like mart.fact_transfermarkt_match_events including all);
insert into shadow_serving_20260716.fact_transfermarkt_match_events
select
  e.transfermarkt_event_id, e.source_event_hash, e.source_event_id,
  e.source_provider, m.canonical_match_id, e.competition_sk, e.competition_key,
  e.match_date, e.player_id, e.player_sk, e.player_in_id, e.player_in_sk,
  e.assist_player_id, e.assist_player_sk, e.tm_player_id, e.tm_club_id,
  e.club_name, e.minute, e.event_type, e.description, e.updated_at
from mart.fact_transfermarkt_match_events e
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id;

drop table if exists shadow_serving_20260716.fact_match_odds cascade;
create table shadow_serving_20260716.fact_match_odds
  (like mart.fact_match_odds including all);
insert into shadow_serving_20260716.fact_match_odds
select
  m.canonical_match_id, e.competition_sk, e.competition_key, e.match_date,
  e.odd_home, e.odd_draw, e.odd_away, e.max_home, e.max_draw, e.max_away,
  e.over25, e.under25, e.max_over25, e.max_under25, e.handicap_size,
  e.handicap_home, e.handicap_away, e.source_provider, e.source_match_id, e.updated_at
from mart.fact_match_odds e
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id;

drop table if exists shadow_serving_20260716.fact_transfermarkt_appearances cascade;
create table shadow_serving_20260716.fact_transfermarkt_appearances
  (like mart.fact_transfermarkt_appearances including all);
insert into shadow_serving_20260716.fact_transfermarkt_appearances
select
  e.transfermarkt_appearance_id, e.source_appearance_hash, e.source_appearance_id,
  e.source_provider, m.canonical_match_id, e.competition_sk, e.competition_key,
  e.match_date, e.player_id, e.player_sk, e.tm_player_id, e.player_name,
  e.player_club_id, e.player_current_club_id, e.tm_competition_id,
  e.minutes_played, e.goals, e.assists, e.yellow_cards, e.red_cards, e.updated_at
from mart.fact_transfermarkt_appearances e
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id;

drop table if exists shadow_serving_20260716.fact_transfermarkt_lineups cascade;
create table shadow_serving_20260716.fact_transfermarkt_lineups
  (like mart.fact_transfermarkt_lineups including all);
insert into shadow_serving_20260716.fact_transfermarkt_lineups
select
  e.transfermarkt_lineup_id, e.source_lineup_hash, e.source_lineup_id,
  e.source_provider, m.canonical_match_id, e.competition_sk, e.competition_key,
  e.match_date, e.player_id, e.player_sk, e.tm_player_id, e.tm_club_id,
  e.player_name, e.lineup_type, e.position_name, e.shirt_number,
  e.is_captain, e.updated_at
from mart.fact_transfermarkt_lineups e
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id;

drop table if exists shadow_serving_20260716.fact_coach_match_assignment cascade;
create table shadow_serving_20260716.fact_coach_match_assignment
  (like mart.fact_coach_match_assignment including all);
insert into shadow_serving_20260716.fact_coach_match_assignment
select
  m.canonical_match_id,
  case when e.team_id = f.home_team_id then g.canonical_home_team_id
       when e.team_id = f.away_team_id then g.canonical_away_team_id end,
  e.coach_identity_id, e.coach_tenure_id, e.assignment_method,
  e.assignment_confidence, e.conflict_reason, e.is_public_eligible,
  e.source, e.source_record_id, e.created_at, e.updated_at
from mart.fact_coach_match_assignment e
join mart.fact_matches f on f.match_id = e.match_id
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
join shadow_match_dedup_20260715.match_group g on g.match_group_key = m.match_group_key;

-- Preserve the active access paths so the transactional swap does not turn a
-- semantic correction into an API performance regression.
do $$
declare
  index_row record;
begin
  for index_row in
    select indexdef, tablename
    from pg_indexes
    where schemaname = 'mart'
      and tablename in (
        'dim_team', 'fact_matches', 'fact_match_events',
        'fact_fixture_lineups', 'fact_fixture_player_stats',
        'fact_elo_match_team_stats', 'fact_transfermarkt_match_events',
        'fact_match_odds', 'fact_transfermarkt_appearances',
        'fact_transfermarkt_lineups', 'fact_coach_match_assignment'
      )
  loop
    execute replace(
      replace(index_row.indexdef, 'CREATE INDEX ', 'CREATE INDEX IF NOT EXISTS '),
      ' ON mart.' || index_row.tablename,
      ' ON shadow_serving_20260716.' || index_row.tablename
    );
  end loop;
end $$;

analyze shadow_serving_20260716.dim_team;
analyze shadow_serving_20260716.fact_matches;
analyze shadow_serving_20260716.fact_match_events;

do $$
begin
  if (select count(*) from shadow_serving_20260716.dim_team) <> 1930 then
    raise exception 'canonical dim_team count changed';
  end if;
  if (select count(*) from shadow_serving_20260716.fact_matches) <> 248853 then
    raise exception 'canonical fact_matches count changed';
  end if;
  if exists (select 1 from shadow_serving_20260716.fact_matches where home_team_id = away_team_id) then
    raise exception 'canonical match has equal home and away team';
  end if;
  if exists (
    select 1 from shadow_serving_20260716.fact_matches f
    left join shadow_serving_20260716.dim_team h on h.team_id = f.home_team_id
    left join shadow_serving_20260716.dim_team a on a.team_id = f.away_team_id
    where h.team_id is null or a.team_id is null
  ) then
    raise exception 'canonical match has an orphan team';
  end if;
end $$;

commit;

select 'dim_team' as relation, count(*) from shadow_serving_20260716.dim_team
union all select 'fact_matches', count(*) from shadow_serving_20260716.fact_matches
union all select 'fact_match_events', count(*) from shadow_serving_20260716.fact_match_events
union all select 'fact_fixture_lineups', count(*) from shadow_serving_20260716.fact_fixture_lineups
union all select 'fact_fixture_player_stats', count(*) from shadow_serving_20260716.fact_fixture_player_stats
union all select 'fact_elo_match_team_stats', count(*) from shadow_serving_20260716.fact_elo_match_team_stats
union all select 'fact_transfermarkt_match_events', count(*) from shadow_serving_20260716.fact_transfermarkt_match_events
union all select 'fact_match_odds', count(*) from shadow_serving_20260716.fact_match_odds
union all select 'fact_transfermarkt_appearances', count(*) from shadow_serving_20260716.fact_transfermarkt_appearances
union all select 'fact_transfermarkt_lineups', count(*) from shadow_serving_20260716.fact_transfermarkt_lineups
union all select 'fact_coach_match_assignment', count(*) from shadow_serving_20260716.fact_coach_match_assignment;
