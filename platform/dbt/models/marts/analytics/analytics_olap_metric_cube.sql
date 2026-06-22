with team_rows as (
    select
        tmr.match_id,
        tmr.team_id,
        tmr.team_sk,
        tmr.goals_for,
        tmr.goals_against,
        tmr.wins,
        tmr.draws,
        tmr.losses,
        tmr.points_round,
        tmr.round_number,
        tmr.date_day,
        fm.competition_sk,
        fm.competition_key,
        fm.season_label,
        fm.league_id,
        coalesce(fm.round_name, concat('Round ', fm.round_number::text)) as round_name,
        case when fm.home_team_id = tmr.team_id then 'home' else 'away' end as venue
    from {{ ref('int_team_match_rows') }} tmr
    inner join {{ ref('fact_matches') }} fm on fm.match_id = tmr.match_id
),
competition_season as (
    select
        'competition_season'::text as grain_name,
        competition_key,
        season_label,
        null::int as round_id,
        null::text as round_name,
        null::int as team_id,
        null::text as team_name,
        null::int as coach_id,
        null::text as coach_name,
        null::text as venue,
        count(distinct match_id)::int as matches,
        sum(wins)::int as wins,
        sum(draws)::int as draws,
        sum(losses)::int as losses,
        sum(points_round)::int as points,
        sum(goals_for)::int as goals_for,
        sum(goals_against)::int as goals_against,
        sum(goals_for) - sum(goals_against)::int as goal_diff
    from team_rows
    group by competition_key, season_label
),
competition_season_round as (
    select
        'competition_season_round'::text as grain_name,
        competition_key,
        season_label,
        round_number as round_id,
        min(round_name) as round_name,
        null::int as team_id,
        null::text as team_name,
        null::int as coach_id,
        null::text as coach_name,
        null::text as venue,
        count(distinct match_id)::int as matches,
        sum(wins)::int as wins,
        sum(draws)::int as draws,
        sum(losses)::int as losses,
        sum(points_round)::int as points,
        sum(goals_for)::int as goals_for,
        sum(goals_against)::int as goals_against,
        sum(goals_for) - sum(goals_against)::int as goal_diff
    from team_rows
    group by competition_key, season_label, round_number
),
competition_season_team as (
    select
        'competition_season_team'::text as grain_name,
        tr.competition_key,
        tr.season_label,
        null::int as round_id,
        null::text as round_name,
        tr.team_id,
        coalesce(dt.team_name, 'Time indisponivel') as team_name,
        null::int as coach_id,
        null::text as coach_name,
        null::text as venue,
        count(distinct tr.match_id)::int as matches,
        sum(tr.wins)::int as wins,
        sum(tr.draws)::int as draws,
        sum(tr.losses)::int as losses,
        sum(tr.points_round)::int as points,
        sum(tr.goals_for)::int as goals_for,
        sum(tr.goals_against)::int as goals_against,
        sum(tr.goals_for) - sum(tr.goals_against)::int as goal_diff
    from team_rows tr
    left join {{ ref('dim_team') }} dt on dt.team_id = tr.team_id
    group by tr.competition_key, tr.season_label, tr.team_id, dt.team_name
),
competition_season_team_round as (
    select
        'competition_season_team_round'::text as grain_name,
        tr.competition_key,
        tr.season_label,
        tr.round_number as round_id,
        min(tr.round_name) as round_name,
        tr.team_id,
        coalesce(dt.team_name, 'Time indisponivel') as team_name,
        null::int as coach_id,
        null::text as coach_name,
        null::text as venue,
        count(distinct tr.match_id)::int as matches,
        sum(tr.wins)::int as wins,
        sum(tr.draws)::int as draws,
        sum(tr.losses)::int as losses,
        sum(tr.points_round)::int as points,
        sum(tr.goals_for)::int as goals_for,
        sum(tr.goals_against)::int as goals_against,
        sum(tr.goals_for) - sum(tr.goals_against)::int as goal_diff
    from team_rows tr
    left join {{ ref('dim_team') }} dt on dt.team_id = tr.team_id
    group by tr.competition_key, tr.season_label, tr.round_number, tr.team_id, dt.team_name
),
competition_season_team_venue as (
    select
        'competition_season_team_venue'::text as grain_name,
        tr.competition_key,
        tr.season_label,
        null::int as round_id,
        null::text as round_name,
        tr.team_id,
        coalesce(dt.team_name, 'Time indisponivel') as team_name,
        null::int as coach_id,
        null::text as coach_name,
        tr.venue,
        count(distinct tr.match_id)::int as matches,
        sum(tr.wins)::int as wins,
        sum(tr.draws)::int as draws,
        sum(tr.losses)::int as losses,
        sum(tr.points_round)::int as points,
        sum(tr.goals_for)::int as goals_for,
        sum(tr.goals_against)::int as goals_against,
        sum(tr.goals_for) - sum(tr.goals_against)::int as goal_diff
    from team_rows tr
    left join {{ ref('dim_team') }} dt on dt.team_id = tr.team_id
    group by tr.competition_key, tr.season_label, tr.team_id, dt.team_name, tr.venue
),
coach_team_rows as (
    select distinct
        tr.match_id,
        tr.team_id,
        tr.team_sk,
        tr.goals_for,
        tr.goals_against,
        tr.wins,
        tr.draws,
        tr.losses,
        tr.points_round,
        tr.competition_key,
        tr.season_label,
        dc.coach_id,
        dc.coach_name
    from team_rows tr
    inner join {{ ref('stg_team_coaches') }} tc
        on tc.team_id = tr.team_id
        and tr.date_day >= coalesce(tc.start_date, date '1900-01-01')
        and tr.date_day <= coalesce(tc.end_date, date '2999-12-31')
    inner join {{ ref('dim_coach') }} dc
        on dc.provider = tc.provider and dc.coach_id = tc.coach_id
),
competition_season_coach as (
    select
        'competition_season_coach'::text as grain_name,
        competition_key,
        season_label,
        null::int as round_id,
        null::text as round_name,
        null::int as team_id,
        null::text as team_name,
        coach_id,
        coalesce(coach_name, 'Nome indisponivel') as coach_name,
        null::text as venue,
        count(distinct match_id)::int as matches,
        sum(wins)::int as wins,
        sum(draws)::int as draws,
        sum(losses)::int as losses,
        sum(points_round)::int as points,
        sum(goals_for)::int as goals_for,
        sum(goals_against)::int as goals_against,
        sum(goals_for) - sum(goals_against)::int as goal_diff
    from coach_team_rows
    group by competition_key, season_label, coach_id, coach_name
)
select * from competition_season
union all
select * from competition_season_round
union all
select * from competition_season_team
union all
select * from competition_season_team_round
union all
select * from competition_season_team_venue
union all
select * from competition_season_coach
