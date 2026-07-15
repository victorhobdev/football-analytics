# Manifesto de partidas — reconciliação multifonte

**Estado:** `BLOCKED_NOT_APPROVED` (inventário/dry-run; nenhum cutover). O rekey de clubes foi materializado em sombra, mas a deduplicação de partidas ainda não foi aplicada.

Uma linha final por partida só pode ser emitida depois da decisão de identidade de ambos os times e da decisão de publicação. Enquanto isso, `pending`, `manual_review`, `blocked` e `rejected` não podem gerar fato.

## Inventário atual

| fonte | linked_to_sportmonks / auto_approved | new_coverage / pending | publicação derivada ainda `publishable` | suppressed_duplicate |
|---|---:|---:|---:|---:|
| dataset_brasileirao | 1.786 | 7.379 | 7.379 | 0 |
| transfermarkt | 6.787 | 25.845 | 25.841 | 4 |
| eloratings | 6.909 | 223.648 | 207.773 | 15.875 |
| **total** | **15.482** | **256.872** | **240.993** | **15.879** |

O campo `publication_status=publishable` é uma tabela derivada antiga e hoje contradiz `review_status=pending`; o teste bloqueante reproduziu exatamente 240.993 linhas. O rebuild sombra não as publicou.

## Decisão operacional implementada

- `linked_to_sportmonks`: `survivor_match_id = local_fixture_id`; não cria segundo fato externo.
- `new_coverage`: só entra em `stg_external_matches` quando `review_status=auto_approved`, `publication_status=publishable` e ambos os `source_team_key` apontam para `control.team_identity` ativo.
- Demais estados: quarentena/retirada de cobertura, sem exclusão raw.
- Candidatos fortes de duplicação (não apagados): Brasileirão 99, Elo 877, Transfermarkt 222, total 1.198.
- Os seis pares Flamengo × América-MG descritos no diagnóstico existem nos dois lados e aguardam decisão de match.

## Manifesto final pendente

Os 240.993 IDs de publicação, seus `duplicate_of`, precedência de atributos, inventário de eventos/lineups/stats, delta por filho e aprovação não foram fabricados. Gerá-los agora violaria a regra de não promover `pending` e não apagar candidatos automaticamente. O próximo executor deve preencher uma linha por ID, incluindo `canonical_match_id`, `survivor_match_id`, método, evidência, aprovação e rollback antes do cutover.

## Reconciliação SQL em sombra

Após o rekey dos clubes, a busca SQL encontrou 10.244 grupos exatos de partidas duplicadas, representando 11.019 linhas excedentes. A regra foi data + mandante/visitante canônicos + competição + edição + placar. Outros 53 pares diferem por um dia, mas têm horário compatível; ficaram em `manual_review`.

O resultado detalhado e a fusão sem soma estão em [normalizacao_partidas_sql_20260715.md](./normalizacao_partidas_sql_20260715.md). Nenhum desses grupos foi apagado nos marts ativos.
