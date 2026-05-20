# MART Frontend/BFF Contracts

Data de referencia: `2026-03-20`  
Projeto: `football-analytics`

## 0) Fonte de verdade e evidencias

Fonte de verdade usada para este mapeamento:

- modelos finais em `dbt/models/marts/core/*.sql` e `dbt/models/marts/analytics/*.sql`
- qualidade final em `dbt/target/run_results.json` (`dbt test --select marts.core marts.analytics`)
- auditoria final `raw -> mart` em:
  - `artifacts/mart_final_audit_20260320/scope_status_summary.csv`
  - `artifacts/mart_final_audit_20260320/mart_raw_scope_matrix.csv`
- quality gates finais em:
  - `dbt/target/run_results.json`
  - `docs/GUIA_MESTRE_APLICACAO.md`

Evidencia objetiva consolidada:

- `dbt test` escopo `marts.core marts.analytics`: `124 pass`, `0 fail`, `0 error` (`dbt/target/run_results.json`, `generated_at=2026-03-20T18:16:58.497303Z`)
- auditoria final `raw -> mart`:
  - `COMPLETO=32`
  - `PROVIDER_COVERAGE_GAP=18`
  - `PARCIAL=0`
  - `PIPELINE_BUG / INCONSISTENCIA=0`
  - `NAO_INGESTADO=0`
- quality gates finais: `gold_marts_checkpoint=success=True`, `data_quality_checks=success (rows_in=34, rows_out=34)`

Nota de ambiente (incerteza explicitada):

- nao foi possivel consultar o banco em runtime neste ciclo (`dockerDesktopLinuxEngine` indisponivel localmente);
- por isso, o mapeamento usa como fonte de verdade o estado persistido no repositorio (modelos dbt + artefatos finais de validacao).

## 1) Diagnostico e delimitacao de escopo

Separacao do problema:

- codigo/pipeline: sem evidencia de bug residual no fechamento final do `mart` para o escopo auditado.
- dados/provider: lacunas residuais classificadas como `PROVIDER_COVERAGE_GAP`.
- validacao: `dbt test` e quality gates finais verdes.
- ambiente: indisponibilidade local de Docker apenas para verificacao online nesta execucao.

Escopo deste documento:

- mapear consumo frontend/BFF a partir do `mart` atual.
- definir contratos praticos por entidade/pagina/widget.
- explicitar caveats de coverage para UX e BFF.

Fora de escopo:

- rebuild/rematerializacao de pipeline.
- redesenho amplo de frontend.
- refatoracao de modelo dbt.

## 2) Inventario de fontes mart relevantes para consumo

| Fonte mart | Grain | Uso principal para frontend/BFF |
|---|---|---|
| `mart.fact_matches` | 1 linha por partida (`match_id`) | lista/detalhe de partidas, filtros globais, base de varios agregados |
| `mart.fact_match_events` | 1 linha por evento (`event_id`) | timeline de eventos por partida |
| `mart.fact_fixture_lineups` | 1 linha por (`provider`,`fixture`,`team`,`lineup`) com `player_id` valido | aba lineups no detalhe da partida |
| `mart.fact_fixture_player_stats` | 1 linha por (`provider`,`fixture`,`team`,`player`) | aba player stats da partida |
| `mart.player_match_summary` | 1 linha por `fixture_player_stat_id` | lista/perfil de jogador no recorte |
| `mart.player_season_summary` | 1 linha por (`competition_sk`,`season`,`player_id`,`team_id`) | resumo sazonal de jogador |
| `mart.player_90_metrics` | 1 linha por (`competition_sk`,`season`,`player_id`,`team_id`) | rankings/metrics normalizadas por 90 |
| `mart.dim_competition` | 1 linha por competicao (`league_id`) | catalogo de competicoes |
| `mart.dim_team` | 1 linha por time (`team_id`) | lookup de time e joins de nome |
| `mart.dim_player` | 1 linha por jogador (`player_id`) | lookup de jogador e joins de nome |
| `mart.dim_venue` | 1 linha por estadio (`venue_id`) | lookup de venue para match header/list |
| `mart.fact_standings_snapshots` | snapshot por (`provider`,`season_id`,`stage_id`,`round_id`,`team_id`) | tabela/classificacao por rodada |
| `mart.standings_evolution` | por (`competition_sk`,`season`,`team_id`,`round_key`) | evolucao de pontos/posicao |
| `mart.league_summary` | por (`competition_sk`,`season`) | cards executivos por liga/temporada |
| `mart.team_monthly_stats` | por (`season`,`year`,`month`,`team_sk`) | cards/trends de time |
| `mart.head_to_head_summary` | por (`provider`,`league_id`,`pair_team_id`,`pair_opponent_id`) | widget/pagina H2H |
| `mart.coach_performance_summary` | por (`provider`,`coach_tenure_id`) | paginas de tecnicos e widgets |

## 3) Mapa de contratos de consumo (entidades principais)

Legenda de status:

- `PRONTO`: pode ser exposto hoje com normalizacao minima.
- `PRONTO_COM_CAVEAT`: pode ser exposto hoje, mas com tratamento explicito de coverage.
- `PRECISA_BFF`: exige composicao/normalizacao no BFF antes de entregar payload robusto.
- `NAO_RECOMENDADO_DIRETO`: nao expor diretamente para frontend.

### 3.1 Contrato `competition.catalog`

- Objetivo: alimentar lista de competicoes e contexto de navegacao.
- Fontes mart: `dim_competition`.
- Grain: 1 item por competicao.
- Campos essenciais:
  - `league_id`
  - `competition_sk`
  - `league_name`
- Campos opcionais:
  - `country` (hoje preenchido como `null` no modelo)
  - `updated_at`
- Joins/agregacoes no BFF:
  - opcional: anexar `season_count` e `latest_season` via `fact_matches`.
- Caveats:
  - sem caveat relevante de provider para a propria dimensao.
- Status: `PRONTO`.

### 3.2 Contrato `season.catalog_by_competition`

- Objetivo: listar temporadas consumiveis por competicao.
- Fontes mart: `fact_matches`, `league_summary`, `standings_evolution`.
- Grain: 1 item por (`league_id`,`season`).
- Campos essenciais:
  - `league_id`
  - `season`
- Campos opcionais:
  - `first_match_date` (`league_summary.first_match_date`)
  - `last_match_date` (`league_summary.last_match_date`)
  - `total_matches`
  - `total_goals`
  - `avg_goals_per_match`
- Joins/agregacoes no BFF:
  - derivar temporada de `fact_matches` (nao existe `dim_season` ativa em `models/marts/core`).
  - padronizar label (`2024`, `2024_25`, etc.).
- Caveats:
  - metadado rico de temporada (nome oficial, janela) nao esta consolidado em dimensao mart dedicada.
- Status: `PRECISA_BFF`.

### 3.3 Contrato `team.directory`

- Objetivo: lookup de times para filtros, headers e links.
- Fontes mart: `dim_team`.
- Grain: 1 item por `team_id`.
- Campos essenciais:
  - `team_id`
  - `team_sk`
  - `team_name`
- Campos opcionais:
  - `logo_url` (hoje `null` por contrato atual do modelo)
  - `updated_at`
- Joins/agregacoes no BFF:
  - opcional: contexto por temporada via `team_monthly_stats` e `fact_matches`.
- Caveats:
  - atributos ricos de identidade do time (logo, pais, estadio principal) nao estao fechados no mart atual.
- Status: `PRONTO`.

### 3.4 Contrato `player.directory`

- Objetivo: lookup de jogadores para filtros e links.
- Fontes mart: `dim_player`.
- Grain: 1 item por `player_id`.
- Campos essenciais:
  - `player_id`
  - `player_sk`
  - `player_name`
- Campos opcionais:
  - `updated_at`
- Joins/agregacoes no BFF:
  - anexar ultimo contexto de time/posicao via `player_match_summary`.
- Caveats:
  - nacionalidade/perfil biografico nao existe no mart atual.
- Status: `PRONTO`.

### 3.5 Contrato `venue.directory`

- Objetivo: metadados de estadio para lista/detalhe de partidas.
- Fontes mart: `dim_venue`.
- Grain: 1 item por `venue_id`.
- Campos essenciais:
  - `venue_id`
  - `venue_sk`
  - `venue_name`
- Campos opcionais:
  - `venue_city`
  - `venue_country`
  - `updated_at`
- Joins/agregacoes no BFF:
  - join por `venue_id` com `fact_matches`.
- Caveats:
  - `venue_country` pode vir nulo no estado atual.
- Status: `PRONTO`.

### 3.6 Contrato `match.list_and_header`

- Objetivo: lista de fixtures e header do detalhe de partida.
- Fontes mart: `fact_matches`, `dim_competition`, `dim_team`, `dim_venue`.
- Grain: 1 item por `match_id`.
- Campos essenciais:
  - `match_id`
  - `league_id` / `competition_sk`
  - `season`
  - `round_number`
  - `date_day`
  - `home_team_id`, `away_team_id`
  - `home_goals`, `away_goals`, `result`
- Campos opcionais:
  - `home_possession`, `away_possession`
  - `home_shots`, `away_shots`
  - `venue_id` / `venue_name`
- Joins/agregacoes no BFF:
  - joins com dimensoes para nomes.
  - conversao de chaves numericas para ids string do contrato API.
- Caveats:
  - `kickoff_at` com timestamp e `status` de partida nao estao completos no `mart.fact_matches`; hoje o BFF usa `raw.fixtures` para esses campos.
- Status: `PRECISA_BFF`.

### 3.7 Contrato `match.events_timeline`

- Objetivo: aba de eventos do detalhe da partida.
- Fontes mart: `fact_match_events`, `dim_team`, `dim_player`.
- Grain: 1 item por evento (`event_id`).
- Campos essenciais:
  - `event_id`
  - `match_id`
  - `time_elapsed`
  - `event_type`
  - `event_detail`
- Campos opcionais:
  - `time_extra`
  - `team_id`, `player_id`, `assist_player_id`
  - `is_goal`
  - `is_time_elapsed_anomalous`
- Joins/agregacoes no BFF:
  - joins em dimensoes para `team_name` e `player_name`.
  - ordenacao cronologica (`time_elapsed`, `event_id`).
- Caveats:
  - herda `PROVIDER_COVERAGE_GAP` em escopos especificos (gap agregado de eventos = `8` fixtures no portfolio auditado).
- Status: `PRONTO_COM_CAVEAT`.

### 3.8 Contrato `match.lineups`

- Objetivo: aba de lineups/titulares/reservas.
- Fontes mart: `fact_fixture_lineups`, `dim_team`, `dim_player`.
- Grain: 1 item por (`fixture_lineup_id`).
- Campos essenciais:
  - `fixture_lineup_id`
  - `match_id`
  - `team_id`
  - `player_id`
- Campos opcionais:
  - `player_name`
  - `position_name`
  - `jersey_number`
  - `is_starter`
  - `formation_field`
  - `formation_position`
  - `minutes_played`
- Joins/agregacoes no BFF:
  - agrupar por time e ordenar titulares/reservas.
- Caveats:
  - maior gap residual de provider no portfolio (`91` fixtures faltantes no agregado auditado).
  - por contrato do fato, registros com `player_id` nulo nao entram no mart; frontend precisa estado de indisponibilidade parcial.
- Status: `PRONTO_COM_CAVEAT`.

### 3.9 Contrato `match.player_stats`

- Objetivo: aba de estatisticas individuais por partida.
- Fontes mart: `fact_fixture_player_stats`, `player_match_summary`, `dim_team`, `dim_player`.
- Grain: 1 item por `fixture_player_stat_id`.
- Campos essenciais:
  - `fixture_player_stat_id`
  - `match_id`
  - `team_id`
  - `player_id`
  - `minutes_played`
  - `goals`
  - `assists`
- Campos opcionais:
  - `shots_total`, `shots_on_goal`
  - `passes_total`, `key_passes`
  - `tackles`, `interceptions`, `duels`
  - `yellow_cards`, `red_cards`
  - `goalkeeper_saves`, `clean_sheets`
  - `xg`, `rating`, `position_name`, `is_starter`
- Joins/agregacoes no BFF:
  - joins de nomes com dimensoes.
  - normalizacao de numeros para payload frontend.
- Caveats:
  - `PROVIDER_COVERAGE_GAP` residual (gap agregado de player stats = `48` fixtures).
  - `passes_completed`/`pass_accuracy_pct` nao estao materializados no mart consumido hoje.
- Status: `PRONTO_COM_CAVEAT`.

### 3.10 Contrato `standings.current_and_evolution`

- Objetivo: tabela/classificacao e evolucao por rodada.
- Fontes mart: `fact_standings_snapshots`, `standings_evolution`, `dim_team`, `dim_round`, `dim_stage`.
- Grain:
  - snapshot: 1 item por (`provider`,`season_id`,`stage_id`,`round_id`,`team_id`)
  - evolucao: 1 item por (`competition_sk`,`season`,`team_id`,`round_key`)
- Campos essenciais:
  - `competition_sk`/`league_id`
  - `season` ou `season_id`
  - `team_id`
  - `position`
  - `points`
  - `goals_for`, `goals_against`, `goal_diff`
  - `round_key` (evolucao)
- Campos opcionais:
  - `won`, `draw`, `lost`
  - `round_label`
  - `points_accumulated`, `goal_diff_accumulated`
- Joins/agregacoes no BFF:
  - join com `dim_team` para nome.
  - selecao da rodada atual (`max(round_key)` por recorte).
- Caveats:
  - `position` validado ate `80`; frontend nao pode assumir maximo fixo de 20/30.
- Status: `PRONTO`.

### 3.11 Contrato `analytics.cards_and_rankings`

- Objetivo: cards e widgets analiticos de home/competicao/temporada.
- Fontes mart:
  - `league_summary`
  - `team_monthly_stats`
  - `player_season_summary`
  - `player_90_metrics`
  - `head_to_head_summary`
  - `coach_performance_summary`
- Grain: varia por modelo (liga-temporada, time-mes, jogador-temporada, par de times, tenure).
- Campos essenciais por subdominio:
  - liga: `competition_sk`, `season`, `total_matches`, `total_goals`, `avg_goals_per_match`
  - time mes: `season`,`year`,`month`,`team_id`,`matches`,`points`,`goal_diff`
  - jogador temporada: `player_id`,`team_id`,`matches`,`minutes_played`,`goals`,`assists`,`avg_rating`
  - jogador por 90: `goals_per_90`,`assists_per_90`,`xg_per_90`
  - h2h: `pair_team_id`,`pair_opponent_id`,`total_matches`,`pair_team_wins`,`draws`
  - tecnico: `coach_id`,`team_id`,`matches`,`wins`,`draws`,`losses`,`points_per_match`
- Campos opcionais:
  - `updated_at`, nomes enriquecidos, filtros extras.
- Joins/agregacoes no BFF:
  - composicao de widgets com multiplas fontes.
  - normalizacao de ids e labels.
- Caveats:
  - `player-pass-accuracy` segue sem materializacao direta no mart atual (na API atual ja retorna `unsupported` para esse ranking).
  - rankings de time por posse/passe exigem agregacao no BFF; um deles hoje usa `raw.match_statistics`.
- Status:
  - `PRONTO`: `league_summary`, `standings_evolution`, `player_season_summary`, `player_90_metrics`, `head_to_head_summary`, `coach_performance_summary`
  - `PRECISA_BFF`: ranking de posse/passe e widgets compostos multi-fonte
  - `NAO_RECOMENDADO_DIRETO`: expor JSON bruto (`statistics`, `details`, `payload`) ao frontend

## 4) Caveats de coverage para frontend (explicitos)

Distribuicao final da auditoria por escopo:

- `COMPLETO=32`
- `PROVIDER_COVERAGE_GAP=18`
- `PARCIAL=0`
- `PIPELINE_BUG / INCONSISTENCIA=0`
- `NAO_INGESTADO=0`

Competicoes com gap residual relevante:

| competition_key | gap_events | gap_lineups | gap_player_stats |
|---|---:|---:|---:|
| brasileirao_a | 4 | 1 | 1 |
| brasileirao_b | 0 | 7 | 7 |
| bundesliga | 1 | 1 | 1 |
| champions_league | 2 | 23 | 2 |
| copa_do_brasil | 0 | 36 | 36 |
| libertadores | 1 | 23 | 1 |

Estados que o frontend deve tratar explicitamente:

- `indisponivel`: quando o contrato da secao retorna lista vazia para o recorte.
- `parcial`: quando `meta.coverage.status=partial`.
- `coverage do provider`: quando a secao afetada for eventos/lineups/player stats em escopos com gap conhecido.
- `nao suportado no escopo`: metrica/feature nao materializada (ex.: `player-pass-accuracy`, insights ainda sem dado).

## 5) Matriz pagina/widget -> fontes do mart

| Pagina/Widget | Fontes mart principais | Join/adaptacao BFF | Status |
|---|---|---|---|
| Home / dashboard geral | `league_summary`, `standings_evolution`, `player_90_metrics`, `team_monthly_stats` | compor cards + highlights + ordenacoes | `PRECISA_BFF` |
| Lista de competicoes | `dim_competition` | opcional: contar temporadas via `fact_matches` | `PRONTO` |
| Pagina da competicao | `dim_competition`, `league_summary`, `fact_matches` | consolidar blocos (resumo, temporadas, atalhos) | `PRECISA_BFF` |
| Pagina da temporada | `fact_matches`, `league_summary`, `standings_evolution`, `team_monthly_stats` | derivar temporada e montar hub | `PRECISA_BFF` |
| Tabela / classificacao | `fact_standings_snapshots`, `standings_evolution`, `dim_team` | selecionar rodada e enriquecer nomes | `PRONTO` |
| Lista de partidas / fixtures | `fact_matches`, `dim_team`, `dim_competition`, `dim_venue` | normalizar payload de listagem (ids, nomes, filtros) | `PRECISA_BFF` |
| Detalhe de partida (header) | `fact_matches`, `dim_team`, `dim_competition`, `dim_venue` | montar header unico + contexto de competicao/rodada | `PRECISA_BFF` |
| Aba de eventos | `fact_match_events`, `dim_team`, `dim_player` | ordenar timeline + nomes | `PRONTO_COM_CAVEAT` |
| Aba de lineups | `fact_fixture_lineups`, `dim_team`, `dim_player` | agrupar titulares/reservas por time | `PRONTO_COM_CAVEAT` |
| Aba de estatisticas de jogadores | `fact_fixture_player_stats`, `player_match_summary`, `dim_team`, `dim_player` | normalizar colunas de tabela e tipos numericos | `PRONTO_COM_CAVEAT` |
| Paginas de time | `dim_team`, `team_monthly_stats`, `fact_matches`, `standings_evolution` | composicao por temporada e forma recente; BFF minimo ja aberto com `/teams/{teamId}` e `/teams/{teamId}/contexts` | `PRECISA_BFF` |
| Paginas de jogador | `dim_player`, `player_match_summary`, `player_season_summary`, `player_90_metrics` | resumo + historico + ultimos jogos | `PRONTO_COM_CAVEAT` |
| Comparativos / widgets analiticos | `head_to_head_summary`, `coach_performance_summary`, `player_90_metrics`, `team_monthly_stats` | composicao multi-fonte e normalizacao de ranking | `PRECISA_BFF` |
| Filtros globais (competicao/temporada/time/jogador) | `dim_competition`, `fact_matches`, `dim_team`, `dim_player` | dicionarios de filtro + validacao de combinacao | `PRONTO` |
| Ranking `player-pass-accuracy` | (nao materializado no mart atual) | exigiria camada adicional ou redefinicao de metrica | `NAO_RECOMENDADO_DIRETO` |

## 6) Contratos prioritarios para implementacao

### Lote 1 - implementar agora com seguranca

- `competition.catalog`
- `team.directory`, `player.directory`, `venue.directory`
- `match.list_and_header` (sem depender de campos nao materializados)
- `match.events_timeline` + banner de coverage
- `match.lineups` + banner de coverage
- `match.player_stats` + banner de coverage
- `standings.current_and_evolution`
- `player.profile` (resumo + ultimos jogos) baseado em `player_match_summary`/`player_season_summary`

Motivo: dados e regras ja consolidados no mart com caveat conhecido de provider.

### Lote 2 - depende de adaptacao pequena no BFF

- `season.catalog_by_competition` (derivacao de temporada sem `dim_season`)
- pagina de competicao e pagina de temporada (hub composto)
- paginas de time (resumo por periodo + forma recente)
- widgets executivos de home cross-modulo
- `head_to_head` e `coaches` como endpoints dedicados consumindo marts analiticas

Motivo: requer composicao multi-modelo e padronizacao de payload.

### Lote 3 - aguardar refinamento adicional

- rankings dependentes de metrica nao materializada (`player-pass-accuracy`)
- qualquer contrato que exponha diretamente JSON tecnico (`payload`, `statistics`, `details`)
- insights (`/api/v1/insights`) enquanto permanecer retornando vazio com coverage `unknown`

Motivo: risco de contrato instavel ou sem sustentacao mart direta no estado atual.

## 7) Diretrizes objetivas de consumo

Consumir diretamente do mart via BFF (normalizacao minima):

- catalogos/dimensoes (`dim_competition`, `dim_team`, `dim_player`, `dim_venue`)
- fatos centrais (`fact_matches`, `fact_match_events`, `fact_fixture_lineups`, `fact_fixture_player_stats`)
- analiticos consolidados (`league_summary`, `standings_evolution`, `player_season_summary`, `player_90_metrics`, `head_to_head_summary`, `coach_performance_summary`)

Onde o BFF deve normalizar payload obrigatoriamente:

- joins de nome (`*_id` -> `*_name`) para contratos de tela.
- unificacao de tipos (`int/bigint/numeric` -> payload frontend consistente).
- composicao de secoes no detalhe da partida.
- derivacao de temporada por competicao.
- paginacao, ordenacao e `meta.coverage`.

Onde o frontend deve tratar coverage gap explicitamente:

- detalhe de partida: eventos, lineups, player stats.
- paginas de jogador/rankings quando metrica depende de `fixture_player_stats`.
- qualquer modulo com `meta.coverage.status in ('partial','empty','unknown')`.

## 8) Conflitos explicitados (manual antigo vs mart atual)

Conflitos identificados e resolucao:

1. O material historico antigo do frontend tratava `raw` como camada factual mais robusta e `mart` em consolidacao.  
   Resolucao: para consumo frontend/BFF neste estado validado, `mart` passa a ser camada principal; `raw` vira apoio pontual e nao camada primaria de contrato.

2. `docs/BFF_API_CONTRACT.md` e registry frontend incluem `player-pass-accuracy` como ranking esperado.  
   Resolucao: no estado atual, metrica nao esta materializada para ranking confiavel; classificar como `NAO_RECOMENDADO_DIRETO` ate adaptacao adicional.

3. Blueprint de rotas antigo (`/competitions`, `/teams`, `/h2h`) diverge da arvore atual implementada (`/competition/[id]`, `/clubs`, `/head-to-head`).  
   Resolucao: contratos devem ser orientados por dados do mart e endpoints BFF; ajuste de IA/rotas fica em lote de adaptacao frontend, sem bloquear consumo de dados.

## 9) Proximo passo seguro

Executar um bloco curto de implementacao BFF em cima deste mapeamento:

1. fechar contratos `competition`, `season`, `team`, `standings`, `match center sections`.
2. padronizar `meta.coverage` por secao de partida.
3. marcar explicitamente modulos `unsupported` (`player-pass-accuracy`, insights sem dado).
