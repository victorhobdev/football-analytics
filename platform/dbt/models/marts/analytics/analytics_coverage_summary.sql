{{ config(pre_hook="set local max_parallel_workers_per_gather = 0") }}

with match_base as (
    select
        m.competition_sk,
        m.competition_key,
        m.season_label,
        m.match_id,
        m.home_goals,
        m.away_goals,
        case when m.home_shots is not null or m.away_shots is not null then 1 else 0 end as has_team_stats
    from {{ ref('fact_matches') }} m
),
match_totals as (
    select
        competition_sk,
        competition_key,
        season_label,
        count(distinct match_id)::int as total_matches,
        sum(case when home_goals is not null and away_goals is not null then 1 else 0 end)::int as matches_with_score,
        sum(has_team_stats)::int as matches_with_team_stats
    from match_base
    group by competition_sk, competition_key, season_label
),
match_events as (
    select distinct
        fm.competition_sk,
        fm.competition_key,
        fm.season_label,
        me.match_id
    from {{ ref('fact_match_events') }} me
    inner join {{ ref('fact_matches') }} fm on fm.match_id = me.match_id
),
match_events_agg as (
    select
        competition_sk,
        competition_key,
        season_label,
        count(distinct match_id)::int as matches_with_events
    from match_events
    group by competition_sk, competition_key, season_label
),
lineups as (
    select distinct
        fm.competition_sk,
        fm.competition_key,
        fm.season_label,
        fl.match_id
    from {{ ref('fact_fixture_lineups') }} fl
    inner join {{ ref('fact_matches') }} fm on fm.match_id = fl.match_id
),
lineups_agg as (
    select
        competition_sk,
        competition_key,
        season_label,
        count(distinct match_id)::int as matches_with_lineups
    from lineups
    group by competition_sk, competition_key, season_label
),
player_stats as (
    select distinct
        fm.competition_sk,
        fm.competition_key,
        fm.season_label,
        fps.match_id
    from {{ ref('fact_fixture_player_stats') }} fps
    inner join {{ ref('fact_matches') }} fm on fm.match_id = fps.match_id
),
player_stats_agg as (
    select
        competition_sk,
        competition_key,
        season_label,
        count(distinct match_id)::int as matches_with_player_stats
    from player_stats
    group by competition_sk, competition_key, season_label
),
players_with_minutes as (
    select distinct
        fm.competition_sk,
        fm.competition_key,
        fm.season_label,
        fps.player_sk
    from {{ ref('fact_fixture_player_stats') }} fps
    inner join {{ ref('fact_matches') }} fm on fm.match_id = fps.match_id
    where coalesce(fps.minutes_played, 0) > 0
),
players_agg as (
    select
        competition_sk,
        competition_key,
        season_label,
        count(distinct player_sk)::int as players_with_minutes
    from players_with_minutes
    group by competition_sk, competition_key, season_label
),
coaches_agg as (
    select
        fm.competition_sk,
        fm.competition_key,
        fm.season_label,
        count(distinct tc.coach_id)::int as coaches_with_assignment
    from {{ ref('fact_matches') }} fm
    inner join {{ ref('stg_team_coaches') }} tc
        on (tc.team_id = fm.home_team_id or tc.team_id = fm.away_team_id)
        and fm.date_day >= coalesce(tc.start_date, date '1900-01-01')
        and fm.date_day <= coalesce(tc.end_date, date '2999-12-31')
    group by fm.competition_sk, fm.competition_key, fm.season_label
),
combined as (
    select
        mt.competition_sk,
        mt.competition_key,
        mt.season_label,
        mt.total_matches,
        mt.matches_with_score,
        coalesce(me.matches_with_events, 0)::int as matches_with_events,
        coalesce(li.matches_with_lineups, 0)::int as matches_with_lineups,
        coalesce(ps.matches_with_player_stats, 0)::int as matches_with_player_stats,
        mt.matches_with_team_stats,
        coalesce(ca.coaches_with_assignment, 0)::int as coaches_with_assignment,
        coalesce(pm.players_with_minutes, 0)::int as players_with_minutes,
        case
            when mt.total_matches > 0
            then round((mt.matches_with_score::numeric / mt.total_matches) * 100, 2)
        end as score_pct,
        case
            when mt.total_matches > 0
            then round((coalesce(me.matches_with_events, 0)::numeric / mt.total_matches) * 100, 2)
        end as events_pct,
        case
            when mt.total_matches > 0
            then round((coalesce(li.matches_with_lineups, 0)::numeric / mt.total_matches) * 100, 2)
        end as lineups_pct,
        case
            when mt.total_matches > 0
            then round((coalesce(ps.matches_with_player_stats, 0)::numeric / mt.total_matches) * 100, 2)
        end as player_stats_pct,
        case
            when mt.total_matches > 0
            then round((mt.matches_with_team_stats::numeric / mt.total_matches) * 100, 2)
        end as team_stats_pct
    from match_totals mt
    left join match_events_agg me on me.competition_sk = mt.competition_sk and me.season_label = mt.season_label
    left join lineups_agg li on li.competition_sk = mt.competition_sk and li.season_label = mt.season_label
    left join player_stats_agg ps on ps.competition_sk = mt.competition_sk and ps.season_label = mt.season_label
    left join coaches_agg ca on ca.competition_sk = mt.competition_sk and ca.season_label = mt.season_label
    left join players_agg pm on pm.competition_sk = mt.competition_sk and pm.season_label = mt.season_label
)
select
    competition_sk,
    competition_key,
    season_label,
    total_matches,
    matches_with_score,
    matches_with_events,
    matches_with_lineups,
    matches_with_player_stats,
    matches_with_team_stats,
    coaches_with_assignment,
    players_with_minutes,
    score_pct,
    events_pct,
    lineups_pct,
    player_stats_pct,
    team_stats_pct,
    case when score_pct >= 95 then 'complete' when score_pct >= 60 then 'partial' else 'insufficient' end as score_status,
    case when events_pct >= 95 then 'complete' when events_pct >= 60 then 'partial' else 'insufficient' end as events_status,
    case when lineups_pct >= 95 then 'complete' when lineups_pct >= 60 then 'partial' else 'insufficient' end as lineups_status,
    case when player_stats_pct >= 95 then 'complete' when player_stats_pct >= 60 then 'partial' else 'insufficient' end as player_stats_status,
    case when team_stats_pct >= 95 then 'complete' when team_stats_pct >= 60 then 'partial' else 'insufficient' end as team_stats_status
from combined
