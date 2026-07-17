\set ON_ERROR_STOP on

begin;

do $$
begin
  if (select count(*) from shadow_team_identity_20260715.canonical_team) <> 1930 then
    raise exception 'canonical team count changed';
  end if;
  if exists (
    select 1
    from shadow_team_identity_20260715.canonical_team
    where identity_state <> 'active' or merged_into_team_id is not null
  ) then
    raise exception 'canonical registry contains a non-active or merged row';
  end if;
end $$;

delete from control.team_identity;

insert into control.team_identity (
  canonical_team_id, team_name, country_or_territory, team_type, gender,
  category, identity_state, merged_into_team_id, decision_method,
  decision_confidence, decision_evidence, created_at, updated_at
)
select
  canonical_team_id, team_name, country_or_territory, team_type, gender,
  category, identity_state, merged_into_team_id, decision_method,
  decision_confidence,
  decision_evidence || jsonb_build_object('promoted_at', '2026-07-16', 'source', 'approved_shadow_manifest'),
  now(), now()
from shadow_team_identity_20260715.canonical_team;

update raw.provider_entity_map p
set is_active = false,
    mapping_state = 'retired',
    needs_manual_review = false,
    review_reason = coalesce(p.review_reason, 'canonical_team_id_retired_by_normalization_20260716'),
    evidence = p.evidence || jsonb_build_object(
      'retired_at', '2026-07-16',
      'reason', 'canonical team ID is not present in the approved registry'
    ),
    updated_at = now()
where p.entity_type = 'team'
  and p.is_active
  and p.canonical_id ~ '^[0-9]+$'
  and not exists (
    select 1
    from control.team_identity t
    where t.canonical_team_id = p.canonical_id::bigint
      and t.identity_state = 'active'
  );

select setval(
  'control.team_identity_id_seq',
  greatest((select max(canonical_team_id) + 1 from control.team_identity), 3000000001931),
  false
);

do $$
begin
  if (select count(*) from control.team_identity) <> 1930 then
    raise exception 'promoted canonical registry count mismatch';
  end if;
  if exists (
    select canonical_team_id, team_name, country_or_territory, team_type, gender, category,
           identity_state, merged_into_team_id, decision_method, decision_confidence
    from control.team_identity
    except
    select canonical_team_id, team_name, country_or_territory, team_type, gender, category,
           identity_state, merged_into_team_id, decision_method, decision_confidence
    from shadow_team_identity_20260715.canonical_team
  ) then
    raise exception 'promoted canonical registry differs from shadow source';
  end if;
  if exists (
    select 1
    from raw.provider_entity_map p
    left join control.team_identity t
      on p.canonical_id ~ '^[0-9]+$'
     and t.canonical_team_id = p.canonical_id::bigint
     and t.identity_state = 'active'
    where p.entity_type = 'team'
      and p.is_active
      and p.mapping_state = 'approved'
      and t.canonical_team_id is null
  ) then
    raise exception 'an approved active source team points outside the canonical registry';
  end if;
end $$;

commit;

select count(*) as canonical_team_count,
       min(canonical_team_id) as min_canonical_team_id,
       max(canonical_team_id) as max_canonical_team_id
from control.team_identity;
