with settings as (
    select date '2025-12-31' as cutoff
),
coach_source as (
    select
        tc.provider,
        tc.coach_tenure_id,
        tc.team_id,
        coalesce(nullif(trim(tc.team_name), ''), dt.team_name, concat('Unknown Team #', tc.team_id::text)) as team_name,
        tc.coach_id,
        coalesce(tc.position_id, 0) as position_id,
        coalesce(tc.active, false) as active,
        coalesce(tc.temporary, false) as temporary,
        tc.start_date,
        tc.end_date,
        tc.payload,
        coalesce(
            nullif(trim(dc.coach_name), ''),
            nullif(trim(rc.coach_name), ''),
            case
                when lower(trim(tc.coach_name)) like 'not applicable %%' then null
                else nullif(trim(tc.coach_name), '')
            end,
            nullif(
                trim(concat_ws(
                    ' ',
                    case
                        when lower(trim(tc.payload->>'given_name')) in ('not applicable', 'n/a', 'na') then null
                        else nullif(trim(tc.payload->>'given_name'), '')
                    end,
                    nullif(trim(tc.payload->>'family_name'), '')
                )),
                ''
            )
        ) as resolved_name
    from mart.stg_team_coaches tc
    left join mart.dim_coach dc
      on dc.provider = tc.provider
     and dc.coach_id = tc.coach_id
    left join raw.coaches rc
      on rc.provider = tc.provider
     and rc.coach_id = tc.coach_id
    left join mart.dim_team dt
      on dt.team_id = tc.team_id
),
tenures as (
    select
        cs.*,
        case
            when cs.position_id = 221 then 'head_coach'
            when cs.payload->>'coach_tenure_scope' = 'edition_scoped_manager_appointment' then 'head_coach'
            when cs.temporary then 'interim_head_coach'
            when cs.position_id = 560 then 'assistant'
            else 'unknown'
        end as inferred_role,
        case
            when cs.start_date is not null and cs.end_date is not null and cs.start_date > cs.end_date then true
            else false
        end as invalid_date_range,
        case
            when cs.start_date is not null and cs.start_date > (select cutoff from settings) then true
            else false
        end as future_tenure,
        case
            when cs.resolved_name is null then true
            when lower(trim(cs.resolved_name)) in ('not applicable', 'n/a', 'na', 'null', 'unknown') then true
            when lower(trim(cs.resolved_name)) like 'not applicable %%' then true
            else false
        end as invalid_name,
        case
            when cs.end_date is null or cs.end_date > (select cutoff from settings) then (select cutoff from settings)
            else cs.end_date
        end as public_end_date
    from coach_source cs
),
public_tenures as (
    select *
    from tenures
    where not invalid_date_range
      and not future_tenure
      and coalesce(start_date, date '1900-01-01') <= coalesce(public_end_date, (select cutoff from settings))
),
match_teams as (
    select
        fm.match_id,
        fm.competition_key,
        fm.league_id,
        fm.season,
        fm.date_day,
        fm.home_team_id as team_id
    from mart.fact_matches fm
    where fm.date_day <= (select cutoff from settings)
    union all
    select
        fm.match_id,
        fm.competition_key,
        fm.league_id,
        fm.season,
        fm.date_day,
        fm.away_team_id as team_id
    from mart.fact_matches fm
    where fm.date_day <= (select cutoff from settings)
),
eligible_candidates as (
    select
        mt.match_id,
        mt.competition_key,
        mt.league_id,
        mt.season,
        mt.date_day,
        mt.team_id,
        pt.team_name,
        pt.coach_tenure_id,
        pt.coach_id,
        pt.resolved_name,
        pt.inferred_role,
        pt.position_id,
        pt.active,
        pt.temporary,
        pt.start_date,
        pt.public_end_date,
        exists (
            select 1
            from public_tenures peer
            where peer.team_id = pt.team_id
              and peer.coach_tenure_id <> pt.coach_tenure_id
              and peer.position_id = 221
              and coalesce(peer.start_date, date '1900-01-01') <= coalesce(pt.public_end_date, (select cutoff from settings))
              and coalesce(peer.public_end_date, (select cutoff from settings)) >= coalesce(pt.start_date, date '1900-01-01')
        ) as has_head_coach_overlap
    from match_teams mt
    join public_tenures pt
      on pt.team_id = mt.team_id
     and mt.date_day >= coalesce(pt.start_date, date '1900-01-01')
     and mt.date_day <= coalesce(pt.public_end_date, (select cutoff from settings))
     and (
        pt.payload->>'edition_key' is null
        or (
            mt.competition_key = split_part(pt.payload->>'edition_key', '__', 1)
            and mt.season::text = split_part(pt.payload->>'edition_key', '__', 2)
        )
     )
),
ranked_candidates as (
    select
        ec.*,
        row_number() over (
            partition by ec.match_id, ec.team_id
            order by
                case
                    when ec.position_id = 221 then 0
                    when ec.inferred_role = 'head_coach' then 0
                    when ec.temporary then 1
                    when ec.active then 2
                    else 3
                end,
                coalesce(ec.start_date, date '1900-01-01') desc,
                coalesce(ec.public_end_date, (select cutoff from settings)) asc,
                ec.coach_tenure_id desc
        ) as rn_owner,
        count(*) over (partition by ec.match_id, ec.team_id) as total_candidates,
        count(*) filter (where ec.inferred_role in ('head_coach', 'interim_head_coach'))
            over (partition by ec.match_id, ec.team_id) as principal_candidates,
        count(*) filter (where ec.inferred_role = 'assistant')
            over (partition by ec.match_id, ec.team_id) as assistant_candidates
    from eligible_candidates ec
),
match_assignment_audit as (
    select
        mt.match_id,
        mt.competition_key,
        mt.league_id,
        mt.season,
        mt.team_id,
        coalesce(dt.team_name, max(rc.team_name)) as team_name,
        max(case when rc.rn_owner = 1 then 1 else 0 end) as has_assignment,
        max(case when coalesce(rc.total_candidates, 0) > 1 then 1 else 0 end) as has_conflict,
        max(case when coalesce(rc.assistant_candidates, 0) > 0 and coalesce(rc.principal_candidates, 0) > 0 then 1 else 0 end)
            as assistant_as_head_risk
    from match_teams mt
    left join ranked_candidates rc
      on rc.match_id = mt.match_id
     and rc.team_id = mt.team_id
    left join mart.dim_team dt
      on dt.team_id = mt.team_id
    group by mt.match_id, mt.competition_key, mt.league_id, mt.season, mt.team_id, dt.team_name
),
tenure_quality as (
    select
        coalesce(nullif(trim(pt.team_name), ''), dt.team_name, concat('Unknown Team #', pt.team_id::text)) as team_name,
        pt.team_id,
        coalesce(split_part(pt.payload->>'edition_key', '__', 1), fm.competition_key) as competition_key,
        coalesce(nullif(split_part(pt.payload->>'edition_key', '__', 2), '')::int, fm.season) as season,
        coalesce(fm.league_id, -1) as league_id,
        count(*) filter (where pt.invalid_name) as invalid_name_tenures,
        count(*) filter (where pt.future_tenure) as future_tenures_hidden,
        count(*) filter (
            where pt.inferred_role = 'assistant'
              and exists (
                  select 1
                  from public_tenures peer
                  where peer.team_id = pt.team_id
                    and peer.coach_tenure_id <> pt.coach_tenure_id
                    and peer.inferred_role in ('head_coach', 'interim_head_coach')
                    and coalesce(peer.start_date, date '1900-01-01') <= coalesce(pt.public_end_date, (select cutoff from settings))
                    and coalesce(peer.public_end_date, (select cutoff from settings)) >= coalesce(pt.start_date, date '1900-01-01')
              )
        ) as assistant_tenure_overlap_count
    from tenures pt
    left join mart.dim_team dt
      on dt.team_id = pt.team_id
    left join lateral (
        select fm.competition_key, fm.season, fm.league_id
        from mart.fact_matches fm
        where (fm.home_team_id = pt.team_id or fm.away_team_id = pt.team_id)
          and fm.date_day >= coalesce(pt.start_date, date '1900-01-01')
          and fm.date_day <= coalesce(
              case
                  when pt.end_date is null or pt.end_date > (select cutoff from settings) then (select cutoff from settings)
                  else pt.end_date
              end,
              (select cutoff from settings)
          )
          and fm.date_day <= (select cutoff from settings)
        order by fm.date_day desc
        limit 1
    ) fm on true
    group by
        coalesce(nullif(trim(pt.team_name), ''), dt.team_name, concat('Unknown Team #', pt.team_id::text)),
        pt.team_id,
        coalesce(split_part(pt.payload->>'edition_key', '__', 1), fm.competition_key),
        coalesce(nullif(split_part(pt.payload->>'edition_key', '__', 2), '')::int, fm.season),
        coalesce(fm.league_id, -1)
)
select
    maa.competition_key,
    maa.league_id,
    maa.season,
    maa.team_id,
    maa.team_name,
    count(*) as matches_total,
    sum(maa.has_assignment) as matches_with_assignment,
    count(*) - sum(maa.has_assignment) as matches_without_assignment,
    sum(maa.has_conflict) as matches_with_conflict,
    coalesce(max(tq.invalid_name_tenures), 0) as invalid_name_tenures,
    coalesce(max(tq.future_tenures_hidden), 0) as future_tenures_hidden,
    greatest(sum(maa.assistant_as_head_risk), coalesce(max(tq.assistant_tenure_overlap_count), 0)) as assistant_as_head_risk,
    (
        (count(*) - sum(maa.has_assignment)) > 0
        or sum(maa.has_conflict) > 0
        or coalesce(max(tq.invalid_name_tenures), 0) > 0
        or coalesce(max(tq.future_tenures_hidden), 0) > 0
        or greatest(sum(maa.assistant_as_head_risk), coalesce(max(tq.assistant_tenure_overlap_count), 0)) > 0
    ) as public_surface_impacted
from match_assignment_audit maa
left join tenure_quality tq
  on tq.team_id = maa.team_id
 and tq.competition_key is not distinct from maa.competition_key
 and tq.season is not distinct from maa.season
 and tq.league_id is not distinct from maa.league_id
where maa.competition_key is not null
group by maa.competition_key, maa.league_id, maa.season, maa.team_id, maa.team_name
order by matches_without_assignment desc, matches_with_conflict desc, matches_total desc, team_name asc;
