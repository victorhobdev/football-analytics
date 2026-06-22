\set ON_ERROR_STOP on

begin;

insert into mart.coach_identity (
  provider,
  provider_coach_id,
  canonical_name,
  display_name,
  aliases,
  image_url,
  identity_confidence,
  source_refs,
  updated_at
)
select
  stc.provider,
  stc.coach_id,
  max(nullif(btrim(stc.coach_name), '')) as canonical_name,
  max(nullif(btrim(stc.coach_name), '')) as display_name,
  '[]'::jsonb,
  max(nullif(btrim(stc.image_path), '')) filter (
    where coalesce(stc.is_placeholder_image, false) = false
  ) as image_url,
  0.95::numeric,
  jsonb_agg(distinct jsonb_build_object(
    'source', 'stg_team_coaches',
    'coachTenureId', stc.coach_tenure_id
  )),
  now()
from mart.stg_team_coaches stc
where stc.coach_id is not null
  and nullif(btrim(stc.coach_name), '') is not null
group by stc.provider, stc.coach_id
on conflict (provider, provider_coach_id) do update set
  canonical_name = coalesce(excluded.canonical_name, mart.coach_identity.canonical_name),
  display_name = coalesce(excluded.display_name, mart.coach_identity.display_name),
  image_url = coalesce(excluded.image_url, mart.coach_identity.image_url),
  identity_confidence = greatest(
    coalesce(mart.coach_identity.identity_confidence, 0),
    excluded.identity_confidence
  ),
  source_refs = excluded.source_refs,
  updated_at = now();

insert into mart.coach_tenure (
  coach_identity_id,
  team_id,
  role,
  start_date,
  end_date,
  source,
  source_confidence,
  is_date_estimated,
  is_current_as_of_source,
  source_updated_at,
  updated_at
)
select
  ci.coach_identity_id,
  stc.team_id,
  case
    when coalesce(stc.temporary, false) then 'interim_head_coach'
    else 'head_coach'
  end,
  stc.start_date,
  stc.end_date,
  'stg_team_coaches',
  0.85::numeric,
  false,
  coalesce(stc.active, false),
  stc.updated_at,
  now()
from mart.stg_team_coaches stc
join mart.coach_identity ci
  on ci.provider = stc.provider
 and ci.provider_coach_id = stc.coach_id
where stc.team_id is not null
  and stc.start_date is not null
  and (stc.end_date is null or stc.end_date >= stc.start_date)
on conflict (coach_identity_id, team_id, role, start_date, source) do update set
  end_date = excluded.end_date,
  source_confidence = greatest(
    coalesce(mart.coach_tenure.source_confidence, 0),
    excluded.source_confidence
  ),
  is_current_as_of_source = excluded.is_current_as_of_source,
  source_updated_at = excluded.source_updated_at,
  updated_at = now();

with candidates as (
  select
    fm.match_id,
    team_scope.team_id,
    ct.coach_identity_id,
    ct.coach_tenure_id,
    ct.role,
    count(*) over (
      partition by fm.match_id, team_scope.team_id
    ) as candidate_count
  from mart.fact_matches fm
  cross join lateral (
    values (fm.home_team_id), (fm.away_team_id)
  ) as team_scope(team_id)
  join mart.coach_tenure ct
    on ct.team_id = team_scope.team_id
   and ct.role in ('head_coach', 'interim_head_coach')
   and fm.date_day >= ct.start_date
   and fm.date_day <= coalesce(ct.end_date, date '2025-12-31')
  where fm.date_day <= date '2025-12-31'
),
resolved as (
  select *
  from candidates
  where candidate_count = 1
)
insert into mart.fact_coach_match_assignment (
  match_id,
  team_id,
  coach_identity_id,
  coach_tenure_id,
  assignment_method,
  assignment_confidence,
  conflict_reason,
  is_public_eligible,
  source,
  source_record_id,
  updated_at
)
select
  r.match_id,
  r.team_id,
  r.coach_identity_id,
  r.coach_tenure_id,
  case
    when r.role = 'interim_head_coach' then 'interim_head_coach_tenure'
    else 'single_head_coach_tenure'
  end,
  0.85::numeric,
  null,
  true,
  'stg_team_coaches',
  concat(r.match_id, ':', r.team_id),
  now()
from resolved r
on conflict (match_id, team_id) do update set
  coach_identity_id = excluded.coach_identity_id,
  coach_tenure_id = excluded.coach_tenure_id,
  assignment_method = excluded.assignment_method,
  assignment_confidence = excluded.assignment_confidence,
  conflict_reason = excluded.conflict_reason,
  is_public_eligible = excluded.is_public_eligible,
  source = excluded.source,
  source_record_id = excluded.source_record_id,
  updated_at = now();

analyze mart.coach_identity;
analyze mart.coach_tenure;
analyze mart.fact_coach_match_assignment;

commit;
