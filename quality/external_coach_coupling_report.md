# External coach coupling report

## Escopo

- Camada externa carregada em raw/staging.
- Nenhuma promocao para `mart.coach_tenure`.
- Nenhuma promocao para `mart.fact_coach_match_assignment`.
- Janela aplicada: `2020-01-01` ate `2025-12-31`.

## Cobertura potencial

- Match-teams publicos na janela: `32522`
- Assignments publicos atuais: `10903` (`33.52%`)
- Match-teams novos automaticamente promoviveis em staging: `8201`
- Cobertura potencial se promovidos: `19104` (`58.74%`)
- Match-teams em review: `8908`

## Gates

- `outside_window_assignment_candidates`: `0`
- `would_overwrite_public_assignment`: `0`
- `assistant_promotable_candidates`: `0`
- `invalid_promotable_names`: `0`

## Classificacao dos fatos externos

- `blocked_invalid_interval`: `2`
- `blocked_invalid_name`: `1451`
- `blocked_non_senior_or_season_team`: `9838`
- `blocked_outside_window`: `1915`
- `blocked_unresolved_team`: `119970`
- `likely_duplicate`: `144`
- `low_value_context`: `570`
- `promotable_candidate`: `343`
- `review_needed`: `17804`

## Status dos candidatos por partida

- `blocked_conflict`: `24`
- `promotable`: `8201`
- `review_needed`: `15913`

## Fontes com candidatos promoviveis

- `wikidata_P286_team_to_person`: `343` candidatos, `8225` match-teams brutos cobertos

## Times com maior cobertura incremental potencial

- `Real Madrid`: `196` match-teams
- `Manchester City`: `191` match-teams
- `Paris Saint Germain`: `188` match-teams
- `Atlético Madrid`: `176` match-teams
- `Borussia Dortmund`: `169` match-teams
- `Chelsea`: `167` match-teams
- `AC Milan`: `166` match-teams
- `Juventus`: `164` match-teams
- `Arsenal`: `158` match-teams
- `Sevilla`: `157` match-teams
- `Manchester United`: `153` match-teams
- `São Paulo`: `150` match-teams
- `Olympique Marseille`: `145` match-teams
- `Aston Villa`: `144` match-teams
- `Villarreal`: `144` match-teams
- `Tottenham Hotspur`: `142` match-teams
- `Real Sociedad`: `140` match-teams
- `Internacional`: `138` match-teams
- `Newcastle United`: `136` match-teams
- `Atlético Mineiro`: `135` match-teams

## Amostra de confirmacao

Esta amostra nao altera criterio por clube; serve apenas para conferir nomes conhecidos contra o mesmo motor geral.
- `Flamengo` | `Dorival Júnior` | 2022-06-10 ate 2022-11-25 | `promotable_candidate` | lacuna `43`
- `Flamengo` | `Jorge Sampaoli` | 2023-04-17 ate 2023-09-28 | `promotable_candidate` | lacuna `39`
- `Flamengo` | `Paulo Sousa` | 2021-12-29 ate 2022-06-10 | `promotable_candidate` | lacuna `18`
- `Flamengo` | `Rogério Ceni` | 2020-11-10 ate 2021-07-10 | `promotable_candidate` | lacuna `16`
- `Flamengo` | `Tite` | 2023-10-09 ate 2024-09-30 | `promotable_candidate` | lacuna `12`
- `Flamengo` | `Maurício Souza` | 2021-11-29 ate 2021-12-29 | `promotable_candidate` | lacuna `4`
- `Flamengo` | `Vítor Pereira` | 2023-01-01 ate 2023-04-10 | `promotable_candidate` | lacuna `1`
- `Flamengo` | `Dorival Júnior` | 2020-01-01 ate 2025-12-31 | `review_needed` | lacuna `176`
- `Flamengo` | `Mano Menezes` | 2020-01-01 ate 2025-12-31 | `review_needed` | lacuna `176`
- `Flamengo` | `Nelsinho Baptista` | 2020-01-01 ate 2025-12-31 | `review_needed` | lacuna `176`
- `Flamengo` | `Dorival Júnior` | 2022-01-01 ate 2025-12-31 | `review_needed` | lacuna `117`
- `Flamengo` | `Dorival Júnior` | 2022-01-01 ate 2022-12-31 | `review_needed` | lacuna `61`
- `Flamengo` | `Tite` | 2023-01-01 ate 2025-12-31 | `review_needed` | lacuna `56`
- `Flamengo` | `Tite (football manager)` | 2023-01-01 ate 2024-12-31 | `review_needed` | lacuna `56`
- `Flamengo` | `Vítor Pereira (footballer, born 1968)` | 2023-01-01 ate 2023-12-31 | `review_needed` | lacuna `56`
- `Flamengo` | `Jorge Sampaoli` | 2023-04-14 ate 2023-09-28 | `review_needed` | lacuna `40`
- `Flamengo` | `Filipe Luís` | 2024-01-01 ate 2025-12-31 | `likely_duplicate` | lacuna `0`
- `Flamengo` | `Filipe Luís` | 2024-09-30 ate 2025-12-31 | `likely_duplicate` | lacuna `0`
- `Flamengo` | `Jorge Jesus` | 2020-01-01 ate 2020-07-17 | `low_value_context` | lacuna `0`
- `Flamengo` | `Jorge Jesus` | 2020-01-01 ate 2020-07-17 | `low_value_context` | lacuna `0`
- `Flamengo` | `Rogério Ceni` | 2020-01-01 ate 2021-01-01 | `low_value_context` | lacuna `0`
- `Flamengo` | `Domènec Torrent` | 2020-07-31 ate 2020-11-09 | `low_value_context` | lacuna `0`
- `Flamengo` | `Adílio (footballer, born 1956)  Adílio  1` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Aílton Ferraz` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Andrade (footballer, born 1957)` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Antônio Lopes` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Armando Renganeschi` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Athirson` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Aymoré Moreira` | ? ate ? | `blocked_outside_window` | lacuna `0`
- `Flamengo` | `Cândido de Oliveira` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Candinho` | ? ate ? | `blocked_outside_window` | lacuna `0`
- `Flamengo` | `Carlinhos (footballer, born 1937)` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Carlos Alberto Torres` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `César Sampaio` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Charlie Williams (footballer, born 1873)` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Cláudio Coutinho` | ? ate ? | `blocked_outside_window` | lacuna `0`
- `Flamengo` | `Cláudio Coutinho` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Cristóvão Borges` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Daniel Frasson` | ? ate ? | `review_needed` | lacuna `0`
- `Flamengo` | `Deivid` | ? ate ? | `review_needed` | lacuna `0`

## Arquivos gerados

- Resumo JSON: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\quality\external_coach_coupling_summary.json`
- Candidatos promoviveis: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\quality\external_coach_coupling_promotable_candidates.csv`
- Conflitos: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\quality\external_coach_coupling_conflicts.csv`
- Cobertura por recorte: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\quality\external_coach_coupling_coverage.csv`

## Leitura operacional

- `promotable` ainda significa promovivel por regra, nao promovido ao produto.
- `review_needed` pode enriquecer historico depois de validacao ou segunda fonte.
- `blocked_conflict` impede publicacao ate escolha manual ou fonte mais forte.
