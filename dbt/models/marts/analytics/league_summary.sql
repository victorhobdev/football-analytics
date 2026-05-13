with matches as (
    select * from {{ ref('fact_matches') }}
),
competition as (
    select * from {{ ref('dim_competition') }}
),
aggregated as (
    select
        m.league_id,
        c.league_name,
        m.season,
        count(*)::int as total_matches,
        sum(coalesce(m.total_goals, 0))::int as total_goals,
        round(sum(coalesce(m.total_goals, 0))::numeric / nullif(count(*), 0), 4) as avg_goals_per_match,
        min(m.date_day) as first_match_date,
        max(m.date_day) as last_match_date
    from matches m
    left join competition c
      on c.league_id = m.league_id
    group by m.league_id, c.league_name, m.season
)
select * from aggregated
