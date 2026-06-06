# External coach coupling report

## Escopo

- Camada externa carregada em raw/staging.
- Nenhuma promocao para `mart.coach_tenure`.
- Nenhuma promocao para `mart.fact_coach_match_assignment`.
- Janela aplicada: `2020-01-01` ate `2025-12-31`.

## Cobertura potencial

- Match-teams publicos na janela: `32522`
- Assignments publicos atuais: `19104` (`58.74%`)
- Match-teams novos automaticamente promoviveis em staging: `163`
- Cobertura potencial se promovidos: `19267` (`59.24%`)
- Match-teams em review: `2560`

## Gates

- `outside_window_assignment_candidates`: `0`
- `would_overwrite_public_assignment`: `0`
- `assistant_promotable_candidates`: `0`
- `invalid_promotable_names`: `0`

## Classificacao dos fatos externos

- `blocked_invalid_interval`: `2`
- `blocked_invalid_name`: `1451`
- `blocked_non_senior_or_season_team`: `9838`
- `blocked_outside_window`: `1939`
- `blocked_unresolved_team`: `119939`
- `likely_duplicate`: `657`
- `low_value_context`: `571`
- `promotable_candidate`: `5`
- `review_needed`: `17635`

## Status dos candidatos por partida

- `blocked_conflict`: `24`
- `promotable`: `163`
- `review_needed`: `5166`

## Fontes com candidatos promoviveis

- `wikidata_P286_team_to_person`: `5` candidatos, `187` match-teams brutos cobertos

## Times com maior cobertura incremental potencial

- `Palmeiras`: `163` match-teams

## Amostra de confirmacao

Esta amostra nao altera criterio por clube; serve apenas para conferir nomes conhecidos contra o mesmo motor geral.
- `Palmeiras` | `Abel Ferreira` | 2020-11-04 ate 2025-12-31 | `promotable_candidate` | lacuna `163`
- `Palmeiras` | `Dorival Júnior` | 2020-01-01 ate 2025-12-31 | `review_needed` | lacuna `163`
- `Palmeiras` | `Mano Menezes` | 2020-01-01 ate 2025-12-31 | `review_needed` | lacuna `163`
- `Palmeiras` | `Roger Machado` | 2020-01-01 ate 2025-12-31 | `review_needed` | lacuna `163`
- `Palmeiras` | `Tite` | 2020-01-01 ate 2025-12-31 | `review_needed` | lacuna `163`
- `Palmeiras` | `Abel Ferreira` | 2020-01-01 ate 2020-12-31 | `low_value_context` | lacuna `0`
- `Palmeiras` | `Vanderlei Luxemburgo` | 2020-01-01 ate 2020-12-31 | `low_value_context` | lacuna `0`
- `Palmeiras` | `Abel Ferreira  ComIH  1` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Abel Picabea` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Abel Picabéa` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Ageu` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Alberto Valentim` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Amílcar Barbuy` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Andrey Lopes` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Antônio Carlos Zago` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Armando Del Debbio` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Armando Renganeschi` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Aymoré Moreira` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Aymoré Moreira` | ? ate ? | `blocked_outside_window` | lacuna `0`
- `Palmeiras` | `Aymoré Moreira` | ? ate ? | `blocked_outside_window` | lacuna `0`
- `Palmeiras` | `Aymoré Moreira` | ? ate ? | `blocked_outside_window` | lacuna `0`
- `Palmeiras` | `Caio Júnior` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Caio Zanardi` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Candinho` | ? ate ? | `blocked_outside_window` | lacuna `0`
- `Palmeiras` | `Carlos Alberto Silva` | ? ate ? | `blocked_outside_window` | lacuna `0`
- `Palmeiras` | `Carlos Castilho` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Chinesinho` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Cleber Xavier` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Conrad Ross` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Diede Lameiro` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Dino Sani` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Diogo Giacomini` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Dorival Júnior` | ? ate ? | `blocked_outside_window` | lacuna `0`
- `Palmeiras` | `Dudu (footballer, born 1939)` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Eduardo Baptista` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Émerson Leão` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Émerson Leão` | ? ate ? | `blocked_outside_window` | lacuna `0`
- `Palmeiras` | `Émerson Leão` | ? ate ? | `blocked_outside_window` | lacuna `0`
- `Palmeiras` | `Ephigênio de Freitas` | ? ate ? | `review_needed` | lacuna `0`
- `Palmeiras` | `Imre Hirschl` | ? ate ? | `review_needed` | lacuna `0`

## Arquivos gerados

- Resumo JSON: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\platform\reports\quality\external_coach_coupling_summary.json`
- Candidatos promoviveis: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\platform\reports\quality\external_coach_coupling_promotable_candidates.csv`
- Conflitos: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\platform\reports\quality\external_coach_coupling_conflicts.csv`
- Cobertura por recorte: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\platform\reports\quality\external_coach_coupling_coverage.csv`

## Leitura operacional

- `promotable` ainda significa promovivel por regra, nao promovido ao produto.
- `review_needed` pode enriquecer historico depois de validacao ou segunda fonte.
- `blocked_conflict` impede publicacao ate escolha manual ou fonte mais forte.
