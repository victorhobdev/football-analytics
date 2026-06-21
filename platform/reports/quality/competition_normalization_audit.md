# Auditoria de Normalização de Competições

> **Data:** 2026-06-20  
> **Tipo:** Revisão + normalização do catálogo de competições  
> **Objetivo:** Eliminar duplicatas no produto (ex.: dois "Brasileirão Série A" na aba de competições), remover o badge "Em publicação" de cards externos, e consolidar 4 fontes de dados num único catálogo consistente.

---

## Sumário Executivo

O Football Analytics hoje ingere dados de **4 fontes distintas** (SportMonks, Transfermarkt, Elo Ratings, StatsBomb) mas **não possui uma camada de normalização ativa** que as una. O resultado é que a aba de Competições exibe até 3 cards para a mesma competição (ex.: Brasileirão Série A aparece como publicado, como Transfermarkt e como Elo), e todas as competições externas exibem um badge "Em publicação" sem serem clicáveis.

A infraestrutura de normalização **existe** (`control.competition_provider_map`, `control.competitions`, `api/context_registry`) mas está **vazia** para as fontes externas. A normalização do StatsBomb foi feita corretamente e serve como referência de padrão.

Este documento detalha: inventário completo de fontes, mapeamento de duplicatas reais, causa-raiz da fragmentação, infraestrutura existente, decisões de produto, e um plano de normalização camada a camada (dados → API → frontend).

---

## 1. Inventário de Fontes de Dados

### 1.1 Fonte 1 — SportMonks (Publicado)

| Dimensão | Valor |
|---|---|
| Tabelas raw | `raw.fixtures`, `raw.match_statistics`, `raw.fixture_lineups`, `raw.fixture_player_statistics`, `raw.match_events`, `raw.player_transfers`, `raw.competition_leagues`, `raw.competition_seasons` |
| Tabela fato publicada | `mart.fact_matches` |
| Competições publicadas | **31** (keys em `fact_matches.competition_key`) |
| Partidas totais | ~17.900 |
| Tabela dimensão | `mart.dim_competition` (chaveada por `league_id` SportMonks) |

**Competições publicadas (31 keys em `mart.fact_matches`):**

| # | competition_key | Nome (dim_competition) | Partidas | Temporadas | Origem primária |
|---:|---|---|---:|---:|---|
| 1 | `brasileirao_a` | Serie A | 1.900 | 5 | SportMonks |
| 2 | `brasileirao_b` | Serie B | 1.894 | 5 | SportMonks |
| 3 | `premier_league` | Premier League | 1.938 | 6 | SportMonks |
| 4 | `la_liga` | La Liga | 2.387 | 22 | SportMonks |
| 5 | `bundesliga` | Bundesliga | 1.258 | 5 | SportMonks |
| 6 | `serie_a_it` | Serie A | 1.902 | 6 | SportMonks |
| 7 | `ligue_1` | Ligue 1 | 1.749 | 5 | SportMonks |
| 8 | `primeira_liga` | — | 612 | 2 | SportMonks |
| 9 | `champions_league` | — | 943 | 22 | SportMonks |
| 10 | `libertadores` | — | 775 | 5 | SportMonks |
| 11 | `sudamericana` | — | 314 | 2 | SportMonks |
| 12 | `copa_do_brasil` | Copa do Brasil | 610 | 5 | SportMonks |
| 13 | `supercopa_do_brasil` | — | 1 | 1 | SportMonks |
| 14 | `fifa_world_cup_mens` | — | 964 | 22 | SportMonks |
| 15 | `fifa_intercontinental_cup` | — | 5 | 1 | SportMonks |
| 16 | `copa_america` | — | 32 | 1 | SportMonks |
| 17 | `african_cup_of_nations` | — | 52 | 1 | SportMonks |
| 18 | `copa_del_rey` | — | 3 | 3 | StatsBomb |
| 19 | `fa_womens_super_league` | — | 457 | 4 | StatsBomb |
| 20 | `frauen_bundesliga` | — | 132 | 1 | StatsBomb |
| 21 | `serie_a_women` | — | 130 | 1 | StatsBomb |
| 22 | `liga_f` | — | 240 | 1 | StatsBomb |
| 23 | `uefa_euro` | — | 102 | 2 | StatsBomb |
| 24 | `uefa_womens_euro` | — | 62 | 2 | StatsBomb |
| 25 | `fifa_womens_world_cup` | — | 116 | 2 | StatsBomb |
| 26 | `fifa_u20_world_cup` | — | 1 | 1 | StatsBomb |
| 27 | `major_league_soccer` | — | 6 | 1 | StatsBomb |
| 28 | `nwsl` | — | 173 | 2 | StatsBomb |
| 29 | `north_american_league` | — | 1 | 1 | StatsBomb |
| 30 | `liga_profesional_argentina` | — | 2 | 2 | StatsBomb |
| 31 | `indian_super_league` | — | 115 | 1 | StatsBomb |
| 32 | `uefa_europa_league` | — | 3 | 1 | StatsBomb |

> **Nota:** As linhas 18-32 são competições injetadas pelo StatsBomb Open Data via `UNION ALL` em `stg_matches.sql` (linhas 77-162). Elas possuem `league_id = 930000000000 + competition_id` (IDs acima de 930 bilhões para não colidir com SportMonks). O `competition_key` é mapeado via `canonical_competition_key` (campo da tabela `raw.statsbomb_matches`) com fallback hardcoded (`case competition_id when 35 then 'uefa_europa_league' ...` — ver seção 4.4).

**Registro frontend:** `SUPPORTED_COMPETITIONS` em `competitions.registry.ts` lista apenas 15 com definições visuais, mas o catálogo pode exibir qualquer chave com nome dinâmico.

---

### 1.2 Fonte 2 — Transfermarkt

| Dimensão | Valor |
|---|---|
| Tabelas raw | `raw.tm_competitions`, `raw.tm_games`, `raw.tm_clubs`, `raw.tm_players`, `raw.tm_transfers`, `raw.tm_appearances`, `raw.tm_game_events`, `raw.tm_game_lineups`, `raw.tm_player_valuations`, `raw.tm_club_games` |
| Competições com partidas | **67** |
| Total de partidas | ~59.000+ |
| ID primário | `competition_id` (TEXT, ex.: `"BRA1"`, `"GB1"`, `"CL"`) |
| Tabela de catálogo | `raw.tm_competitions` (colunas: competition_id, competition_code, name, type, sub_type, country_name, confederation) |

**Competições Transfermarkt com overlap com o publicado (10):**

| TM ID | Nome TM | País | Confederação | Equivalente publicado |
|---:|---|---|---|---|
| BRA1 | campeonato-brasileiro-serie-a | Brazil | amerika | `brasileirao_a` |
| GB1 | premier-league | England | europa | `premier_league` |
| ES1 | laliga | Spain | europa | `la_liga` |
| IT1 | serie-a | Italy | europa | `serie_a_it` |
| L1 | bundesliga | Germany | europa | `bundesliga` |
| FR1 | ligue-1 | France | europa | `ligue_1` |
| PO1 | liga-portugal | Portugal | europa | `primeira_liga` |
| CL | uefa-champions-league | — | europa | `champions_league` |
| COPA | copa-america | — | amerika | `copa_america` |
| AFCN | africa-cup-of-nations | — | afrika | `african_cup_of_nations` |

**Competições Transfermarkt adicionais genuínas (57):**

Incluem ligas de 2ª/3ª divisão, copas nacionais europeias, supercopas, ligas asiáticas, etc. Exemplos notáveis:

| TM ID | Nome | País | Tipo |
|---:|---|---|---|
| NL1 | eredivisie | Netherlands | domestic_league |
| BE1 | jupiler-pro-league | Belgium | domestic_league |
| TR1 | super-lig | Turkey | domestic_league |
| SC1 | scottish-premiership | Scotland | domestic_league |
| E1 | championship | England | domestic_league |
| E2 | league-one | England | domestic_league |
| E3 | league-two | England | domestic_league |
| D2 | 2-bundesliga (não listado, ver nota) | Germany | domestic_league |
| SP2 | segunda-división | Spain | domestic_league |
| I2 | serie-b (não listado) | Italy | domestic_league |
| KLUB | fifa-klub-wm | — | other |
| RUS | premier-liga | Russia | domestic_league |
| ARG1 | torneo-apertura | Argentina | domestic_league |

*(E mais ~45 competições adicionais incluindo copas nacionais, supercopas, ligas escandinavas, asiáticas, etc.)*

> **Nota:** A query de Transfermarkt no `home.py` filtra `where coalesce(gt.matches_count, 0) > 0`, então só competições com partidas real são incluídas. A tabela `raw.tm_games` tem ~59k linhas.

---

### 1.3 Fonte 3 — Elo Ratings

| Dimensão | Valor |
|---|---|
| Tabelas raw | `raw.elo_matches`, `raw.elo_ratings` |
| Divisões com partidas | **38** |
| Total de partidas | ~270.000+ |
| ID primário | `division` (TEXT, ex.: `"BRA"`, `"E0"`, `"D1"`) |
| Período coberto | Até 26 temporadas (ligas europeias principais), 13 temporadas (outras) |

**Divisões Elo com overlap com o publicado (31):**

| Division | Nome Elo | País | Equivalente publicado |
|---:|---|---|---|
| BRA | Brasileirão Série A | Brasil | `brasileirao_a` |
| E0 | Premier League | Inglaterra | `premier_league` |
| D1 | Bundesliga | Alemanha | `bundesliga` |
| SP1 | La Liga | Espanha | `la_liga` |
| I1 | Serie A | Itália | `serie_a_it` |
| F1 | Ligue 1 | França | `ligue_1` |
| P1 | Primeira Liga | Portugal | `primeira_liga` |
| N1 | Eredivisie | Holanda | *(sem pub)* — ver nota |
| B1 | Pro League | Bélgica | *(sem pub)* — ver nota |
| T1 | Süper Lig | Turquia | *(sem pub)* — ver nota |
| G1 | Super League | Grécia | *(sem pub)* — ver nota |
| SC0 | Scottish Premiership | Escócia | *(sem pub)* — ver nota |
| SC1 | Scottish Championship | Escócia | *(sem pub)* — ver nota |
| SC2 | Scottish League One | Escócia | *(sem pub)* — ver nota |
| SC3 | Scottish League Two | Escócia | *(sem pub)* — ver nota |
| AUT | Bundesliga | Áustria | *(sem pub)* — ver nota |
| DEN | Superliga | Dinamarca | *(sem pub)* — ver nota |
| FIN | Veikkausliiga | Finlândia | *(sem pub)* — ver nota |
| NOR | Eliteserien | Noruega | *(sem pub)* — ver nota |
| SWE | Allsvenskan | Suécia | *(sem pub)* — ver nota |
| RUS | Premier Liga | Rússia | *(sem pub)* — ver nota |
| ROM | SuperLiga | Romênia | *(sem pub)* — ver nota |
| POL | Ekstraklasa | Polônia | *(sem pub)* — ver nota |
| SUI | Super League | Suíça | *(sem pub)* — ver nota |
| IRL | League of Ireland | Irlanda | *(sem pub)* — ver nota |
| ARG | Primera División | Argentina | *(sem pub)* — ver nota |
| CHN | Chinese Super League | China | *(sem pub)* — ver nota |
| JAP | J1 League | Japão | *(sem pub)* — ver nota |
| MEX | Liga MX | México | *(sem pub)* — ver nota |
| USA | Major League Soccer | EUA | *(sem pub)* — ver nota |
| EC | CONMEBOL | América do Sul | *(sem pub)* — ver nota |

> **Nota:** ~18 desses 31 Elo divisions não têm equivalente no published (Eredivisie, Pro League, Süper Lig, ligas escocesas, etc.). Elas são "overlap" apenas entre Elo e Transfermarkt, não com o catálogo SportMonks.

**Divisões Elo adicionais genuínas (7):**

| Division | Nome | Tipo | Motivo |
|---:|---|---|---|
| E1 | Championship | 2ª divisão Inglaterra | Não existe no publicado nem no TM com matches |
| E2 | League One | 3ª divisão Inglaterra | Idem |
| E3 | League Two | 4ª divisão Inglaterra | Idem |
| D2 | 2. Bundesliga | 2ª divisão Alemanha | Idem |
| SP2 | Segunda División | 2ª divisão Espanha | Idem |
| I2 | Serie B | 2ª divisão Itália | Idem |
| F2 | Ligue 2 | 2ª divisão França | Idem |

> Essas 7 divisões são exclusivas do Elo. O TM pode ter dados equivalentes, mas sob IDs diferentes ou com 0 partidas no filtro.

---

### 1.4 Fonte 4 — StatsBomb Open Data

| Dimensão | Valor |
|---|---|
| Tabelas raw | `raw.statsbomb_matches`, `raw.statsbomb_events`, `raw.statsbomb_lineups`, `raw.statsbomb_three_sixty_frames`, `raw.statsbomb_three_sixty_freeze_frame`, `raw.statsbomb_competition_seasons` |
| Partidas diretas ingeridas | ~0 (matches não carregados diretamente) |
| Eventos promovidos de orphans | 962.185 |
| Lineups promovidos de orphans | 9.825 |
| Competições identificadas | ~15+ (com `canonical_competition_key` ou fallback mapeado) |
| Identidade | Mapeada via `canonical_competition_key` + `identity_status` na tabela `raw.statsbomb_matches` |
| Integração com produto | **Já normalizada** — entra em `mart.fact_matches` via `UNION ALL` em `stg_matches.sql` |

> **Status:** O StatsBomb já está devidamente normalizado no fluxo publicado. Não aparece como fonte separada no catálogo de competições. Serve como **referência de padrão** de normalização (ver seção 4.4).

---

## 2. Mapa de Duplicatas (Overlap)

### 2.1 Exemplo concreto — Brasileirão Série A

A consulta `_fetch_competitions` no `home.py` gera um card para cada `competition_key` distinto em `mart.fact_matches`. A consulta `_fetch_external_competitions` gera um card para cada linha de `tm_competitions` (com matches) e para cada `division` do Elo.

**Resultado no produto: 3 cards separados para a mesma competição**

```
Card 1: competitionKey = "brasileirao_a"
        competitionName = "Campeonato Brasileiro Série A"
        source = (omitted → treated as "published")
        publicationStatus = (omitted → treated as "published")
        matchesCount = 1.900, seasonsCount = 5
        status: clicável ✓
        → Fonte: SportMonks + StatsBomb (via fact_matches)

Card 2: competitionKey = "tm_bra1"
        competitionName = "Campeonato brasileiro serie a"
        source = "transfermarkt"
        publicationStatus = "external_ingested"
        matchesCount = 557, seasonsCount = 9
        status: NÃO clicável, badge "Em publicação"
        → Fonte: raw.tm_competitions + raw.tm_games

Card 3: competitionKey = "elo_bra"
        competitionName = "Brasileirão Série A"
        source = "eloratings"
        publicationStatus = "external_ingested"
        matchesCount = 4.850, seasonsCount = 13
        status: NÃO clicável, badge "Em publicação"
        → Fonte: raw.elo_matches
```

### 2.2 Exemplo concreto — Premier League

```
Card 1: "premier_league"    — publicado (1.938 partidas, 6 temporadas) → clicável
Card 2: "tm_gb1"            — transfermarkt "premier-league" (5.320, 26) → "Em publicação"
Card 3: "elo_e0"            — eloratings "Premier League" (9.410, 26) → "Em publicação"
```

### 2.3 Contagem total de duplicatas

| Fonte | Cards únicos no catálogo | Overlap com publicado | Adicionais genuínos |
|---|---:|---:|---:|
| Publicado (SportMonks + StatsBomb) | 31 | — | 31 |
| Transfermarkt | 67 | **10** | 57 |
| Elo Ratings | 38 | **31** (~13 apenas publicado) | ~25 (outra fonte) + 7 (exclusivo) |
| **Soma bruta (sem normalização)** | **136** | — | — |
| **Catálogo canônico esperado** | **~95** | 0 duplicatas | ~64 adicionais |

### 2.4 Matriz de sobreposição por competição

| Competição canônica | SportMonks | StatsBomb | TM ID | Elo Div | Cards visíveis hoje |
|---|:---:|:---:|:---:|:---:|:---:|
| Brasileirão Série A | ✓ | ✗ | BRA1 | BRA | **3** |
| Premier League | ✓ | ✗ | GB1 | E0 | **3** |
| La Liga | ✓ | ✗ | ES1 | SP1 | **3** |
| Serie A (Itália) | ✓ | ✗ | IT1 | I1 | **3** |
| Bundesliga | ✓ | ✗ | L1 | D1 | **3** |
| Ligue 1 | ✓ | ✗ | FR1 | F1 | **3** |
| Liga Portugal | ✓ | ✗ | PO1 | P1 | **3** |
| Champions League | ✓ | ✗ | CL | — | **2** |
| Copa América | ✓ | ✗ | COPA | — | **2** |
| Africa Cup of Nations | ✓ | ✗ | AFCN | — | **2** |
| Eredivisie | ✗ | ✗ | NL1 | N1 | **2** |
| Jupiler Pro League | ✗ | ✗ | BE1 | B1 | **2** |
| Süper Lig | ✗ | ✗ | TR1 | T1 | **2** |
| Scottish Premiership | ✗ | ✗ | SC1 | SC0 | **2** |
| Copa del Rey | ✗ | ✓ | CDR | — | **2** |
| Frauen Bundesliga | ✗ | ✓ | — | — | 1 |
| MLS | ✗ | ✓ | MLS1 | USA | **2** |
| Chinese Super League | ✗ | ✓ | CHN1 | CHN | **2** |
| Copa do Mundo FIFA | ✓ | — | — | — | 1 |
| ... | | | | | |

---

## 3. Causa-Raiz da Fragmentação

A duplicação não é um bug pontual — é a ausência de uma camada de normalização entre fontes externas e o catálogo publicado. Os 10 pontos abaixo documentam cada quebra na cadeia.

### 3.1 Camada de Dados

**[CR-1] `control.competition_provider_map` está VAZIA (0 linhas)**

Essa tabela foi projetada exatamente para mapear `(provider, provider_league_id) → competition_key`, mas nunca foi semeada para Transfermarkt ou Elo. A tabela existe com schema, constraints e FK para `control.competitions`, mas não tem dados.

> `db/migrations/20260329190000_control_competition_catalog_foundation.sql` — criação do schema  
> `api/src/routers/home.py` — não consulta essa tabela

**[CR-2] `control.competitions` cobre apenas 14 competições**

Apenas as competições "core" do SportMonks foram registradas. As 17 competições adicionais injetadas pelo StatsBomb (via `stg_matches.sql`) e todas as do TM/Elo não têm entrada. Isso significa que o catálogo canônico de referência está incompleto.

> 14 registros: `brasileirao_a`, `brasileirao_b`, `bundesliga`, `champions_league`, `copa_do_brasil`, `fifa_intercontinental_cup`, `la_liga`, `libertadores`, `ligue_1`, `premier_league`, `primeira_liga`, `serie_a_it`, `sudamericana`, `supercopa_do_brasil`

**[CR-3] `mart.dim_competition` não possui `competition_key`**

É construída a partir de `stg_matches.league_id` (SportMonks) e não possui coluna `competition_key`. O join com `fact_matches` é feito via `competition_sk = md5(concat('competition:', league_id))`. Isso funciona para SportMonks mas não para TM/Elo que não passam pelo `stg_matches`.

> `platform/dbt/models/marts/core/dim_competition.sql` — colunas: `competition_sk`, `league_id`, `league_name`, `country`, `updated_at`

**[CR-4] Tabelas de identidade externa existem mas estão vazias**

`control.tm_game_fixture_xref` (TM game → fixture local), `control.brasileirao_fixture_xref` (brasileirão → fixture local), e `control.tm_player_xref` foram criadas na migração `20260620052000` mas não receberam dados. Apenas o StatsBomb tem camada de identidade funcional (`mart.stg_statsbomb_match_identity`, `bridge_statsbomb_team_identity`, `bridge_statsbomb_player_identity`).

> `db/migrations/20260620052000_external_warehouse_datasets_foundation.sql` — criação das tabelas xref  
> `db/migrations/20260619180000_statsbomb_open_data_foundation.sql` — criação das tabelas statsbomb identity (populadas)

### 3.2 Camada API

**[CR-5] `_fetch_external_competitions` não faz crosswalk com o catálogo publicado**

No `api/src/routers/home.py:541-657`, a função consulta `raw.tm_competitions` e `raw.elo_matches` diretamente e gera IDs sintéticos (`tm:{competition_id}`, `elo:{division}`) sem verificar se a competição já existe no catálogo publicado. Não consulta `control.competition_provider_map`.

```python
# home.py:601 — TM card sem crosswalk
payload.append({
    "competitionId": f"tm:{row['competition_id']}",
    "competitionKey": f"tm_{str(row['competition_id']).strip().lower()}",
    ...
    "source": "transfermarkt",
    "publicationStatus": "external_ingested",
})

# home.py:632 — Elo card sem crosswalk
payload.append({
    "competitionId": f"elo:{division}",
    "competitionKey": f"elo_{division.lower()}",
    ...
    "source": "eloratings",
    "publicationStatus": "external_ingested",
})
```

**[CR-6] `context_registry._CANONICAL_COMPETITIONS` só cobre SportMonks**

Os `source_ids` no registro canônico são todos IDs numéricos SportMonks (ex.: `(71, 648)` para Brasileirão A). Não há mapeamento para códigos TM (`BRA1`) ou códigos Elo (`BRA`, `E0`). A função `get_canonical_competition_by_key()` só resolve por `competition_key` canônico — os keys sintéticos `tm_bra1` e `elo_bra` nunca resolvem.

> `api/src/core/context_registry.py:15-121`

**[CR-7] Dois arrays separados no response da API**

O endpoint `GET /api/v1/home` retorna `competitions` (publicado) e `externalCompetitions` (TM + Elo) como arrays separados no JSON. O frontend faz concatenação simples sem deduplicação.

```python
# home.py:795-800
return build_api_response({
    "archiveSummary": archive_summary,
    "competitions": competitions,
    "externalCompetitions": external_competitions,  # array separado
    "editorialHighlights": editorial_highlights,
})
```

### 3.3 Camada Frontend

**[CR-8] `competitions/page.tsx` faz merge cego de published + external**

Linhas 386-398: os dois arrays são mapeados para `CatalogCompetition` e concatenados sem verificar `competitionKey` duplicados.

```typescript
// competitions/page.tsx:386-398
const publishedCompetitions = useMemo(
  () => (homeQuery.data?.competitions ?? []).map(buildCatalogCompetition),
  [homeQuery.data?.competitions],
);
const externalCompetitions = useMemo(
  () => (homeQuery.data?.externalCompetitions ?? []).map(buildCatalogCompetition),
  [homeQuery.data?.externalCompetitions],
);
const allCompetitions = useMemo(
  () => [...publishedCompetitions, ...externalCompetitions],  // merge cego
  [externalCompetitions, publishedCompetitions],
);
```

**[CR-9] Badge "Em publicação" sempre renderizado para externos**

Linha 159: `buildCompetitionCardHref` retorna `null` quando `publicationStatus !== "published"`, impedindo navegação. Linha 269: `TableAction` exibe o badge "Em publicação" como fallback. Linha 369: o footer do card mobile também mostra "Em publicação".

```typescript
// competitions/page.tsx:158-172
function buildCompetitionCardHref(competition: CatalogCompetition): string | null {
  if (competition.publicationStatus !== "published") {
    return null;  // nunca gera link para externos
  }
  return buildCompetitionHubPath(competition.key);
}

function buildCompetitionPendingLabel(_competition: CatalogCompetition): string {
  return "Em publicação";  // texto exibido no card
}
```

**[CR-10] Home page usa só `competitions`, inconsistente com catálogo**

O `HomeExecutivePage.tsx:476` consome `homeQuery.data?.competitions` mas ignora `externalCompetitions`. Já a página de catálogo consome ambos. Isso gera inconsistência visual entre as duas páginas — a home mostra menos competições que o catálogo.

> `frontend/src/app/(platform)/(home)/HomeExecutivePage.tsx:476`

---

## 4. Infraestrutura de Normalização Existente

### 4.1 Tabelas de controle (prontas, mas parcialmente vazias)

| Tabela | Schema | Função | Linhas | Status |
|---|---|---|---:|---|
| `competitions` | `control` | Catálogo canônico de competições | 14 | Parcial — só SportMonks core |
| `competition_provider_map` | `control` | Crosswalk `(provider, provider_league_id) → competition_key` | 0 | **Vazia** |
| `season_catalog` | `control` | Catálogo de temporadas por provider | Populado | Parcial — Copa do Mundo |
| `competition_wiki_mapping` | `control` | URLs de referência Wikipedia | 0 | **Vazia** |
| `tm_game_fixture_xref` | `control` | Mapeamento TM game → fixture local | 0 | **Vazia** |
| `brasileirao_fixture_xref` | `control` | Mapeamento brasileirão → fixture local | 0 | **Vazia** |
| `tm_player_xref` | `control` | Mapeamento TM player → player local | 0 | **Vazia** |

**Schema de `competition_provider_map`:**

```sql
competition_key      TEXT NOT NULL  -- FK → control.competitions
provider             TEXT NOT NULL  -- ex.: 'transfermarkt', 'eloratings', 'fjelstul_worldcup'
provider_league_id   BIGINT NOT NULL  -- ID na fonte (note: TM usa TEXT IDs!)
provider_name        TEXT
is_active            BOOLEAN NOT NULL DEFAULT TRUE
UNIQUE (provider, provider_league_id)
```

> **Atenção:** `provider_league_id` é `BIGINT` mas os IDs do Transfermarkt são TEXT (ex.: `"BRA1"`, `"GB1"`). Isso precisa ser ajustado (mudar para TEXT ou usar hash numérico) antes de semear.

### 4.2 Registro canônico da API

| Componente | Arquivo | Cobertura |
|---|---|---|
| `_CANONICAL_COMPETITIONS` | `api/src/core/context_registry.py:15-121` | 15 competições SportMonks com `source_ids` |
| `get_canonical_competition_by_key()` | idem:144-150 | Lookup por key |
| `expand_competition_ids_for_query()` | idem:161-165 | Expansão de source_ids |
| `normalize_competition_id()` | idem:168-172 | Normaliza para ID canônico |
| `build_canonical_context()` | idem:192-216 | Constrói contexto com nome e temporada |

**Estrutura do `CanonicalCompetition`:**

```python
@dataclass(frozen=True)
class CanonicalCompetition:
    competition_id: int          # ID canônico (SportMonks)
    competition_key: str         # Key canônica (ex.: "brasileirao_a")
    default_name: str            # Nome exibido
    source_ids: tuple[int, ...]  # IDs SportMonks equivalentes
    season_calendar: str         # "annual" ou "split_year"
```

Os `source_ids` são exclusivamente inteiros SportMonks. Não há espaço para códigos TM (`BRA1`) ou códigos Elo (`BRA`).

### 4.3 Registro de competições do frontend

| Componente | Arquivo | Cobertura |
|---|---|---|
| `SUPPORTED_COMPETITIONS` | `frontend/src/config/competitions.registry.ts:45-238` | 15 definições com nome, país, região, tipo, escopo, asset visual |
| `getCompetitionByKey()` | idem:245-248 | Lookup por key |
| `getCompetitionById()` | idem:240-243 | Lookup por id |

O frontend pode renderizar qualquer competição com nome dinâmico (fallback usando iniciais do nome), mas as 15 definições no registry fornecem dados curados (shortName, visualAssetId, country).

### 4.4 Padrão de normalização do StatsBomb (referência)

O StatsBomb demonstra a normalização **correta** e serve como padrão a replicar para TM e Elo.

**Passo 1 — Ingestão com identidade:**

A tabela `raw.statsbomb_matches` possui campos de identidade:

```sql
competition_id              BIGINT NOT NULL      -- ID original StatsBomb
canonical_competition_key   TEXT                 -- Key canônica no produto
identity_status             TEXT NOT NULL        -- 'new_external_match' etc.
identity_confidence         NUMERIC(5,4)
identity_reason             TEXT
```

**Passo 2 — Mapeamento no dbt (`stg_matches.sql:96-118`):**

```sql
-- Segunda branch do UNION ALL em stg_matches.sql (linhas 77-162)
-- Mapeia StatsBomb competition_id → competition_key canônico
competition_key = coalesce(
    canonical_competition_key,                    -- campo da tabela (override manual)
    case competition_id
        when 35 then 'uefa_europa_league'        -- fallback hardcoded
        when 37 then 'fa_womens_super_league'
        when 44 then 'major_league_soccer'
        -- ... 17 mapeamentos total
        else null
    end
)
```

**Passo 3 — IDs não-colidentes:**

```sql
-- Prefixo alto para evitar conflitos com SportMonks IDs
930000000000 + competition_id as league_id,      -- ex.: 930000000035 = UEFA Europa League
930000000000 + home_team_id as home_team_id,
```

**Passo 4 — Entrada via `mart.fact_matches`:**

Como `stg_matches` faz `UNION ALL`, partidas StatsBomb aparecem como qualquer outra partida publicada, com o `competition_key` correto. O `fact_matches` herda o `competition_key` e a contagem funciona normalmente.

**Resultado:** O StatsBomb enriquece o catálogo publicado de forma **invisível** — nenhum card duplicado, nenhuma referência separada.

### 4.5 Padrão de deduplicação do mercado (transferências)

O `api/src/routers/market.py` demonstra deduplicação cruzada entre SportMonks e Transfermarkt:

```sql
-- market.py:329-336 — transfermarkt_transfers exclui registros já cobertos
and not exists (
    select 1
    from sportmonks_transfers sm
    where sm.transfer_date = to_date(tm.transfer_date_raw, 'YYYY-MM-DD')
      and sm.normalized_player_name = _normalized_sql(tm.player_name)
)
```

**Padrão:** `NOT EXISTS` com match em `(data, nome normalizado)`. Funciona para transferências mas **não foi aplicado** para competições. Serve como referência de dedup na camada API.

---

## 5. Decisões de Produto

| Data | Decisão | Detalhamento |
|---|---|---|
| 2026-06-20 | **Merge de duplicatas:** enriquecer com a fonte mais rica | Quando uma competição existe em múltiplas fontes, o card único mostra os números da fonte com **maior cobertura histórica** (mais temporadas ou mais partidas). A fonte vencedora é indicada no selo. Ex.: Brasileirão Série A mostra 4.850 partidas / 13 temporadas (Elo vence) em vez de 1.900 / 5 (SportMonks). |
| 2026-06-20 | **Competições adicionais:** construir páginas genéricas | Competições externas sem equivalente publicado (ex.: Eredivisie, Jupiler Pro League) terão **páginas de detalhe genéricas**. Todos os cards serão clicáveis. Requer nova rota + endpoints. |
| 2026-06-20 | **Eliminar badge "Em publicação"** | O badge `publicationStatus: "external_ingested"` será removido. Todo card que entra no catálogo será clicável. Não existe mais estado intermediário. |
| 2026-06-20 | **StatsBomb como padrão de referência** | A normalização StatsBomb (canonical_competition_key + UNION ALL em stg_matches) é o modelo arquitetural a replicar para TM e Elo. |

---

## 6. Plano de Normalização — Camada a Camada

### 6.1 Camada de Dados (DB)

**Objetivo:** Semear `control.competition_provider_map` e expandir `control.competitions` com todas as fontes, criando o crosswalk canônico.

#### 6.1.1 Nova migração: Seed do catálogo canônico expandido

**Arquivo a criar:** `db/migrations/YYYYMMDDHHMMSS_competition_canonical_catalog_expansion.sql`

**A. Ajustar `provider_league_id` para suportar TEXT**

O campo atual é `BIGINT` mas TM usa IDs TEXT (`"BRA1"`, `"GB1"`). Opções:

- **Opção recomendada:** Adicionar coluna `provider_league_code TEXT` e usar essa para lookup textual
- **Alternativa:** Converter IDs TM para hash numérico

```sql
ALTER TABLE control.competition_provider_map
  ADD COLUMN provider_league_code TEXT;

-- Criar índice UNIQUE na combinação textual
CREATE UNIQUE INDEX uq_provider_league_code
  ON control.competition_provider_map (provider, provider_league_code)
  WHERE provider_league_code IS NOT NULL;
```

**B. Expandir `control.competitions` com competições adicionais**

```sql
-- Competições do StatsBomb que não estão no catálogo
INSERT INTO control.competitions (competition_key, competition_name, competition_type, country_name, confederation_name, tier, is_active, display_priority)
VALUES
  ('copa_del_rey',             'Copa del Rey',              'cup',             'Spain',        'UEFA',  NULL, TRUE, 105),
  ('fa_womens_super_league',   'FA WSL',                    'league',          'England',      'UEFA',  1,    TRUE, 140),
  ('frauen_bundesliga',        'Frauen Bundesliga',         'league',          'Germany',      'UEFA',  1,    TRUE, 140),
  ('serie_a_women',            'Serie A Femminile',         'league',          'Italy',        'UEFA',  1,    TRUE, 140),
  ('liga_f',                   'Liga F',                    'league',          'Spain',        'UEFA',  1,    TRUE, 140),
  ('uefa_euro',                'UEFA Euro',                 'cup',             NULL,           'UEFA',  NULL, TRUE, 70),
  ('uefa_womens_euro',         'UEFA Women's Euro',         'cup',             NULL,           'UEFA',  NULL, TRUE, 140),
  ('fifa_womens_world_cup',    'FIFA Women's World Cup',    'cup',             NULL,           'FIFA',  NULL, TRUE, 80),
  ('fifa_u20_world_cup',       'FIFA U-20 World Cup',       'cup',             NULL,           'FIFA',  NULL, TRUE, 140),
  ('major_league_soccer',      'Major League Soccer',       'league',          'United States','CONCACAF', 1, TRUE, 120),
  ('nwsl',                     'NWSL',                      'league',          'United States','CONCACAF', 1, TRUE, 140),
  ('north_american_league',    'North American League',      'league',          'United States', NULL,   1,    TRUE, 140),
  ('liga_profesional_argentina','Liga Profesional',         'league',          'Argentina',    'CONMEBOL', 1, TRUE, 110),
  ('indian_super_league',      'Indian Super League',       'league',          'India',        'AFC',   1,    TRUE, 130),
  ('uefa_europa_league',       'UEFA Europa League',        'cup',             NULL,           'UEFA',  NULL, TRUE, 75),
ON CONFLICT (competition_key) DO UPDATE SET
  competition_name = EXCLUDED.competition_name,
  updated_at = now();

-- Competições adicionais do TM/Elo (que não têm equivalente SportMonks)
-- Exemplos:
INSERT INTO control.competitions (competition_key, competition_name, competition_type, country_name, confederation_name, tier, is_active, display_priority)
VALUES
  ('eredivisie',           'Eredivisie',              'league', 'Netherlands', 'UEFA', 1, TRUE, 120),
  ('jupiler_pro_league',   'Jupiler Pro League',      'league', 'Belgium',     'UEFA', 1, TRUE, 125),
  ('championship',          'Championship',            'league', 'England',     'UEFA', 2, TRUE, 130),
  ('league_one',           'League One',              'league', 'England',     'UEFA', 3, TRUE, 135),
  ('league_two',           'League Two',              'league', 'England',     'UEFA', 4, TRUE, 136),
  ('bundesliga_2',         '2. Bundesliga',           'league', 'Germany',     'UEFA', 2, TRUE, 130),
  ('segunda_division',     'Segunda División',        'league', 'Spain',       'UEFA', 2, TRUE, 130),
  ('serie_b',              'Serie B',                 'league', 'Italy',       'UEFA', 2, TRUE, 130),
  ('ligue_2',              'Ligue 2',                 'league', 'France',      'UEFA', 2, TRUE, 130),
  ('super_lig',            'Süper Lig',               'league', 'Turkey',      'UEFA', 1, TRUE, 130),
  ('scottish_premiership', 'Scottish Premiership',    'league', 'Scotland',    'UEFA', 1, TRUE, 135),
  ('scottish_championship','Scottish Championship',   'league', 'Scotland',    'UEFA', 2, TRUE, 136),
  ('super_league_greece',  'Super League Greece',     'league', 'Greece',      'UEFA', 1, TRUE, 130),
  ('superliga_denmark',    'Superliga',               'league', 'Denmark',     'UEFA', 1, TRUE, 130),
  ('eliteserien',          'Eliteserien',             'league', 'Norway',      'UEFA', 1, TRUE, 130),
  ('allsvenskan',          'Allsvenskan',             'league', 'Sweden',      'UEFA', 1, TRUE, 130),
  ('premier_liga_russia',  'Premier Liga',            'league', 'Russia',      'UEFA', 1, TRUE, 130),
  ('superliga_romania',    'SuperLiga',               'league', 'Romania',     'UEFA', 1, TRUE, 130),
  ('ekstraklasa',          'Ekstraklasa',             'league', 'Poland',      'UEFA', 1, TRUE, 130),
  ('super_league_swiss',   'Super League',            'league', 'Switzerland', 'UEFA', 1, TRUE, 130),
  ('league_of_ireland',    'League of Ireland',       'league', 'Ireland',     'UEFA', 1, TRUE, 135),
  ('primera_division_arg', 'Primera División',        'league', 'Argentina',   'CONMEBOL', 1, TRUE, 110),
  ('chinese_super_league', 'Chinese Super League',    'league', 'China',      'AFC',   1, TRUE, 130),
  ('j1_league',            'J1 League',               'league', 'Japan',       'AFC',   1, TRUE, 130),
  ('liga_mx',              'Liga MX',                 'league', 'Mexico',      'CONCACAF', 1, TRUE, 120),
  ('conmebol',             'CONMEBOL',                'cup',    NULL,          'CONMEBOL', NULL, TRUE, 100)
ON CONFLICT (competition_key) DO UPDATE SET
  competition_name = EXCLUDED.competition_name,
  updated_at = now();
```

**C. Semear `competition_provider_map` com mapeamentos TM → canônico**

```sql
-- TM competicoes com overlap no publicado
INSERT INTO control.competition_provider_map (competition_key, provider, provider_league_id, provider_league_code, provider_name, is_active)
VALUES
  ('brasileirao_a',           'transfermarkt', 0, 'BRA1', 'Campeonato Brasileiro Série A', TRUE),
  ('premier_league',          'transfermarkt', 0, 'GB1',  'Premier League',              TRUE),
  ('la_liga',                 'transfermarkt', 0, 'ES1',  'La Liga',                    TRUE),
  ('serie_a_it',              'transfermarkt', 0, 'IT1',  'Serie A',                    TRUE),
  ('bundesliga',              'transfermarkt', 0, 'L1',   'Bundesliga',                 TRUE),
  ('ligue_1',                'transfermarkt', 0, 'FR1',  'Ligue 1',                   TRUE),
  ('primeira_liga',           'transfermarkt', 0, 'PO1',  'Liga Portugal',              TRUE),
  ('champions_league',        'transfermarkt', 0, 'CL',   'UEFA Champions League',      TRUE),
  ('copa_america',            'transfermarkt', 0, 'COPA', 'Copa América',               TRUE),
  ('african_cup_of_nations',  'transfermarkt', 0, 'AFCN', 'Africa Cup of Nations',       TRUE),
  -- TM competicoes adicionais (sem equivalente publicado)
  ('eredivisie',              'transfermarkt', 0, 'NL1',  'Eredivisie',                 TRUE),
  ('jupiler_pro_league',      'transfermarkt', 0, 'BE1',  'Jupiler Pro League',         TRUE),
  ('championship',             'transfermarkt', 0, 'E1',   'Championship',               TRUE),
  ('league_one',               'transfermarkt', 0, 'E2',   'League One',                 TRUE),
  ('league_two',               'transfermarkt', 0, 'E3',   'League Two',                 TRUE),
  ('ligue_2',                 'transfermarkt', 0, 'F2',   'Ligue 2',                    TRUE),
  ('super_lig',               'transfermarkt', 0, 'TR1',  'Süper Lig',                  TRUE),
  ('scottish_premiership',    'transfermarkt', 0, 'SC1',  'Scottish Premiership',        TRUE),
  ('primera_division_arg',    'transfermarkt', 0, 'ARG1', 'Torneo Apertura',            TRUE),
  ('chinese_super_league',    'transfermarkt', 0, 'CHN1', 'J1 League',                  TRUE),
  ('j1_league',               'transfermarkt', 0, 'JAP1', 'J1 League',                  TRUE),
  ('liga_mx',                 'transfermarkt', 0, 'MEX1', 'Liga MX Clausura',           TRUE),
  -- ... ~57 mapeamentos adicionais
ON CONFLICT (competition_key, provider) DO UPDATE SET
  provider_league_code = EXCLUDED.provider_league_code,
  provider_name = EXCLUDED.provider_name,
  is_active = EXCLUDED.is_active,
  updated_at = now();
```

**D. Semear mapeamentos Elo → canônico**

```sql
INSERT INTO control.competition_provider_map (competition_key, provider, provider_league_id, provider_league_code, provider_name, is_active)
VALUES
  ('brasileirao_a',           'eloratings', 0, 'BRA', 'Brasileirão Série A',  TRUE),
  ('premier_league',          'eloratings', 0, 'E0',  'Premier League',        TRUE),
  ('bundesliga',              'eloratings', 0, 'D1',  'Bundesliga',           TRUE),
  ('la_liga',                 'eloratings', 0, 'SP1', 'La Liga',              TRUE),
  ('serie_a_it',              'eloratings', 0, 'I1',  'Serie A',              TRUE),
  ('ligue_1',                 'eloratings', 0, 'F1',  'Ligue 1',             TRUE),
  ('primeira_liga',           'eloratings', 0, 'P1',  'Primeira Liga',        TRUE),
  ('eredivisie',              'eloratings', 0, 'N1',  'Eredivisie',           TRUE),
  ('jupiler_pro_league',      'eloratings', 0, 'B1',  'Pro League',           TRUE),
  ('super_lig',               'eloratings', 0, 'T1',  'Süper Lig',            TRUE),
  ('super_league_greece',     'eloratings', 0, 'G1',  'Super League Greece',   TRUE),
  ('scottish_premiership',    'eloratings', 0, 'SC0', 'Scottish Premiership', TRUE),
  ('scottish_championship',   'eloratings', 0, 'SC1', 'Scottish Championship',TRUE),
  ('championship',             'eloratings', 0, 'E1',  'Championship',          TRUE),
  ('league_one',               'eloratings', 0, 'E2',  'League One',           TRUE),
  ('league_two',               'eloratings', 0, 'E3',  'League Two',           TRUE),
  ('bundesliga_2',           'eloratings', 0, 'D2',  '2. Bundesliga',         TRUE),
  ('segunda_division',       'eloratings', 0, 'SP2', 'Segunda División',     TRUE),
  ('serie_b',                 'eloratings', 0, 'I2',  'Serie B',              TRUE),
  ('ligue_2',                 'eloratings', 0, 'F2',  'Ligue 2',              TRUE),
  ('superliga_denmark',       'eloratings', 0, 'DEN', 'Superliga',            TRUE),
  ('eliteserien',             'eloratings', 0, 'NOR', 'Eliteserien',           TRUE),
  ('allsvenskan',             'eloratings', 0, 'SWE', 'Allsvenskan',           TRUE),
  ('premier_liga_russia',     'eloratings', 0, 'RUS', 'Premier Liga',         TRUE),
  ('superliga_romania',       'eloratings', 0, 'ROM', 'SuperLiga',            TRUE),
  ('ekstraklasa',             'eloratings', 0, 'POL', 'Ekstraklasa',          TRUE),
  ('super_league_swiss',      'eloratings', 0, 'SUI', 'Super League',         TRUE),
  ('league_of_ireland',       'eloratings', 0, 'IRL', 'League of Ireland',     TRUE),
  ('primera_division_arg',     'eloratings', 0, 'ARG', 'Primera División',     TRUE),
  ('chinese_super_league',    'eloratings', 0, 'CHN', 'Chinese Super League',  TRUE),
  ('j1_league',               'eloratings', 0, 'JAP', 'J1 League',            TRUE),
  ('liga_mx',                 'eloratings', 0, 'MEX', 'Liga MX',              TRUE),
  ('major_league_soccer',     'eloratings', 0, 'USA', 'Major League Soccer',  TRUE),
  ('conmebol',                'eloratings', 0, 'EC',  'CONMEBOL',             TRUE)
ON CONFLICT (competition_key, provider) DO UPDATE SET
  provider_league_code = EXCLUDED.provider_league_code,
  provider_name = EXCLUDED.provider_name,
  is_active = EXCLUDED.is_active,
  updated_at = now();
```

**E. Mapeamento de profundidade (fonte mais rica)**

Para implementar "enriquecer com a fonte mais rica", consultar as contagens por fonte e determinar qual tem maior profundidade. Recomendação: implementar na camada API (Python), comparando counts das 3 fontes por competição_key e selecionando o máximo. Não requer nova tabela no DB.

---

### 6.2 Camada API

**Objetivo:** Refatorar `_fetch_external_competitions` para usar o crosswalk e mesclar em vez de listar separadamente.

#### 6.2.1 Refatorar `api/src/routers/home.py`

**A. Nova consulta: `_fetch_competition_source_depth()`**

Consulta `control.competition_provider_map` + `raw.tm_games` + `raw.elo_matches` para obter, por competição canônica, as métricas de profundidade por fonte.

**B. Refatorar `_fetch_competitions()` para unificar publicado + externo**

Em vez de dois métodos separados (`_fetch_competitions` + `_fetch_external_competitions`), ter um único método que:

1. Começa com o catálogo publicado (`mart.fact_matches`)
2. Para cada competição, enriquece com TM e Elo via crosswalk (se tiverem mais profundidade)
3. Adiciona competições adicionais do TM/Elo que não existem no publicado (via `competition_provider_map` LEFT JOIN com `fact_matches` retornando NULL)
4. Cada card sai com: `competitionKey`, `dominantSource` (qual fonte tem mais dados), `matchesCount`, `seasonsCount`
5. **Remove** `publicationStatus` do response

**C. Remover `externalCompetitions` do response**

```python
# ANTES (home.py:795-800):
return build_api_response({
    "archiveSummary": archive_summary,
    "competitions": competitions,
    "externalCompetitions": external_competitions,  ← REMOVER
    "editorialHighlights": editorial_highlights,
})

# DEPOIS:
return build_api_response({
    "archiveSummary": archive_summary,
    "competitions": unified_competitions,  # já inclui tudo normalizado
    "editorialHighlights": editorial_highlights,
})
```

**D. Remover `_infer_competition_catalog_metadata()` hardcodes**

As funções `_infer_competition_catalog_metadata` (linha 119), `_infer_transfermarkt_catalog_metadata` (linha 255) e `_infer_elo_catalog_metadata` (linha 283) contêm centenas de linhas de if/elif hardcodes. Com o crosswalk, os metadados vêm de `control.competitions` + lookup dinâmico.

#### 6.2.2 Expandir `api/src/core/context_registry.py`

- Adicionar `source_ids` textuais para TM/Elo (usando `provider_league_code`)
- Adicionar competições adicionais que hoje não existem no registro
- Possivelmente migrar de `source_ids: tuple[int, ...]` para `source_ids: tuple[str, ...]` para suportar códigos textuais

#### 6.2.3 Novos endpoints para competições adicionais (escopo posterior)

Para suportar páginas genéricas de detalhe:

- `GET /api/v1/competitions/{key}` — dados da competição (metadados)
- `GET /api/v1/competitions/{key}/seasons` — temporadas disponíveis por fonte
- `GET /api/v1/competitions/{key}/seasons/{season}/matches` — partidas por temporada

---

### 6.3 Camada Frontend

**Objetivo:** Eliminar duplicação visual, remover "Em publicação", criar páginas genéricas.

#### 6.3.1 Atualizar tipos

**Arquivo:** `frontend/src/features/home/types/home.types.ts`

```typescript
// REMOVER:
publicationStatus?: "published" | "external_ingested" | null;
externalCompetitions?: HomeCompetitionCard[];

// ADICIONAR:
dominantSource?: "published" | "transfermarkt" | "eloratings" | "statsbomb" | "multi" | null;
additionalSources?: string[];  // outras fontes com dados menores
```

**`HomePageData`:**

```typescript
// ANTES:
export interface HomePageData {
  archiveSummary: HomeArchiveSummary;
  competitions: HomeCompetitionCard[];
  externalCompetitions?: HomeCompetitionCard[];  // REMOVER
  editorialHighlights: HomeEditorialHighlight[];
}

// DEPOIS:
export interface HomePageData {
  archiveSummary: HomeArchiveSummary;
  competitions: HomeCompetitionCard[];  // único array, já normalizado
  editorialHighlights: HomeEditorialHighlight[];
}
```

#### 6.3.2 Refatorar `competitions/page.tsx`

**A. Remover separação published vs external (linhas 386-398):**

```typescript
// ANTES:
const publishedCompetitions = useMemo(
  () => (homeQuery.data?.competitions ?? []).map(buildCatalogCompetition),
  [homeQuery.data?.competitions],
);
const externalCompetitions = useMemo(
  () => (homeQuery.data?.externalCompetitions ?? []).map(buildCatalogCompetition),
  [homeQuery.data?.externalCompetitions],
);
const allCompetitions = useMemo(
  () => [...publishedCompetitions, ...externalCompetitions],
  [externalCompetitions, publishedCompetitions],
);

// DEPOIS:
const allCompetitions = useMemo(
  () => (homeQuery.data?.competitions ?? []).map(buildCatalogCompetition),
  [homeQuery.data?.competitions],
);
```

**B. Atualizar tipo `CatalogCompetition` (linha 22-37):**

```typescript
// REMOVER:
publicationStatus: "published" | "external_ingested";

// ADICIONAR:
dominantSource: "published" | "transfermarkt" | "eloratings" | "statsbomb" | "multi";
```

**C. Remover badge "Em publicação" (linhas 158-172, 269, 369):**

- Remover `buildCompetitionCardHref` que retorna `null` para externos
- Remover `buildCompetitionPendingLabel` ("Em publicação")
- Remover `TableAction` que renderiza o badge
- Tornar TODOS os cards clicáveis com link para página de detalhe

**D. Atualizar `getCompetitionSourceLabel` (linhas 88-98):**

```typescript
function getCompetitionSourceLabel(source: CatalogCompetition['dominantSource']): string {
  switch (source) {
    case 'transfermarkt': return 'Transfermarkt';
    case 'eloratings': return 'Elo+Matches';
    case 'statsbomb': return 'StatsBomb';
    case 'multi': return 'Multi-fonte';
    default: return 'Publicado';
  }
}
```

**E. Atualizar header tags (linha 497):**

Remover `{formatWholeNumber(externalCompetitions.length)} externas` do header. Substituir por breakdown por fonte dominante.

#### 6.3.3 Criar página genérica de competição

**Arquivo a criar:** `frontend/src/app/(platform)/competitions/[key]/page.tsx`

Página genérica que:
- Recebe `key` como parâmetro de rota
- Consulta API para metadados da competição
- Lista temporadas disponíveis
- Permite drill-down para partidas

#### 6.3.4 Refatorar `HomeExecutivePage.tsx`

- Consumir o array unificado (sem mudanças significativas se `competitions` já estiver normalizado)
- Garantir que competições adicionais (ex.: Eredivisie) apareçam nos cards de Nacionais/Continentais com os mesmos metadados

---

## 7. Mapa de Arquivos

### 7.1 Novos arquivos

| Arquivo | Descrição | Prioridade |
|---|---|---:|
| `db/migrations/YYYYMMDD_competition_canonical_catalog_expansion.sql` | Seed do crosswalk completo (~105 mapeamentos) | Alta |
| `frontend/src/app/(platform)/competitions/[key]/page.tsx` | Página genérica de competição | Média |
| `api/src/routers/competitions.py` | Novo router para detalhe de competição (opcional) | Média |

### 7.2 Arquivos existentes a modificar

| Arquivo | Mudança | Linhas afetadas |
|---|---|---|
| `api/src/routers/home.py` | Unificar `_fetch_competitions` + `_fetch_external_competitions`; remover `externalCompetitions` do response; usar crosswalk | 356-657, 788-809 |
| `api/src/core/context_registry.py` | Expandir `_CANONICAL_COMPETITIONS` com entries TM/Elo | 15-121 |
| `frontend/src/features/home/types/home.types.ts` | Trocar `publicationStatus`/`externalCompetitions` por `dominantSource` | 23-24, 61 |
| `frontend/src/app/(platform)/competitions/page.tsx` | Remover merge cego; remover "Em publicação"; tornar todos clicáveis | 22-37, 158-172, 269, 369, 386-398, 497 |
| `frontend/src/app/(platform)/(home)/HomeExecutivePage.tsx` | Consumir array unificado (se necessário) | 476 |
| `frontend/src/config/competitions.registry.ts` | Expandir `SUPPORTED_COMPETITIONS` com competições adicionais (opcional) | 45-238 |

### 7.3 Arquivos NÃO modificados

| Arquivo | Razão |
|---|---|
| `platform/dbt/models/staging/stg_matches.sql` | StatsBomb já normalizado — funciona como referência, não precisa de mudança |
| `api/src/routers/market.py` | Transferências já fazem dedup cruzada — não afetado |
| `platform/dbt/models/marts/core/dim_competition.sql` | Continua servindo SportMonks — não precisa de `competition_key` |
| `frontend/src/features/market/components/MarketPageContent.tsx` | Não consome competições — não afetado |

---

## 8. Impacto Esperado

### 8.1 Catálogo de competições

| Métrica | Antes | Depois |
|---|---:|---:|
| Competições publicadas | 31 | 31 |
| Competições externas (TM + Elo) | 105 | 0 (mescladas) |
| Competições adicionais (canônicas novas) | 0 | ~64 |
| **Total no catálogo** | **136** (com duplicatas) | **~95** (sem duplicatas) |
| Duplicatas visíveis | ~41+ | **0** |
| Cards com "Em publicação" | 105 | **0** |
| Cards clicáveis | 31 | **~95** |

### 8.2 Consistência do produto

| Aspecto | Antes | Depois |
|---|---|---|
| Home page mostra | 31 competições | ~95 competições |
| Catálogo mostra | 136 cards (com duplicatas) | ~95 cards (sem duplicatas) |
| Brasileirão Série A aparece | 3 vezes | 1 vez (enriquecido com Elo) |
| Premier League aparece | 3 vezes | 1 vez |
| Eredivisie aparece | 2 vezes (TM + Elo) | 1 vez |
| Fontes indicadas no card | "Publicado" / "Transfermarkt" / "Elo+Matches" separados | "Elo+Matches" (dominante) ou "Multi-fonte" |
| CTA no card | "Ver temporadas" (publicado) ou "Em publicação" (bloqueado) | "Ver temporadas" (todos) |

---

## 9. Referências de Código

| Arquivo:linha | Descrição |
|---|---|
| `api/src/routers/home.py:19-65` | Hardcodes `_TM_CONFEDERATION_LABELS` e `_ELO_DIVISION_NAMES` — devem vir do DB |
| `api/src/routers/home.py:119-227` | `_infer_competition_catalog_metadata()` — hardcodes de 14 competições published |
| `api/src/routers/home.py:255-280` | `_infer_transfermarkt_catalog_metadata()` — hardcodes de tipos TM |
| `api/src/routers/home.py:283-296` | `_infer_elo_catalog_metadata()` — lookup em `_ELO_DIVISION_NAMES` |
| `api/src/routers/home.py:356-538` | `_fetch_competitions()` — gera cards publicados |
| `api/src/routers/home.py:541-657` | `_fetch_external_competitions()` — gera cards TM + Elo separados |
| `api/src/routers/home.py:788-809` | `get_home_page()` — retorna dois arrays separados |
| `api/src/core/context_registry.py:15-121` | `_CANONICAL_COMPETITIONS` — registro canônico (SportMonks only) |
| `frontend/src/app/(platform)/competitions/page.tsx:22-37` | Tipo `CatalogCompetition` com `publicationStatus` e `source` |
| `frontend/src/app/(platform)/competitions/page.tsx:65-86` | `buildCatalogCompetition()` — mapeia card para tipo local |
| `frontend/src/app/(platform)/competitions/page.tsx:158-172` | `buildCompetitionCardHref()` e `buildCompetitionPendingLabel()` — lógica "Em publicação" |
| `frontend/src/app/(platform)/competitions/page.tsx:265-282` | `TableAction` — renderiza badge ou link |
| `frontend/src/app/(platform)/competitions/page.tsx:386-398` | Merge cego `[...published, ...external]` |
| `frontend/src/app/(platform)/competitions/page.tsx:497` | Header tag "externas" |
| `frontend/src/features/home/types/home.types.ts:23-24` | Tipos `source` e `publicationStatus` |
| `frontend/src/features/home/types/home.types.ts:61` | `externalCompetitions` no `HomePageData` |
| `frontend/src/app/(platform)/(home)/HomeExecutivePage.tsx:476` | Home consome só `competitions` |
| `frontend/src/config/competitions.registry.ts:45-238` | `SUPPORTED_COMPETITIONS` (15 definições) |
| `platform/dbt/models/staging/stg_matches.sql:96-118` | Mapeamento StatsBomb → competition_key (padrão de referência) |
| `platform/dbt/models/staging/stg_matches.sql:77-162` | UNION ALL StatsBomb branch em stg_matches |
| `platform/dbt/models/marts/core/dim_competition.sql:1-33` | Dimensão sem `competition_key` |
| `db/migrations/20260329190000_control_competition_catalog_foundation.sql` | Schema de `control.competitions` e `competition_provider_map` |
| `db/migrations/20260423000010_wc_control_catalog_seed.sql` | Exemplo de seed com `ON CONFLICT DO UPDATE` |
| `db/migrations/20260620052000_external_warehouse_datasets_foundation.sql` | Criação de tabelas raw externas (TM, Elo, Brasileirão) |
| `db/migrations/20260619180000_statsbomb_open_data_foundation.sql` | Criação de tabelas StatsBomb + identity |
| `api/src/routers/market.py:329-336` | Padrão de dedup cruzada (NOT EXISTS) — referência |

---

## 10. Histórico de Decisões

| Data | Decisão | Contexto e Razão |
|---|---|---|
| 2026-06-20 | **Merge:** enriquecer com a fonte mais rica | O card único mostra números da fonte com maior cobertura (mais temporadas/partidas). Preserva profundidade histórica sem double-counting. |
| 2026-06-20 | **Adicionais:** construir páginas genéricas | Todas as competições do catálogo terão página de detalhe, mesmo sem dados no mart publicado. Requer nova rota + endpoints. |
| 2026-06-20 | **Eliminar badge "Em publicação"** | Todo card no catálogo será clicável ou oculto. Não existe mais estado intermediário "em publicação". |
| 2026-06-20 | **StatsBomb como referência** | A normalização StatsBomb (`canonical_competition_key` + `UNION ALL` em `stg_matches`) é o modelo arquitetural a replicar. |
| 2026-06-20 | **Usar `control.competition_provider_map`** | A tabela já existe com schema e FK. Basta semear com dados. Não é necessário reinventar. |
| 2026-06-20 | **Mudar `provider_league_id` para TEXT** | TM usa IDs textuais (`"BRA1"`). Precisa de ajuste de schema ou coluna adicional. |
