with team_season_stats as (
    select
        fm.competition_key,
        fm.season_label,
        tr.team_id,
        coalesce(dt.team_name, 'Time indisponivel') as team_name,
        count(distinct tr.match_id)::int as matches,
        sum(tr.wins)::int as wins,
        sum(tr.draws)::int as draws,
        sum(tr.losses)::int as losses,
        sum(tr.points_round)::int as points,
        sum(tr.goals_for)::int as goals_for,
        sum(tr.goals_against)::int as goals_against,
        sum(tr.goals_for) - sum(tr.goals_against)::int as goal_diff,
        case
            when count(distinct tr.match_id) > 0
            then round(sum(tr.points_round)::numeric / count(distinct tr.match_id), 4)
        end as avg_goals_per_match
    from {{ ref('int_team_match_rows') }} tr
    inner join {{ ref('fact_matches') }} fm on fm.match_id = tr.match_id
    left join {{ ref('dim_team') }} dt on dt.team_id = tr.team_id
    group by fm.competition_key, fm.season_label, tr.team_id, dt.team_name
),
comp_season_overview as (
    select
        fm.competition_key,
        fm.season_label,
        count(distinct tr.match_id)::int as matches,
        sum(tr.wins)::int as wins,
        sum(tr.draws)::int as draws,
        sum(tr.losses)::int as losses,
        sum(tr.points_round)::int as points,
        sum(tr.goals_for)::int as goals_for,
        sum(tr.goals_against)::int as goals_against,
        sum(tr.goals_for) - sum(tr.goals_against)::int as goal_diff,
        case
            when count(distinct tr.match_id) > 0
            then round(sum(tr.points_round)::numeric / count(distinct tr.match_id), 4)
        end as avg_goals_per_match
    from {{ ref('int_team_match_rows') }} tr
    inner join {{ ref('fact_matches') }} fm on fm.match_id = tr.match_id
    group by fm.competition_key, fm.season_label
),
team_pairs as (
    select
        fm.competition_key,
        fm.season_label,
        least(fm.home_team_id, fm.away_team_id) as entity_a_id,
        greatest(fm.home_team_id, fm.away_team_id) as entity_b_id
    from {{ ref('fact_matches') }} fm
    where fm.home_team_id != fm.away_team_id
    group by fm.competition_key, fm.season_label, least(fm.home_team_id, fm.away_team_id), greatest(fm.home_team_id, fm.away_team_id)
),
team_vs_team as (
    select
        'team_vs_team'::text as comparison_type,
        tp.entity_a_id::text as entity_a_id,
        tp.entity_b_id::text as entity_b_id,
        a.team_name as entity_a_label,
        b.team_name as entity_b_label,
        concat(tp.competition_key, ' / ', tp.season_label) as scope_description,
        a.matches as matches_a,
        b.matches as matches_b,
        a.wins as wins_a,
        b.wins as wins_b,
        a.draws as draws_a,
        b.draws as draws_b,
        a.losses as losses_a,
        b.losses as losses_b,
        a.points as points_a,
        b.points as points_b,
        a.goals_for as goals_for_a,
        b.goals_for as goals_for_b,
        a.goals_against as goals_against_a,
        b.goals_against as goals_against_b,
        a.goal_diff as goal_diff_a,
        b.goal_diff as goal_diff_b,
        a.avg_goals_per_match as avg_goals_a,
        b.avg_goals_per_match as avg_goals_b
    from team_pairs tp
    left join team_season_stats a on a.competition_key = tp.competition_key and a.season_label = tp.season_label and a.team_id = tp.entity_a_id
    left join team_season_stats b on b.competition_key = tp.competition_key and b.season_label = tp.season_label and b.team_id = tp.entity_b_id
),
season_pairs as (
    select
        competition_key,
        season_label as entity_a_id,
        lag(season_label) over (partition by competition_key order by season_label) as entity_b_id
    from (select distinct competition_key, season_label from comp_season_overview) seasons
),
season_vs_season as (
    select
        'season_vs_season'::text as comparison_type,
        sp.entity_a_id::text,
        sp.entity_b_id::text,
        sp.entity_a_id::text as entity_a_label,
        sp.entity_b_id::text as entity_b_label,
        sp.competition_key as scope_description,
        a.matches as matches_a,
        b.matches as matches_b,
        a.wins as wins_a,
        b.wins as wins_b,
        a.draws as draws_a,
        b.draws as draws_b,
        a.losses as losses_a,
        b.losses as losses_b,
        a.points as points_a,
        b.points as points_b,
        a.goals_for as goals_for_a,
        b.goals_for as goals_for_b,
        a.goals_against as goals_against_a,
        b.goals_against as goals_against_b,
        a.goal_diff as goal_diff_a,
        b.goal_diff as goal_diff_b,
        a.avg_goals_per_match as avg_goals_a,
        b.avg_goals_per_match as avg_goals_b
    from season_pairs sp
    left join comp_season_overview a on a.competition_key = sp.competition_key and a.season_label = sp.entity_a_id
    left join comp_season_overview b on b.competition_key = sp.competition_key and b.season_label = sp.entity_b_id
    where sp.entity_b_id is not null
),
team_venue as (
    select
        fm.competition_key,
        fm.season_label,
        fm.home_team_id as team_id,
        coalesce(dt.team_name, 'Time indisponivel') as team_name,
        'home' as venue,
        count(distinct fm.match_id)::int as matches,
        sum(case when coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0) then 1 else 0 end)::int as wins,
        sum(case when coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 1 else 0 end)::int as draws,
        sum(case when coalesce(fm.home_goals, 0) < coalesce(fm.away_goals, 0) then 1 else 0 end)::int as losses,
        sum(
            case
                when coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0) then 3
                when coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 1
                else 0
            end
        )::int as points,
        sum(coalesce(fm.home_goals, 0))::int as goals_for,
        sum(coalesce(fm.away_goals, 0))::int as goals_against,
        sum(coalesce(fm.home_goals, 0)) - sum(coalesce(fm.away_goals, 0))::int as goal_diff,
        case
            when count(distinct fm.match_id) > 0
            then round(sum(coalesce(fm.home_goals, 0))::numeric / count(distinct fm.match_id), 4)
        end as avg_goals_per_match
    from {{ ref('fact_matches') }} fm
    left join {{ ref('dim_team') }} dt on dt.team_id = fm.home_team_id
    group by fm.competition_key, fm.season_label, fm.home_team_id, dt.team_name
    union all
    select
        fm.competition_key,
        fm.season_label,
        fm.away_team_id as team_id,
        coalesce(dt.team_name, 'Time indisponivel') as team_name,
        'away' as venue,
        count(distinct fm.match_id)::int as matches,
        sum(case when coalesce(fm.away_goals, 0) > coalesce(fm.home_goals, 0) then 1 else 0 end)::int as wins,
        sum(case when coalesce(fm.away_goals, 0) = coalesce(fm.home_goals, 0) then 1 else 0 end)::int as draws,
        sum(case when coalesce(fm.away_goals, 0) < coalesce(fm.home_goals, 0) then 1 else 0 end)::int as losses,
        sum(
            case
                when coalesce(fm.away_goals, 0) > coalesce(fm.home_goals, 0) then 3
                when coalesce(fm.away_goals, 0) = coalesce(fm.home_goals, 0) then 1
                else 0
            end
        )::int as points,
        sum(coalesce(fm.away_goals, 0))::int as goals_for,
        sum(coalesce(fm.home_goals, 0))::int as goals_against,
        sum(coalesce(fm.away_goals, 0)) - sum(coalesce(fm.home_goals, 0))::int as goal_diff,
        case
            when count(distinct fm.match_id) > 0
            then round(sum(coalesce(fm.away_goals, 0))::numeric / count(distinct fm.match_id), 4)
        end as avg_goals_per_match
    from {{ ref('fact_matches') }} fm
    left join {{ ref('dim_team') }} dt on dt.team_id = fm.away_team_id
    group by fm.competition_key, fm.season_label, fm.away_team_id, dt.team_name
),
home_vs_away as (
    select
        'home_vs_away'::text as comparison_type,
        h.team_id::text as entity_a_id,
        h.team_id::text as entity_b_id,
        h.team_name as entity_a_label,
        concat(h.team_name, ' (Fora)') as entity_b_label,
        concat(h.competition_key, ' / ', h.season_label) as scope_description,
        h.matches as matches_a,
        a.matches as matches_b,
        h.wins as wins_a,
        a.wins as wins_b,
        h.draws as draws_a,
        a.draws as draws_b,
        h.losses as losses_a,
        a.losses as losses_b,
        h.points as points_a,
        a.points as points_b,
        h.goals_for as goals_for_a,
        a.goals_for as goals_for_b,
        h.goals_against as goals_against_a,
        a.goals_against as goals_against_b,
        h.goal_diff as goal_diff_a,
        a.goal_diff as goal_diff_b,
        h.avg_goals_per_match as avg_goals_a,
        a.avg_goals_per_match as avg_goals_b
    from team_venue h
    inner join team_venue a on a.competition_key = h.competition_key and a.season_label = h.season_label and a.team_id = h.team_id and a.venue = 'away'
    where h.venue = 'home'
),
team_with_max_round as (
    select
        fm.competition_key,
        fm.season_label,
        tr.team_id,
        coalesce(dt.team_name, 'Time indisponivel') as team_name,
        tr.round_number,
        max(tr.round_number) over (partition by fm.competition_key, fm.season_label, tr.team_id) as max_round,
        tr.match_id,
        tr.wins,
        tr.draws,
        tr.losses,
        tr.points_round,
        tr.goals_for,
        tr.goals_against
    from {{ ref('int_team_match_rows') }} tr
    inner join {{ ref('fact_matches') }} fm on fm.match_id = tr.match_id
    left join {{ ref('dim_team') }} dt on dt.team_id = tr.team_id
    where tr.round_number > 0
),
team_half_stats as (
    select
        competition_key,
        season_label,
        team_id,
        team_name,
        case when round_number <= max_round * 0.5 then 'first_half' else 'second_half' end as period_half,
        count(distinct match_id)::int as matches,
        sum(wins)::int as wins,
        sum(draws)::int as draws,
        sum(losses)::int as losses,
        sum(points_round)::int as points,
        sum(goals_for)::int as goals_for,
        sum(goals_against)::int as goals_against,
        sum(goals_for) - sum(goals_against)::int as goal_diff,
        case
            when count(distinct match_id) > 0
            then round(sum(points_round)::numeric / count(distinct match_id), 4)
        end as avg_goals_per_match
    from team_with_max_round
    group by competition_key, season_label, team_id, team_name,
        case when round_number <= max_round * 0.5 then 'first_half' else 'second_half' end
),
period_vs_period as (
    select
        'period_vs_period'::text as comparison_type,
        f.team_id::text as entity_a_id,
        f.team_id::text as entity_b_id,
        concat(f.team_name, ' (1o Turno)') as entity_a_label,
        concat(f.team_name, ' (2o Turno)') as entity_b_label,
        concat(f.competition_key, ' / ', f.season_label) as scope_description,
        f.matches as matches_a,
        s.matches as matches_b,
        f.wins as wins_a,
        s.wins as wins_b,
        f.draws as draws_a,
        s.draws as draws_b,
        f.losses as losses_a,
        s.losses as losses_b,
        f.points as points_a,
        s.points as points_b,
        f.goals_for as goals_for_a,
        s.goals_for as goals_for_b,
        f.goals_against as goals_against_a,
        s.goals_against as goals_against_b,
        f.goal_diff as goal_diff_a,
        s.goal_diff as goal_diff_b,
        f.avg_goals_per_match as avg_goals_a,
        s.avg_goals_per_match as avg_goals_b
    from team_half_stats f
    inner join team_half_stats s
        on s.competition_key = f.competition_key and s.season_label = f.season_label and s.team_id = f.team_id and s.period_half = 'second_half'
    where f.period_half = 'first_half'
)
select * from team_vs_team
union all
select * from season_vs_season
union all
select * from home_vs_away
union all
select * from period_vs_period
