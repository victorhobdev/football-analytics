# Auditoria de cutover da normalização multifonte — 2026-07-16

**Estado final:** `CUTOVER_CONCLUIDO_COM_ROLLBACK_RETIDO`

O cadastro canônico, o crosswalk, as decisões de publicação e 103 objetos do mart foram promovidos em produção. O schema `mart_rollback_20260716` permanece preservado. Nenhuma tabela de fatos da camada `raw` foi reescrita e nenhum objeto de Power BI foi alterado.

## 1. Resultado executivo

| gate | antes | depois | resultado |
|---|---:|---:|---|
| `mart.dim_team` | 3.060 | **1.930** | verde |
| `mart.fact_matches` | 259.872 | **248.853** | verde |
| `control.team_identity` | 3.060 | **1.930** | verde |
| source teams aprovados e ativos | 13 | **6.140** | verde |
| source teams legados aposentados | 0 | **13** | preservados, inativos |
| `pending + publishable` | 240.993 | **0** | verde |
| `home_team_id = away_team_id` | 0 | **0** | verde |
| partidas com time órfão | 0 | **0** | verde |
| fatos com IDs Flamengo aposentados | aplicável | **0** | verde |

Hashes de conteúdo pós-cutover:

- `dim_team`: `d01e23cd2427a5fcb78a549b1d9f3412`;
- `fact_matches`: `c385ce298b5cccf77002e2a7d1fd570a`;
- crosswalk ativo, ordenado canonicamente: SHA-256 `470530eb1343e1bf5ce9abd4e5c589bfd2dd0e2f3345b54f96bcb9f4563bab8e`.

Os hashes de `dim_team` e `fact_matches` são iguais no PostgreSQL local e em produção. As 6.140 linhas do crosswalk também são exatamente iguais nos dois ambientes; o MD5 nativo do `string_agg` divergia apenas pela collation de ordenação, por isso a comparação final usou ordenação canônica fora do banco.

## 2. Autoridade, backup e baseline

- Commit observado localmente: `0ccfede84a9627f20ad0f6e28859c83428e980dd`.
- Produção: `144.22.218.77`, projeto `/home/ubuntu/football-analytics`.
- Backup completo pré-normalização: `/home/ubuntu/football-analytics/.deploy-backups/full-pre-normalization-20260716T123718Z-z1.dump`.
- Tamanho: aproximadamente 5,0 GB.
- SHA-256: `d1e3e8d9cd6db2a9d0f1d876e69963287ca9b7c19be07b9eac1902c954ef8081`.
- TOC: 1.278 linhas / 1.267 entradas, PostgreSQL 16.14 custom archive.
- O teste de restauração integral foi interrompido por decisão explícita do usuário após reconstruir 13 GB de um banco de aproximadamente 40 GB. O dump e o TOC foram preservados; não se declara restore integral testado.

Watermarks finais permaneceram iguais ao baseline, logo não existia delta para reaplicar:

| objeto | watermark UTC |
|---|---|
| `raw.fixtures` | `2026-04-11 06:11:51.861596+00` |
| `raw.brasileirao_matches` | `2026-06-20 14:29:11.032211+00` |
| `raw.elo_matches` | `2026-06-20 14:29:14.824732+00` |
| `raw.tm_games` | `2026-06-20 14:31:39.304364+00` |
| `raw.statsbomb_matches` | `2026-06-19 21:41:41.808957+00` |

Não havia Airflow, scheduler ou writer de ingestão em execução na VM. API e frontend eram somente leitores durante o swap.

## 3. Decisões e manifestos

- 3.061 linhas do manifesto de clubes: todas `approved`.
- 1.930 clubes canônicos ativos.
- 5.884 chaves-base aprovadas no manifesto.
- 256 aliases operacionais adicionais projetados de lados de partidas aprovadas.
- 6.140 chaves aprovadas e ativas no crosswalk final.
- 43 decisões negativas preservadas.
- 240.993 decisões de publicação com `approval_basis='user_approved_2026-07-16'`.
- 53 candidatos com diferença de data ficaram `separate_approved`; nenhum foi fundido automaticamente.
- 28 partidas StatsBomb ambíguas permanecem em quarentena, sem publicação inventada.
- 12 identidades de time StatsBomb continuam `unresolved`, sem fato canônico órfão.

Não resta decisão humana indispensável para o cutover executado. Casos ambíguos e não resolvidos permanecem explicitamente fora da cobertura publicada.

## 4. Canários de identidade

- Flamengo: um único canônico `3000000000284`, `Clube de Regatas do Flamengo`.
- As oito chaves ativas observadas para Flamengo (legado, SportMonks, Brasileirão, Elo e Transfermarkt) apontam para `3000000000284`.
- Belenenses: `3000000000000`.
- B SAD: `3000000000001`.
- CRB: origens legadas `6188` e `275822` permanecem unificadas no canônico aprovado.
- Nenhum dos quatro IDs Flamengo legados aparece nos fatos promovidos.
- A busca produtiva por `Flamengo` retorna exatamente um item do tipo `team`.

Treze mapas StatsBomb preexistentes usavam chaves não contextuais e IDs legados. Eles não foram apagados: foram marcados `retired`/inativos. O loader foi corrigido para ler somente mappings `approved` e ativos, eliminando a seleção não determinística em ingestões futuras.

## 5. Partidas e fatos filhos

| objeto promovido | linhas |
|---|---:|
| `fact_matches` | 248.853 |
| `fact_match_events` | 13.520.851 |
| `fact_fixture_lineups` | 747.908 |
| `fact_fixture_player_stats` | 607.187 |
| `fact_elo_match_team_stats` | 428.530 |
| `fact_transfermarkt_match_events` | 128.901 |
| `fact_match_odds` | 211.911 |
| `fact_transfermarkt_appearances` | 250.768 |
| `fact_transfermarkt_lineups` | 323.078 |

O gate completo verificou zero evento cujo `team_id` não fosse um dos lados da partida. Não há órfãos de time, `home=away`, IDs aposentados ou bridge StatsBomb aprovado apontando para time inexistente. Bridges StatsBomb com `local_match_id` resolvido têm zero órfão em `fact_matches`.

## 6. Migrations e crosswalk

Migrations aplicadas transacionalmente e registradas em `public.schema_migrations`:

- `20260716130000_provider_entity_contextual_keys`;
- `20260716140000_match_review_approved_state`;
- `20260716141000_seed_configured_season_catalog`.

`raw.provider_entity_map` continua sendo o único crosswalk autoritativo. `mart.team_identity_alias` não decide identidade. A camada raw de fatos não foi alterada; apenas o mapa operacional de entidades recebeu mappings aprovados e aposentadorias auditáveis.

## 7. Rebuild sombra e cutover

Artefatos finais na VM:

- identidade/partidas: `normalization_shadow_20260716.dump`, SHA-256 `2bb102e88390962bcf94a7204f57402371918316e48e57deac9584a801c79caf`;
- serving final usado: `normalization_serving_20260716_v3.dump`, SHA-256 `198ae4214f99c5601c191c5ba4c5cbc5c99ac099c96ac9e41af0bb132c2df981`;
- release de scripts inicial v3: SHA-256 `6a8d81cae3d8ba7d48440fbd7afa93b18db615bb0649c7869420e4eebf146ddf`.

O primeiro ensaio de cutover em produção abortou integralmente por `lock_timeout`: uma sessão dbt interrompida ainda mantinha lock de leitura. A sessão foi terminada e o segundo swap concluiu em uma transação:

- 103 objetos promovidos;
- 82 objetos anteriores movidos para `mart_rollback_20260716`;
- 21 objetos novos;
- 31 objetos operacionais não-dbt do mart foram preservados no lugar.

O active `mart.stg_matches` é o próprio objeto promovido: OID atual `1972620`, OID registrado no manifesto de cutover `1972620`, hash da view `319444715ec07f88f1741c17c1380340`. O gate de OID retornou zero divergência.

## 8. Testes

### Python

- suíte recomendada do repositório, sem integração: **90 passed**;
- identidade/normalização: **11 passed**;
- rota de partidas após otimização: **4 passed**.

### dbt local

- 103 modelos materializados;
- execução corrigida do grafo: 102/103 e rerun isolado verde do único modelo corrigido;
- testes completos: 371 passes, um teste de unicidade interrompido por `/dev/shm`;
- rerun serial do teste interrompido: **pass**;
- parity pré-cutover falhava deliberadamente porque o mart ativo ainda era legado.

### dbt produção

- suíte ampla: 165 testes consecutivos passaram; interrompida por custo excessivo dos `not_null` StatsBomb, sem teste vermelho;
- seleção bloqueante: 6/7 passaram (`pending`, publicação externa, season config, goal team, resultado e total de gols);
- o sétimo teste (`test_statsbomb_linked_team_uses_local_id`) foi interrompido após mais de 13 minutos por expandir `stg_matches` completo;
- substituição SQL direta do gate StatsBomb: zero bridge de time aprovado órfão e zero bridge de partida resolvido órfão.

Não há teste crítico vermelho. A limitação residual é tempo de execução de testes genéricos sobre views que expandem dezenas de milhões de linhas.

## 9. Validação funcional

Somente a API foi reconstruída/reiniciada. Frontend, Caddy e PostgreSQL permaneceram ativos.

| superfície | resultado | tempo observado |
|---|---:|---:|
| `/` | 200 | 0,50 s |
| `/bff/health` | 200 | 0,97–3,72 s |
| `/bff/api/v1/home` | 200 | 20–26 s em cache frio |
| `/bff/api/v1/matches?page=1&pageSize=1` | 200 | 16–40 s |
| `/bff/api/v1/players?limit=1` | 200 | 2–4 s |
| `/bff/api/v1/market/transfers?limit=1` | 200 | 12–15 s |
| `/bff/api/v1/teams?page=1&pageSize=1` | 200 | 6,6 s |
| `/bff/api/v1/competition-editions?competitionKey=brasileirao_a` | 200 | 4,2 s |
| `/bff/api/v1/search?q=Flamengo` | 200 | 4,2 s |
| perfil Flamengo com contexto 2025 | 200 | 2,1 s |

A rota de partidas era 500 antes da normalização por ausência de `mart.match_depth_profile`. Após o cutover passou a 200, mas inicialmente excedia 90 s. A API foi corrigida para executar a contagem total separadamente em vez de `count(*) over()` sobre todo o enriquecimento. O tempo caiu para 16–40 s. Continua sendo o principal risco de performance, mas não é regressão funcional contra o baseline 500.

## 10. Rollback exato

Enquanto nenhum writer de ingestão for retomado, o rollback do mart é:

```bash
cd /home/ubuntu/football-analytics
docker compose --env-file deploy/oci/.env -f deploy/oci/compose.yml exec -T postgres \
  psql -U football -d football_dw -v ON_ERROR_STOP=1 -f /dev/stdin \
  < .releases/normalization-20260716/v3/platform/scripts/rollback_canonical_mart.sql
docker compose --env-file deploy/oci/.env -f deploy/oci/compose.yml restart api
```

O rollback foi ensaiado localmente: voltou de 1.930/248.853 para 3.060/259.872 e restaurou os OIDs antigos. O schema produtivo `mart_rollback_20260716` possui 82 objetos. Para desfazer também `control`/crosswalk, usar o dump completo pré-normalização com seleção dos objetos necessários; o restore integral não foi validado por decisão do usuário.

Após o primeiro write futuro, swap-back puro não deve ser usado. A estratégia passa a ser roll-forward, salvo captura/replay explícito do delta.

## 11. Riscos residuais

1. A lista de partidas ainda leva 16–40 s; precisa de serving/indexação específica em trabalho posterior.
2. A suíte dbt integral em produção é cara e não terminou; 165 testes passaram e os gates críticos tiveram cobertura direta.
3. O restore integral do dump completo não foi concluído, conforme instrução do usuário.
4. Existem 28 partidas StatsBomb ambíguas e 12 times StatsBomb não resolvidos em quarentena.
5. Os schemas sombra e de rollback consomem espaço e só devem ser removidos após uma janela de observação acordada.
6. Power BI não foi alterado; modelos que persistam IDs legados devem ser atualizados posteriormente para os novos IDs canônicos.

## 12. Arquivos principais alterados

- migrations `20260716130000`, `20260716140000`, `20260716141000`;
- modelos dbt de staging, bridges, dimensões, fatos e analytics relacionados à identidade canônica;
- `platform/scripts/materialize_authoritative_team_crosswalk.sql`;
- `platform/scripts/promote_canonical_team_registry.sql`;
- `platform/scripts/promote_multisource_decisions.sql`;
- `platform/scripts/materialize_provider_team_aliases.sql`;
- `platform/scripts/prepare_canonical_shadow_for_cutover.sql`;
- `platform/scripts/validate_multisource_cutover.sql`;
- `platform/scripts/cutover_canonical_mart.sql`;
- `platform/scripts/rollback_canonical_mart.sql`;
- `platform/scripts/ingest_statsbomb_open_data.py`;
- `api/src/routers/matches.py`;
- `api/tests/test_matches_routes.py`;
- manifestos e relatórios de qualidade relacionados.

Nenhum commit, push ou alteração de Power BI foi realizado nesta execução.
