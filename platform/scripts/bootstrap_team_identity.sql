-- One-time, idempotent bootstrap of the provider-independent team registry.
-- This creates internal IDs and review candidates only. It does not merge teams,
-- rewrite raw data, or rekey any fact table.

\set ON_ERROR_STOP on

begin;

do $$
begin
  if not exists (select 1 from control.team_identity) then
    alter sequence control.team_identity_id_seq restart with 2000000000000;
  end if;
end $$;

create temporary table team_bootstrap_map (
  legacy_team_id bigint primary key,
  team_name text not null,
  canonical_team_id bigint not null
) on commit drop;

with existing as (
  select
    nullif(decision_evidence ->> 'legacy_dim_team_id', '')::bigint as legacy_team_id,
    canonical_team_id
  from control.team_identity
  where decision_evidence ? 'legacy_dim_team_id'
), inserted as (
  insert into control.team_identity (
    team_name,
    team_type,
    gender,
    category,
    identity_state,
    decision_method,
    decision_evidence
  )
  select
    d.team_name,
    'club',
    'unknown',
    'senior',
    'active',
    'legacy_bootstrap',
    jsonb_build_object(
      'legacy_dim_team_id', d.team_id,
      'bootstrap_scope', 'mart.dim_team',
      'bootstrap_rule', 'one_internal_id_per_legacy_row'
    )
  from mart.dim_team d
  left join existing e on e.legacy_team_id = d.team_id
  where e.legacy_team_id is null
  returning
    (decision_evidence ->> 'legacy_dim_team_id')::bigint as legacy_team_id,
    team_name,
    canonical_team_id
)
insert into team_bootstrap_map (legacy_team_id, team_name, canonical_team_id)
select legacy_team_id, team_name, canonical_team_id
from inserted;

insert into team_bootstrap_map (legacy_team_id, team_name, canonical_team_id)
select
  d.team_id,
  d.team_name,
  ti.canonical_team_id
from mart.dim_team d
join control.team_identity ti
  on ti.decision_evidence ? 'legacy_dim_team_id'
 and (ti.decision_evidence ->> 'legacy_dim_team_id')::bigint = d.team_id
on conflict (legacy_team_id) do nothing;

insert into raw.provider_entity_map (
  provider, entity_type, source_id, source_team_key, canonical_id, mapping_state
)
select
  'legacy_dim_team',
  'team',
  legacy_team_id::text,
  'legacy_dim_team:' || legacy_team_id::text,
  canonical_team_id::text,
  'approved'
from team_bootstrap_map
on conflict (provider, entity_type, source_team_key) do nothing;

with occurrence_rows as (
  select
    home_team_id as legacy_team_id,
    home_team_name as observed_name,
    coalesce(source_provider, provider) as source,
    count(*)::bigint as occurrence_count
  from mart.stg_matches
  where home_team_id is not null
  group by 1, 2, 3
  union all
  select
    away_team_id as legacy_team_id,
    away_team_name as observed_name,
    coalesce(source_provider, provider) as source,
    count(*)::bigint as occurrence_count
  from mart.stg_matches
  where away_team_id is not null
  group by 1, 2, 3
), evidence as (
  select
    m.legacy_team_id,
    m.team_name,
    m.canonical_team_id,
    coalesce(max(
      case lower(o.source)
        when 'sportmonks' then 3
        when 'transfermarkt' then 2
        when 'dataset_brasileirao' then 1
        when 'eloratings' then 1
        else 0
      end
    ), 0) as provider_priority,
    coalesce(sum(o.occurrence_count), 0)::bigint as occurrence_count,
    coalesce(
      jsonb_agg(
        distinct jsonb_build_object(
          'source', o.source,
          'observed_name', o.observed_name,
          'occurrence_count', o.occurrence_count
        )
      ) filter (where o.source is not null),
      '[]'::jsonb
    ) as source_evidence
  from team_bootstrap_map m
  left join occurrence_rows o on o.legacy_team_id = m.legacy_team_id
  group by m.legacy_team_id, m.team_name, m.canonical_team_id
), ranked as (
  select
    e.*,
    row_number() over (
      partition by e.team_name
      order by e.provider_priority desc, e.occurrence_count desc, e.legacy_team_id
    ) as name_rank,
    count(*) over (partition by e.team_name) as name_group_size
  from evidence e
), group_evidence as (
  select
    team_name,
    jsonb_agg(
      jsonb_build_object(
        'legacy_team_id', legacy_team_id,
        'canonical_team_id', canonical_team_id,
        'provider_priority', provider_priority,
        'occurrence_count', occurrence_count,
        'source_evidence', source_evidence,
        'name_rank', name_rank
      )
      order by name_rank
    ) as members
  from ranked
  where name_group_size > 1
  group by team_name
)
insert into control.entity_reconciliation_review_queue (
  entity_type,
  source,
  source_entity_id,
  candidate_canonical_id,
  status,
  reason,
  source_label,
  evidence
)
select
  'team',
  'legacy_dim_team',
  r.legacy_team_id::text,
  s.canonical_team_id,
  'pending',
  'exact_name_duplicate_candidate',
  r.team_name,
  jsonb_build_object(
    'candidate_rule', 'exact team_name; provider priority, observed occurrences, then lowest legacy ID',
    'recommended_survivor_legacy_team_id', s.legacy_team_id,
    'recommended_survivor_canonical_team_id', s.canonical_team_id,
    'members', g.members,
    'approval_required', true
  )
from ranked r
join ranked s
  on s.team_name = r.team_name
 and s.name_rank = 1
join group_evidence g on g.team_name = r.team_name
where r.name_group_size > 1
  and r.name_rank > 1
on conflict (entity_type, source, source_entity_id, coalesce(candidate_canonical_id, -1)) do nothing;

select
  'team_identity_bootstrap' as operation,
  (select count(*) from control.team_identity) as canonical_registry_rows,
  (select count(*) from raw.provider_entity_map where provider = 'legacy_dim_team' and entity_type = 'team') as legacy_crosswalk_rows,
  (select count(*) from control.entity_reconciliation_review_queue where entity_type = 'team' and source = 'legacy_dim_team') as duplicate_candidate_rows,
  (select count(*) from mart.dim_team) as legacy_dim_team_rows,
  (select count(*) from mart.fact_matches) as fact_match_rows;

commit;
