\set ON_ERROR_STOP on

set maintenance_work_mem = '512MB';

create index if not exists idx_fact_match_events_match_team
  on shadow_dbt_20260716.fact_match_events (match_id, team_id)
  where team_id is not null;

analyze shadow_dbt_20260716.fact_match_events;
analyze shadow_dbt_20260716.fact_matches;

do $$
begin
  if (select count(*) from shadow_dbt_20260716.dim_team) <> 1930
     or (select count(*) from shadow_dbt_20260716.fact_matches) <> 248853 then
    raise exception 'canonical target cardinality changed during preparation';
  end if;
  if not exists (
    select 1 from pg_indexes
    where schemaname = 'shadow_dbt_20260716'
      and tablename = 'fact_match_events'
      and indexname = 'idx_fact_match_events_match_team'
  ) then
    raise exception 'event validation index was not created';
  end if;
end $$;
