# Reconciliação SQL de partidas e fatos

**Data:** 2026-07-15  
**Ambiente:** PostgreSQL local `football_dw`  
**Estado:** materializado somente em sombra; nenhum fato ativo foi apagado ou atualizado

## Diagnóstico

Depois do rekey dos clubes, `match_id` continua sendo uma identidade de origem. A mesma partida aparece em mais de uma fonte, portanto `match_id` sozinho não pode ser a chave semântica do jogo.

A granularidade usada para o primeiro corte seguro é:

```text
data do jogo
+ mandante canônico
+ visitante canônico
+ competição
+ edição/temporada
+ placar final
```

O clube não é chave suficiente. O placar também é obrigatório para impedir que partidas diferentes entre os mesmos clubes sejam unidas.

## Evidência reproduzida

| medida | resultado |
|---|---:|
| linhas de origem em `shadow_team_identity_20260715.fact_matches_rekeyed` | 259.872 |
| grupos canônicos exatos | 248.853 |
| grupos exatos com mais de uma fonte | 10.244 |
| linhas excedentes (`count(grupo) - 1`) | 11.019 |
| grupos com duas linhas | 9.469 |
| grupos com três linhas | 775 |
| candidatos com data diferente por um dia e horário compatível | 53 |
| conflitos de métricas escalares dentro de grupo exato | 0 |

Os 53 casos de diferença de dia ficaram em `manual_review`; não foram fundidos automaticamente. A tolerância usa `date_utc` da staging quando disponível, com janela de 36 horas, e cai para diferença de dia quando o horário é nulo.

## Regra de fusão

Cada grupo exato recebe um `canonical_match_id` novo, alocado por sequence interna iniciada em `4.000.000.000.000`. O ID é persistido por `match_group_key`, portanto a segunda execução não muda as chaves.

Para atributos escalares:

- placar e times vêm da chave do grupo;
- métricas são preenchidas pelo primeiro valor não nulo segundo precedência `SportMonks > Brasileirão > Transfermarkt > Elo > StatsBomb`;
- valores de todas as fontes permanecem em `source_attributes`;
- valores distintos no mesmo atributo iriam para `attribute_conflict`; o estado atual tem zero conflitos;
- nenhuma métrica é somada.

Assim, uma fonte pode contribuir passes e outra chutes sem criar dois jogos. Os filhos não são descartados nem somados: views sombra mantêm cada linha original sob o mesmo `canonical_match_id`.

## Filhos cobertos

| relação | linhas | grupos alcançados |
|---|---:|---:|
| `mart.fact_match_events` | 13.520.851 | 17.910 |
| `mart.fact_fixture_lineups` | 747.908 | 17.842 |
| `mart.fact_fixture_player_stats` | 607.187 | 14.147 |
| `mart.fact_elo_match_team_stats` | 428.530 | 214.265 |
| `mart.fact_transfermarkt_match_events` | 128.901 | 26.575 |

As views `fused_fact_*` preservam `source_match_id`, provedor e todos os atributos dos filhos. A deduplicação posterior de eventos/lineups deve usar a identidade própria do filho, nunca simplesmente `count(*)` por partida.

## Objetos sombra

Schema: `shadow_match_dedup_20260715`

- `source_match`: partidas rekeyadas por clube canônico;
- `match_group`: uma linha por jogo semântico;
- `match_group_member`: inventário de todas as fontes;
- `fused_fact_matches`: uma linha por jogo, atributos unidos sem soma;
- `attribute_conflict`: conflitos escalares auditáveis;
- `near_day_candidate`: candidatos fora da data exata;
- `child_inventory`: cobertura dos filhos;
- `fused_fact_match_events`, `fused_fact_fixture_lineups`, `fused_fact_fixture_player_stats`, `fused_fact_elo_match_team_stats` e `fused_fact_transfermarkt_match_events`: views de linhagem.

O SQL reproduzível está em [materialize_match_dedup_shadow.sql](../../scripts/materialize_match_dedup_shadow.sql).

## Validação

- `259.872 - 248.853 = 11.019`, exatamente a soma de `tamanho_do_grupo - 1` dos grupos duplicados;
- todos os 259.872 `match_id` de origem pertencem a um grupo;
- todos os filhos consultados encontram um grupo;
- `home_team_id` e `away_team_id` canônicos não são iguais;
- hash de `match_group_key -> canonical_match_id`: `ecd6ac3fc706011ed02af54e914a31aa` em duas execuções;
- raw e marts ativos permanecem inalterados.

## Próximo passo seguro

Revisar os 53 candidatos de data tolerada e os eventuais conflitos de identidade de jogador. Só depois disso materializar as views de filhos como fatos finais e substituir os marts em um cutover controlado. O SQL atual é uma prova de deduplicação em sombra, não autorização para apagar os 11.019 membros excedentes.
