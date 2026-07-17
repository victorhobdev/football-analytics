\set ON_ERROR_STOP on

begin;

set local lock_timeout = '30s';
set local statement_timeout = '15min';

do $$
begin
  if to_regnamespace('mart_rollback_20260716') is not null then
    raise exception 'rollback schema mart_rollback_20260716 already exists';
  end if;
  if (select count(*) from shadow_dbt_20260716.dim_team) <> 1930 then
    raise exception 'target dim_team count changed';
  end if;
  if (select count(*) from shadow_dbt_20260716.fact_matches) <> 248853 then
    raise exception 'target fact_matches count changed';
  end if;
  if exists (
    select 1
    from pg_rewrite rw
    join pg_class dependent on dependent.oid = rw.ev_class
    join pg_namespace dn on dn.oid = dependent.relnamespace
    join pg_depend d on d.classid = 'pg_rewrite'::regclass and d.objid = rw.oid
    join pg_class referenced on referenced.oid = d.refobjid
    join pg_namespace rn on rn.oid = referenced.relnamespace
    where dn.nspname = 'shadow_dbt_20260716'
      and rn.nspname = 'mart'
      and exists (
        select 1
        from pg_class target_same_name
        join pg_namespace tn on tn.oid = target_same_name.relnamespace
        where tn.nspname = 'shadow_dbt_20260716'
          and target_same_name.relname = referenced.relname
      )
  ) then
    raise exception 'target view still depends on an active mart object that will be replaced';
  end if;
end $$;

create schema mart_rollback_20260716;
create schema if not exists control;

create table if not exists control.normalization_cutover_object (
  cutover_id text not null,
  object_name text not null,
  promoted_relkind "char" not null,
  previous_exists boolean not null,
  previous_relkind "char",
  previous_oid oid,
  promoted_oid oid not null,
  rollback_schema text not null,
  promoted_at timestamptz not null default now(),
  primary key (cutover_id, object_name)
);

delete from control.normalization_cutover_object
where cutover_id = 'normalization_20260716';

insert into control.normalization_cutover_object (
  cutover_id, object_name, promoted_relkind, previous_exists, previous_relkind, previous_oid,
  promoted_oid, rollback_schema
)
select
  'normalization_20260716',
  target.relname,
  target.relkind,
  active.oid is not null,
  active.relkind,
  active.oid,
  target.oid,
  'mart_rollback_20260716'
from pg_class target
join pg_namespace target_ns on target_ns.oid = target.relnamespace
left join pg_class active
  on active.relnamespace = 'mart'::regnamespace
 and active.relname = target.relname
 and active.relkind in ('r', 'v', 'm')
where target_ns.nspname = 'shadow_dbt_20260716'
  and target.relkind in ('r', 'v', 'm');

do $$
declare
  obj record;
  command text;
begin
  if (select count(*) from control.normalization_cutover_object where cutover_id = 'normalization_20260716') <> 103 then
    raise exception 'unexpected number of target mart objects';
  end if;

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
    execute format('%s mart.%I set schema mart_rollback_20260716', command, obj.object_name);
  end loop;

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
    execute format('%s shadow_dbt_20260716.%I set schema mart', command, obj.object_name);
  end loop;
end $$;

do $$
begin
  if (select count(*) from mart.dim_team) <> 1930
     or (select count(*) from mart.fact_matches) <> 248853 then
    raise exception 'promoted mart cardinality mismatch';
  end if;
  if exists (
    select 1
    from control.normalization_cutover_object a
    left join pg_class c
      on c.relnamespace = 'mart'::regnamespace
     and c.relname = a.object_name
    where a.cutover_id = 'normalization_20260716'
      and c.oid is distinct from a.promoted_oid
  ) then
    raise exception 'a promoted object OID changed during cutover';
  end if;
end $$;

commit;

select count(*) as promoted_objects,
       count(*) filter (where previous_exists) as rollback_objects,
       count(*) filter (where not previous_exists) as new_objects
from control.normalization_cutover_object
where cutover_id = 'normalization_20260716';
