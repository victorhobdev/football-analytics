# StatsBomb Open Data - plano pre-ingestao

## Diagnostico

O diretorio `D:\open-data` contem um checkout completo do **StatsBomb Open
Data**. A estrutura confirmada e:

- `data/competitions.json`;
- `data/matches/<competition_id>/<season_id>.json`;
- `data/events/<match_id>.json`;
- `data/lineups/<match_id>.json`;
- `data/three-sixty/<match_id>.json`.

O warehouse local ja contem uma parte desse dataset na vertical da Copa:

| Tabela | Linhas |
| --- | ---: |
| `raw.wc_match_events` | 534.745 |
| `raw.match_events` | 246.468 |
| `mart.fact_match_events` | 246.468 |

Em `raw.wc_match_events`, a fonte `statsbomb_open_data` ja representa:

| Fonte | Linhas | Partidas |
| --- | ---: | ---: |
| `statsbomb_open_data` | 524.490 | 147 |
| `fjelstul_worldcup` | 10.255 | 827 |

Portanto, a ingestao nova **nao deve recarregar eventos StatsBomb da FIFA World
Cup** como uma tabela paralela de eventos, porque isso duplicaria o mesmo fato
em outro local do warehouse.

Tambem ha risco de duplicacao contra o core SportMonks das competicoes normais.
O DW ja possui partidas, times, jogadores e eventos SportMonks para o portfolio
principal em `mart.fact_matches`, `mart.dim_team`, `mart.dim_player` e
`mart.fact_match_events`. Quando uma partida StatsBomb pertencer a uma
competicao/temporada ja coberta pelo SportMonks, ela deve ser tratada como
**enriquecimento de evento**, nao como nova partida canonica.

## Escopo analisado

Inventario local em `D:\open-data`:

| Area | Contagem |
| --- | ---: |
| Linhas em `competitions.json` | 80 |
| Competicoes/temporadas com arquivos de partidas | 80 |
| Partidas com metadata em `data/matches` | 3.961 |
| Arquivos em `data/events` | 4.235 |
| Arquivos em `data/lineups` | 4.235 |
| Arquivos em `data/three-sixty` | 426 |

Contagem de eventos:

| Escopo | Eventos |
| --- | ---: |
| Total em `data/events` | 14.874.171 |
| FIFA World Cup com metadata | 524.457 |
| Nao-Copa com metadata | 13.387.529 |
| Eventos sem metadata em `data/matches` | 962.185 |

Contagem de 360:

| Escopo | Contagem |
| --- | ---: |
| Arquivos 360 | 426 |
| Arquivos 360 parseaveis | 425 |
| Arquivos 360 invalidos | 1 |
| Frames 360 parseaveis | 1.381.467 |
| Linhas de jogadores em freeze-frame | 21.561.945 |
| Frames 360 de FIFA World Cup | 203.882 |
| Frames 360 nao-Copa | 1.177.585 |

Arquivo 360 invalido:

- `data/three-sixty/3845506.json`: erro de JSON em `line 92794 column 3`.

## Hipoteses

### Confirmada: ha sobreposicao real com o DW

Evidencia:

- O dataset local tem 147 partidas de `competition_id = 43`, `FIFA World Cup`.
- O DW ja tem 147 partidas StatsBomb em `raw.wc_match_events`.
- A tabela existente ja usa `source_name = 'statsbomb_open_data'`.
- A contagem local de eventos de Copa e 524.457; a contagem no banco e
  524.490. A diferenca de 33 eventos indica versao/snapshot diferente, mas o
  escopo e o mesmo.

Conclusao: eventos de Copa do StatsBomb devem ser tratados como **ja ingeridos
no pipeline da Copa**, nao como carga nova generica.

### Confirmada: ha arquivos de eventos/lineups sem metadata de partida

Evidencia:

- 274 arquivos em `events` nao possuem `match_id` correspondente em
  `data/matches`.
- 274 arquivos em `lineups` tambem ficam sem metadata.
- Esses arquivos somam 962.185 eventos.
- Amostras mostram partidas reais, como jogos de Bundesliga 2023/24, mas sem
  linha correspondente no arquivo de matches disponivel localmente.

Conclusao: esses arquivos podem ser preservados em `raw`, mas nao devem ser
promovidos a marts canonicos ate resolver metadata de partida.

### Confirmada: ha problema operacional em um arquivo 360

Evidencia:

- `data/three-sixty/3845506.json` nao parseia como JSON valido.

Conclusao: esse arquivo deve entrar em manifest como `parse_failed` e ficar fora
da carga tabular ate ser baixado novamente ou corrigido na origem.

### Confirmada: ha sobreposicao com SportMonks em competicoes normais

Evidencia no DW:

| Competicao SportMonks | Janela no DW | Partidas |
| --- | --- | ---: |
| `premier_league` | 2021_22 a 2024_25 | 1.520 |
| `la_liga` | 2021_22 a 2024_25 | 1.520 |
| `serie_a_it` | 2021_22 a 2024_25 | 1.521 |
| `bundesliga` | 2021_22 a 2024_25 | 1.224 |
| `ligue_1` | 2021_22 a 2024_25 | 1.372 |
| `champions_league` | 2021_22 a 2024_25 | 925 |

Evidencia no StatsBomb local:

| Competicao StatsBomb | Temporada | Partidas StatsBomb | Status |
| --- | --- | ---: | --- |
| `1. Bundesliga` | 2023/2024 | 34 | sobrepoe `bundesliga` SportMonks |
| `Ligue 1` | 2021/2022 | 26 | sobrepoe `ligue_1` SportMonks |
| `Ligue 1` | 2022/2023 | 32 | sobrepoe `ligue_1` SportMonks |
| `FIFA World Cup` | 2018 e 2022 | 128 | ja carregado na trilha Copa |

Conclusao: para competicoes normais ja existentes, a carga StatsBomb deve criar
pontes para os IDs SportMonks/canonicos existentes, nao novas linhas em
`mart.fact_matches`, `mart.dim_team` ou `mart.dim_player`.

## Regra anti-duplicacao

Usar chaves naturais do StatsBomb, nunca IDs internos gerados localmente como
criterio primario de idempotencia.

Chaves propostas:

| Grao | Chave natural |
| --- | --- |
| Competicao/temporada | `(source_name, competition_id, season_id)` |
| Partida | `(source_name, match_id)` |
| Evento | `(source_name, match_id, event_id)` |
| Evento sem `event_id` | `(source_name, match_id, event_index)` |
| Lineup por jogador | `(source_name, match_id, team_id, player_id)` |
| 360 frame | `(source_name, match_id, event_uuid)` |
| 360 freeze-frame player | `(source_name, match_id, event_uuid, player_id)` |
| Arquivo bruto | `(source_name, relative_path, sha256)` |

Regras especificas:

1. Nao inserir em `raw.statsbomb_events` linhas de partidas que ja estejam em
   `raw.wc_match_events` com `source_name = 'statsbomb_open_data'`.
2. Criar uma view/mart union para analise de eventos:
   - Copa vem de `raw.wc_match_events`;
   - restante vem de `raw.statsbomb_events`.
3. Se for necessario manter um inventario completo do dataset, registrar os
   arquivos de Copa no manifest, mas com `load_status = 'already_loaded_wc'`.
4. Arquivos sem metadata entram em raw/quarentena com
   `metadata_status = 'missing_match_metadata'`.
5. Arquivo 360 invalido entra no manifest com `load_status = 'parse_failed'`.
6. Nao inserir partida StatsBomb em `mart.fact_matches` quando houver match
   SportMonks/canonico equivalente.
7. Nao inserir time StatsBomb em `mart.dim_team` quando houver time canonico
   equivalente.
8. Nao inserir jogador StatsBomb em `mart.dim_player` quando houver jogador
   canonico equivalente.
9. Eventos StatsBomb de partidas SportMonks existentes devem apontar para
   `local_match_id`, `local_team_id` e `local_player_id` por bridge, mantendo
   os IDs StatsBomb como IDs de fonte.

## Deduplicacao contra SportMonks

### Principio

SportMonks continua sendo o core canonico do produto para competicoes normais ja
onboardadas. StatsBomb entra como fonte de enriquecimento granular. Isso evita
duas partidas diferentes representando o mesmo jogo.

### Classificacao de partida StatsBomb

Cada partida StatsBomb deve receber um `identity_status` antes de chegar ao
mart:

| Status | Significado | Acao |
| --- | --- | --- |
| `linked_to_sportmonks` | Match StatsBomb corresponde a `mart.fact_matches.match_id` | Carregar eventos como enriquecimento ligado ao match canonico |
| `new_external_match` | Nao ha match equivalente no core SportMonks | Pode virar fato externo separado |
| `ambiguous_match` | Mais de um candidato SportMonks ou baixa confianca | Quarentena/revisao |
| `missing_match_metadata` | Nao ha linha em `data/matches` | Quarentena raw |
| `already_loaded_wc` | Jogo StatsBomb da Copa ja esta em `raw.wc_match_events` | Nao recarregar eventos genericos |

### Regra de match

A ponte `bridge_statsbomb_match_identity` deve tentar resolver nesta ordem:

1. Mapeamento manual/curado por `(statsbomb_match_id -> mart.fact_matches.match_id)`.
2. Match deterministico por competicao canonica, temporada, data, mandante,
   visitante e placar.
3. Match tolerante por competicao canonica, data +/- 1 dia, times normalizados e
   placar.
4. Revisao manual quando houver empate de candidatos ou divergencia de placar.

Chave candidata para matching deterministico:

```text
canonical_competition_key
season_label
match_date
normalized_home_team_name
normalized_away_team_name
home_score
away_score
```

Para partidas em campo neutro ou fontes com mando divergente, permitir chave
alternativa com times invertidos, mas nunca promover automaticamente se o placar
tambem exigir inversao sem evidencia.

### Regra de time

Times StatsBomb devem entrar primeiro em `bridge_statsbomb_team_identity`:

| Campo StatsBomb | Campo canonico esperado |
| --- | --- |
| `team.id` | `source_team_id` |
| `team.name` | `source_team_name` |
| match context | competicao/temporada/data |
| `mart.dim_team.team_id` | `local_team_id` |

O time so pode ser considerado resolvido quando:

- aparece como mandante/visitante em uma partida ja ligada ao SportMonks; ou
- tem alias curado e unico; ou
- tem match forte por nome normalizado dentro da mesma competicao/temporada.

Nao criar `dim_team` novo para clubes ja presentes no SportMonks.

### Regra de jogador

Jogadores StatsBomb devem entrar primeiro em `bridge_statsbomb_player_identity`.
A resolucao automatica deve ser mais conservadora que a de times:

1. Se a partida esta ligada ao SportMonks e o jogador aparece em lineup/evento,
   buscar candidato em `mart.fact_fixture_lineups` ou
   `mart.fact_fixture_player_stats` pelo `local_match_id`, `local_team_id` e
   nome normalizado.
2. Se houver unico candidato, marcar como `linked_to_sportmonks`.
3. Se houver homonimo, nome incompleto, acento divergente ou ausencia no lineup,
   marcar como `ambiguous_player`.

Nao criar `dim_player` novo para atleta StatsBomb em competicoes ja cobertas
pelo SportMonks sem uma decisao explicita. Para competicoes externas novas,
pode haver dimensao externa separada ou jogador local sintetico, mas nao misturar
com `mart.dim_player` sem bridge.

### Regra de evento

Eventos SportMonks e StatsBomb nao sao duplicatas linha-a-linha: os provedores
tem granularidade e taxonomia diferentes. A duplicacao perigosa esta no **jogo**
e nas **entidades**, nao no evento individual.

Portanto:

- nao comparar `raw.match_events.event_id` com `StatsBomb event.id`;
- nao inserir StatsBomb em `mart.fact_match_events` existente;
- criar fato separado `mart.fact_statsbomb_match_event`;
- quando houver `local_match_id`, expor StatsBomb como enriquecimento granular;
- manter `provider = 'statsbomb_open_data'` e `source_event_id` sempre.

### Quality gates contra SportMonks

Antes de qualquer mart StatsBomb:

- toda partida com `identity_status = 'linked_to_sportmonks'` deve ter
  exatamente um `local_match_id`;
- nenhuma partida `linked_to_sportmonks` pode gerar nova linha em
  `mart.fact_matches`;
- todo evento StatsBomb de partida ligada deve carregar `local_match_id`;
- nenhum time StatsBomb resolvido pode criar novo `mart.dim_team`;
- nenhum jogador StatsBomb resolvido pode criar novo `mart.dim_player`;
- partidas `ambiguous_match` e jogadores `ambiguous_player` ficam fora dos
  marts finais;
- relatorio de cobertura deve separar:
  - partidas novas externas;
  - partidas ligadas ao SportMonks;
  - partidas Copa ja carregadas;
  - partidas em quarentena.

## Uso maximo seguro do dataset

Pode usar imediatamente, sem duplicar fatos ja existentes:

- 13.387.529 eventos nao-Copa com metadata;
- 3.814 partidas nao-Copa com metadata;
- lineups das partidas nao-Copa com metadata;
- 1.177.585 frames 360 nao-Copa parseaveis;
- 21.561.945 linhas de freeze-frame parseaveis, separando Copa e nao-Copa por
  chave natural.

Dentro desse bloco, partidas de ligas ja cobertas pelo SportMonks devem ser
classificadas como `linked_to_sportmonks` quando houver match unico. Elas
continuam aproveitaveis, mas como enriquecimento granular ligado ao match
canonico.

Pode preservar em raw, mas sem promover para mart ainda:

- 962.185 eventos sem metadata em `data/matches`;
- 274 arquivos de lineups sem metadata;
- eventos de Copa ja existentes, apenas como referencias no manifest.

Nao carregar ate corrigir:

- `data/three-sixty/3845506.json`.

## Desenho de tabelas recomendado

### Controle

Criar tabela de manifest:

- `control.external_file_manifest`
  - `source_name`;
  - `dataset_root`;
  - `relative_path`;
  - `file_size_bytes`;
  - `sha256`;
  - `detected_entity`;
  - `provider_match_id`;
  - `load_status`;
  - `parse_error`;
  - `ingested_at`.

Criar ou reaproveitar catalogo de fonte:

- `control.external_data_sources`
  - `source_name = 'statsbomb_open_data'`;
  - `license_status`;
  - `terms_summary`;
  - `attribution_required = true`;
  - `usage_scope = 'research_attribution_required'`.

### Raw

Tabelas novas:

- `raw.statsbomb_competition_seasons`;
- `raw.statsbomb_matches`;
- `raw.statsbomb_lineups`;
- `raw.statsbomb_events`;
- `raw.statsbomb_three_sixty_frames`;
- `raw.statsbomb_three_sixty_freeze_frame`;
- `raw.statsbomb_quarantine_events`;
- `raw.statsbomb_quarantine_lineups`.
- `raw.statsbomb_match_identity_candidates`;
- `raw.statsbomb_team_identity_candidates`;
- `raw.statsbomb_player_identity_candidates`.

Observacao: `raw.statsbomb_events` deve excluir partidas ja existentes em
`raw.wc_match_events`. Para partidas SportMonks normais, a tabela pode receber
os eventos, mas com `local_match_id` preenchido por bridge antes de promocao.
A tabela de quarentena aceita eventos sem metadata para nao perder volume bruto,
mas bloqueia promocao analitica.

### Staging dbt

Modelos sugeridos:

- `stg_statsbomb_competition_seasons`;
- `stg_statsbomb_matches`;
- `stg_statsbomb_lineups`;
- `stg_statsbomb_events`;
- `stg_statsbomb_three_sixty_frames`;
- `stg_statsbomb_three_sixty_freeze_frame`;
- `stg_statsbomb_event_types`;
- `stg_statsbomb_players`;
- `stg_statsbomb_teams`.

### Mart

Marts novos:

- `mart.fact_statsbomb_match_event`;
- `mart.fact_statsbomb_shot`;
- `mart.fact_statsbomb_pass`;
- `mart.fact_statsbomb_carry`;
- `mart.fact_statsbomb_pressure`;
- `mart.fact_statsbomb_lineup_slot`;
- `mart.fact_statsbomb_360_freeze_frame`;
- `mart.dim_statsbomb_event_type`;
- `mart.bridge_statsbomb_match_identity`;
- `mart.bridge_statsbomb_team_identity`;
- `mart.bridge_statsbomb_player_identity`.

Criar uma view analitica para evento unificado:

- `mart.vw_external_match_events_unified`
  - inclui `raw.wc_match_events` para Copa StatsBomb;
  - inclui `mart.fact_statsbomb_match_event` para nao-Copa;
  - inclui `source_table` para rastreabilidade.

## Ordem segura de execucao

1. Criar manifest de arquivos com hash SHA-256, tamanho, entidade detectada e
   status inicial.
2. Registrar fonte StatsBomb em tabela de controle, incluindo obrigacao de
   atribuicao.
3. Criar DDL raw com constraints de unicidade por chave natural.
4. Carregar `competitions.json` e todos os `matches`.
5. Gerar candidatos de identidade contra SportMonks para partidas, times e
   jogadores.
6. Congelar classificacao de cada partida:
   `linked_to_sportmonks`, `new_external_match`, `ambiguous_match`,
   `already_loaded_wc` ou `missing_match_metadata`.
7. Carregar lineups apenas para partidas com metadata, separando ligadas,
   externas novas e ambiguas.
8. Carregar eventos apenas para partidas com metadata e excluindo os 147 jogos
   de Copa ja presentes em `raw.wc_match_events`.
9. Carregar eventos/lineups sem metadata em tabelas de quarentena.
10. Carregar 360 parseavel, marcando o arquivo invalido como falha operacional.
11. Criar staging dbt e testes de unicidade.
12. Criar marts especializados.
13. Criar view union de eventos para consulta analitica.
14. Rodar auditoria de contagens por fonte, competicao, temporada, partida e
    tipo de evento.

## Quality gates obrigatorios

Antes de promover para mart:

- `raw.statsbomb_matches`: unico por `(source_name, match_id)`.
- `raw.statsbomb_events`: unico por `(source_name, match_id, event_id)`.
- `raw.statsbomb_events`: nenhum `match_id` presente em `raw.wc_match_events`
  para `source_name = 'statsbomb_open_data'`.
- `raw.statsbomb_events`: todo `match_id` existe em `raw.statsbomb_matches`.
- `bridge_statsbomb_match_identity`: maximo de um `local_match_id` por
  `statsbomb_match_id`.
- `bridge_statsbomb_team_identity`: maximo de um `local_team_id` por
  `source_team_id` dentro do contexto resolvido.
- `bridge_statsbomb_player_identity`: maximo de um `local_player_id` por
  `source_player_id` dentro do contexto resolvido.
- partidas ligadas ao SportMonks nao podem aumentar contagem de
  `mart.fact_matches`.
- `raw.statsbomb_three_sixty_frames`: todo `event_uuid` deve existir em evento
  StatsBomb carregado ou em `raw.wc_match_events`.
- `raw.statsbomb_quarantine_events`: nenhuma linha pode aparecer em mart.
- manifest: nenhum arquivo com `parse_failed` pode ser tratado como carregado.

## Proximo passo seguro

Implementar primeiro apenas o inventario/manifest e as DDLs de controle/raw,
sem carregar os 13 GB de eventos. Depois rodar um piloto com uma competicao
nao-Copa, por exemplo `Copa America` ou `UEFA Euro`, para validar:

- idempotencia;
- tamanho em disco;
- tempo de carga;
- constraints;
- modelos dbt;
- consultas analiticas.

So depois do piloto verde a carga completa deve ser executada.
