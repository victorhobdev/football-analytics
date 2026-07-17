\set ON_ERROR_STOP on

begin;

update shadow_dbt_20260716.fact_matches
set tie_id = null;

update shadow_dbt_20260716.fact_matches f
set tie_id = t.tie_id
from shadow_dbt_20260716.int_tie_matches t
where t.match_id = f.match_id;

drop table if exists shadow_dbt_20260716.fact_coach_match_assignment;
create table shadow_dbt_20260716.fact_coach_match_assignment
  (like shadow_serving_20260716.fact_coach_match_assignment including all);
insert into shadow_dbt_20260716.fact_coach_match_assignment
select * from shadow_serving_20260716.fact_coach_match_assignment;

-- Rebind snapshot-only views to the final target objects so the promoted mart
-- has no runtime dependency on the intermediate shadow_serving schema.
do $$
declare
  view_sql text;
begin
  select replace(
    pg_get_viewdef('shadow_dbt_20260716.int_matches_enriched'::regclass, true),
    'shadow_serving_20260716.',
    'shadow_dbt_20260716.'
  ) into view_sql;
  execute 'create or replace view shadow_dbt_20260716.int_matches_enriched as ' || view_sql;

  select replace(
    pg_get_viewdef('shadow_dbt_20260716.int_tie_matches'::regclass, true),
    'shadow_serving_20260716.',
    'shadow_dbt_20260716.'
  ) into view_sql;
  execute 'create or replace view shadow_dbt_20260716.int_tie_matches as ' || view_sql;
end $$;

do $$
begin
  if exists (
    select 1
    from shadow_dbt_20260716.fact_matches f
    left join shadow_dbt_20260716.dim_tie t using (tie_id)
    where f.tie_id is not null and t.tie_id is null
  ) then
    raise exception 'canonical fact_matches contains a stale tie_id';
  end if;
  if exists (
    select 1
    from shadow_dbt_20260716.fact_coach_match_assignment f
    left join shadow_dbt_20260716.fact_matches m using (match_id)
    left join shadow_dbt_20260716.dim_team t using (team_id)
    where m.match_id is null or t.team_id is null
  ) then
    raise exception 'coach assignment contains an orphan identity';
  end if;
end $$;

commit;
