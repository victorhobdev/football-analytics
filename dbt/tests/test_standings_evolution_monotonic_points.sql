-- Regra: pontos acumulados nao podem diminuir ao longo das rodadas.
-- Tabela: standings_evolution
-- Rationale: acumulado deve ser monotonicamente nao-decrescente por competicao/temporada/time.

with ordered as (
    select
        competition_sk,
        season,
        team_id,
        round_key,
        points_accumulated,
        lag(points_accumulated) over (
            partition by competition_sk, season, team_id
            order by round_key
        ) as prev_points
    from {{ ref('standings_evolution') }}
)
select *
from ordered
where prev_points is not null
  and points_accumulated < prev_points
