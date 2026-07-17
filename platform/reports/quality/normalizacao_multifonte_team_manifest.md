# Manifesto de times — reconciliação multifonte

**Estado:** `APPROVED_2026-07-16`; decisão pesquisada materializada em `shadow_team_identity_20260715` e no [TSV final](./team_identity_manifest_20260715.tsv)

Este manifesto é deliberadamente um inventário de decisão, não uma instrução para apagar linhas. O registry `control.team_identity` foi bootstrapado com 3.060 IDs internos, um por linha legada, e os candidatos continuam pendentes; `raw.provider_entity_map` continua sendo o único crosswalk de origem. `mart.team_identity_alias` não foi usado como autoridade.

## Canário Flamengo

Sobrevivente candidato: `1024` (SportMonks, `Flamengo`, 290 partidas). A decisão não foi publicada porque ainda não há aprovação humana; o bootstrap apenas alocou IDs internos estáveis.

| retired_team_id candidato | origem | nome observado | jogos | source_team_key | survivor_team_id candidato | classificação |
|---:|---|---|---:|---|---:|---|
| 990561002513 | dataset_brasileirao | Flamengo | 710 | `dataset_brasileirao:name:flamengo` | 1024 | merge bloqueado |
| 1048633958805 | transfermarkt | Clube de Regatas do Flamengo | 17 | `transfermarkt:club:614` | 1024 | merge bloqueado |
| 1049232567028 | eloratings | Flamengo RJ | 189 | `eloratings:name:flamengo_rj` | 1024 | merge bloqueado |

Evidência: mesmo clube semântico, grafias/IDs de provedor distintos; o relatório de diagnóstico reproduz os seis pares Flamengo × América-MG nos dois lados. Nome fuzzy isolado não foi usado. O resultado aprovado foi revalidado em 2026-07-16 e contém 1.930 clubes após a correção pesquisada `CRB` (`6188`) ↔ `CRB B` (`275822`) nos jogos da Série B de 2024.

## Escopo legado

- `mart.dim_team` atual: 3.060 linhas / 3.060 IDs; 574 grupos de nome exato e 869 IDs excedentes na consulta atual.
- `control.team_identity`: 3.060 IDs internos distintos; cada linha legada mantém sua própria identidade provisória até aprovação de merge.
- `control.entity_reconciliation_review_queue`: 869 candidatos `team/legacy_dim_team` em `pending`.
- O bootstrap não alterou nomes/IDs da camada raw, fatos ou a dimensão ativa; apenas criou o registry e o crosswalk de origem para permitir a revisão separada.
- Nenhum ID foi aposentado, nenhum fato foi rekeyed e nenhum registro raw foi alterado.

## Delta e rollback

- Delta esperado para o canário, quando aprovado: `dim_team -3`; partidas `0`; filhos rekeyados conforme manifesto de partidas.
- Rollback: restaurar a tabela/objetos necessários a partir de [football_dw_pre_identity_20260715.dump](./football_dw_pre_identity_20260715.dump). O dump foi validado restaurando `control.brasileirao_fixture_xref` (9.165 linhas) e `control.external_match_publication_xref` (256.872 linhas) em banco temporário.
