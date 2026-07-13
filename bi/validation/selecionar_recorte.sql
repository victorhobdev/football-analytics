-- Cobertura de todo o conjunto público de mart.* para os segmentadores do Power BI.
-- O identificador de escopo é sempre provider + competition_key + season_label.
-- Execute: docker exec -i football_postgres psql -U football -d football_dw -f - < bi/validation/selecionar_recorte.sql
with player_match_coverage as (
    select
        match_id,
        bool_or(minutes_played is not null) as has_minutes,
        bool_or(goals is not null) as has_goals,
        bool_or(assists is not null) as has_assists,
        bool_or(shots_total is not null) as has_shots,
        bool_or(rating is not null) as has_rating
    from mart.fact_fixture_player_stats
    group by match_id
),
scope_coverage as (
    select
        fm.provider,
        fm.competition_key,
        fm.season_label,
        count(*)::int as total_matches,
        count(*) filter (where fm.home_goals is not null and fm.away_goals is not null)::int as matches_with_score,
        count(*) filter (where fm.home_shots is not null or fm.away_shots is not null)::int as matches_with_team_stats,
        count(pmc.match_id)::int as matches_with_player_stats,
        count(pmc.match_id) filter (where pmc.has_minutes)::int as matches_with_minutes,
        count(pmc.match_id) filter (where pmc.has_goals)::int as matches_with_goals,
        count(pmc.match_id) filter (where pmc.has_assists)::int as matches_with_assists,
        count(pmc.match_id) filter (where pmc.has_shots)::int as matches_with_shots,
        count(pmc.match_id) filter (where pmc.has_rating)::int as matches_with_rating,
        min(fm.date_day) as first_match_date,
        max(fm.date_day) as last_match_date
    from mart.fact_matches fm
    left join player_match_coverage pmc on pmc.match_id = fm.match_id
    group by fm.provider, fm.competition_key, fm.season_label
)
select
    concat_ws('|', provider, competition_key, season_label) as scope_key,
    provider,
    competition_key,
    season_label,
    total_matches,
    matches_with_score,
    round(100.0 * matches_with_score / nullif(total_matches, 0), 2) as score_pct,
    matches_with_team_stats,
    round(100.0 * matches_with_team_stats / nullif(total_matches, 0), 2) as team_stats_pct,
    matches_with_player_stats,
    round(100.0 * matches_with_player_stats / nullif(total_matches, 0), 2) as player_stats_pct,
    matches_with_minutes,
    round(100.0 * matches_with_minutes / nullif(total_matches, 0), 2) as minutes_pct,
    matches_with_goals,
    round(100.0 * matches_with_goals / nullif(total_matches, 0), 2) as goals_pct,
    matches_with_assists,
    round(100.0 * matches_with_assists / nullif(total_matches, 0), 2) as assists_pct,
    matches_with_shots,
    round(100.0 * matches_with_shots / nullif(total_matches, 0), 2) as shots_pct,
    matches_with_rating,
    round(100.0 * matches_with_rating / nullif(total_matches, 0), 2) as rating_pct,
    case when matches_with_score * 100.0 / nullif(total_matches, 0) >= 95 then true else false end as team_ranking_eligible,
    case when matches_with_team_stats * 100.0 / nullif(total_matches, 0) >= 95 then true else false end as team_stats_eligible,
    case when matches_with_player_stats * 100.0 / nullif(total_matches, 0) >= 95 then true else false end as player_ranking_eligible,
    first_match_date,
    last_match_date
from scope_coverage
order by provider, competition_key, season_label;
