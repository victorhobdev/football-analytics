\set ON_ERROR_STOP on

begin;

do $$
begin
  if (select count(*) from shadow_match_dedup_20260715.publication_decision) <> 240993 then
    raise exception 'publication manifest count changed';
  end if;
  if exists (
    select 1
    from shadow_match_dedup_20260715.publication_decision
    where approval_basis <> 'user_approved_2026-07-16'
  ) then
    raise exception 'publication manifest contains an unapproved decision';
  end if;
end $$;

update control.brasileirao_fixture_xref x
set review_status = 'approved',
    source_evidence = x.source_evidence || jsonb_build_object(
      'normalization_approval', d.evidence,
      'normalization_decision', d.decision_status,
      'normalization_approval_basis', d.approval_basis
    ),
    updated_at = now()
from shadow_match_dedup_20260715.publication_decision d
where d.source = 'dataset_brasileirao'
  and d.source_entity_id = x.brasileirao_match_id
  and x.review_status = 'pending';

update control.tm_game_fixture_xref x
set review_status = 'approved',
    source_evidence = x.source_evidence || jsonb_build_object(
      'normalization_approval', d.evidence,
      'normalization_decision', d.decision_status,
      'normalization_approval_basis', d.approval_basis
    ),
    updated_at = now()
from shadow_match_dedup_20260715.publication_decision d
where d.source = 'transfermarkt'
  and d.source_entity_id = x.tm_game_id
  and x.review_status = 'pending';

update control.elo_match_xref x
set review_status = 'approved',
    source_evidence = x.source_evidence || jsonb_build_object(
      'normalization_approval', d.evidence,
      'normalization_decision', d.decision_status,
      'normalization_approval_basis', d.approval_basis
    ),
    updated_at = now()
from shadow_match_dedup_20260715.publication_decision d
where d.source = 'eloratings'
  and d.source_entity_id = x.elo_match_hash
  and x.review_status = 'pending';

do $$
begin
  if exists (
    select 1
    from control.external_match_publication_xref px
    join (
      select brasileirao_match_id::text as source_entity_id, 'dataset_brasileirao'::text as source, review_status
      from control.brasileirao_fixture_xref
      union all
      select tm_game_id::text, 'transfermarkt', review_status from control.tm_game_fixture_xref
      union all
      select elo_match_hash::text, 'eloratings', review_status from control.elo_match_xref
    ) x using (source, source_entity_id)
    where px.publication_status = 'publishable'
      and x.review_status in ('pending', 'manual_review', 'blocked', 'rejected')
  ) then
    raise exception 'a non-approved external match remains publishable';
  end if;
end $$;

commit;

select source, count(*) as approved_rows
from (
  select 'dataset_brasileirao'::text as source, review_status from control.brasileirao_fixture_xref
  union all
  select 'transfermarkt', review_status from control.tm_game_fixture_xref
  union all
  select 'eloratings', review_status from control.elo_match_xref
) decisions
where review_status = 'approved'
group by source
order by source;
