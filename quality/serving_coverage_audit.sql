-- Audit de cobertura raw -> mart -> serving.
-- Objetivo: detectar perda de conteudo entre camadas e separa-la por competicao.
-- Execute no banco local (schema raw e mart).

-- 1) Panorama geral por camada.
select
    (select count(*) from raw.fixtures) as raw_fixtures,
    (select count(*) from mart.fact_matches) as mart_fact_matches,
    (select count(*) from mart.competition_serving_summary) as serving_competition_rows,
    (select coalesce(sum(matches_count), 0) from mart.competition_serving_summary) as serving_matches_total,
    (select count(*) from raw.fixture_lineups) as raw_lineups,
    (select count(*) from mart.fact_fixture_lineups) as mart_lineups,
    (select count(*) from raw.match_events) as raw_match_events,
    (select count(*) from mart.fact_match_events) as mart_match_events,
    (select count(*) from raw.fixture_player_statistics) as raw_fixture_player_statistics,
    (select count(*) from mart.fact_fixture_player_stats) as mart_fixture_player_stats,
    (select count(*) from mart.player_match_summary) as mart_player_match_summary,
    (select count(*) from mart.player_serving_summary) as mart_player_serving_summary;

-- 2) Cobertura por competicao (raw fixtures vs fact_matches vs serving_summary).
with raw_by_league as (
    select
        f.league_id,
        count(*)::int as raw_fixtures
    from raw.fixtures f
    where f.league_id is not null
    group by f.league_id
),
fact_by_league as (
    select
        fm.league_id,
        count(*)::int as fact_matches
    from mart.fact_matches fm
    group by fm.league_id
),
serving_by_league as (
    select
        css.league_id,
        css.matches_count::int as serving_matches
    from mart.competition_serving_summary css
),
combined as (
    select
        coalesce(r.league_id, f.league_id, s.league_id) as league_id,
        coalesce(r.raw_fixtures, 0) as raw_fixtures,
        coalesce(f.fact_matches, 0) as fact_matches,
        coalesce(s.serving_matches, 0) as serving_matches
    from raw_by_league r
    full outer join fact_by_league f
      on f.league_id = r.league_id
    full outer join serving_by_league s
      on s.league_id = coalesce(r.league_id, f.league_id)
)
select
    c.league_id,
    dc.league_name,
    c.raw_fixtures,
    c.fact_matches,
    c.serving_matches,
    (c.raw_fixtures - c.fact_matches) as raw_minus_fact,
    (c.fact_matches - c.serving_matches) as fact_minus_serving
from combined c
left join mart.dim_competition dc
  on dc.league_id = c.league_id
where c.raw_fixtures <> c.fact_matches
   or c.fact_matches <> c.serving_matches
order by
    abs(c.raw_fixtures - c.fact_matches) desc,
    abs(c.fact_matches - c.serving_matches) desc,
    c.league_id asc;

-- 3) Fixtures em raw que nao entraram em fact_matches.
-- Ajuda a separar filtro semantico (dados incompletos) de erro operacional.
select
    f.fixture_id,
    f.league_id,
    f.season,
    f.date_utc,
    f.home_team_id,
    f.away_team_id,
    f.status_short,
    f.status_long
from raw.fixtures f
left join mart.fact_matches fm
  on fm.match_id = f.fixture_id
where fm.match_id is null
order by f.date_utc desc nulls last
limit 200;

-- 4) Cobertura de dados taticos por competicao (estatisticas/lineups/eventos/player stats).
with fact_match_base as (
    select
        fm.league_id,
        count(distinct fm.match_id)::int as fact_matches
    from mart.fact_matches fm
    group by fm.league_id
),
stats_cov as (
    select
        rf.league_id,
        count(distinct ms.fixture_id)::int as match_statistics_matches
    from raw.match_statistics ms
    join raw.fixtures rf
      on rf.fixture_id = ms.fixture_id
    group by rf.league_id
),
lineups_cov as (
    select
        rf.league_id,
        count(distinct fl.fixture_id)::int as lineups_matches
    from raw.fixture_lineups fl
    join raw.fixtures rf
      on rf.fixture_id = fl.fixture_id
    group by rf.league_id
),
events_cov as (
    select
        rf.league_id,
        count(distinct me.fixture_id)::int as events_matches
    from raw.match_events me
    join raw.fixtures rf
      on rf.fixture_id = me.fixture_id
    group by rf.league_id
),
player_stats_cov as (
    select
        rf.league_id,
        count(distinct fps.fixture_id)::int as player_stats_matches
    from raw.fixture_player_statistics fps
    join raw.fixtures rf
      on rf.fixture_id = fps.fixture_id
    group by rf.league_id
)
select
    f.league_id,
    dc.league_name,
    f.fact_matches,
    coalesce(s.match_statistics_matches, 0) as match_statistics_matches,
    coalesce(l.lineups_matches, 0) as lineups_matches,
    coalesce(e.events_matches, 0) as events_matches,
    coalesce(p.player_stats_matches, 0) as player_stats_matches,
    round(coalesce(s.match_statistics_matches, 0)::numeric / nullif(f.fact_matches, 0) * 100, 2) as match_statistics_pct,
    round(coalesce(l.lineups_matches, 0)::numeric / nullif(f.fact_matches, 0) * 100, 2) as lineups_pct,
    round(coalesce(e.events_matches, 0)::numeric / nullif(f.fact_matches, 0) * 100, 2) as events_pct,
    round(coalesce(p.player_stats_matches, 0)::numeric / nullif(f.fact_matches, 0) * 100, 2) as player_stats_pct
from fact_match_base f
left join stats_cov s
  on s.league_id = f.league_id
left join lineups_cov l
  on l.league_id = f.league_id
left join events_cov e
  on e.league_id = f.league_id
left join player_stats_cov p
  on p.league_id = f.league_id
left join mart.dim_competition dc
  on dc.league_id = f.league_id
order by f.fact_matches desc, f.league_id asc;

-- 5) Player serving vs player_match_summary (perda de entidade).
with pms as (
    select count(distinct player_id)::int as players_pms from mart.player_match_summary
),
pss as (
    select count(distinct player_id)::int as players_pss from mart.player_serving_summary
)
select
    pms.players_pms,
    pss.players_pss,
    (pms.players_pms - pss.players_pss) as players_missing_in_serving
from pms
cross join pss;

-- 6) Jogadores presentes no player_match_summary e ausentes no player_serving_summary.
select
    pms.player_id,
    max(pms.player_name) as player_name,
    count(distinct pms.match_id)::int as matches_in_pms
from mart.player_match_summary pms
left join mart.player_serving_summary pss
  on pss.player_id = pms.player_id
where pss.player_id is null
group by pms.player_id
order by matches_in_pms desc, pms.player_id asc
limit 200;
