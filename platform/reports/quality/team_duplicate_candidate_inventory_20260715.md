# Inventário de candidatos a duplicação de clubes

> **Resultado superado:** a contagem `2.733` abaixo mede somente a etapa de
> sobreposição de partidas. A pesquisa completa de chaves nativas, contexto e
> fontes externas concluiu **1.930 clubes canônicos em sombra** após a correção CRB. Consulte
> [resultado_normalizacao_semantica_clubes_20260715.md](resultado_normalizacao_semantica_clubes_20260715.md).

**Data:** 2026-07-15
**Ambiente:** PostgreSQL local `football_dw`
**Escopo:** identificação, manifesto e materialização em sombra; nenhum merge ou rekey aplicado nos marts ativos

## Resultado executado

| medida | resultado |
|---|---:|
| linhas em `mart.dim_team` | 3.060 |
| IDs legados distintos | 3.060 |
| grupos com `team_name` exato repetido | 574 |
| IDs excedentes nesses grupos | 869 |
| IDs internos em `control.team_identity` | 3.060 |
| relações `legacy_dim_team` em `raw.provider_entity_map` | 3.060 |
| candidatos de time em `control.entity_reconciliation_review_queue` | 869 |
| candidatos com status diferente de `pending` | 0 |
| linhas em `mart.fact_matches` antes/depois | 259.872 / 259.872 |

Os 3.060 IDs internos são estáveis e independentes do provedor. A sequence usa o intervalo `2.000.000.000.000–2.000.000.003.059`, separado dos IDs legados. Cada linha legada recebeu inicialmente um ID próprio (`decision_method = legacy_bootstrap`), porque alocar a chave não é o mesmo que aprovar uma fusão. Os 869 excedentes foram apenas enfileirados para decisão.

O script foi executado novamente como teste de idempotência: não criou novos IDs, não alterou a fila e não sobrescreve um crosswalk que venha a ser decidido manualmente.

## Regra da fila

O script versionado [bootstrap_team_identity.sql](../../scripts/bootstrap_team_identity.sql) usa, nesta ordem, como recomendação de sobrevivente dentro de cada nome exato:

1. maior prioridade de fonte observada nos jogos (`sportmonks`, `transfermarkt`, `dataset_brasileirao`/`eloratings`, demais);
2. maior número de ocorrências em `mart.stg_matches`;
3. menor `mart.dim_team.team_id` como desempate determinístico.

Essa regra produz uma recomendação auditável, não uma aprovação. Homônimos, variações de grafia e clubes de categorias diferentes continuam exigindo revisão. Não foi usado fuzzy match para executar merge.

## Grupos exatos maiores

| nome | tamanho | excedentes | IDs legados |
|---|---:|---:|---|
| Aston Villa | 5 | 4 | 15, 910000000059, 910000002647, 985233031060, 1005080931358 |
| Brentford | 5 | 4 | 236, 960748939801, 978890180164, 979447005493, 992527114843 |
| Luton | 5 | 4 | 996976796601, 1001083339969, 1019917199976, 1023003324520, 1026607186836 |
| Portsmouth | 5 | 4 | 910000000105, 973116063213, 1003204026093, 1043392054622, 1046742035543 |
| Rangers | 5 | 4 | 62, 964548087097, 980042478253, 998536802601, 1039733967206 |
| Sheffield United | 5 | 4 | 21, 981681634557, 1010502322545, 1028636070439, 1031672818331 |
| Southampton | 5 | 4 | 65, 910000000025, 1009155442516, 1016283962856, 1039263897379 |
| Villarreal | 5 | 4 | 3477, 910000000222, 910000006604, 1019230468340, 1030814717557 |

## Canário Flamengo

Os quatro IDs conhecidos têm quatro grafias/identidades legadas e receberam IDs internos distintos durante o bootstrap:

| ID legado | nome | canonical interno bootstrap | jogos | decisão |
|---:|---|---:|---:|---|
| 1024 | Flamengo | 2000000002941 | 290 | sobrevivente recomendado, pendente |
| 990561002513 | Flamengo | 2000000002224 | 710 | candidato exato, pendente |
| 1048633958805 | Clube de Regatas do Flamengo | 2000000002284 | 17 | candidato semântico, revisão explícita |
| 1049232567028 | Flamengo RJ | 2000000001844 | 189 | candidato semântico, revisão explícita |

A fila automática de nome exato contém o ID `990561002513`. Os dois nomes diferentes não foram fundidos nem classificados por fuzzy match; devem ser adicionados à mesma decisão semântica somente após confirmar evidência de provedor, país, gênero/categoria e partidas sobrepostas. O sobrevivente recomendado é o legado `1024`, mas ainda não foi promovido.

## Consulta de auditoria

Para listar os candidatos pendentes:

```sql
select
  source_entity_id::bigint as retired_legacy_team_id,
  candidate_canonical_id,
  source_label as team_name,
  status,
  evidence
from control.entity_reconciliation_review_queue
where entity_type = 'team'
  and source = 'legacy_dim_team'
order by source_label, retired_legacy_team_id;
```

Para conferir o vínculo de todos os legados ao novo registry:

```sql
select count(*) as legacy_rows,
       count(distinct canonical_id) as internal_ids
from raw.provider_entity_map
where provider = 'legacy_dim_team'
  and entity_type = 'team';
```

## Próximo bloco seguro

Tratar os grupos da fila por decisão explícita. Para cada grupo aprovado, registrar o sobrevivente, evidência e impacto; só então atualizar o crosswalk de cada origem real, marcar os IDs aposentados/merged e reconstruir fatos e filhos em sombra. O bootstrap desta etapa não alterou `mart.dim_team`, `mart.fact_matches` ou qualquer tabela `raw` de origem.

## Resolução por fingerprint de partida

Foi executado um cruzamento em todos os 519.744 lados de partidas de `mart.stg_matches`. O fingerprint usa data UTC, competição, placar relativo ao clube e adversário normalizado; exige fontes diferentes e pelo menos cinco fingerprints coincidentes para formar uma ligação confirmada.

| medida | resultado |
|---|---:|
| IDs analisados | 3.060 |
| pares de IDs ligados por evidência de partida | 398 |
| IDs dentro de componentes ligados | 508 |
| componentes semânticos formados | 181 |
| IDs excedentes dentro desses componentes | 327 |
| clubes únicos confirmados por essa regra | **2.733** |
| IDs sem ligação de partida suficiente | 2.552 |

O número `2.733` é o resultado reproduzível da regra de evidência de partida, não uma fusão executada na dimensão ativa. Os 2.552 IDs sem ligação suficiente continuam separados; eles podem ser singletons legítimos ou duplicatas com coberturas temporais/competitivas sem sobreposição.

### Flamengo

O grafo confirmou três IDs por seis ou mais jogos coincidentes:

| IDs | jogos coincidentes |
|---|---:|
| `1024` ↔ `990561002513` | 6 |
| `990561002513` ↔ `1049232567028` | 8 |

`1048633958805` não tem sobreposição temporal com esses registros no staging. O raw do Transfermarkt identifica o `club_id=614` como `Clube de Regatas do Flamengo`, correspondendo ao [perfil do CR Flamengo no Transfermarkt](https://www.transfermarkt.com/flamengo-rio-de-janeiro/datenfakten/verein/614); essa é evidência de identidade de fonte, mas não foi misturada silenciosamente ao grafo de partidas.

## Limite da validação externa nesta execução

O banco permite formar fingerprints para os 3.060 registros, mas não existe uma fonte web única e autoritativa que cubra todos os clubes e todas as partidas históricas. Uma busca aberta também pode retornar homônimos: por exemplo, “Flamengo” pode apontar ao [CR Flamengo](https://www.flamengo.com.br/historia/origem.html) ou a outro clube com o mesmo nome, como o [Flamengo de Volta Redonda](https://pt.wikipedia.org/wiki/Clube_de_Regatas_do_Flamengo_%28Volta_Redonda%29). Portanto, a internet é evidência corroborativa para cada grupo, não uma regra automática de merge.

O fingerprint evita declarar `3.060 - 869` automaticamente. A contagem operacional agora é `2.733` clubes confirmados pela regra definida; os restantes precisam de evidência adicional antes de qualquer merge.
