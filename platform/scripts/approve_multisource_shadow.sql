-- Records the explicit 2026-07-16 approval of the existing shadow result.
-- No raw or active mart table is changed.

\set ON_ERROR_STOP on

begin;

alter table shadow_team_identity_20260715.team_manifest
  add column if not exists approval_state text,
  add column if not exists approval_basis text;

update shadow_team_identity_20260715.team_manifest
set approval_state = 'approved',
    approval_basis = 'user_approved_2026-07-16';

alter table shadow_match_dedup_20260715.match_group
  add column if not exists approval_state text,
  add column if not exists approval_basis text;

update shadow_match_dedup_20260715.match_group
set approval_state = 'approved',
    approval_basis = 'user_approved_2026-07-16';

update shadow_match_dedup_20260715.near_day_candidate
set decision_status = 'separate_approved',
    evidence = evidence || jsonb_build_object(
      'approval_basis', 'user_approved_2026-07-16',
      'decision', 'keep_as_separate_matches'
    );

create table if not exists shadow_match_dedup_20260715.publication_decision (
  source text not null,
  source_entity_id text not null,
  source_match_id bigint not null,
  canonical_match_id bigint not null,
  decision_status text not null,
  approval_basis text not null,
  evidence jsonb not null default '{}'::jsonb,
  primary key (source, source_entity_id)
);

truncate shadow_match_dedup_20260715.publication_decision;

with approved_publications as (
  select px.source, px.source_entity_id, px.canonical_external_match_id
  from control.external_match_publication_xref px
  join control.brasileirao_fixture_xref bx
    on px.source = 'dataset_brasileirao'
   and px.source_entity_id = bx.brasileirao_match_id::text
  where bx.review_status = 'pending'
    and px.publication_status = 'publishable'

  union all

  select px.source, px.source_entity_id, px.canonical_external_match_id
  from control.external_match_publication_xref px
  join control.tm_game_fixture_xref tx
    on px.source = 'transfermarkt'
   and px.source_entity_id = tx.tm_game_id::text
  where tx.review_status = 'pending'
    and px.publication_status = 'publishable'

  union all

  select px.source, px.source_entity_id, px.canonical_external_match_id
  from control.external_match_publication_xref px
  join control.elo_match_xref ex
    on px.source = 'eloratings'
   and px.source_entity_id = ex.elo_match_hash::text
  where ex.review_status = 'pending'
    and px.publication_status = 'publishable'
)
insert into shadow_match_dedup_20260715.publication_decision (
  source, source_entity_id, source_match_id, canonical_match_id,
  decision_status, approval_basis, evidence
)
select
  p.source,
  p.source_entity_id,
  p.canonical_external_match_id,
  m.canonical_match_id,
  case when g.source_count > 1
       then 'approved_duplicate_representation'
       else 'approved_new_coverage'
  end,
  'user_approved_2026-07-16',
  jsonb_build_object(
    'match_group_key', m.match_group_key,
    'source_count', g.source_count,
    'canonical_rule', 'exact_group; near_day_candidates_remain_separate'
  )
from approved_publications p
join shadow_match_dedup_20260715.match_group_member m
  on m.source_match_id = p.canonical_external_match_id
join shadow_match_dedup_20260715.match_group g
  on g.match_group_key = m.match_group_key;

do $$
begin
  if (select count(*) from shadow_team_identity_20260715.team_manifest) <> 3061 then
    raise exception 'team manifest row count changed';
  end if;
  if exists (
    select 1 from shadow_team_identity_20260715.team_manifest
    where approval_state <> 'approved'
  ) then
    raise exception 'team manifest contains a non-approved row';
  end if;
  if (select count(*) from shadow_match_dedup_20260715.match_group) <> 248853 then
    raise exception 'match manifest row count changed';
  end if;
  if exists (
    select 1 from shadow_match_dedup_20260715.match_group
    where approval_state <> 'approved'
  ) then
    raise exception 'match manifest contains a non-approved row';
  end if;
  if (select count(*) from shadow_match_dedup_20260715.near_day_candidate) <> 53 then
    raise exception 'near-day candidate count changed';
  end if;
  if exists (
    select 1 from shadow_match_dedup_20260715.near_day_candidate
    where decision_status <> 'separate_approved'
  ) then
    raise exception 'near-day candidate was not kept separate';
  end if;
  if (select count(*) from shadow_match_dedup_20260715.publication_decision) <> 240993 then
    raise exception 'publication decision count changed';
  end if;
end $$;

commit;

select
  (select count(*) from shadow_team_identity_20260715.team_manifest where approval_state = 'approved') as approved_team_rows,
  (select count(*) from shadow_match_dedup_20260715.match_group where approval_state = 'approved') as approved_match_groups,
  (select count(*) from shadow_match_dedup_20260715.near_day_candidate where decision_status = 'separate_approved') as approved_separate_near_day,
  (select count(*) from shadow_match_dedup_20260715.publication_decision) as approved_publications;
