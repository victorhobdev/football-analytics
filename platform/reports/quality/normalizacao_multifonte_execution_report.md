# Execução — normalização multifonte de clubes e partidas

**Data:** 2026-07-15
> **Atualização de 2026-07-16:** os blockers descritos neste relatório histórico foram resolvidos e o cutover foi concluído. A evidência final e o rollback estão em `normalizacao_multifonte_cutover_audit_20260716.md`.

**Commit observado:** `484c410dfdfc908b9fe5aa9bb54a899e8a7c78bf`
**Ambiente:** Postgres local `football_dw`; nenhum writer de produção foi usado
**Resultado:** manifesto pesquisado materializado em `shadow_team_identity_20260715`; marts ativos preservados; cutover histórico **bloqueado** pelos gates de publicação/partidas ainda pendentes

Este documento registra o que foi executado, o que foi comprovado e o blocker real. Não há merge, rekey ou exclusão de dados históricos nos marts ativos; o rekey descrito adiante é somente uma cópia sombra auditável.

## 1. Baseline reproduzido

| verificação | baseline atual |
|---|---:|
| Flamengo `1024` / SportMonks | 290 partidas |
| Flamengo `990561002513` / Brasileirão | 710 partidas |
| Flamengo `1048633958805` / Transfermarkt | 17 partidas |
| Flamengo `1049232567028` / Elo | 189 partidas |
| `mart.dim_team` (linhas / IDs distintos) | 3.060 / 3.060 |
| grupos de nome exato / IDs excedentes | 574 / 869 |
| `mart.fact_matches` (linhas / IDs distintos) | 259.872 / 259.872 |
| pending + publishable | 240.993 |
| candidatos fortes de partidas | 1.198 (99 Brasileirão, 877 Elo, 222 Transfermarkt) |

O baseline exportado por `platform/scripts/export_reconciliation_baseline.py` confirmou raw: Brasileirão 9.165, Elo 230.557, StatsBomb 4.235, Transfermarkt 88.808; e os 15.482 links locais aprovados (1.786 + 6.787 + 6.909).

O relatório inicial registrava 870 IDs excedentes. A consulta atual, executada antes do bootstrap, reproduziu 574 grupos e 869 excedentes; o delta de um ID é tratado como mudança do estado dos dados, não como número forçado.

Watermarks observados:

| objeto | máximo |
|---|---|
| `raw.fixtures` | 2026-04-11 06:11:51Z |
| `raw.brasileirao_matches` | 2026-06-20 14:29:11Z |
| `raw.elo_matches` | 2026-06-20 14:29:14Z |
| `raw.tm_games` | 2026-06-20 14:31:39Z |
| `raw.statsbomb_matches` | 2026-06-19 21:41:41Z |
| xrefs externos | 2026-06-21 11:57:00Z |
| `mart.fact_matches` | 2026-06-21 11:59:39Z |

O Postgres está com `data_checksums=off`; 8.977 de 8.995 entradas de `control.external_file_manifest` têm `sha256=skipped`. Não foi possível declarar checksum de conteúdo raw completo. O backup restaurável e contagens/bytes de relação foram capturados como baseline de integridade; a ausência de checksum é risco residual explícito.

## 2. Autoridade, migration e backup

- `20260715120000_team_identity_registry.sql` foi criada e aplicada localmente (`public.schema_migrations` agora registra `20260715120000`).
- `control.team_identity` possui sequence de ID interno, estado `active/merged/retired`, `merged_into_team_id`, país/território, tipo, gênero e categoria. Não existe UNIQUE em `team_name`.
- O bootstrap idempotente em `platform/scripts/bootstrap_team_identity.sql` criou 3.060 IDs internos, um por linha legada de `mart.dim_team`, sem declarar nenhum merge.
- A sequence interna começa em `2.000.000.000.000`, separada do espaço numérico dos IDs legados/provedores; o intervalo bootstrap atual é `2.000.000.000.000–2.000.000.003.059`.
- `raw.provider_entity_map` recebeu 3.060 relações `legacy_dim_team -> canonical_team_id`; esse é o único crosswalk autoritativo.
- `control.entity_reconciliation_review_queue` recebeu 869 candidatos de time em `pending`, cobrindo os 574 grupos exatos. Nenhuma decisão humana foi sobrescrita.
- A segunda execução do bootstrap foi idempotente: não criou IDs novos, não alterou a fila e usa `ON CONFLICT DO NOTHING` no crosswalk para preservar futuras decisões manuais.
- `raw.provider_entity_map` continua sendo o único crosswalk de origem. `mart.team_identity_alias` não decide identidade.
- Backup: [football_dw_pre_identity_20260715.dump](./football_dw_pre_identity_20260715.dump), 4.209.358.829 bytes, TOC validado por `pg_restore -l`.
- Rollback testado: banco temporário restaurou `control.brasileirao_fixture_xref` (9.165 linhas) e `control.external_match_publication_xref` (256.872 linhas), foi consultado e removido.

## 3. Divergência de autoridade encontrada

`pg_get_viewdef(mart.stg_matches)` continua diferente do SQL versionado:

- view ativa: `d75a2ebe6992843783d06a27a7fecfb4`
- view versionada em `shadow_identity`: `f9a460215e836b3da9e093e9ba6ba175`

A view ativa contém `brasileirao_external`, `transfermarkt_external` e `eloratings_external_base`, promove qualquer `publication_status='publishable'` e calcula IDs de time com `960200000000 + md5(provider:competition:name)`. Esse SQL não estava no `stg_matches.sql` versionado.

O SQL foi versionado de forma segura em `stg_external_matches.sql`: só aceita `new_coverage + auto_approved + publishable`, cria `source_team_key` contextual, exige `raw.provider_entity_map` e `control.team_identity` ativo, e não possui fallback hash de nome. `stg_matches.sql` agora o incorpora. A view ativa não foi substituída: fazer isso seria cutover antes de manifestos/aprovação.

## 4. Mudanças executadas

1. `build_external_match_publication_xref.py` ganhou `is_publishable_new_coverage`; o loader só lê xrefs `review_status='auto_approved'`.
2. `stg_elo_matches.sql` e `stg_tm_match_identity.sql` não aceitam mais `publishable` isolado; links reutilizam `local_fixture_id`.
3. `stg_matches.sql` resolve StatsBomb por `stg_statsbomb_team_identity`: lado ligado usa `local_team_id`; `stg_fixture_lineups.sql` recebeu a mesma regra.
4. `stg_external_matches.sql` centraliza Brasileirão, Transfermarkt e Elo; sem mapa canônico ativo a linha não publica.
5. A migration do registry foi aplicada apenas no ambiente local. Nenhuma tabela raw foi escrita.

## 5. Testes e rebuild sombra

- Testes novos ficaram RED antes da implementação (3 falhas) e GREEN depois: **5 passed** em `tests/test_multisource_identity_guards.py`.
- Suíte Python: **13 passed** com `PYTHONPATH=infra/airflow/dags`.
- `dbt compile` dos cinco modelos tocados passou; projeto final contém 103 modelos e 373 data tests.
- Views finais `stg_external_matches` + `stg_matches` passaram em `shadow_identity`; a cadeia `+fact_matches` (15 nós) passou.
- Rebuild completo anterior percorreu 102 modelos: 101 passaram e `analytics_superlative_summary` falhou por `UNION types text and bigint cannot be matched`. O `dbt build` também encontrou `test_competition_season_config_alignment` (15 resultados) e falta de `/dev/shm` em um teste StatsBomb. São blockers independentes ainda não verdes.

Resultado da sombra final:

- `shadow_identity.stg_external_matches`: 0 linhas — correto para o estado atual, pois ainda não há mapas aprovados dos provedores externos para os novos IDs internos e todos os `new_coverage` estão pendentes.
- `shadow_identity.stg_matches`: 18.879 partidas; `shadow_identity.fact_matches`: 18.879/18.879 IDs únicos.
- Delta contra o baseline ativo: `259.872 - 18.879 = 240.993`, exatamente a cobertura externa pending retirada. Isso prova bloqueio de publicação, não normalização histórica concluída.
- As 268 partidas StatsBomb com lados mapeados passaram a usar IDs locais; lineups ligados também usam `local_team_id`.

Gates críticos:

| gate | resultado |
|---|---|
| pending nunca publica | **FAIL 240.993** no estado ativo; stale publication xref ainda existe |
| StatsBomb ligado usa ID local | PASS |
| linked externo reutiliza local fixture | PASS |
| view ativa = SQL versionado | **FAIL** (hashes acima) |

## 6. Manifestos

- [Manifesto de times](./normalizacao_multifonte_team_manifest.md): canário Flamengo, três IDs candidatos a aposentadoria, source keys e delta esperado; estado `BLOCKED_NOT_APPROVED`.
- [Manifesto de partidas](./normalizacao_multifonte_match_manifest.md): inventário por fonte, linked/pending/publication stale, candidatos fortes e regra de não apagar.

Os 3.060 times legados agora têm IDs internos e crosswalk de bootstrap. Os 869 candidatos continuam sem decisão final; os 240.993 IDs de publicação e seus filhos ainda não têm decisão final linha a linha. Não foram inventados `duplicate_of`, precedência ou aprovação.

## 7. Blocker real e condição de retomada

1. O registry possui 3.060 IDs de bootstrap, mas `control.entity_reconciliation_review_queue` mantém 869 candidatos de time em `pending`; não há autoridade aprovada para transformar os quatro Flamengos nem os 574 grupos.
2. A view ativa ainda publica os 240.993 pending; o parity gate falha. Substituí-la agora seria cutover sem manifesto final.
3. O rebuild integral ainda tem falhas independentes (alinhamento de competição, tipo de UNION e limite `/dev/shm`).
4. Não há checksum de conteúdo raw completo.

Para retomar: aprovar/bootstrap do registry (preservando singletons e os cinco IDs legados ausentes do staging), preencher `raw.provider_entity_map` uma única vez, decidir cada publicação/partida e filhos nos manifestos, rebuild full-refresh em sombra, corrigir os três gates independentes, comparar checksums e só então executar pause-writers/delta replay/swap/rollback. Nenhuma dessas decisões foi assumida automaticamente.

## 8. Materialização pesquisada em sombra

O script `platform/scripts/materialize_team_identity_shadow.py` reutiliza a resolução de `analyze_team_identity_uniqueness.py` e grava somente o schema `shadow_team_identity_20260715`. A alocação usa uma sequence interna iniciada em `3.000.000.000.000`; não há hash de nome/fonte para gerar IDs.

| objeto sombra | resultado |
|---|---:|
| `canonical_team` | **1.930** IDs internos ativos |
| `provider_entity_map` | 5.884 chaves, incluindo SportMonks/Transfermarkt nativos e Elo/Brasileirão contextuais |
| `team_manifest` | 3.061 linhas (merge/separate/split_context) |
| `negative_decision` | 43 pares rejeitados auditáveis |
| `fact_matches_rekeyed` | 259.872 linhas, 0 órfãos, 0 `home=away` |

O canário Flamengo tem um único canônico sombra `3000000000284`; os quatro legados `1024`, `990561002513`, `1048633958805` e `1049232567028` apontam para ele. Belenenses (`3000000000000`) e B SAD (`3000000000001`) são distintos, e o Elo `1002633571734` tem chaves `pre_2018`/`post_2018`.

A segunda execução foi repetida após a correção CRB e preservou cardinalidade, crosswalk e rekey. O hash de conteúdo final do cadastro foi `df7e27fbfd43a5eb44d0be4572fc1488`; o do crosswalk foi `42d7b3104a4e358c5d049d0927ad373f`; o do manifesto foi `651737ab781a0a9831fda2d0462b72db`.

O critério de 1.933 IDs não foi forçado: a auditoria mostrou que ele contava quatro entidades no componente Belenenses, embora os três legados representem clube + SAD. A validação posterior dos fatos filhos confirmou ainda que `CRB B` (`275822`) era um rótulo incorreto para o CRB principal (`6188`) em 13 partidas da Série B de 2024. A materialização corrigida é 1.930; o delta está registrado no relatório semântico e no manifesto TSV.

## 9. Reconciliação de partidas em SQL

Em `shadow_match_dedup_20260715`, a chave semântica encontrou 10.244 grupos duplicados exatos e 11.019 linhas excedentes dentro de 259.872 partidas. Foram mantidos 53 pares com diferença de um dia para revisão manual. `fused_fact_matches` escolhe atributos não nulos por precedência e guarda o inventário completo das fontes; views `fused_fact_*` preservam eventos, escalações e estatísticas sem soma ou descarte.

## Arquivos alterados nesta execução

- `db/migrations/20260715120000_team_identity_registry.sql`
- `platform/dbt/models/staging/stg_external_matches.sql`
- `platform/dbt/models/staging/stg_matches.sql`
- `platform/dbt/models/staging/stg_elo_matches.sql`
- `platform/dbt/models/staging/stg_tm_match_identity.sql`
- `platform/dbt/models/staging/stg_fixture_lineups.sql`
- `platform/scripts/build_external_match_publication_xref.py`
- `platform/scripts/bootstrap_team_identity.sql`
- `platform/scripts/build_team_match_fingerprint_candidates.py`
- `platform/scripts/analyze_team_identity_uniqueness.py`
- `platform/scripts/materialize_team_identity_shadow.py`
- `platform/scripts/materialize_match_dedup_shadow.sql`
- `platform/reports/quality/resultado_normalizacao_semantica_clubes_20260715.md`
- `platform/reports/quality/normalizacao_partidas_sql_20260715.md`
- `platform/reports/quality/team_identity_manifest_20260715.tsv`
- `platform/reports/quality/team_identity_negative_decisions_20260715.tsv`
- `tests/test_team_match_fingerprint_candidates.py`
- `platform/dbt/tests/test_external_pending_not_publishable.sql`
- `platform/dbt/tests/test_statsbomb_linked_team_uses_local_id.sql`
- `platform/dbt/tests/test_linked_external_reuses_local_fixture.sql`
- `platform/dbt/tests/test_stg_matches_active_view_parity.sql`
- `tests/test_multisource_identity_guards.py`
- `platform/reports/quality/normalizacao_multifonte_team_manifest.md`
- `platform/reports/quality/normalizacao_multifonte_match_manifest.md`

Nenhum commit, push ou alteração em produção foi feito.
