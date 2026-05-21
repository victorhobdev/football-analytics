# Plano de ingestao SportMonks para confiabilidade do produto

## Decisao de produto

A SportMonks deve ser usada como fonte transacional principal quando entrega o grao correto.

Para tecnicos, o grao correto e `fixture + team + coach`. O endpoint de fixture com include `coaches` e o unico caminho pesquisado que pode alimentar `fact_coach_match_assignment` com confianca operacional.

Para transferencias, o grao correto e `transfer_event`. A API cobre bem evento confirmado, origem, destino, jogador, data, tipo e valor bruto. Ela nao resolve sozinha moeda, fonte editorial, season local nem semantica de base/youth.

## Estado atual confirmado

Auditoria local em `quality/coach_assignment_audit_summary.md`:

- `34.322` match-team publicos auditados;
- `7.494` com tecnico atribuivel hoje;
- `26.828` sem tecnico atribuivel;
- `854` com conflito de multiplos elegiveis;
- `288` riscos de assistant competindo com principal.

Conclusao: o produto ainda nao deve tratar rankings de tecnico como confiaveis fora das areas que passarem pelo novo fluxo de atribuicao por partida.

## Capacidades aproveitaveis da SportMonks

### Tecnicos

Usar:

- `GET /v3/football/fixtures/{id}?include=coaches;participants;state`
- `GET /v3/football/fixtures/between/{start}/{end}/{team_id}?include=coaches;participants;state`
- `GET /v3/football/coaches/{id}`
- `GET /v3/football/coaches/search/{query}`
- `GET /v3/football/coaches/latest`

Nao usar como fonte primaria de historico:

- `teams/{team_id}?include=coaches`, porque a relacao documentada e staff atual;
- `participants.coaches`, ate prova empirica de que representa tecnico da partida;
- `lineups`, porque e player-only no estado atual e na documentacao pesquisada.

Gravacao esperada:

- `mart.stg_coach_identity_candidates`: identidade do coach;
- `mart.stg_coach_lineup_assignments`: tecnico observado no fixture;
- `mart.coach_identity`: identidade canonica;
- `mart.fact_coach_match_assignment`: tecnico principal publico por `match_id + team_id`;
- `mart.coach_tenure`: apenas derivado ou enriquecido, nunca fonte primaria de desempenho.

### Transferencias

Usar:

- `GET /v3/football/transfers/{id}`
- `GET /v3/football/transfers/latest`
- `GET /v3/football/transfers/between/{startDate}/{endDate}`
- `GET /v3/football/transfers/teams/{id}`
- `GET /v3/football/transfers/players/{id}`

Includes:

- `type`
- `fromTeam`
- `toTeam`
- `player`
- `position`
- `detailedPosition`

Gravacao esperada:

- `raw.player_transfers`: payload bruto e campos operacionais atuais;
- `mart.stg_player_transfers`: camada consumida hoje pela rota `/api/v1/market/transfers`;
- futura tabela canonica `mart.player_transfer_event`, se o produto precisar separar evento confirmado, enriquecimento de moeda e season local.

Campos nao confiaveis pela API sozinha:

- `fee_currency`;
- `season_id`;
- `source_name` / `source_url`;
- semantica editorial de taxa;
- movimentos de base/youth.

## Ordem de execucao

### Bloco 1 - Probes reais de payload

Objetivo: provar se o plano Pro/historico liberado entrega o payload necessario no nosso recorte publico.

Escopo minimo:

- Flamengo 2021;
- Flamengo 2022;
- Flamengo 2024;
- Everton Ribeiro transfer history;
- janela mensal de transferencias em dezembro de 2023.

Saida obrigatoria:

- tabela ou JSON de probes;
- amostra de payload bruto;
- cardinalidade `fixture + team -> coaches`;
- presenca de link coach/time;
- taxa de fixtures finalizados com coach utilizavel.

Gate:

- tecnicos automatizados se `fixtures.coaches` cobrir pelo menos 95% das partidas finalizadas do recorte amostrado e trouxer vinculo claro com time;
- caso contrario, SportMonks entra como identidade/enriquecimento e o assignment canonico continua exigindo fallback manual.

### Bloco 2 - Raw/staging SportMonks

Objetivo: persistir payload bruto antes de promover qualquer dado.

Tabelas novas recomendadas:

```text
raw.sportmonks_fixture_coaches
raw.sportmonks_coaches
raw.sportmonks_transfer_events
mart.stg_sportmonks_fixture_coach_assignments
mart.stg_sportmonks_transfer_events
```

Chaves naturais:

```text
raw.sportmonks_fixture_coaches: provider + fixture_id + team_id + coach_id
raw.sportmonks_coaches: provider + coach_id
raw.sportmonks_transfer_events: provider + transfer_id
mart.stg_sportmonks_fixture_coach_assignments: fixture_id + team_id + coach_id + source_run_id
mart.stg_sportmonks_transfer_events: provider + transfer_id
```

Regras:

- payload bruto sempre preservado;
- `ingested_run` obrigatorio;
- nenhum dado com `starting_at` ou `transfer_date` posterior a `PRODUCT_DATA_CUTOFF` fica elegivel para UI publica;
- registros sem link local de time/jogador ficam em staging, nao em fato final.

### Bloco 3 - Crosswalk local

Objetivo: resolver IDs SportMonks para IDs locais sem heuristica solta na rota.

Mapas necessarios:

```text
sportmonks_fixture_id -> mart.fact_matches.match_id
sportmonks_team_id -> mart.dim_team.team_id
sportmonks_coach_id -> mart.coach_identity.coach_identity_id
sportmonks_player_id -> mart.dim_player.player_id
```

Gates:

- `fixture_id` sem match local bloqueia assignment;
- `team_id` sem time local bloqueia assignment e transferencia publica;
- `coach_id` sem nome valido bloqueia ranking;
- `player_id` sem jogador local bloqueia transferencia publica.

### Bloco 4 - Materializar tecnico por partida

Promocao:

```text
raw.sportmonks_fixture_coaches
-> mart.stg_coach_identity_candidates
-> mart.coach_identity
-> mart.stg_coach_lineup_assignments
-> mart.fact_coach_match_assignment
```

Regras de publicacao:

- exatamente um tecnico principal por `match_id + team_id`;
- `assignment_method = 'lineup_source'` quando vem do include direto `fixtures.coaches`;
- `assignment_confidence >= 0.95` quando ha vinculo explicito coach/time e nome valido;
- conflito fica com `assignment_method = 'blocked_conflict'`, `is_public_eligible = false`;
- `coach_tenure` derivado de primeira/ultima partida recebe `is_date_estimated = true`.

Ordem de backfill:

1. Flamengo 2021, 2022, 2024;
2. Flamengo 2020-2025 completo;
3. Brasileirao A 2020-2025;
4. Copa do Mundo;
5. competicoes internacionais ja visiveis;
6. demais competicoes publicas com maior lacuna no audit.

### Bloco 5 - Endurecer transferencias

Promocao:

```text
raw.sportmonks_transfer_events
-> mart.stg_player_transfers
-> mart.player_transfer_event
```

Regras:

- `transfer_id` SportMonks e a chave idempotente;
- `type_id = 218` vira emprestimo;
- `type_id = 9688` vira retorno de emprestimo;
- `type_id = 219` vira transferencia definitiva;
- `type_id = 220` vira transferencia livre;
- `fee_currency = null` ate fonte confiavel;
- `season_id` deriva de calendario local e deve carregar `season_resolution_method`;
- API publica nao deve assumir `EUR` quando a moeda nao veio do provider.

Observacao importante: `api/src/routers/market.py` ja foi corrigido para retornar `currency = null` quando a moeda nao vem de fonte confiavel. Qualquer moeda futura precisa vir de enriquecimento explicito.

### Bloco 6 - Gates antes da UI

Tecnicos:

- 100% dos coaches publicos com nome valido;
- 0 assignments publicos duplicados por `match_id + team_id`;
- 0 assistants publicados como principal quando existe principal observado;
- cobertura por competicao/temporada/time exibida no BFF;
- rankings usam apenas `fact_coach_match_assignment.is_public_eligible = true`.

Transferencias:

- 100% dos eventos publicos com `transfer_id`, `player_id`, `date`, `type_id`;
- `from_team_id` ou `to_team_id` resolvido para time local quando o evento aparece em filtro de clube;
- `fee_currency` nao inventada;
- `season_id` marcado como derivado;
- eventos depois de `PRODUCT_DATA_CUTOFF` fora da UI publica.

## Entregas tecnicas imediatas

1. Criar script de probe SportMonks para Flamengo e Everton Ribeiro.
2. Criar DDL raw/staging SportMonks com chaves idempotentes.
3. Rodar probe e gerar `quality/sportmonks_probe_report.md`.
4. Implementar backfill piloto de `fact_coach_match_assignment` para Flamengo 2021-2022.
5. Trocar a rota de tecnicos para consumir assignments publicos apenas no recorte piloto.
6. Corrigir a moeda em transferencias para nao inferir `EUR` sem fonte.

## Criterio de sucesso

O produto fica mais confiavel quando a UI deixa de apresentar estimativa temporal como verdade estatistica.

Para tecnicos, isso significa desempenho calculado por `fact_coach_match_assignment`.

Para mercado, isso significa transferencia confirmada por evento idempotente, com moeda e season marcadas como ausentes/derivadas quando a API nao entrega o campo.
