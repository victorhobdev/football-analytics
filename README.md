# Football Analytics

![Next.js](https://img.shields.io/badge/Next.js-15-0f172a?logo=nextdotjs)
![React](https://img.shields.io/badge/React-19-0f172a?logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-BFF-065f46?logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Data%20Warehouse-1d4ed8?logo=postgresql)
![Airflow](https://img.shields.io/badge/Airflow-Orchestration-b91c1c?logo=apacheairflow)
![dbt](https://img.shields.io/badge/dbt-Transformations-f97316?logo=dbt)
![Metabase](https://img.shields.io/badge/Metabase-BI-2563eb?logo=metabase)

Plataforma full-stack de exploração de futebol histórico, construída como produto de dados ponta a ponta: ingestão, modelagem, BFF, frontend analítico e camada de BI.

O projeto não tenta ser um placar ao vivo. Ele organiza um arquivo histórico com navegação canônica por competição, temporada, partida, time, jogador e rankings.

**Repositório:** [github.com/victorhob1981/football-analytics](https://github.com/victorhob1981/football-analytics)

![Screenshot do produto](frontend/phase1_top.png)

## O que este projeto é

`football-analytics` é uma aplicação de exploração futebolística orientada por temporadas fechadas e acervo histórico. A proposta de produto é transformar dados operacionais de futebol em uma experiência navegável e consistente, com contexto de competição, recorte de temporada, central da partida, rankings e perfis contextuais.

Na prática, o projeto combina:

- pipeline de dados com orquestração e camadas explícitas;
- modelagem analítica para consumo de produto;
- BFF em FastAPI para estabilizar contrato entre dado e interface;
- frontend em Next.js com superfícies reais de navegação;
- assets e BI acoplados ao mesmo fluxo de produto.

## Características do projeto

Este projeto reúne capacidades técnicas de ponta a ponta:

- produto de dados com separação clara entre ingestão, warehouse, BFF e UI;
- modelagem canônica de competições e temporadas;
- frontend analítico com múltiplas superfícies navegáveis;
- preocupação real com qualidade, contratos e readiness de release;
- escopo com volume e cobertura suficientes para discussão séria de arquitetura.

## Atributos principais

| Dimensão | Evidência objetiva |
| --- | --- |
| Escopo de catálogo | `14` competições canônicas expostas no frontend e no BFF |
| Núcleo auditado forte | `10` competições com snapshot consolidado de cobertura |
| Escala histórica | `50` escopos competição-temporada, `15.265` fixtures, `267.590` eventos de partida |
| Profundidade de produto | competições, season hub, rankings, partidas, times, jogadores, head-to-head, mercado e técnicos |
| Arquitetura | Airflow + MinIO + Postgres + dbt + FastAPI + Next.js + Metabase |
| Qualidade operacional | gates locais de backend/dados e frontend para readiness |

## Cobertura atual do acervo

Núcleo com cobertura auditada forte no repositório:

- Campeonato Brasileiro Série A
- Campeonato Brasileiro Série B
- Copa Libertadores da América
- Copa do Brasil
- Premier League
- UEFA Champions League
- La Liga
- Serie A (Itália)
- Bundesliga
- Ligue 1

Catálogo canônico exposto hoje pelo app e BFF:

- Brasileirão Série A
- Brasileirão Série B
- Libertadores
- Sudamericana
- Copa do Brasil
- Supercopa do Brasil
- FIFA Intercontinental Cup
- Premier League
- Champions League
- La Liga
- Serie A Italy
- Bundesliga
- Ligue 1
- Liga Portugal

Leitura correta do estado atual:

- o produto já nasce multi-competição;
- o núcleo mais forte está consolidado em `10` competições auditadas;
- parte do catálogo adicional já existe no código e no contrato, mas depende de validação runtime para cobertura total.

## Superfícies de produto já implementadas

Rotas públicas existentes no frontend:

- `/`
- `/competitions`
- `/competitions/[competitionKey]`
- `/competitions/[competitionKey]/seasons/[seasonLabel]`
- `/matches`
- `/matches/[matchId]`
- `/teams`
- `/teams/[teamId]`
- `/players`
- `/players/[playerId]`
- `/rankings/[rankingType]`
- `/head-to-head`
- `/market`
- `/coaches`
- `/coaches/[coachId]`
- rotas legadas: `/clubs`, `/clubs/[clubId]`, `/competition/[competitionId]`

Domínios de API/BFF já expostos:

- `health`
- `home`
- `competition_hub`
- `matches`
- `teams`
- `players`
- `rankings`
- `search`
- `standings`
- `market`
- `coaches`
- `insights`

## Stack técnica

### Frontend

- Next.js `15`
- React `19`
- TypeScript
- TanStack Query
- TanStack Table
- Recharts
- Zustand
- Tailwind CSS `4`

### Backend / BFF

- FastAPI
- Uvicorn
- Psycopg `3`
- contrato HTTP desacoplado da semântica interna do warehouse

### Dados e plataforma

- PostgreSQL
- Airflow
- MinIO
- dbt
- Metabase

## Arquitetura em uma linha

```text
Ingestão -> Bronze -> Silver -> Raw -> Mart/dbt -> BFF -> Frontend -> BI
```

Responsabilidade por camada:

- `ingestion/`: captura e processamento inicial
- `infra/airflow/`: orquestração
- `platform/dbt/`: transformações e marts
- `platform/quality/`: quality gates
- `api/`: BFF em FastAPI
- `frontend/`: aplicação Next.js
- `tools/`: gates, utilitários e scripts operacionais

## Estrutura do repositório

```text
football-analytics/
├── api/                # BFF em FastAPI
├── frontend/           # aplicação Next.js
├── ingestion/          # ingestão e testes da camada
├── infra/airflow/      # DAGs e configuração de orquestração
├── platform/dbt/       # modelagem analítica
├── platform/quality/   # validações e qualidade
├── docs/               # contratos, readiness e documentação funcional
├── tools/              # gates e scripts utilitários
├── data/               # dados e artefatos locais
└── docker-compose.yml  # stack local base
```

## Como rodar localmente

### 1. Subir a infraestrutura base

```powershell
docker compose up -d postgres dbmate minio airflow-init airflow-webserver airflow-scheduler metabase
```

### 2. Rodar o BFF

O ponto de entrada do BFF está em `api/src/main.py`.

```powershell
python -m pip install -r api/requirements.txt
uvicorn api.src.main:app --reload
```

### 3. Rodar o frontend

O frontend consome `NEXT_PUBLIC_BFF_BASE_URL`.

```powershell
cd frontend
pnpm install
$env:NEXT_PUBLIC_BFF_BASE_URL="http://127.0.0.1:8000"
pnpm dev -- --port 3001
```

### 4. Endpoints locais úteis

- app: `http://localhost:3001`
- BFF docs: `http://127.0.0.1:8000/docs`
- health: `http://127.0.0.1:8000/health`
- Airflow: `http://localhost:8080`
- Metabase: `http://localhost:3000`

Observação importante:

- o comando acima sobe o frontend em `3001` para evitar conflito com o Metabase em `3000`.

## Validação e readiness

Gate mínimo de frontend:

```powershell
python tools/frontend_release_gate.py
```

Gate mínimo de backend/dados:

```powershell
python tools/backend_data_readiness_gate.py
```


## Documentação complementar

- [Guia mestre da aplicação](docs/GUIA_MESTRE_APLICACAO.md)
- [Contrato público da BFF](docs/BFF_API_CONTRACT.md)
- [Contratos de dados](docs/contracts/data_contracts.md)
- [Contrato mart -> frontend -> BFF](docs/MART_FRONTEND_BFF_CONTRACTS.md)
- [Readiness de frontend](docs/FRONTEND_RELEASE_READINESS.md)
- [Readiness de backend/dados](docs/BACKEND_DATA_RELEASE_READINESS.md)

## Resumo do que está implementado aqui

- visão de produto, não só scripts isolados;
- integração real entre data engineering, backend e frontend;
- modelagem orientada a domínio;
- preocupação com contratos, cobertura e rastreabilidade;
