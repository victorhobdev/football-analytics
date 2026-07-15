-- SQL-only, non-destructive match reconciliation.
-- Exact semantic duplicates are collapsed in shadow; near-day matches remain
-- review candidates. Raw tables and active marts are never modified.

\set ON_ERROR_STOP on

create schema if not exists shadow_match_dedup_20260715;
create sequence if not exists shadow_match_dedup_20260715.canonical_match_id_seq start with 4000000000000;

create table if not exists shadow_match_dedup_20260715.source_match (
  source_match_id bigint primary key,
  provider text not null,
  source_priority integer not null,
  date_day date,
  canonical_home_team_id bigint,
  canonical_away_team_id bigint,
  competition_key text,
  season_label text,
  home_goals integer,
  away_goals integer,
  home_shots integer,
  home_shots_on_target integer,
  home_possession integer,
  home_corners integer,
  home_fouls integer,
  away_shots integer,
  away_shots_on_target integer,
  away_possession integer,
  away_corners integer,
  away_fouls integer,
  match_group_key text not null
);

create index if not exists ix_shadow_source_match_group
  on shadow_match_dedup_20260715.source_match (match_group_key);
create index if not exists ix_shadow_source_match_lookup
  on shadow_match_dedup_20260715.source_match
    (canonical_home_team_id, canonical_away_team_id, competition_key, season_label, date_day);
alter table shadow_match_dedup_20260715.source_match
  add column if not exists date_utc timestamptz;

create table if not exists shadow_match_dedup_20260715.match_group (
  match_group_key text primary key,
  canonical_match_id bigint not null unique,
  date_day date,
  canonical_home_team_id bigint,
  canonical_away_team_id bigint,
  competition_key text,
  season_label text,
  home_goals integer,
  away_goals integer,
  source_count integer not null,
  provider_count integer not null,
  decision_status text not null,
  duplicate_of text,
  evidence jsonb not null default '{}'::jsonb
);

create table if not exists shadow_match_dedup_20260715.match_group_member (
  match_group_key text not null references shadow_match_dedup_20260715.match_group(match_group_key),
  canonical_match_id bigint not null,
  source_match_id bigint not null,
  provider text not null,
  date_day date,
  primary key (match_group_key, source_match_id)
);

create table if not exists shadow_match_dedup_20260715.fused_fact_matches (
  canonical_match_id bigint primary key,
  match_group_key text not null unique,
  date_day date,
  canonical_home_team_id bigint,
  canonical_away_team_id bigint,
  competition_key text,
  season_label text,
  home_goals integer,
  away_goals integer,
  home_shots integer,
  home_shots_on_target integer,
  home_possession integer,
  home_corners integer,
  home_fouls integer,
  away_shots integer,
  away_shots_on_target integer,
  away_possession integer,
  away_corners integer,
  away_fouls integer,
  source_match_ids bigint[] not null,
  source_providers text[] not null,
  source_attributes jsonb not null default '[]'::jsonb
);

create table if not exists shadow_match_dedup_20260715.attribute_conflict (
  match_group_key text not null,
  canonical_match_id bigint not null,
  attribute text not null,
  distinct_values text[] not null,
  primary key (match_group_key, attribute)
);

create table if not exists shadow_match_dedup_20260715.near_day_candidate (
  left_match_id bigint not null,
  right_match_id bigint not null,
  day_delta integer not null,
  provider_pair text[] not null,
  match_group_left text not null,
  match_group_right text not null,
  decision_status text not null default 'manual_review',
  evidence jsonb not null default '{}'::jsonb,
  primary key (left_match_id, right_match_id)
);

create table if not exists shadow_match_dedup_20260715.child_inventory (
  child_relation text primary key,
  source_rows bigint not null,
  matched_rows bigint not null,
  touched_match_groups bigint not null,
  source_match_ids bigint not null
);

truncate shadow_match_dedup_20260715.source_match;

insert into shadow_match_dedup_20260715.source_match (
  source_match_id, provider, source_priority, date_day,
  date_utc,
  canonical_home_team_id, canonical_away_team_id, competition_key, season_label,
  home_goals, away_goals, home_shots, home_shots_on_target, home_possession,
  home_corners, home_fouls, away_shots, away_shots_on_target, away_possession,
  away_corners, away_fouls, match_group_key
)
select
  f.match_id,
  f.provider,
  case f.provider
    when 'sportmonks' then 500
    when 'dataset_brasileirao' then 400
    when 'transfermarkt' then 300
    when 'eloratings' then 200
    when 'statsbomb_open_data' then 100
    else 50
  end,
  f.date_day,
  st.date_utc,
  f.canonical_home_team_id,
  f.canonical_away_team_id,
  f.competition_key,
  f.season_label,
  f.home_goals,
  f.away_goals,
  f.home_shots,
  f.home_shots_on_target,
  f.home_possession,
  f.home_corners,
  f.home_fouls,
  f.away_shots,
  f.away_shots_on_target,
  f.away_possession,
  f.away_corners,
  f.away_fouls,
  md5(concat_ws('|',
    coalesce(f.date_day::text, ''),
    coalesce(f.canonical_home_team_id::text, ''),
    coalesce(f.canonical_away_team_id::text, ''),
    coalesce(f.competition_key, ''),
    coalesce(f.season_label, ''),
    coalesce(f.home_goals::text, ''),
    coalesce(f.away_goals::text, '')
  ))
from shadow_team_identity_20260715.fact_matches_rekeyed f
left join mart.stg_matches st on st.fixture_id = f.match_id;

truncate shadow_match_dedup_20260715.match_group_member;
delete from shadow_match_dedup_20260715.match_group g
where not exists (
  select 1
  from shadow_match_dedup_20260715.source_match s
  where s.match_group_key = g.match_group_key
);

insert into shadow_match_dedup_20260715.match_group (
  match_group_key, canonical_match_id, date_day, canonical_home_team_id,
  canonical_away_team_id, competition_key, season_label, home_goals, away_goals,
  source_count, provider_count, decision_status, evidence
)
select
  s.match_group_key,
  coalesce(old.canonical_match_id, nextval('shadow_match_dedup_20260715.canonical_match_id_seq')),
  min(s.date_day),
  min(s.canonical_home_team_id),
  min(s.canonical_away_team_id),
  min(s.competition_key),
  min(s.season_label),
  min(s.home_goals),
  min(s.away_goals),
  count(*),
  count(distinct s.provider),
  case when count(*) > 1 then 'duplicate_exact' else 'singleton' end,
  jsonb_build_object('group_rule', 'date+canonical_home+canonical_away+competition+edition+score')
from shadow_match_dedup_20260715.source_match s
left join shadow_match_dedup_20260715.match_group old using (match_group_key)
group by s.match_group_key, old.canonical_match_id
on conflict (match_group_key) do update set
  date_day = excluded.date_day,
  canonical_home_team_id = excluded.canonical_home_team_id,
  canonical_away_team_id = excluded.canonical_away_team_id,
  competition_key = excluded.competition_key,
  season_label = excluded.season_label,
  home_goals = excluded.home_goals,
  away_goals = excluded.away_goals,
  source_count = excluded.source_count,
  provider_count = excluded.provider_count,
  decision_status = excluded.decision_status,
  evidence = excluded.evidence;

insert into shadow_match_dedup_20260715.match_group_member (
  match_group_key, canonical_match_id, source_match_id, provider, date_day
)
select s.match_group_key, g.canonical_match_id, s.source_match_id, s.provider, s.date_day
from shadow_match_dedup_20260715.source_match s
join shadow_match_dedup_20260715.match_group g using (match_group_key);

truncate shadow_match_dedup_20260715.fused_fact_matches;
insert into shadow_match_dedup_20260715.fused_fact_matches (
  canonical_match_id, match_group_key, date_day, canonical_home_team_id,
  canonical_away_team_id, competition_key, season_label, home_goals, away_goals,
  home_shots, home_shots_on_target, home_possession, home_corners, home_fouls,
  away_shots, away_shots_on_target, away_possession, away_corners, away_fouls,
  source_match_ids, source_providers, source_attributes
)
select
  g.canonical_match_id,
  g.match_group_key,
  g.date_day,
  g.canonical_home_team_id,
  g.canonical_away_team_id,
  g.competition_key,
  g.season_label,
  g.home_goals,
  g.away_goals,
  (array_agg(s.home_shots order by s.source_priority desc, s.source_match_id) filter (where s.home_shots is not null))[1],
  (array_agg(s.home_shots_on_target order by s.source_priority desc, s.source_match_id) filter (where s.home_shots_on_target is not null))[1],
  (array_agg(s.home_possession order by s.source_priority desc, s.source_match_id) filter (where s.home_possession is not null))[1],
  (array_agg(s.home_corners order by s.source_priority desc, s.source_match_id) filter (where s.home_corners is not null))[1],
  (array_agg(s.home_fouls order by s.source_priority desc, s.source_match_id) filter (where s.home_fouls is not null))[1],
  (array_agg(s.away_shots order by s.source_priority desc, s.source_match_id) filter (where s.away_shots is not null))[1],
  (array_agg(s.away_shots_on_target order by s.source_priority desc, s.source_match_id) filter (where s.away_shots_on_target is not null))[1],
  (array_agg(s.away_possession order by s.source_priority desc, s.source_match_id) filter (where s.away_possession is not null))[1],
  (array_agg(s.away_corners order by s.source_priority desc, s.source_match_id) filter (where s.away_corners is not null))[1],
  (array_agg(s.away_fouls order by s.source_priority desc, s.source_match_id) filter (where s.away_fouls is not null))[1],
  array_agg(s.source_match_id order by s.source_priority desc, s.source_match_id),
  array_agg(s.provider order by s.source_priority desc, s.source_match_id),
  jsonb_agg(jsonb_build_object(
    'source_match_id', s.source_match_id,
    'provider', s.provider,
    'home_shots', s.home_shots,
    'away_shots', s.away_shots,
    'home_possession', s.home_possession,
    'away_possession', s.away_possession
  ) order by s.source_priority desc, s.source_match_id)
from shadow_match_dedup_20260715.match_group g
join shadow_match_dedup_20260715.source_match s using (match_group_key)
group by g.canonical_match_id, g.match_group_key, g.date_day,
         g.canonical_home_team_id, g.canonical_away_team_id,
         g.competition_key, g.season_label, g.home_goals, g.away_goals;

truncate shadow_match_dedup_20260715.attribute_conflict;
insert into shadow_match_dedup_20260715.attribute_conflict (
  match_group_key, canonical_match_id, attribute, distinct_values
)
select s.match_group_key, g.canonical_match_id, v.attribute,
       array_agg(distinct v.value order by v.value)
from shadow_match_dedup_20260715.source_match s
join shadow_match_dedup_20260715.match_group g using (match_group_key)
cross join lateral (values
  ('home_shots', s.home_shots::text),
  ('home_shots_on_target', s.home_shots_on_target::text),
  ('home_possession', s.home_possession::text),
  ('home_corners', s.home_corners::text),
  ('home_fouls', s.home_fouls::text),
  ('away_shots', s.away_shots::text),
  ('away_shots_on_target', s.away_shots_on_target::text),
  ('away_possession', s.away_possession::text),
  ('away_corners', s.away_corners::text),
  ('away_fouls', s.away_fouls::text)
) v(attribute, value)
where v.value is not null
group by s.match_group_key, g.canonical_match_id, v.attribute
having count(distinct v.value) > 1;

truncate shadow_match_dedup_20260715.near_day_candidate;
insert into shadow_match_dedup_20260715.near_day_candidate (
  left_match_id, right_match_id, day_delta, provider_pair,
  match_group_left, match_group_right, evidence
)
select
  least(a.source_match_id, b.source_match_id),
  greatest(a.source_match_id, b.source_match_id),
  abs(a.date_day - b.date_day),
  array[a.provider, b.provider],
  a.match_group_key,
  b.match_group_key,
  jsonb_build_object(
    'rule', 'same_canonical_sides+competition+edition+score+date_delta_le_1',
    'left_date', a.date_day,
    'right_date', b.date_day,
    'left_date_utc', a.date_utc,
    'right_date_utc', b.date_utc
  )
from shadow_match_dedup_20260715.source_match a
join shadow_match_dedup_20260715.source_match b
  on a.source_match_id < b.source_match_id
 and a.provider <> b.provider
 and a.date_day is not null
 and b.date_day is not null
 and abs(a.date_day - b.date_day) = 1
 and (
   (a.date_utc is not null and b.date_utc is not null
    and abs(extract(epoch from (a.date_utc - b.date_utc))) <= 36 * 3600)
   or a.date_utc is null or b.date_utc is null
 )
 and a.canonical_home_team_id = b.canonical_home_team_id
 and a.canonical_away_team_id = b.canonical_away_team_id
 and a.competition_key = b.competition_key
 and a.season_label is not distinct from b.season_label
 and a.home_goals is not distinct from b.home_goals
 and a.away_goals is not distinct from b.away_goals
on conflict (left_match_id, right_match_id) do nothing;

truncate shadow_match_dedup_20260715.child_inventory;
insert into shadow_match_dedup_20260715.child_inventory (
  child_relation, source_rows, matched_rows, touched_match_groups, source_match_ids
)
select 'mart.fact_match_events', count(*), count(m.source_match_id), count(distinct m.match_group_key), count(distinct e.match_id)
from mart.fact_match_events e
left join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
union all
select 'mart.fact_fixture_lineups', count(*), count(m.source_match_id), count(distinct m.match_group_key), count(distinct e.match_id)
from mart.fact_fixture_lineups e
left join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
union all
select 'mart.fact_fixture_player_stats', count(*), count(m.source_match_id), count(distinct m.match_group_key), count(distinct e.match_id)
from mart.fact_fixture_player_stats e
left join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
union all
select 'mart.fact_elo_match_team_stats', count(*), count(m.source_match_id), count(distinct m.match_group_key), count(distinct e.match_id)
from mart.fact_elo_match_team_stats e
left join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
union all
select 'mart.fact_transfermarkt_match_events', count(*), count(m.source_match_id), count(distinct m.match_group_key), count(distinct e.match_id)
from mart.fact_transfermarkt_match_events e
left join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id;

select
  (select count(*) from shadow_match_dedup_20260715.source_match) as source_matches,
  (select count(*) from shadow_match_dedup_20260715.match_group) as canonical_matches,
  (select count(*) from shadow_match_dedup_20260715.match_group where source_count > 1) as exact_duplicate_groups,
  (select coalesce(sum(source_count - 1), 0) from shadow_match_dedup_20260715.match_group where source_count > 1) as exact_duplicate_excess,
  (select count(*) from shadow_match_dedup_20260715.near_day_candidate) as near_day_candidates,
  (select count(*) from shadow_match_dedup_20260715.attribute_conflict) as attribute_conflicts;

-- Child views retain every source row under one canonical match. They do not
-- sum or discard events/lineups/stats; the source row remains auditable.
create or replace view shadow_match_dedup_20260715.fused_fact_match_events as
select g.canonical_match_id, e.*
from mart.fact_match_events e
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
join shadow_match_dedup_20260715.match_group g on g.match_group_key = m.match_group_key;

create or replace view shadow_match_dedup_20260715.fused_fact_fixture_lineups as
select g.canonical_match_id, e.*
from mart.fact_fixture_lineups e
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
join shadow_match_dedup_20260715.match_group g on g.match_group_key = m.match_group_key;

create or replace view shadow_match_dedup_20260715.fused_fact_fixture_player_stats as
select g.canonical_match_id, e.*
from mart.fact_fixture_player_stats e
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
join shadow_match_dedup_20260715.match_group g on g.match_group_key = m.match_group_key;

create or replace view shadow_match_dedup_20260715.fused_fact_elo_match_team_stats as
select g.canonical_match_id, e.*
from mart.fact_elo_match_team_stats e
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
join shadow_match_dedup_20260715.match_group g on g.match_group_key = m.match_group_key;

create or replace view shadow_match_dedup_20260715.fused_fact_transfermarkt_match_events as
select g.canonical_match_id, e.*
from mart.fact_transfermarkt_match_events e
join shadow_match_dedup_20260715.match_group_member m on m.source_match_id = e.match_id
join shadow_match_dedup_20260715.match_group g on g.match_group_key = m.match_group_key;
