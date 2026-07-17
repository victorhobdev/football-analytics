\set ON_ERROR_STOP on

begin;

create temporary table provider_team_alias_candidate (
  provider text not null,
  source_team_key text not null,
  source_id text not null,
  canonical_id text not null,
  primary key (provider, source_team_key)
) on commit drop;

with candidate as (
  select
    'dataset_brasileirao'::text as provider,
    'dataset_brasileirao:name:' || lower(regexp_replace(trim(x.home_team_name_raw), '[^[:alnum:]]+', ' ', 'g')) as source_team_key,
    lower(regexp_replace(trim(x.home_team_name_raw), '[^[:alnum:]]+', ' ', 'g')) as source_id,
    p.canonical_id
  from control.brasileirao_fixture_xref x
  join control.external_match_publication_xref px
    on px.source = 'dataset_brasileirao' and px.source_entity_id = x.brasileirao_match_id
  join mart.fact_matches f on f.match_id = px.canonical_external_match_id
  join raw.provider_entity_map p
    on p.provider = 'legacy_dim_team' and p.entity_type = 'team' and p.source_id = f.home_team_id::text
  where x.review_status = 'approved'

  union all

  select
    'dataset_brasileirao',
    'dataset_brasileirao:name:' || lower(regexp_replace(trim(x.away_team_name_raw), '[^[:alnum:]]+', ' ', 'g')),
    lower(regexp_replace(trim(x.away_team_name_raw), '[^[:alnum:]]+', ' ', 'g')),
    p.canonical_id
  from control.brasileirao_fixture_xref x
  join control.external_match_publication_xref px
    on px.source = 'dataset_brasileirao' and px.source_entity_id = x.brasileirao_match_id
  join mart.fact_matches f on f.match_id = px.canonical_external_match_id
  join raw.provider_entity_map p
    on p.provider = 'legacy_dim_team' and p.entity_type = 'team' and p.source_id = f.away_team_id::text
  where x.review_status = 'approved'
), safe as (
  select provider, source_team_key, min(source_id) as source_id, min(canonical_id) as canonical_id
  from candidate
  group by provider, source_team_key
  having count(distinct canonical_id) = 1
)
insert into provider_team_alias_candidate
select * from safe;

with candidate as (
  select
    'transfermarkt'::text as provider,
    coalesce(
      'transfermarkt:club:' || nullif(trim(g.home_club_id), ''),
      'transfermarkt:name:' || lower(regexp_replace(trim(x.home_team_name_raw), '[^[:alnum:]]+', ' ', 'g'))
    ) as source_team_key,
    coalesce(nullif(trim(g.home_club_id), ''), lower(regexp_replace(trim(x.home_team_name_raw), '[^[:alnum:]]+', ' ', 'g'))) as source_id,
    p.canonical_id
  from control.tm_game_fixture_xref x
  join control.external_match_publication_xref px
    on px.source = 'transfermarkt' and px.source_entity_id = x.tm_game_id
  join raw.tm_games g on g.game_id = x.tm_game_id
  join mart.fact_matches f on f.match_id = px.canonical_external_match_id
  join raw.provider_entity_map p
    on p.provider = 'legacy_dim_team' and p.entity_type = 'team' and p.source_id = f.home_team_id::text
  where x.review_status = 'approved'

  union all

  select
    'transfermarkt',
    coalesce(
      'transfermarkt:club:' || nullif(trim(g.away_club_id), ''),
      'transfermarkt:name:' || lower(regexp_replace(trim(x.away_team_name_raw), '[^[:alnum:]]+', ' ', 'g'))
    ),
    coalesce(nullif(trim(g.away_club_id), ''), lower(regexp_replace(trim(x.away_team_name_raw), '[^[:alnum:]]+', ' ', 'g'))),
    p.canonical_id
  from control.tm_game_fixture_xref x
  join control.external_match_publication_xref px
    on px.source = 'transfermarkt' and px.source_entity_id = x.tm_game_id
  join raw.tm_games g on g.game_id = x.tm_game_id
  join mart.fact_matches f on f.match_id = px.canonical_external_match_id
  join raw.provider_entity_map p
    on p.provider = 'legacy_dim_team' and p.entity_type = 'team' and p.source_id = f.away_team_id::text
  where x.review_status = 'approved'
), safe as (
  select provider, source_team_key, min(source_id) as source_id, min(canonical_id) as canonical_id
  from candidate
  group by provider, source_team_key
  having count(distinct canonical_id) = 1
)
insert into provider_team_alias_candidate
select * from safe;

do $$
begin
  if (select count(*) from provider_team_alias_candidate where provider = 'dataset_brasileirao') <> 45 then
    raise exception 'dataset_brasileirao alias candidate count changed';
  end if;
  if (select count(*) from provider_team_alias_candidate where provider = 'transfermarkt') <> 351 then
    raise exception 'transfermarkt alias candidate count changed';
  end if;
  if exists (
    select 1
    from provider_team_alias_candidate c
    join raw.provider_entity_map p
      on p.provider = c.provider
     and p.entity_type = 'team'
     and p.source_team_key = c.source_team_key
    where p.canonical_id <> c.canonical_id
  ) then
    raise exception 'provider alias conflicts with the authoritative crosswalk';
  end if;
end $$;

insert into raw.provider_entity_map (
  provider, entity_type, source_id, source_team_key, canonical_id,
  mapping_state, mapping_confidence, resolution_method, evidence,
  needs_manual_review, is_active, first_seen_at, updated_at
)
select
  provider, 'team', source_id, source_team_key, canonical_id,
  'approved', 'exact', 'approved_match_side_projection',
  jsonb_build_object(
    'approval_basis', 'user_approved_2026-07-16',
    'evidence', 'source key projected from an approved published match side'
  ),
  false, true, now(), now()
from provider_team_alias_candidate
on conflict (provider, entity_type, source_team_key) do update set
  source_id = excluded.source_id,
  canonical_id = excluded.canonical_id,
  mapping_state = excluded.mapping_state,
  mapping_confidence = excluded.mapping_confidence,
  resolution_method = excluded.resolution_method,
  evidence = raw.provider_entity_map.evidence || excluded.evidence,
  needs_manual_review = false,
  is_active = true,
  updated_at = now();

commit;

select provider, count(*) as authoritative_team_keys
from raw.provider_entity_map
where entity_type = 'team'
group by provider
order by provider;
