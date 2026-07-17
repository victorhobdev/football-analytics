with match_scoring as (
    select
        match_id,
        competition_key,
        season_label,
        'most_goals_match' as category,
        total_goals as value,
        concat('Match ', match_id::text) as entity_name,
        match_id::text as entity_id,
        concat(competition_key, ' / ', season_label) as scope,
        count(*) over (partition by competition_key, season_label)::int as sample_size,
        row_number() over (
            partition by competition_key, season_label
            order by total_goals desc, match_id desc
        ) as rn
    from {{ ref('fact_matches') }}
    where total_goals is not null
),
biggest_win as (
    select
        match_id,
        competition_key,
        season_label,
        'biggest_win' as category,
        abs(coalesce(home_goals, 0) - coalesce(away_goals, 0)) as value,
        concat('Match ', match_id::text) as entity_name,
        match_id::text as entity_id,
        concat(competition_key, ' / ', season_label) as scope,
        count(*) over (partition by competition_key, season_label)::int as sample_size,
        row_number() over (
            partition by competition_key, season_label
            order by abs(coalesce(home_goals, 0) - coalesce(away_goals, 0)) desc, match_id desc
        ) as rn
    from {{ ref('fact_matches') }}
    where home_goals is not null and away_goals is not null
),
team_attack as (
    select
        fm.competition_key,
        fm.season_label,
        'best_attack' as category,
        tr.team_id as entity_id,
        dt.team_name as entity_name,
        sum(tr.goals_for) as value,
        concat(fm.competition_key, ' / ', fm.season_label) as scope,
        count(distinct tr.match_id)::int as sample_size,
        row_number() over (
            partition by fm.competition_key, fm.season_label
            order by sum(tr.goals_for) desc, tr.team_id desc
        ) as rn
    from {{ ref('int_team_match_rows') }} tr
    inner join {{ ref('fact_matches') }} fm on fm.match_id = tr.match_id
    left join {{ ref('dim_team') }} dt on dt.team_id = tr.team_id
    group by fm.competition_key, fm.season_label, tr.team_id, dt.team_name
),
team_defense as (
    select
        fm.competition_key,
        fm.season_label,
        'best_defense' as category,
        tr.team_id as entity_id,
        dt.team_name as entity_name,
        sum(tr.goals_against) as value,
        concat(fm.competition_key, ' / ', fm.season_label) as scope,
        count(distinct tr.match_id)::int as sample_size,
        row_number() over (
            partition by fm.competition_key, fm.season_label
            order by sum(tr.goals_against) asc, tr.team_id desc
        ) as rn
    from {{ ref('int_team_match_rows') }} tr
    inner join {{ ref('fact_matches') }} fm on fm.match_id = tr.match_id
    left join {{ ref('dim_team') }} dt on dt.team_id = tr.team_id
    group by fm.competition_key, fm.season_label, tr.team_id, dt.team_name
),
team_goal_diff as (
    select
        fm.competition_key,
        fm.season_label,
        'best_goal_diff' as category,
        tr.team_id as entity_id,
        dt.team_name as entity_name,
        sum(tr.goals_for) - sum(tr.goals_against) as value,
        concat(fm.competition_key, ' / ', fm.season_label) as scope,
        count(distinct tr.match_id)::int as sample_size,
        row_number() over (
            partition by fm.competition_key, fm.season_label
            order by (sum(tr.goals_for) - sum(tr.goals_against)) desc, tr.team_id desc
        ) as rn
    from {{ ref('int_team_match_rows') }} tr
    inner join {{ ref('fact_matches') }} fm on fm.match_id = tr.match_id
    left join {{ ref('dim_team') }} dt on dt.team_id = tr.team_id
    group by fm.competition_key, fm.season_label, tr.team_id, dt.team_name
),
round_scoring as (
    select
        competition_key,
        season_label,
        'most_goals_round' as category,
        round_number::text as entity_id,
        concat('Round ', round_number::text) as entity_name,
        sum(coalesce(total_goals, 0)) as value,
        concat(competition_key, ' / ', season_label) as scope,
        count(distinct match_id)::int as sample_size,
        row_number() over (
            partition by competition_key, season_label
            order by sum(coalesce(total_goals, 0)) desc, round_number desc
        ) as rn
    from {{ ref('fact_matches') }}
    where round_number > 0
    group by competition_key, season_label, round_number
),
round_avg as (
    select
        competition_key,
        season_label,
        'highest_avg_goals_round' as category,
        round_number::text as entity_id,
        concat('Round ', round_number::text) as entity_name,
        round(avg(coalesce(total_goals, 0))::numeric, 4) as value,
        concat(competition_key, ' / ', season_label) as scope,
        count(distinct match_id)::int as sample_size,
        row_number() over (
            partition by competition_key, season_label
            order by avg(coalesce(total_goals, 0)) desc, round_number desc
        ) as rn
    from {{ ref('fact_matches') }}
    where round_number > 0
    group by competition_key, season_label, round_number
),
team_ppg as (
    select
        fm.competition_key,
        fm.season_label,
        'best_team_ppg' as category,
        tr.team_id::text as entity_id,
        dt.team_name as entity_name,
        round(sum(tr.points_round)::numeric / nullif(count(distinct tr.match_id), 0), 4) as value,
        concat(fm.competition_key, ' / ', fm.season_label) as scope,
        count(distinct tr.match_id)::int as sample_size,
        row_number() over (
            partition by fm.competition_key, fm.season_label
            order by
                (sum(tr.points_round)::numeric / nullif(count(distinct tr.match_id), 0)) desc,
                sum(tr.goals_for) desc,
                tr.team_id desc
        ) as rn
    from {{ ref('int_team_match_rows') }} tr
    inner join {{ ref('fact_matches') }} fm on fm.match_id = tr.match_id
    left join {{ ref('dim_team') }} dt on dt.team_id = tr.team_id
    group by fm.competition_key, fm.season_label, tr.team_id, dt.team_name
),
coach_stats as (
    select
        fm.competition_key,
        fm.season_label,
        tc.coach_id,
        coalesce(dc.coach_name, 'Nome indisponivel') as coach_name,
        count(distinct fm.match_id)::int as total_matches,
        sum(
            case
                when (tc.team_id = fm.home_team_id and coalesce(fm.home_goals, 0) > coalesce(fm.away_goals, 0))
                     or (tc.team_id = fm.away_team_id and coalesce(fm.away_goals, 0) > coalesce(fm.home_goals, 0))
                then 3
                when coalesce(fm.home_goals, 0) = coalesce(fm.away_goals, 0) then 1
                else 0
            end
        )::int as total_points
    from {{ ref('fact_matches') }} fm
    inner join {{ ref('stg_team_coaches') }} tc
        on (tc.team_id = fm.home_team_id or tc.team_id = fm.away_team_id)
        and fm.date_day >= coalesce(tc.start_date, date '1900-01-01')
        and fm.date_day <= coalesce(tc.end_date, date '2999-12-31')
    left join {{ ref('dim_coach') }} dc
        on dc.provider = tc.provider and dc.coach_id = tc.coach_id
    group by fm.competition_key, fm.season_label, tc.coach_id, dc.coach_name
),
coach_ppm as (
    select
        competition_key,
        season_label,
        'coach_best_ppm' as category,
        coach_id::text as entity_id,
        coach_name as entity_name,
        round(total_points::numeric / nullif(total_matches, 0), 4) as value,
        concat(competition_key, ' / ', season_label) as scope,
        total_matches as sample_size,
        row_number() over (
            partition by competition_key, season_label
            order by
                (total_points::numeric / nullif(total_matches, 0)) desc,
                total_matches desc,
                coach_id desc
        ) as rn
    from coach_stats
    where total_matches > 0
),
coach_most_matches as (
    select
        competition_key,
        season_label,
        'coach_most_matches' as category,
        coach_id::text as entity_id,
        coach_name as entity_name,
        total_matches as value,
        concat(competition_key, ' / ', season_label) as scope,
        total_matches as sample_size,
        row_number() over (
            partition by competition_key, season_label
            order by total_matches desc, coach_id desc
        ) as rn
    from coach_stats
    where total_matches > 0
),
combined as (
    select category, 'total_goals'::text as metric_name, entity_id::text, entity_name, value::numeric, scope, sample_size from match_scoring where rn = 1
    union all
    select category, 'goal_difference'::text as metric_name, entity_id::text, entity_name, value::numeric, scope, sample_size from biggest_win where rn = 1
    union all
    select category, 'goals_for'::text as metric_name, entity_id::text, entity_name, value::numeric, scope, sample_size from team_attack where rn = 1
    union all
    select category, 'goals_against'::text as metric_name, entity_id::text, entity_name, value::numeric, scope, sample_size from team_defense where rn = 1
    union all
    select category, 'goal_diff'::text as metric_name, entity_id::text, entity_name, value::numeric, scope, sample_size from team_goal_diff where rn = 1
    union all
    select category, 'goals'::text as metric_name, entity_id::text, entity_name, value::numeric, scope, sample_size from round_scoring where rn = 1
    union all
    select category, 'avg_goals'::text as metric_name, entity_id::text, entity_name, value::numeric, scope, sample_size from round_avg where rn = 1
    union all
    select category, 'points_per_game'::text as metric_name, entity_id::text, entity_name, value::numeric, scope, sample_size from team_ppg where rn = 1
    union all
    select category, 'points_per_match'::text as metric_name, entity_id::text, entity_name, value::numeric, scope, sample_size from coach_ppm where rn = 1
    union all
    select category, 'matches'::text as metric_name, entity_id::text, entity_name, value::numeric, scope, sample_size from coach_most_matches where rn = 1
)
select * from combined
