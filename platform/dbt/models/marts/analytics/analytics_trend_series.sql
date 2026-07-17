with match_base as (
    select
        m.competition_sk,
        m.competition_key,
        m.season_label,
        m.match_id,
        m.round_number,
        coalesce(m.round_name, concat('Round ', m.round_number::text)) as round_name,
        extract(year from m.date_day)::int as year,
        lpad(extract(month from m.date_day)::int::text, 2, '0') as month,
        coalesce(m.total_goals, 0) as total_goals,
        case
            when coalesce(m.home_goals, 0) > coalesce(m.away_goals, 0) then 1 else 0
        end as home_win,
        case
            when coalesce(m.home_goals, 0) < coalesce(m.away_goals, 0) then 1 else 0
        end as away_win,
        case
            when coalesce(m.home_goals, 0) = coalesce(m.away_goals, 0) then 1 else 0
        end as draw
    from {{ ref('fact_matches') }} m
    where m.round_number > 0
),
round_trends as (
    select
        competition_sk,
        competition_key,
        season_label,
        'round' as period_type,
        round_number::text as period,
        max(round_name) as round_name,
        round_number as period_sort_key,
        count(distinct match_id)::int as matches,
        sum(total_goals)::int as total_goals,
        case
            when count(distinct match_id) > 0
            then round(sum(total_goals)::numeric / count(distinct match_id), 4)
        end as avg_goals,
        sum(home_win)::int as home_wins,
        sum(away_win)::int as away_wins,
        sum(draw)::int as draws
    from match_base
    group by competition_sk, competition_key, season_label, round_number
),
month_trends as (
    select
        competition_sk,
        competition_key,
        season_label,
        'month' as period_type,
        concat(year, '-', month) as period,
        concat(year, '-', month) as round_name,
        year * 100 + month::int as period_sort_key,
        count(distinct match_id)::int as matches,
        sum(total_goals)::int as total_goals,
        case
            when count(distinct match_id) > 0
            then round(sum(total_goals)::numeric / count(distinct match_id), 4)
        end as avg_goals,
        sum(home_win)::int as home_wins,
        sum(away_win)::int as away_wins,
        sum(draw)::int as draws
    from match_base
    group by competition_sk, competition_key, season_label, year, month
)
select * from round_trends
union all
select * from month_trends
order by competition_sk, season_label, period_type, period_sort_key
