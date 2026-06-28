# Plano de expansao do Data Warehouse

Este plano transforma a pesquisa de fontes externas em uma rota executavel para
expandir o Data Warehouse do Football Analytics sem inflar necessariamente o
serving da aplicacao.

## Objetivo

O banco de serving atual e propositalmente enxuto. Para uso academico em Data
Warehouse, o crescimento deve acontecer principalmente nas camadas `raw`,
`staging` e `mart`, preservando o serving apenas para dados curados e usados
pela API/frontend.

Sucesso esperado:

- ampliar volume historico e geografico do DW;
- adicionar novos graos analiticos, como odds, clima, ratings, eventos e
  selecoes;
- demonstrar variedade de fontes, granularidade e modelagem dimensional;
- manter licenca, origem e confianca documentadas por fonte.

## Decisao arquitetural

Separar as fontes em tres aneis:

| Anel | Uso | Criterio |
| --- | --- | --- |
| Core aberto | Pode sustentar marts academicos e demonstracoes | Licenca clara como CC0, CC BY 4.0, ODbL ou equivalente |
| Analitico com ressalva | Pode entrar no DW local com governanca | Fonte util, mas licenca/ToS exige cuidado ou nao e totalmente explicita |
| Experimental restrito | Nao redistribuir e nao promover para serving | Dados derivados de scraping, ToS sensivel ou proveniencia heterogenea |

Toda ingestao nova deve registrar `source_name`, `source_url`,
`source_license`, `source_terms_reviewed_at`, `ingested_at`, `batch_id`,
`payload_hash`, `raw_record_id` e `confidence_status`.

## Fontes priorizadas

### 1. OpenFootball / football.db

Uso principal: ampliar cobertura de competicoes, temporadas e resultados.

Valor para o DW:

- muitas ligas e copas por pais;
- historico amplo;
- baixo risco juridico quando confirmado como CC0/dominio publico;
- bom esqueleto para `dim_competition`, `dim_season`, `dim_team` e
  `fact_match_result`.

Camadas sugeridas:

- `raw.openfootball_matches`;
- `raw.openfootball_teams`;
- `raw.openfootball_competitions`;
- `stg_openfootball_matches`;
- `mart.fact_external_match_results`;
- `mart.bridge_external_team_identity`.

Prioridade: alta.

### 2. martj42/international_results

Uso principal: historico profundo de selecoes masculinas desde 1872.

Valor para o DW:

- partidas internacionais;
- gols;
- decisoes por penaltis;
- torneios, cidades, paises e mando neutro;
- excelente para cruzar com a trilha da Copa do Mundo.

Camadas sugeridas:

- `raw.intl_results`;
- `raw.intl_goalscorers`;
- `raw.intl_shootouts`;
- `stg_intl_matches`;
- `mart.fact_national_team_match`;
- `mart.fact_national_team_goal`;
- `mart.fact_penalty_shootout`;
- `mart.dim_tournament`.

Prioridade: alta.

### 3. football-data.co.uk

Uso principal: resultados historicos, estatisticas de partida e odds.

Valor para o DW:

- CSVs simples;
- muitas ligas e temporadas;
- odds por bookmaker;
- arbitros e estatisticas em algumas competicoes;
- alto potencial de crescimento fisico e analitico.

Ressalva: tratar como uso academico/local ate validar licenca e termos com
cuidado.

Camadas sugeridas:

- `raw.football_data_uk_matches`;
- `raw.football_data_uk_odds`;
- `stg_football_data_uk_matches`;
- `mart.fact_match_odds_snapshot`;
- `mart.fact_bookmaker_quote`;
- `mart.fact_referee_match_stats`;
- `mart.dim_bookmaker`;
- `mart.dim_referee`.

Prioridade: alta, com gate juridico antes de redistribuir.

### 4. Wyscout public event dataset

Uso principal: granularidade fina de eventos.

Valor para o DW:

- milhoes de eventos;
- partidas, jogadores, times, competicoes, arbitros e tecnicos;
- bom para demonstrar fatos no grao de evento;
- adequado para analises por zona, tipo de acao, jogador, tempo e posse.

Camadas sugeridas:

- `raw.wyscout_events`;
- `raw.wyscout_matches`;
- `raw.wyscout_players`;
- `raw.wyscout_teams`;
- `raw.wyscout_referees`;
- `raw.wyscout_coaches`;
- `stg_wyscout_events`;
- `mart.fact_external_match_event`;
- `mart.fact_possession_action`;
- `mart.dim_event_type`;
- `mart.dim_referee`.

Prioridade: alta para sofisticacao analitica.

### 5. StatsBomb Open Data

Uso principal: eventos modernos, lineups e contexto tatico.

Valor para o DW:

- eventos detalhados;
- lineups;
- dados 360 em partidas selecionadas;
- otimo para analises de xG, finalizacoes, posse, pressao e sequencias.

Ressalva: manter termos da StatsBomb documentados no repo antes de ingestao.

Camadas sugeridas:

- `raw.statsbomb_competitions`;
- `raw.statsbomb_matches`;
- `raw.statsbomb_lineups`;
- `raw.statsbomb_events`;
- `raw.statsbomb_360`;
- `stg_statsbomb_events`;
- `mart.fact_external_match_event`;
- `mart.fact_shot_context`;
- `mart.fact_lineup_slot`;
- `mart.dim_event_type`.

Prioridade: alta para qualidade analitica, media para volume historico.

### 6. Meteostat

Uso principal: clima por partida.

Valor para o DW:

- adiciona dominio nao futebolistico com forte valor de BI;
- permite fatos por estacao, horario, estadio e kickoff;
- aumenta variedade sem contaminar o core esportivo.

Camadas sugeridas:

- `raw.meteostat_stations`;
- `raw.meteostat_hourly`;
- `raw.meteostat_daily`;
- `mart.dim_weather_station`;
- `mart.fact_match_weather_hourly`;
- `mart.fact_match_weather_daily`.

Prioridade: media-alta.

### 7. FiveThirtyEight Soccer SPI

Uso principal: ratings e probabilidades historicas.

Valor para o DW:

- previsoes jogo a jogo;
- ratings SPI;
- historico derivado para analise pre-jogo.

Ressalva: fonte historica encerrada em 2023, entao nao serve para atualizacao
futura.

Camadas sugeridas:

- `raw.fivethirtyeight_spi_matches`;
- `raw.fivethirtyeight_spi_rankings`;
- `mart.fact_match_prediction`;
- `mart.fact_team_rating_snapshot`.

Prioridade: media.

### 8. OpenLigaDB

Uso principal: ampliar resultados e tabelas de ligas via API aberta.

Valor para o DW:

- JSON via API;
- varias competicoes e temporadas;
- bom para calendario, resultados e standings simples.

Ressalva: validar qualidade antes de promover para mart, pois a base permite
edicoes comunitarias.

Prioridade: media.

### 9. Wikidata, Wikipedia e OpenStreetMap

Uso principal: enriquecimento semantico, identidade e geografia.

Valor para o DW:

- aliases multilingues;
- paises, cidades, estadios e coordenadas;
- ligacao semantica entre fontes;
- suporte para `bridge_entity_identity`.

Camadas sugeridas:

- `raw.wikidata_entities`;
- `raw.osm_stadiums`;
- `mart.dim_country`;
- `mart.dim_city`;
- `mart.dim_stadium`;
- `mart.bridge_entity_identity`;
- `mart.bridge_entity_alias`.

Prioridade: media, mas essencial para reconciliacao.

## Fontes experimentais ou com alto risco

### Transfermarkt-derived datasets

Valor:

- transferencias;
- valores de mercado;
- appearances;
- attendance;
- lineups;
- grande volume e formato amigavel.

Risco:

- origem ligada ao Transfermarkt, cujo ToS normalmente restringe scraping e
  copia automatizada.

Decisao recomendada:

- manter fora do serving;
- usar apenas em trilha experimental local;
- marcar como `usage_scope = experimental_not_for_redistribution`;
- revisar juridicamente antes de qualquer publicacao.

### worldfootballR, FBref e similares

Valor:

- dados ricos de FBref, Transfermarkt, Understat e Fotmob.

Risco:

- wrappers herdam os termos e restricoes dos sites de origem;
- scraping massivo pode ser contratualmente sensivel.

Decisao recomendada:

- usar para exploracao e validacao de modelo;
- nao tratar como fonte principal do DW sem politica explicita por origem.

## Modelo dimensional sugerido

Novos fatos:

- `fact_external_match_result`;
- `fact_external_match_event`;
- `fact_match_odds_snapshot`;
- `fact_bookmaker_quote`;
- `fact_national_team_match`;
- `fact_national_team_goal`;
- `fact_penalty_shootout`;
- `fact_team_rating_snapshot`;
- `fact_match_prediction`;
- `fact_match_weather_hourly`;
- `fact_match_weather_daily`;
- `fact_transfer_external`;
- `fact_player_market_value_snapshot`;
- `fact_travel_distance`.

Novas dimensoes:

- `dim_source`;
- `dim_bookmaker`;
- `dim_referee`;
- `dim_weather_station`;
- `dim_tournament`;
- `dim_country`;
- `dim_city`;
- `dim_stadium`;
- `dim_event_type`;
- `dim_external_provider`.

Pontes de identidade:

- `bridge_entity_identity`;
- `bridge_entity_alias`;
- `bridge_match_identity`;
- `bridge_team_identity`;
- `bridge_player_identity`;
- `bridge_competition_identity`.

## Ordem de execucao recomendada

### Onda 0 - Governanca minima

1. Criar `dim_source` e contrato de metadados de ingestao.
2. Definir statuses: `trusted`, `academic_local`, `experimental`,
   `blocked_for_redistribution`.
3. Criar padrao de nomes: `raw.<source>_*`, `stg_<source>_*`,
   `mart.fact_*`.
4. Criar testes dbt para unicidade, nao nulidade de chaves naturais e lineage
   de fonte.

### Onda 1 - Fontes abertas e faceis

1. OpenFootball.
2. martj42/international_results.
3. Meteostat.
4. OpenLigaDB.

Objetivo: crescer historico, selecoes, geografia e clima com baixo atrito.

### Onda 2 - Volume historico e odds

1. football-data.co.uk.
2. FiveThirtyEight SPI.
3. football-data.org apenas se os termos forem aceitaveis para o escopo local.

Objetivo: criar fatos de odds, previsao, arbitro e estatisticas de partida.

### Onda 3 - Eventos avancados

1. Wyscout public event dataset.
2. StatsBomb Open Data.

Objetivo: criar marts de evento, finalizacao, posse, lineups e contexto tatico.

### Onda 4 - Identidade e fontes sensiveis

1. Wikidata.
2. OpenStreetMap.
3. Transfermarkt-derived datasets somente em trilha experimental.
4. worldfootballR/FBref somente para exploracao controlada.

Objetivo: reconciliar identidades e avaliar dominios de mercado sem contaminar
serving ou publicacao.

## Proximo bloco executavel

O primeiro bloco pratico deve ser pequeno e verificavel:

1. Criar tabela de controle `control.external_data_sources`.
2. Criar DDL raw para `international_results`:
   - `raw.external_international_results`;
   - `raw.external_international_goalscorers`;
   - `raw.external_international_shootouts`.
3. Criar script de ingestao CSV idempotente.
4. Criar modelos dbt staging.
5. Criar marts:
   - `mart.fact_national_team_match`;
   - `mart.fact_national_team_goal`;
   - `mart.fact_penalty_shootout`.
6. Validar contagens, chaves naturais e range de datas.

Esse bloco e o melhor ponto de partida porque adiciona muito historico, tem
licenca aberta segundo a pesquisa, usa CSV simples e conversa diretamente com a
vertical da Copa do Mundo.

## Criterios de aceite por fonte

Uma fonte nova so deve passar de `raw` para `mart` quando:

- licenca e termos estiverem registrados;
- chaves naturais forem estaveis;
- duplicatas forem conhecidas ou resolvidas;
- contagens por arquivo/lote forem auditadas;
- entidades principais tiverem estrategia de identidade;
- marts tiverem testes dbt basicos;
- a fonte estiver classificada quanto a redistribuicao.

## Fora de escopo imediato

- jogar todo dado novo no serving;
- reescrever rotas do frontend para consumir fontes externas diretamente;
- tratar fontes com ToS sensivel como verdade publica;
- criar reconciliacao universal antes de validar uma primeira fonte simples.
