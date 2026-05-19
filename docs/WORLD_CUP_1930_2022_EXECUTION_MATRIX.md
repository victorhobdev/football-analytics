# Copa do Mundo 1930-2022 — Matriz de Execução

Referência principal: [WORLD_CUP_INGESTION_SOURCE_DEEP_DIVE_AND_PLAN.md](/C:/Users/Vitinho/Desktop/Projetos/football-analytics/docs/WORLD_CUP_INGESTION_SOURCE_DEEP_DIVE_AND_PLAN.md)

## 1. Objetivo

Transformar o plano-base da Copa do Mundo em uma matriz operacional permanente de:

- `já feito`
- `falta`
- blocos executáveis em ordem

Escopo desta matriz:

- Copa do Mundo masculina `1930-2022`
- manter `2022` verde
- expandir com o maior volume de dado real disponível
- não confundir cobertura estrutural histórica com depth rica de `2018/2022`

---

## 2. Diagnóstico consolidado

O contrato-base da Copa está correto na estratégia de fontes:

- `Fjelstul` como backbone estrutural e histórico;
- `StatsBomb` como profundidade rica em `2018/2022`;
- `StatsBomb` histórico amostral apenas como `sampled_match_enrichment`;
- `raw.wc_match_events` como tabela própria da Copa.

O principal gap atual não é de fonte. É de fundação operacional:

- snapshot gate ainda é `2022-only`;
- serviços e DAGs ainda são `2022-only`;
- catálogo canônico da Copa em `raw.competition_leagues` / `raw.competition_seasons` ainda não foi materializado;
- `2018` e o backbone `1930-2022` ainda não foram carregados.

---

## 3. Estado real atual

### 3.1 Já feito

- Snapshot gate da Copa para `2022`
- Bronze `2022`
- Bootstrap canônico `2022`
- Silver inicial `2022`
- Raw publish inicial `2022`
- Navegabilidade `raw.fixtures <-> raw.wc_match_events`
- BFF e frontend mínimos para `2022`

### 3.2 Ainda não feito

- generalização multi-edição da fundação da Copa
- catálogo da Copa em `raw.competition_leagues` e `raw.competition_seasons`
- ativação operacional de `2018`
- backbone histórico `1930-2022`
- lineups/events históricos discretos fora de `2018/2022`
- `match_statistics` e `fixture_player_statistics` de `2018/2022`

---

## 4. Matriz `já feito vs falta`

| Eixo | Contrato-base | Estado real | Gap | Bloco executável |
|---|---|---|---|---|
| Snapshot gate | snapshots reprodutíveis por fonte, compatíveis com `2022 + 2018` | só `2022`, 1 ativo por fonte | não suporta multi-edição limpa | `B0` |
| Pipeline WC | desenho compatível com `2022 + 2018` | serviços/DAGs `2022-only` | parametrização por edição/tournament | `B0` |
| Seeds da competição | `competition_leagues` / `competition_seasons` para Copa | inexistentes | catálogo da Copa fora do raw canônico | `B1` |
| Backbone estrutural `2022` | fixtures/stages/groups/standings/coaches | feito | nenhum para `2022` | verde |
| Depth rica `2022` | events/lineups/360 | feito | nenhum para `2022` | verde |
| Canonical bootstrap `2022` | team/match/stage/group + player operacional | feito | nenhum para `2022` | verde |
| Silver/raw `2022` | estrutural + events/lineups | feito | stats derivadas faltando | `B7` |
| `2018` full edition | Fjelstul + StatsBomb sem 360 | nada materializado | edição inteira pendente | `B4`, `B6`, `B7` |
| `1930-2022` backbone | Fjelstul estrutural completo | nada materializado fora de `2022` | 21 edições pendentes | `B2`, `B3`, `B5` |
| Históricos sampled StatsBomb | enrichment pontual `1958`, `1962`, `1970`, `1974`, `1986`, `1990` | nada | sampled enrichment pendente | `B8` |
| `match_statistics` | derivado de StatsBomb `2018/2022` | `0` | domínio pendente | `B7` |
| `fixture_player_statistics` | derivado de StatsBomb `2018/2022` | `0` | domínio pendente | `B7` |
| `player_transfers` / `team_sidelined` | gap declarado | `0` | continua fora do escopo por falta de fonte | fora do plano |

---

## 5. Blocos executáveis

### `B0` — Generalizar a fundação da Copa para multi-edição

**Objetivo**

- sair de `2022-only` para uma fundação que aceite múltiplas edições sem quebrar `2022`

**Escopo**

- snapshot gate
- serviços e DAGs da Copa
- parâmetros por edição

**Entregáveis**

- snapshots não presos a `edition_scope = 2022`
- serviços aceitando:
  - `edition_key`
  - `season_label`
  - `fjelstul_tournament_id`
  - expectativas por edição
- DAGs edition-aware, não `*_2022_*`

**Validação**

- rerun de `2022` continua idempotente
- `2022` permanece verde sem delta indevido

**Blocker real**

- qualquer mudança que quebre o caminho verde de `2022`

---

### `B1` — Materializar o catálogo da Copa no raw canônico

**Objetivo**

- criar a presença formal da Copa no catálogo do warehouse

**Escopo**

- `raw.competition_leagues`
- `raw.competition_seasons`

**Entregáveis**

- `competition_key = fifa_world_cup_mens`
- seasons/editions de `1930` a `2022`
- metadata mínima de `participant_scope = national_team` e `format_family` por edição

**Validação**

- `raw.competition_leagues` contém `fifa_world_cup_mens`
- `raw.competition_seasons` contém `1930..2022`

**Blocker real**

- ausência de convenção estável para mapear `league_id` e `season_id` sem colidir com o catálogo existente

---

### `B2` — Bronze histórico estrutural via Fjelstul

**Objetivo**

- carregar o backbone estrutural `1930-2022`

**Escopo mínimo**

- `bronze.fjelstul_wc_matches`
- `bronze.fjelstul_wc_groups`
- `bronze.fjelstul_wc_group_standings`
- `bronze.fjelstul_wc_manager_appointments`
- `bronze.fjelstul_wc_tournament_stages`

**Escopo ampliado para maximizar dado**

- `bronze.fjelstul_wc_squads`
- `bronze.fjelstul_wc_player_appearances`
- `bronze.fjelstul_wc_goals`
- `bronze.fjelstul_wc_bookings`
- `bronze.fjelstul_wc_substitutions`

**Validação**

- 22 edições masculinas presentes
- contagens por edição coerentes com Fjelstul
- gaps pré-1970 marcados como `PROVIDER_COVERAGE_GAP`, não erro

**Blocker real**

- PK nativa do Fjelstul ausente na extração de algum dataset

---

### `B3` — Bootstrap canônico histórico do backbone

**Objetivo**

- resolver identidade estrutural para todas as edições já carregadas via Fjelstul

**Escopo**

- `team`
- `match`
- `stage`
- `group`
- `coach` opcional/source-scoped
- `player` só quando necessário para datasets Fjelstul

**Validação**

- `team` 100%
- `match` 100%
- `stage/group` 100%
- zero colapso indevido de identidades nacionais

**Blocker real**

- regra de identidade nacional histórica ambígua sem dicionário explícito

---

### `B4` — Ativar `2018` full edition

**Objetivo**

- materializar a primeira expansão rica além de `2022`

**Escopo**

- snapshots `2018`
- bronze StatsBomb `2018`:
  - matches
  - events
  - lineups
  - sem 360
- backbone `2018` via Fjelstul
- bootstrap canônico `2018`

**Validação**

- `64` fixtures
- `64` event files
- `64` lineup files
- `0` 360 esperado
- pareamento Fjelstul ↔ StatsBomb `64/64`

**Blocker real**

- mismatch estrutural `home_team`, `away_team`, `stage_key` ou `final_score` entre Fjelstul e StatsBomb

---

### `B5` — Silver/raw histórico estrutural `1930-2022`

**Objetivo**

- publicar o backbone histórico consumível, mesmo sem depth rica em todas as edições

**Escopo**

- `silver.wc_fixtures`
- `silver.wc_stages`
- `silver.wc_groups`
- `silver.wc_group_standings`
- `silver.wc_coaches` ou equivalente
- publicação em:
  - `raw.fixtures`
  - `raw.standings_snapshots`
  - `raw.team_coaches`

**Validação**

- 22 edições publicadas no backbone
- nenhuma orfandade lógica
- coverage manifest por edição/domínio

**Blocker real**

- grain inconsistente entre standings históricos e grupos/stages de edições antigas

---

### `B6` — Lineups e events históricos parciais via Fjelstul

**Objetivo**

- maximizar o dado histórico disponível sem falsear completude

**Escopo**

- `1970+`: usar `player_appearances`, `goals`, `bookings`, `substitutions`
- `<1970`: registrar `PROVIDER_COVERAGE_GAP` explícito

**Saída**

- `silver.wc_lineups` parcial histórica
- `silver.wc_match_events` discreto histórico
- publicação raw só onde a semântica for compatível

**Validação**

- cobertura declarada por edição
- nenhum `NULL` silencioso mascarando gap

**Blocker real**

- tentativa de vender lineup/event coverage pré-1970 como completo

---

### `B7` — Estatísticas derivadas `2018/2022`

**Objetivo**

- capturar a maior profundidade disponível de fato

**Escopo**

- derivar de StatsBomb:
  - `match_statistics`
  - `fixture_player_statistics`
- apenas em `2018` e `2022`

**Validação**

- `2018` e `2022` com domains derivados completos
- nada fora de `2018/2022`
- Kaggle, se usado, apenas como check externo de `2022`

**Blocker real**

- derivação sem contrato lossless suficiente no silver

---

### `B8` — StatsBomb histórico sampled enrichment

**Objetivo**

- aproveitar o extra disponível sem mentir cobertura de edição

**Escopo**

- `1958`, `1962`, `1970`, `1974`, `1986`, `1990`
- enrichment só por partida publicada no snapshot

**Regra**

- não entra como “edição coberta”
- entra como `PARTIAL_MATCH_SAMPLE`

**Validação**

- contagens exatas:
  - `1958 = 2`
  - `1962 = 1`
  - `1970 = 6`
  - `1974 = 6`
  - `1986 = 3`
  - `1990 = 1`

**Blocker real**

- qualquer camada tentando promover sample para completude edition-wide

---

## 6. Ordem recomendada

1. `B0` — generalizar fundação multi-edição
2. `B1` — catálogo/season seeds da Copa
3. `B2` — bronze histórico estrutural Fjelstul
4. `B3` — bootstrap canônico histórico
5. `B5` — silver/raw estrutural `1930-2022`
6. `B4` — ativação full de `2018`
7. `B6` — lineups/events históricos discretos Fjelstul
8. `B7` — estatísticas derivadas `2018/2022`
9. `B8` — sampled enrichment StatsBomb histórico

**Justificativa**

- maximiza primeiro a cobertura histórica real
- preserva `2022`
- adiciona depth rica depois, onde ela existe de verdade
- evita começar por `2018` e deixar `1930-2014` ainda vazio no backbone

---

## 7. Leituras operacionais fixas

### O que conta como concluído

- só conta como concluído o que tiver:
  - snapshot local
  - carga no banco
  - validação objetiva
  - rerun idempotente

### O que não conta como concluído

- “a fonte existe”
- “o desenho já é compatível”
- “o snapshot está disponível no upstream”
- “o plano fala que depois entra”

### Regra de coverage

- `2018` e `2022` podem atingir depth rica real
- `1930-2014` podem atingir backbone estrutural completo
- históricos sampled do StatsBomb nunca podem ser promovidos a edição completa

---

## 8. Próximo passo seguro

O próximo passo correto é **executar só o `B0`**:

- generalizar snapshot gate
- remover hardcode `2022-only` dos serviços/DAGs da Copa
- preservar `2022` verde

Sem isso, a ingestão geral `1930-2022` nasce com retrabalho garantido.
