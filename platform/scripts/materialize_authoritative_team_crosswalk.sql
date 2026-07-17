\set ON_ERROR_STOP on

begin;

do $$
begin
  if (select count(*) from shadow_team_identity_20260715.provider_entity_map) <> 5884 then
    raise exception 'shadow team crosswalk count changed';
  end if;
  if exists (
    select 1
    from shadow_team_identity_20260715.provider_entity_map
    where mapping_state <> 'approved'
  ) then
    raise exception 'shadow team crosswalk contains a non-approved mapping';
  end if;
end $$;

insert into raw.provider_entity_map (
  provider, entity_type, source_id, source_team_key, canonical_id,
  edition_key, mapping_state, mapping_confidence, resolution_method,
  evidence, needs_manual_review, is_active, first_seen_at, updated_at,
  valid_from, valid_to
)
select
  provider,
  entity_type,
  source_id,
  source_team_key,
  canonical_team_id::text,
  edition_key,
  mapping_state,
  mapping_confidence,
  resolution_method,
  evidence || jsonb_build_object('materialized_at', '2026-07-16', 'source', 'approved_shadow_manifest'),
  false,
  true,
  now(),
  now(),
  valid_from,
  valid_to
from shadow_team_identity_20260715.provider_entity_map
on conflict (provider, entity_type, source_team_key) do update set
  source_id = excluded.source_id,
  canonical_id = excluded.canonical_id,
  edition_key = excluded.edition_key,
  mapping_state = excluded.mapping_state,
  mapping_confidence = excluded.mapping_confidence,
  resolution_method = excluded.resolution_method,
  evidence = raw.provider_entity_map.evidence || excluded.evidence,
  needs_manual_review = false,
  is_active = true,
  valid_from = excluded.valid_from,
  valid_to = excluded.valid_to,
  updated_at = now();

do $$
begin
  if exists (
    select 1
    from shadow_team_identity_20260715.provider_entity_map s
    left join raw.provider_entity_map r
      on r.provider = s.provider
     and r.entity_type = s.entity_type
     and r.source_team_key = s.source_team_key
    where r.canonical_id is distinct from s.canonical_team_id::text
       or r.mapping_state <> 'approved'
       or not r.is_active
  ) then
    raise exception 'authoritative team crosswalk does not match the approved shadow manifest';
  end if;
end $$;

commit;

select provider, count(*) as approved_active_team_keys
from raw.provider_entity_map
where entity_type = 'team'
  and mapping_state = 'approved'
  and is_active
group by provider
order by provider;
