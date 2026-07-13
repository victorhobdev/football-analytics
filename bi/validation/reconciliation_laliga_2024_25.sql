-- Fixture de reconciliacao; nao limita o escopo do relatorio.
-- O resultado esperado no snapshot de 2026-07-12 e PASS (380 partidas validas, 20 times, 760 linhas time-partida).
with fixture_matches as (
    select *
    from mart.fact_matches
    where provider = 'sportmonks'
      and competition_key = 'la_liga'
      and season_label = '2024_25'
),
valid_matches as (
    select * from fixture_matches
    where home_goals is not null and away_goals is not null
),
fact_team_match as (
    select match_id, home_team_id as team_id from valid_matches
    union all
    select match_id, away_team_id from valid_matches
)
select
    count(*) filter (where home_goals is not null and away_goals is not null)::int as valid_matches,
    count(*) filter (where home_goals is null or away_goals is null)::int as excluded_matches_without_score,
    (select count(distinct team_id)::int from fact_team_match) as teams,
    (select count(*)::int from fact_team_match) as fact_team_match_rows,
    case
        when count(*) filter (where home_goals is not null and away_goals is not null) = 380
         and count(*) filter (where home_goals is null or away_goals is null) = 0
         and (select count(distinct team_id) from fact_team_match) = 20
         and (select count(*) from fact_team_match) = 760
        then 'PASS'
        else 'CHECK_SOURCE_REFRESH'
    end as fixture_status
from fixture_matches;
