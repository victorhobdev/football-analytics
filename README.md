# Football Analytics

Plataforma de consulta e navegação de dados de futebol — competições, temporadas, partidas, times, jogadores, rankings, transferências e Copa do Mundo em uma única interface.

[Repositório](https://github.com/victorhob1981/football-analytics)

---

## Contexto

Dados de futebol estão distribuídos entre múltiplas fontes (SportMonks, Transfermarkt, StatsBomb, etc.), cada uma com seu schema, cobertura e periodicidade. Este projeto consolida essas fontes em um banco analítico PostgreSQL e expõe os dados através de uma API FastAPI consumida por um frontend Next.js.

O objetivo é permitir a navegação entre entidades do futebol — de uma competição a uma partida, de um ranking a um perfil de jogador — sem perder o contexto de filtros aplicados.

---

## Arquitetura

```
APIs externas (SportMonks, API-Football)
       |
       v
   [Airflow] --> MinIO (bronze/silver) --> PostgreSQL (raw)
       |
       v
   [dbt] --> PostgreSQL (mart dimensional)
       |
       v
   [FastAPI BFF] <--> [Next.js frontend + Metabase BI]
```

### Camadas

1. **Ingestão** — Airflow DAGs extraem dados de APIs esportivas, armazenam JSON bruto no MinIO (bronze), transformam para Parquet (silver) e carregam no PostgreSQL (schema `raw`).
2. **Transformação** — dbt converte tabelas `raw` em um modelo dimensional (schemas `staging` → `intermediate` → `mart`). 106 modelos, 46 testes de dados.
3. **Servir** — Um subconjunto dos dados é publicado via `postgres_fdw` em um schema `publication` somente leitura.
4. **API** — FastAPI BFF com 15 rotas consulta o schema `publication` e retorna dados prontos para a interface.
5. **UI** — Next.js 15 com React 19, TanStack Query, Zustand para estado global, TailwindCSS.
6. **BI** — Metabase conectado ao mesmo banco para consultas ad-hoc.

---

## Componentes

### Frontend (`frontend/`)

- **Páginas**: catálogo de competições, central da partida, rankings, perfis de time/jogador/técnico, confronto direto, mercado, Copa do Mundo, analytics
- **Padrão**: cada módulo de funcionalidade segue `{components,hooks,services,types}/` dentro de `features/`
- **Proxy BFF**: requisições `/api/*` são roteadas via Next.js para o backend FastAPI, com cache para GET
- **Estado global**: Zustand para filtros (competição, temporada) preservados entre rotas
- **Bibliotecas**: TanStack Table (virtualização), Recharts (gráficos), TanStack Query (cache/refetch)

### API (`api/`)

- FastAPI com pool de conexões psycopg
- 15 rotas: competições, partidas, jogadores, times, rankings, mercado, analytics, Copa do Mundo, health, search
- Middleware: CORS, logging (request_id + duration + DB stats), rate limiting in-memory (3 buckets)
- Schemas Pydantic para validação e serialização (Decimal → float, datetime → ISO)

### Banco (`db/`)

- PostgreSQL 16 com `pg_stat_statements`
- 61 migrations (dbmate) organizadas por timestamp
- Schemas: `raw` (dados ingeridos), `control` (catálogo de competições), `mart` (modelo dimensional), `publication` (visão de servir)

### Orquestração (`infra/airflow/`)

- 46 DAGs em três estágios: bronze → silver → postgres
- Dois provedores de dados: SportMonks (principal) e API-Football (fallback), selecionáveis via env var
- Operadores Python com mapeamento field-by-field entre API e schema do banco

### Transformação (`platform/dbt/`)

- 106 modelos SQL versionados
- Materialização: staging/intermediate como views, marts como tabelas
- 46 testes de dados (asserções de consistência, unicidade, integridade referencial)
- 17 modelos analíticos para BI (OLAP cube, trend series, summaries)

### Quality (`platform/quality/`)

- Great Expectations para validação de dados em staging
- Scripts de release gate (`tools/frontend_release_gate.py`, `tools/backend_data_readiness_gate.py`)
- Relatórios de qualidade em `platform/reports/`

---

## Exemplos de uso

```bash
# Catálogo de competições com estrutura
curl http://localhost:8000/api/v1/competition-structure

# Partidas de uma competição/temporada
curl "http://localhost:8000/api/v1/matches?competition_id=br1&season_id=2025"

# Ranking de artilheiros
curl "http://localhost:8000/api/v1/rankings/goals?competition_id=br1&season_id=2025"

# Perfil de jogador
curl http://localhost:8000/api/v1/players/12345

# Confronto direto entre dois times
curl "http://localhost:8000/api/v1/head-to-head?team_a_id=10&team_b_id=20"

# Copa do Mundo - edições disponíveis
curl http://localhost:8000/api/v1/world-cup/editions
```

## Stack

| Camada | Tecnologia | Função |
|---|---|---|
| Frontend | Next.js 15 + React 19 + TypeScript 5.7 | SPA com server-side rendering e proxy BFF |
| UI Components | TailwindCSS 4, TanStack Table 8, Recharts 3, Zustand 5 | Estilização, tabelas virtuais, gráficos, estado global |
| API | Python 3.13 + FastAPI 0.116 + Uvicorn 0.35 | BFF com pooling assíncrono e rate limiting |
| Database | PostgreSQL 16 + pg_stat_statements | Banco analítico com migrations versionadas |
| Migration | dbmate 2 | Migrações SQL por timestamp |
| Orchestration | Apache Airflow 2.9 (LocalExecutor) | Pipeline de ingestão bronze → silver → postgres |
| Data Transformation | dbt-core 1.8 (adapter PostgreSQL) | Modelagem dimensional e testes de dados |
| Data Quality | Great Expectations 0.18, dbt tests | Validação de schemas e consistência |
| Object Storage | MinIO (S3-compatible) | Armazenamento intermediário bronze/silver |
| BI | Metabase 0.60 | Interface de consulta ad-hoc |
| Containerization | Docker Compose (10 serviços) | Ambiente local completo |

---

## Dados

### Fontes

| Fonte | Cobertura | Tipo |
|---|---|---|
| SportMonks (primária) | Partidas, eventos, escalações, estatísticas, classificações, transferências, técnicos | API REST |
| API-Football (fallback) | Mesma cobertura da SportMonks | API REST |
| Transfermarkt | Valoração de jogadores, transferências, partidas | Dados abertos |
| StatsBomb Open Data | Eventos de partida com coordenadas, 360 freeze frames | Dados abertos |
| Wikidata | Imagens e metadados de técnicos | API pública |
| ELO Ratings | Ratings históricos de partidas | Dataset |

### Cobertura atual

| Métrica | Valor |
|---|---|
| Competições | 15 |
| Temporadas | 72 |
| Partidas | 15k+ |
| Jogadores | 22k+ |

---

## Rodando localmente

### Requisitos

- Docker + Docker Compose
- Python 3.13+
- pnpm
- Chave de API SportMonks (definida em `.env` como `API_KEY_SPORTMONKS`)

### Docker (todos os serviços)

```powershell
docker compose up -d
```

### Serviços individuais (desenvolvimento)

```powershell
# Infraestrutura base (PostgreSQL, MinIO, Airflow, Metabase)
docker compose up -d postgres dbmate minio airflow-init airflow-webserver airflow-scheduler metabase

# API (fora do Docker, com hot reload)
python -m pip install -r api/requirements.txt
uvicorn api.src.main:app --reload

# Frontend (fora do Docker, com hot reload)
cd frontend
pnpm install
pnpm dev -- --port 3001
```

### Endereços

| Serviço | Porta (Docker) | Porta (dev direto) |
|---|---|---|
| Frontend | `localhost:3001` | `localhost:3001` |
| API | `localhost:8010` | `127.0.0.1:8000` |
| API docs | `localhost:8010/docs` | `127.0.0.1:8000/docs` |
| Airflow | `localhost:8080` | — |
| Metabase | `localhost:3000` | — |
| MinIO (API) | `localhost:9000` | — |
| MinIO (Console) | `localhost:9001` | — |

### Validação

```powershell
cd frontend
pnpm typecheck

python tools/frontend_release_gate.py
python tools/backend_data_readiness_gate.py
```

---

## Estrutura do projeto

```
├── api/                 # FastAPI BFF (15 rotas, schemas, testes)
├── frontend/            # Next.js 15 (14 módulos de funcionalidade)
├── db/                  # Migrations (61), bootstrap, publication
├── infra/               # Airflow (46 DAGs), Docker Compose
├── platform/            # dbt (106 modelos, 46 testes), quality, scripts
├── ingestion/           # Scripts de ingestão histórica
├── tools/               # Release gates, scripts de utilidade
└── docker-compose.yml   # 10 serviços
```

---

## Limitações conhecidas

- **Cobertura de dados**: 15 competições. Dados históricos completos dependem da disponibilidade de cada fonte.
- **Taxa de requisição**: A ingestão via APIs externas está sujeita a rate limits. A pipeline pode atrasar em picos de carga.
- **Reconciliação**: Jogadores e partidas entre fontes diferentes (SportMonks vs Transfermarkt vs StatsBomb) são reconciliados por heurísticas; podem existir falsos positivos.
- **Escrita concorrente**: O runtime do Airflow usa LocalExecutor — não há paralelismo distribuído entre workers.
- **Autenticação**: A aplicação não implementa autenticação de usuário. O acesso aos dados é irrestrito na camada de consulta.

---

## Evoluções possíveis

- Expansão para novo conjunto de competições a partir da adição de registros no catálogo de controle e execução da pipeline
- Migração para execução distribuída de tarefas (Airflow CeleryExecutor) para reduzir latência da ingestão
- Camada de autenticação e autorização para cenários multi-usuário
- Exportação de dados via API pública
- Dashboards customizáveis no Metabase para análises específicas
