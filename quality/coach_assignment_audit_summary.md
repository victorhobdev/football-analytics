# Coach assignment audit

## Recorte executado

- Corte público: `2025-12-31`
- Fonte principal de passagem: `mart.stg_team_coaches`
- Fonte principal de partidas: `mart.fact_matches`
- Fontes auxiliares de identidade: `mart.dim_coach`, `raw.coaches`
- Fonte de lineup/súmula de técnico: inexistente nas tabelas atuais; `fixture_lineups` é player-only

## Resumo executivo

- Linhas auditadas (competição/temporada/time): `2423`
- Match-team públicos auditados: `34322`
- Match-team com atribuição atual possível: `7494` (21.8%)
- Match-team sem técnico atribuível hoje: `26828`
- Match-team com conflito de múltiplos elegíveis: `854`
- Passagens com nome inválido: `8`
- Passagens futuras escondidas pelo corte: `0`
- Riscos de assistant competindo com principal: `288`
- Linhas impactadas para superfície pública: `1684`

## Principais áreas sem cobertura

- `serie_a_it` 2022 | Hellas Verona | sem técnico: 39 | conflitos: 0 | risco assistant: 0
- `serie_a_it` 2022 | Spezia | sem técnico: 39 | conflitos: 0 | risco assistant: 0
- `brasileirao_a` 2023 | América Mineiro | sem técnico: 38 | conflitos: 0 | risco assistant: 0
- `brasileirao_a` 2022 | América Mineiro | sem técnico: 38 | conflitos: 0 | risco assistant: 0
- `brasileirao_a` 2021 | América Mineiro | sem técnico: 38 | conflitos: 0 | risco assistant: 0
- `brasileirao_a` 2021 | Atlético GO | sem técnico: 38 | conflitos: 0 | risco assistant: 0
- `brasileirao_a` 2021 | Atlético Mineiro | sem técnico: 38 | conflitos: 0 | risco assistant: 0
- `brasileirao_a` 2022 | Avaí | sem técnico: 38 | conflitos: 0 | risco assistant: 0
- `brasileirao_a` 2024 | Botafogo | sem técnico: 38 | conflitos: 0 | risco assistant: 0
- `brasileirao_a` 2021 | Ceará | sem técnico: 38 | conflitos: 0 | risco assistant: 0

## Principais áreas com conflito

- `brasileirao_a` 2024 | Atlético GO | sem técnico: 0 | conflitos: 38 | risco assistant: 0
- `brasileirao_a` 2023 | Cuiabá | sem técnico: 0 | conflitos: 38 | risco assistant: 23
- `brasileirao_a` 2023 | Vasco da Gama | sem técnico: 0 | conflitos: 38 | risco assistant: 38
- `brasileirao_b` 2025 | Atlético GO | sem técnico: 0 | conflitos: 38 | risco assistant: 0
- `la_liga` 2021 | Real Madrid | sem técnico: 0 | conflitos: 38 | risco assistant: 0
- `la_liga` 2023 | Real Madrid | sem técnico: 0 | conflitos: 38 | risco assistant: 0
- `la_liga` 2022 | Real Madrid | sem técnico: 0 | conflitos: 38 | risco assistant: 0
- `primeira_liga` 2023 | Casa Pia | sem técnico: 0 | conflitos: 34 | risco assistant: 0
- `primeira_liga` 2024 | Casa Pia | sem técnico: 0 | conflitos: 34 | risco assistant: 0
- `brasileirao_a` 2022 | Cuiabá | sem técnico: 0 | conflitos: 33 | risco assistant: 33

## Competições mais afetadas

- `serie_a_it` 2022 | times impactados: `20/20` | sem técnico: `762` | conflitos: `0`
- `brasileirao_b` 2021 | times impactados: `20/20` | sem técnico: `760` | conflitos: `0`
- `ligue_1` 2022 | times impactados: `20/20` | sem técnico: `760` | conflitos: `0`
- `ligue_1` 2020 | times impactados: `20/20` | sem técnico: `760` | conflitos: `0`
- `ligue_1` 2021 | times impactados: `20/20` | sem técnico: `760` | conflitos: `0`
- `premier_league` 2024 | times impactados: `20/20` | sem técnico: `760` | conflitos: `0`
- `premier_league` 2022 | times impactados: `20/20` | sem técnico: `760` | conflitos: `0`
- `premier_league` 2023 | times impactados: `20/20` | sem técnico: `760` | conflitos: `0`
- `premier_league` 2020 | times impactados: `20/20` | sem técnico: `760` | conflitos: `0`
- `premier_league` 2021 | times impactados: `20/20` | sem técnico: `760` | conflitos: `0`

## Flamengo 2020-2025

- 2021 | `brasileirao_a`: sem técnico `38`, conflitos `0`, assistant risk `0`
- 2021 | `copa_do_brasil`: sem técnico `8`, conflitos `0`, assistant risk `0`
- 2021 | `libertadores`: sem técnico `13`, conflitos `0`, assistant risk `0`
- 2022 | `brasileirao_a`: sem técnico `0`, conflitos `22`, assistant risk `22`
- 2022 | `copa_do_brasil`: sem técnico `0`, conflitos `8`, assistant risk `8`
- 2022 | `libertadores`: sem técnico `0`, conflitos `6`, assistant risk `6`
- 2023 | `brasileirao_a`: sem técnico `0`, conflitos `0`, assistant risk `0`
- 2023 | `copa_do_brasil`: sem técnico `0`, conflitos `0`, assistant risk `0`
- 2023 | `libertadores`: sem técnico `0`, conflitos `0`, assistant risk `0`
- 2024 | `brasileirao_a`: sem técnico `14`, conflitos `0`, assistant risk `1`
- 2024 | `copa_do_brasil`: sem técnico `4`, conflitos `0`, assistant risk `0`
- 2024 | `libertadores`: sem técnico `4`, conflitos `0`, assistant risk `0`
- 2025 | `brasileirao_a`: sem técnico `0`, conflitos `0`, assistant risk `0`
- 2025 | `copa_do_brasil`: sem técnico `0`, conflitos `0`, assistant risk `0`
- 2025 | `libertadores`: sem técnico `0`, conflitos `0`, assistant risk `0`
- 2025 | `supercopa_do_brasil`: sem técnico `0`, conflitos `0`, assistant risk `0`

## Leitura operacional

- O dado atual de técnicos ainda é majoritariamente de passagem, não de atribuição por partida.
- A inexistência de uma fonte nativa de coach por súmula/lineup impede fechar a cobertura só com heurística temporal.
- A prioridade prática continua sendo backfill em áreas já públicas, começando por Flamengo 2020-2025 e Série A 2020-2025.
