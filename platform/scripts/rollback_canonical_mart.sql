\set ON_ERROR_STOP on

begin;

set local lock_timeout = '30s';
set local statement_timeout = '15min';

do $$
begin
  if to_regnamespace('mart_rollback_20260716') is null then
    raise exception 'rollback schema is missing';
  end if;
  if to_regnamespace('shadow_dbt_20260716') is null then
    raise exception 'empty target schema is missing';
  end if;
  if exists (
    select 1 from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'shadow_dbt_20260716' and c.relkind in ('r', 'v', 'm')
  ) then
    raise exception 'target schema is not empty before rollback';
  end if;
  if (select count(*) from control.normalization_cutover_object where cutover_id = 'normalization_20260716') <> 103 then
    raise exception 'cutover audit is missing or incomplete';
  end if;
end $$;

do $$
declare
  obj record;
  command text;
begin
  for obj in
    select object_name, promoted_relkind as relkind
    from control.normalization_cutover_object
    where cutover_id = 'normalization_20260716'
    order by object_name
  loop
    command := case obj.relkind
      when 'v' then 'alter view'
      when 'm' then 'alter materialized view'
      else 'alter table'
    end;
    execute format('%s mart.%I set schema shadow_dbt_20260716', command, obj.object_name);
  end loop;

  for obj in
    select object_name, previous_relkind as relkind
    from control.normalization_cutover_object
    where cutover_id = 'normalization_20260716' and previous_exists
    order by object_name
  loop
    command := case obj.relkind
      when 'v' then 'alter view'
      when 'm' then 'alter materialized view'
      else 'alter table'
    end;
    execute format('%s mart_rollback_20260716.%I set schema mart', command, obj.object_name);
  end loop;
end $$;

do $$
begin
  if (select count(*) from mart.dim_team) <> 3060
     or (select count(*) from mart.fact_matches) <> 259872 then
    raise exception 'rollback mart cardinality mismatch';
  end if;
  if exists (
    select 1
    from control.normalization_cutover_object a
    left join pg_class c
      on c.relnamespace = 'mart'::regnamespace
     and c.relname = a.object_name
    where a.cutover_id = 'normalization_20260716'
      and a.previous_exists
      and c.oid is distinct from a.previous_oid
  ) then
    raise exception 'an original object OID was not restored';
  end if;
end $$;

commit;

select count(*) as restored_objects
from control.normalization_cutover_object
where cutover_id = 'normalization_20260716' and previous_exists;
