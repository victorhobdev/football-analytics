# Data Warehouse (DW) e Processos ETL no Football Analytics

## Tema principal

Este documento explica como o projeto **Football Analytics** atende ao eixo **Data Warehouse (DW) e Processos ETL**, solicitado na disciplina de Banco de Dados III.

O objetivo do trabalho é demonstrar a construção de uma solução de **Business Intelligence (BI)** usando dados reais, com organização analítica dos dados, processos de extração, transformação e carga, modelagem dimensional e consultas OLAP para geração de insights.

No projeto, esses conceitos aparecem de forma prática. O Football Analytics coleta, organiza, transforma e publica dados de futebol em uma base analítica PostgreSQL, disponibilizando essas informações para uma API, uma interface web e ferramentas de BI como o Metabase.

---

## 1. Visão geral do projeto

O Football Analytics é uma plataforma de análise de futebol que reúne dados de competições, temporadas, partidas, times, jogadores, rankings, mercado e Copa do Mundo.

A solução não é apenas uma aplicação visual. Ela possui uma arquitetura de dados composta por:

- banco PostgreSQL para armazenamento analítico;
- schemas separados para dados brutos, controle e consumo;
- scripts de ingestão e tratamento de dados;
- modelos dbt para transformação e modelagem analítica;
- Airflow para orquestração de processos;
- API FastAPI para disponibilização dos dados;
- frontend Next.js para navegação e análise;
- Metabase para exploração BI.

Com isso, o projeto atende ao requisito de construir uma solução de BI com dados reais, pois transforma dados operacionais e históricos de futebol em uma base consultável e analítica.

---

## 2. Data Warehouse (DW)

O **Data Warehouse** é o componente responsável por armazenar dados organizados para análise. Diferente de um banco transacional comum, o DW é estruturado para responder perguntas de negócio, gerar indicadores e permitir consultas agregadas.

No Football Analytics, o DW é implementado sobre **PostgreSQL** e organizado em camadas lógicas por meio de schemas.

### 2.1 Schemas principais

| Schema | Função no projeto |
| --- | --- |
| `raw` | Armazena dados brutos ou próximos da origem, como partidas, eventos, estatísticas, temporadas e dados específicos da Copa do Mundo. |
| `mart` | Contém os dados tratados e prontos para consumo analítico, incluindo tabelas fato, dimensões e sumarizações. |
| `control` | Guarda tabelas de controle, mapeamentos, catálogos, snapshots e filas de revisão. |
| `mart_control` | Define configurações de publicação, recortes de competição e temporada usados na camada de consumo. |

Na base local restaurada, foram observadas as seguintes quantidades aproximadas:

| Schema | Quantidade de tabelas |
| --- | ---: |
| `raw` | 37 |
| `mart` | 50 |
| `control` | 12 |
| `mart_control` | 2 |

Essa divisão mostra que o projeto separa corretamente:

- dados de origem;
- dados tratados;
- dados de controle;
- dados prontos para análise e publicação.

---

## 3. Modelagem Dimensional

A **modelagem dimensional** é uma técnica usada em Data Warehouses para facilitar consultas analíticas. Ela organiza os dados em:

- **tabelas fato**, que armazenam eventos mensuráveis;
- **tabelas dimensão**, que descrevem o contexto desses eventos.

No Football Analytics, a camada `mart` segue esse conceito.

### 3.1 Tabelas dimensão

As dimensões representam entidades usadas para filtrar, agrupar e contextualizar análises.

Exemplos encontrados no projeto:

- `mart.dim_competition`: dimensão de competições;
- `mart.dim_team`: dimensão de times;
- `mart.dim_player`: dimensão de jogadores;
- `mart.dim_coach`: dimensão de técnicos;
- `mart.dim_date`: dimensão de datas;
- `mart.dim_venue`: dimensão de estádios/localidades;
- `mart.dim_stage`: dimensão de fases;
- `mart.dim_round`: dimensão de rodadas;
- `mart.dim_group`: dimensão de grupos;
- `mart.dim_tie`: dimensão de confrontos eliminatórios.

Essas dimensões permitem responder perguntas como:

- quais jogadores mais marcaram em uma competição;
- qual time teve melhor campanha em determinada temporada;
- como uma competição evoluiu por fase;
- quais partidas ocorreram em uma data, estádio ou rodada específica.

### 3.2 Tabelas fato

As tabelas fato registram ocorrências ou medições do domínio de futebol.

Exemplos encontrados no projeto:

- `mart.fact_matches`: fatos de partidas;
- `mart.fact_match_events`: eventos das partidas;
- `mart.fact_fixture_player_stats`: estatísticas de jogadores por partida;
- `mart.fact_fixture_lineups`: escalações;
- `mart.fact_group_standings`: classificações por grupo;
- `mart.fact_stage_progression`: progressão por fase;
- `mart.fact_tie_results`: resultados de confrontos eliminatórios.

Essas tabelas permitem calcular métricas como:

- total de partidas;
- gols por competição;
- aproveitamento de times;
- eventos por partida;
- estatísticas individuais de jogadores;
- rankings de desempenho.

---

## 4. Star Schema e Snowflake

O projeto atende ao requisito de criação de esquema **Star Schema** ou **Snowflake**.

### 4.1 Star Schema

No Star Schema, uma tabela fato central se relaciona diretamente com várias dimensões.

Exemplo conceitual no Football Analytics:

```text
dim_competition
dim_date
dim_team
dim_venue
dim_stage
dim_round
        \ 
         fact_matches
        /
dim_player
dim_coach
```

Nesse caso, `fact_matches` funciona como fato central para análise de partidas, conectando informações de competição, data, times, fase, rodada e local.

### 4.2 Snowflake

O projeto também apresenta características de Snowflake, pois algumas dimensões são refinadas em outras estruturas auxiliares.

Por exemplo, uma competição pode ser analisada por:

- temporada;
- fase;
- rodada;
- grupo;
- chave eliminatória;
- partida.

Essa organização permite uma navegação mais detalhada, sem concentrar todo o contexto em uma única tabela.

---

## 5. Processos ETL

ETL significa:

- **Extract**: extração dos dados;
- **Transform**: transformação, limpeza e padronização;
- **Load**: carga dos dados em uma base de destino.

No Football Analytics, o processo também pode ser visto como ELT em alguns pontos, pois parte dos dados é carregada no banco e transformada depois por modelos SQL/dbt.

### 5.1 Extração

A extração ocorre a partir de fontes e artefatos de dados de futebol.

Exemplos no projeto:

- dados de competições;
- dados de partidas;
- estatísticas de jogadores;
- eventos de partidas;
- dados históricos da Copa do Mundo;
- dados de mercado e transferências;
- snapshots e dumps de publicação.

Um exemplo prático usado localmente foi o delta da Copa do Mundo:

```text
artifacts/wc_delta_20260426.tgz
```

Esse arquivo contém CSVs que populam tabelas como:

- `raw.fixtures`;
- `raw.competition_seasons`;
- `raw.wc_goals`;
- `raw.wc_squads`;
- `raw.wc_match_events`;
- `raw.wc_bookings`;
- `raw.wc_substitutions`;
- `raw.wc_player_identity_map`;
- `raw.wc_team_identity_map`.

### 5.2 Transformação

A transformação é feita principalmente por:

- modelos dbt;
- scripts Python;
- SQL de migração;
- regras de padronização e identidade;
- processos de validação.

O diretório principal de transformação é:

```text
platform/dbt/models
```

Dentro dele existem camadas como:

- `staging`: padronização inicial dos dados;
- `intermediate`: transformações intermediárias;
- `marts`: modelos finais para análise;
- `analytics`: sumarizações e modelos voltados a consumo.

Exemplos de transformação:

- normalização de competições e temporadas;
- criação de dimensões;
- criação de fatos;
- cálculo de rankings;
- consolidação de eventos de partidas;
- compatibilização de identidades de times e jogadores;
- organização de dados históricos da Copa do Mundo.

### 5.3 Carga

A carga aparece em diferentes momentos do projeto:

- `dbmate` aplica migrações de banco;
- `pg_restore` restaura snapshots de serving;
- CSVs são carregados para tabelas `raw`;
- dbt materializa tabelas analíticas;
- dados finais são consumidos pela API e pelo Metabase.

Um exemplo de snapshot usado localmente:

```text
artifacts/football_serving_20260426.dump
```

Esse dump carrega uma base pronta para consumo, com dados de competições, jogadores, times e partidas.

Depois, o delta da Copa complementa os dados específicos da vertical histórica da Copa do Mundo.

---

## 6. Orquestração dos processos

O projeto possui suporte a orquestração com **Airflow**.

No arquivo `docker-compose.yml`, existem serviços como:

- `airflow-init`;
- `airflow-webserver`;
- `airflow-scheduler`.

Esses serviços indicam que o projeto foi preparado para executar processos recorrentes de dados, como ingestão, transformação e validação.

Além disso, o mesmo `docker-compose.yml` define:

- `postgres`: banco analítico;
- `dbmate`: migrações;
- `minio`: armazenamento de objetos;
- `metabase`: ferramenta BI;
- `airflow`: orquestração.

Essa composição reforça que o projeto possui uma arquitetura de dados completa, não apenas uma aplicação web isolada.

---

## 7. Business Intelligence (BI)

O projeto atende ao conceito de BI porque transforma dados em informação útil para análise.

As principais camadas de BI são:

- banco analítico PostgreSQL;
- tabelas dimensionais e fatos;
- API para consulta dos dados;
- interface web com páginas analíticas;
- Metabase para dashboards e exploração visual.

Na interface do Football Analytics, é possível explorar:

- competições;
- temporadas;
- rankings;
- times;
- jogadores;
- partidas;
- comparativos;
- mercado;
- Copa do Mundo.

Essas telas funcionam como uma camada de BI aplicada ao domínio futebolístico, permitindo análise de desempenho, histórico e comparação entre entidades.

---

## 8. Análise OLAP

OLAP significa **Online Analytical Processing**. Esse tipo de análise permite consultar grandes volumes de dados em diferentes níveis de agregação.

O projeto permite operações OLAP como:

- **Roll-up**: subir o nível de detalhe;
- **Drill-down**: descer o nível de detalhe;
- **Slice/Dice**: filtrar e combinar recortes;
- **Pivot**: reorganizar métricas em colunas comparativas.

### 8.1 Roll-up

Exemplo: agrupar partidas e gols por competição.

```sql
select
  competition_key,
  count(*) as partidas,
  sum(coalesce(home_goals, 0) + coalesce(away_goals, 0)) as gols,
  round(avg(coalesce(home_goals, 0) + coalesce(away_goals, 0))::numeric, 2) as gols_por_partida
from raw.fixtures
where status_short = 'FT'
group by competition_key
order by partidas desc;
```

Esse exemplo faz roll-up porque resume várias partidas em métricas por competição.

### 8.2 Drill-down

Exemplo: sair do nível de competição e detalhar por temporada.

```sql
select
  competition_key,
  season_label,
  count(*) as partidas,
  sum(coalesce(home_goals, 0) + coalesce(away_goals, 0)) as gols
from raw.fixtures
where competition_key = 'fifa_world_cup_mens'
group by competition_key, season_label
order by season_label;
```

Esse exemplo faz drill-down porque detalha a Copa do Mundo por edição/temporada.

### 8.3 Pivot

Exemplo: comparar temporadas em colunas.

```sql
select
  competition_key,
  count(*) filter (where season_label = '2021') as temporada_2021,
  count(*) filter (where season_label = '2022') as temporada_2022,
  count(*) filter (where season_label = '2023') as temporada_2023,
  count(*) filter (where season_label = '2024') as temporada_2024,
  count(*) filter (where season_label = '2025') as temporada_2025
from raw.fixtures
group by competition_key
order by competition_key;
```

Esse exemplo reorganiza linhas em colunas comparativas.

### 8.4 Slice/Dice

Exemplo: filtrar a Copa de 2022 e listar artilheiros.

```sql
select
  player_name,
  team_name,
  count(*) as gols
from raw.wc_goals
where competition_key = 'fifa_world_cup_mens'
  and season_label = '2022'
  and is_own_goal = false
group by player_name, team_name
order by gols desc, player_name
limit 10;
```

Esse exemplo faz slice/dice porque recorta uma competição, uma temporada e uma métrica específica.

---

## 9. Evidências concretas do projeto

Durante a execução local do projeto, foram observados os seguintes números:

| Métrica | Valor |
| --- | ---: |
| Competições no mart | 14 |
| Times no mart | 602 |
| Jogadores no mart | 22.516 |
| Partidas no mart | 14.193 |
| Edições da Copa do Mundo | 22 |
| Partidas da Copa do Mundo | 964 |
| Gols da Copa do Mundo | 2.720 |
| Registros de elenco da Copa | 10.973 |
| Eventos da Copa do Mundo | 534.745 |

Esses números mostram que o projeto trabalha com uma base real e suficientemente rica para análises BI e OLAP.

---

## 10. Como explicar o funcionamento do projeto

Uma forma simples de apresentar o fluxo é:

```text
Fontes de dados de futebol
        ↓
Extração e carga na camada raw
        ↓
Transformações com scripts, SQL e dbt
        ↓
Criação de dimensões e fatos na camada mart
        ↓
Publicação em API e Metabase
        ↓
Análise em dashboards, rankings e telas do produto
```

Em termos de arquitetura:

1. Os dados entram em formato bruto na camada `raw`.
2. As transformações limpam, padronizam e relacionam os dados.
3. A camada `mart` publica tabelas analíticas.
4. A API FastAPI consulta essas tabelas.
5. O frontend Next.js apresenta rankings, perfis e páginas analíticas.
6. O Metabase permite criar dashboards e consultas de BI.

---

## 11. Conclusão

O projeto **Football Analytics** atende aos conceitos de **Data Warehouse (DW) e Processos ETL** porque possui:

- dados reais de futebol;
- banco analítico PostgreSQL;
- separação em camadas `raw`, `mart`, `control` e `mart_control`;
- modelagem dimensional com tabelas fato e dimensão;
- características de Star Schema e Snowflake;
- processos de extração, transformação e carga;
- uso de dbt, Airflow, dbmate, scripts e dumps;
- ferramenta BI com Metabase;
- consultas OLAP possíveis sobre competições, temporadas, times, jogadores, partidas e eventos.

Portanto, para a disciplina, o projeto pode ser defendido como uma solução completa de BI com DW, ETL, modelagem dimensional e análise OLAP aplicada ao domínio de futebol.
