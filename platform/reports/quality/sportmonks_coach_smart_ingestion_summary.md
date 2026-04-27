# SportMonks smart coach ingestion summary

## Resultado final

O primeiro piloto estava subestimado porque buscava apenas Flamengo. A ingestao foi ampliada em duas etapas:

- varredura por clubes locais em 2024-2025;
- gapfill por `fixtures/multi/{ids}` usando os `match_id` locais ainda sem tecnico.

## Cobertura

- Produto inteiro ate `2025-12-31`: `10.845/34.322` match-team cobertos (`31,60%`).
- Janela acessivel do provider `2024-2025`: `8.756/9.456` match-team cobertos (`92,60%`).
- Flamengo `2024-2025`: `114/114` (`100,00%`).

## Volume ingerido

- `1.959` tecnicos em `raw.sportmonks_coaches`.
- `23.559` linhas `fixture + team + coach` em `raw.sportmonks_fixture_coaches`.
- `23.559` linhas em `mart.stg_sportmonks_fixture_coach_assignments`.
- `10.903` assignments publicos em `mart.fact_coach_match_assignment`.
- `613` tecnicos distintos aparecem em assignments publicos.
- `374` times distintos aparecem em assignments publicos.
- `5.503` partidas distintas aparecem em assignments publicos.

## Principais lacunas restantes em 2024-2025

- `champions_league` 2024: `0/558` (`0,00%`).
- `brasileirao_a` 2024: `720/760` (`94,74%`).
- `brasileirao_b` 2025: `722/758` (`95,25%`).
- `brasileirao_b` 2024: `728/756` (`96,30%`).
- `primeira_liga` 2024: `590/612` (`96,41%`).
- `copa_do_brasil` 2025: `231/244` (`94,67%`).

## Diagnostico

A estrategia mais eficiente nao e buscar por clube isolado. O melhor fluxo e:

1. usar `mart.fact_matches` como indice canonico de fixtures;
2. chamar `fixtures/multi/{ids}` para os jogos ainda sem tecnico;
3. publicar apenas payloads com `coach.meta.participant_id`;
4. deixar sem publicar quando a API nao retorna fixture ou retorna apenas um dos lados.

O teto atual da janela 2024-2025 ficou em `92,60%`. A maior trava residual e cobertura/acesso por competicao, com Champions League 2024 totalmente sem tecnico retornado no acesso atual.
