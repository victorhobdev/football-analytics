with matches as (
    select
        m.competition_sk,
        m.competition_key,
        m.season,
        m.season_label,
        m.match_id,
        m.home_team_id,
        m.away_team_id,
        coalesce(m.home_goals, 0) as home_goals,
        coalesce(m.away_goals, 0) as away_goals,
        coalesce(m.total_goals, 0) as total_goals,
        case when m.home_goals is not null and m.away_goals is not null then 1 else 0 end as has_score,
        m.date_day
    from {{ ref('fact_matches') }} m
),
competition as (
    select * from {{ ref('dim_competition') }}
),
all_teams as (
    select competition_sk, competition_key, season_label, home_team_id as team_id from matches
    union
    select competition_sk, competition_key, season_label, away_team_id as team_id from matches
),
team_counts as (
    select competition_sk, competition_key, season_label, count(distinct team_id)::int as total_teams
    from all_teams group by competition_sk, competition_key, season_label
),
coach_assignments as (
    select distinct
        fm.competition_sk,
        fm.competition_key,
        fm.season_label,
        tc.coach_id
    from {{ ref('fact_matches') }} fm
    inner join {{ ref('stg_team_coaches') }} tc
        on (tc.team_id = fm.home_team_id or tc.team_id = fm.away_team_id)
        and fm.date_day >= coalesce(tc.start_date, date '1900-01-01')
        and fm.date_day <= coalesce(tc.end_date, date '2999-12-31')
),
coach_counts as (
    select competition_sk, competition_key, season_label, count(distinct coach_id)::int as total_coaches
    from coach_assignments group by competition_sk, competition_key, season_label
),
player_matches as (
    select distinct
        fm.competition_sk,
        fm.competition_key,
        fm.season_label,
        fl.player_sk
    from {{ ref('fact_matches') }} fm
    inner join {{ ref('fact_fixture_lineups') }} fl on fl.match_id = fm.match_id
),
player_counts as (
    select competition_sk, competition_key, season_label, count(distinct player_sk)::int as total_players
    from player_matches group by competition_sk, competition_key, season_label
),
events as (
    select distinct fm.competition_sk, fm.competition_key, fm.season_label, me.match_id
    from {{ ref('fact_match_events') }} me
    inner join {{ ref('fact_matches') }} fm on fm.match_id = me.match_id
),
events_counts as (
    select competition_sk, competition_key, season_label, count(distinct match_id)::int as total_matches_with_events
    from events group by competition_sk, competition_key, season_label
),
aggregated as (
    select
        m.competition_sk,
        c.league_id,
        c.league_name,
        m.competition_key,
        m.season,
        m.season_label,
        count(distinct m.match_id)::int as total_matches,
        sum(m.total_goals)::int as total_goals,
        case
            when count(distinct m.match_id) > 0
            then round(sum(m.total_goals)::numeric / count(distinct m.match_id), 4)
        end as avg_goals_per_match,
        coalesce(tc.total_teams, 0)::int as total_teams,
        coalesce(cc.total_coaches, 0)::int as total_coaches,
        coalesce(pc.total_players, 0)::int as total_players,
        sum(m.has_score)::int as total_matches_with_score,
        coalesce(ec.total_matches_with_events, 0)::int as total_matches_with_events
    from matches m
    left join competition c on c.competition_sk = m.competition_sk
    left join team_counts tc on tc.competition_sk = m.competition_sk and tc.season_label = m.season_label
    left join coach_counts cc on cc.competition_sk = m.competition_sk and cc.season_label = m.season_label
    left join player_counts pc on pc.competition_sk = m.competition_sk and pc.season_label = m.season_label
    left join events_counts ec on ec.competition_sk = m.competition_sk and ec.season_label = m.season_label
    group by
        m.competition_sk, c.league_id, c.league_name, m.competition_key, m.season, m.season_label,
        tc.total_teams, cc.total_coaches, pc.total_players, ec.total_matches_with_events
)
select * from aggregated
