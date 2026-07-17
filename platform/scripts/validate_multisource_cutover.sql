-- Read-only gates for the approved 2026-07-16 normalization snapshot.
\set ON_ERROR_STOP on

do $$
begin
  if (select count(*) from shadow_team_identity_20260715.canonical_team) <> 1930 then
    raise exception 'expected 1930 canonical teams';
  end if;
  if (select count(*) from shadow_team_identity_20260715.provider_entity_map) <> 5884 then
    raise exception 'expected 5884 approved source keys';
  end if;
  if exists (
    select 1 from shadow_team_identity_20260715.provider_entity_map
    where mapping_state <> 'approved'
  ) then
    raise exception 'non-approved team identity is present in the shadow crosswalk';
  end if;
  if (select count(*) from shadow_match_dedup_20260715.match_group) <> 248853 then
    raise exception 'expected 248853 canonical matches';
  end if;
  if (select count(*) from shadow_match_dedup_20260715.publication_decision) <> 240993 then
    raise exception 'publication manifest is incomplete';
  end if;
  if exists (
    select 1 from shadow_match_dedup_20260715.near_day_candidate
    where decision_status <> 'separate_approved'
  ) then
    raise exception 'a near-day candidate lacks an explicit separate decision';
  end if;
  if (select count(*) from shadow_dbt_20260716.dim_team) <> 1930
     or (select count(*) from shadow_dbt_20260716.fact_matches) <> 248853 then
    raise exception 'serving shadow cardinality changed';
  end if;
  if exists (
    select 1 from shadow_dbt_20260716.fact_matches
    where home_team_id = away_team_id
  ) then
    raise exception 'canonical match contains equal home and away teams';
  end if;
  if exists (
    select 1
    from shadow_dbt_20260716.fact_matches f
    left join shadow_dbt_20260716.dim_team h on h.team_id = f.home_team_id
    left join shadow_dbt_20260716.dim_team a on a.team_id = f.away_team_id
    where h.team_id is null or a.team_id is null
  ) then
    raise exception 'canonical match contains an orphan team';
  end if;
  if exists (
    select 1
    from shadow_dbt_20260716.fact_match_events e
    join shadow_dbt_20260716.fact_matches f using (match_id)
    where e.team_id is not null and e.team_id not in (f.home_team_id, f.away_team_id)
  ) then
    raise exception 'event team is not a side of its canonical match';
  end if;
end $$;

select 'canonical_teams' gate, count(*) value from shadow_team_identity_20260715.canonical_team
union all select 'source_keys', count(*) from shadow_team_identity_20260715.provider_entity_map
union all select 'canonical_matches', count(*) from shadow_match_dedup_20260715.match_group
union all select 'approved_publications', count(*) from shadow_match_dedup_20260715.publication_decision
union all select 'near_day_kept_separate', count(*) from shadow_match_dedup_20260715.near_day_candidate where decision_status = 'separate_approved'
union all select 'serving_events', count(*) from shadow_dbt_20260716.fact_match_events;
