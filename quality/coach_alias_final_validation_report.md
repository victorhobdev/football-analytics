# Coach alias final validation

## Escopo

- Janela publica validada: `2020-01-01` a `2025-12-31`.
- Identidades antigas foram preservadas em `mart.coach_identity`.
- A unificacao operacional acontece via `mart.coach_identity_alias`, `mart.team_identity_alias` e `mart.v_coach_identity_resolution`.

## Aliases aplicados

- `Tite` <= `Adenor Bacchi` (`sportmonks:474720`).
- `Rafael Paiva` <= `Cledson Rafael de Paiva` (`sportmonks:37690429`).
- `Abel Moreira Ferreira` <= `Abel Ferreira` (`wikidata:Q318415`).
- `Palmeiras` <= `Sociedade Esportiva Palmeiras` (`wikidata:Q80964`).
- `Palmeiras` <= `SE Palmeiras`.

## Resultado da execucao

- A primeira aplicacao dos aliases moveu `75` atribuicoes publicas que ainda apontavam para identidades alias.
- `rows_on_alias_identity`: `75` antes da aplicacao inicial; `0` depois.
- A promocao pos-alias inseriu `163` atribuicoes adicionais para Palmeiras/Abel.
- Nenhuma nova identidade foi criada para Abel; o Wikidata `Q318415` foi acoplado a `coach_identity_id = 17`.

## Cobertura global final

- Identidades totais em `mart.coach_identity`: `2.103`.
- Tecnicos distintos com jogos publicos atribuidos: `810`.
- Atribuicoes publicas de tecnico-time-jogo: `19.267`.
- Match-teams no recorte: `32.522`.
- Cobertura publica final: `59,24%`.
- Aliases ativos de tecnico: `4`.
- Aliases ativos de clube: `4`.

## Gates finais

- Atribuicoes fora da janela: `0`.
- Duplicatas por `match_id + team_id`: `0`.
- Nomes invalidos em atribuicoes publicas: `0`.
- Atribuicoes ainda apontando para identidade alias: `0`.

## Conferencia por clube

| Clube | Total match-teams | Atribuidos | Faltantes |
|---|---:|---:|---:|
| Flamengo | 290 | 247 | 43 |
| Palmeiras | 268 | 268 | 0 |
| Vasco da Gama | 229 | 130 | 99 |

## Conferencia manual resumida

### Flamengo

- `Tite` agora concentra as atribuicoes antes divididas entre `Tite` e `Adenor Bacchi`.
- Ainda faltam `43` jogos-time, concentrados principalmente em 2021 e em lacunas ja identificadas.
- `Vitor Pereira` segue subcoberto com apenas `1` jogo.
- `Bruno Pivetti` em `2025-12-06` continua suspeito e deve ir para revisao manual.

### Palmeiras

- `Abel Moreira Ferreira` agora cobre `268/268` jogos-time do Palmeiras no recorte local.
- Fonte externa `wikidata_P286_team_to_person`: `163` jogos de `2021-04-22` a `2023-12-07`.
- Fonte SportMonks: `105` jogos de `2024-04-04` a `2025-12-07`.
- O alias de clube `Sociedade Esportiva Palmeiras -> Palmeiras` resolveu o falso negativo que bloqueava a promocao.

### Vasco da Gama

- `Rafael Paiva` agora concentra as atribuicoes antes divididas entre `Rafael Paiva` e `Cledson Rafael de Paiva`.
- Cobertura permanece parcial: `130/229`.
- 2021 e 2022 seguem sem cobertura suficiente.
- Sobreposicoes em 2025 entre `Felipe`, `Fernando Diniz` e `Fabio Carille` continuam exigindo revisao de fonte/criterio.

## Risco residual

- A pagina publica ainda precisa consumir diretamente `mart.fact_coach_match_assignment` ou uma view derivada dela para refletir integralmente a cobertura nova.
- A camada de alias esta pronta para novos casos, mas so os aliases verificados nesta execucao foram promovidos como `active`.
