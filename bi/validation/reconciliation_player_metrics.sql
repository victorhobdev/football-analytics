-- Resultado de referencia SQL para rankings de jogadores.
-- Retorna todos os escopos e explicita a cobertura; o relatorio tambem permite analisar recortes abaixo de 95%.
with scope_coverage as (
    select
        fm.provider,
        fm.competition_key,
        fm.season_label,
        count(distinct fm.match_id) as total_matches,
        count(distinct fps.match_id) as player_stats_matches
    from mart.fact_matches fm
    left join mart.fact_fixture_player_stats fps
      on fps.provider = fm.provider
     and fps.match_id = fm.match_id
    group by fm.provider, fm.competition_key, fm.season_label
),
valid_player_rows as (
    select
        fm.provider,
        fm.competition_key,
        fm.season_label,
        fps.match_id,
        fps.player_sk,
        max(fps.team_name) as team_name_reference,
        max(fps.minutes_played) as minutes_played,
        max(fps.goals) as goals,
        max(fps.assists) as assists,
        max(fps.shots_total) as shots_total,
        max(fps.rating) as rating
    from mart.fact_fixture_player_stats fps
    inner join mart.fact_matches fm
      on fm.provider = fps.provider
     and fm.match_id = fps.match_id
    where fm.home_goals is not null
      and fm.away_goals is not null
      and fps.player_sk is not null
    group by fm.provider, fm.competition_key, fm.season_label, fps.match_id, fps.player_sk
)
select
    v.provider,
    v.competition_key,
    v.season_label,
    round(100.0 * sc.player_stats_matches / nullif(sc.total_matches, 0), 2) as player_stats_pct,
    sc.player_stats_matches * 100.0 / nullif(sc.total_matches, 0) >= 95 as player_ranking_eligible,
    v.player_sk,
    dp.player_name,
    max(v.team_name_reference) as team_name_reference,
    count(distinct v.match_id)::int as matches,
    sum(coalesce(v.minutes_played, 0))::numeric as minutes_played,
    sum(coalesce(v.goals, 0))::numeric as goals,
    sum(coalesce(v.assists, 0))::numeric as assists,
    sum(coalesce(v.shots_total, 0))::numeric as shots_total,
    round(avg(v.rating), 3) as average_rating
from valid_player_rows v
inner join mart.dim_player dp on dp.player_sk = v.player_sk
inner join scope_coverage sc
  on sc.provider = v.provider
 and sc.competition_key = v.competition_key
 and sc.season_label = v.season_label
group by v.provider, v.competition_key, v.season_label, sc.total_matches,
         sc.player_stats_matches, v.player_sk, dp.player_name
order by v.provider, v.competition_key, v.season_label, goals desc, assists desc,
         average_rating desc nulls last, dp.player_name;
