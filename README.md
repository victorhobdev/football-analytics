# football-analytics

Plataforma de dados para analise de futebol com fluxo oficial:
`ingestao -> silver/raw -> dbt_run -> great_expectations_checks -> data_quality_checks`.

## Stack
- Airflow (orquestracao): `infra/airflow/dags/`
- MinIO (lake bronze/silver): buckets `football-bronze`, `football-silver`
- Postgres (warehouse): schemas `raw`, `mart` (dbt target), `gold` (legacy historico)
- dbt (transformacao): `dbt/`
- Great Expectations + SQL assertions (quality gates): `quality/great_expectations/` + `infra/airflow/dags/data_quality_checks.py`
- Metabase (BI): `bi/metabase/`
- Providers de ingestao: `sportmonks` (default) e `api_football` (fallback), selecionados por `ACTIVE_PROVIDER`
- CI: `.github/workflows/ci.yml`

## Nucleo canonico de ingestao
Source of truth para clients/providers/writer usado pelos DAGs:
- HTTP client: `infra/airflow/dags/common/http_client.py`
- Providers (registry + adapters): `infra/airflow/dags/common/providers/`
- Raw writer (bronze payload): `infra/airflow/dags/common/raw_writer.py`
- Servicos de ingestao/mapeamento/load: `infra/airflow/dags/common/services/`

Observacao:
- Modulos legados duplicados em `src/` e placeholders em `ingestion/src/` foram descontinuados/removidos para evitar divergencia.
- Novas evolucoes de ingestao devem acontecer somente em `infra/airflow/dags/common/`.

## Subir stack local
1. Criar `.env`:
```powershell
Copy-Item .env.example .env
```
2. Preencher credenciais e variaveis obrigatorias.
3. Subir servicos:
```powershell
docker compose up -d
```
4. Validar servicos:
```powershell
docker compose ps
```

URLs:
- Airflow: `http://localhost:8080` (`AIRFLOW_ADMIN_USERNAME` / `AIRFLOW_ADMIN_PASSWORD` do `.env`)
- MinIO Console: `http://localhost:9001`
- Metabase: `http://localhost:3000`

## Subir ambiente local completo (PowerShell)
Comando unico a partir da raiz do repo:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\start-local.ps1
```

O script:
- sobe/valida `docker compose`;
- repara dependencias do frontend quando o `node_modules` estiver inconsistente;
- sobe a BFF em `http://127.0.0.1:8010`;
- sobe o frontend em `http://127.0.0.1:3001`;
- grava logs em `artifacts/local-run/`.

Se voce ja estiver dentro de uma sessao PowerShell e preferir liberar so para a sessao atual:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\tools\start-local.ps1
```

## Migracoes de schema (caminho unico)
Schema evolui apenas por `dbmate` em `db/migrations/`.

Comandos:
```powershell
make db-up
make db-status
```

Ou direto:
```powershell
docker compose run --rm dbmate --migrations-dir /db/migrations up
```

## Rodar pipeline no Airflow
DAG principal: `pipeline_brasileirao`.

Execucao de teste:
```powershell
$conf='{"league_id":648,"season":2024,"provider":"sportmonks"}'
docker compose exec -T airflow-webserver airflow dags test pipeline_brasileirao 2026-02-17 -c $conf
```

Backfill deterministico de statistics (PowerShell-safe):
```powershell
# Backfill por temporada (season_id alias de season)
@'
import json
import subprocess
conf = json.dumps({
    "mode": "backfill",
    "provider": "sportmonks",
    "league_id": 648,
    "season_id": 2024
})
subprocess.run(
    ["airflow", "dags", "test", "ingest_statistics_bronze", "2026-02-17", "-c", conf],
    check=True,
)
'@ | docker compose exec -T airflow-webserver python -

# Backfill por lista explicita de fixtures
@'
import json
import subprocess
conf = json.dumps({
    "mode": "backfill",
    "provider": "sportmonks",
    "league_id": 648,
    "season_id": 2024,
    "fixture_ids": [1180355, 1180356, 1180357]
})
subprocess.run(
    ["airflow", "dags", "test", "ingest_statistics_bronze", "2026-02-17", "-c", conf],
    check=True,
)
'@ | docker compose exec -T airflow-webserver python -
```

Notas do modo backfill:
- Persistencia em `raw.provider_sync_state` com `scope_key` dedicado (inclui hash da lista quando `fixture_ids` e explicito).
- Retomada por cursor sem full-scan de S3 (evita reprocessar fixtures ja concluidos no mesmo escopo).
- Escrita idempotente mantida via upsert no raw (`ON CONFLICT (fixture_id, team_id) DO UPDATE ... IS DISTINCT FROM`).
- Rate limit/retry seguem o provider HTTP + `INGEST_STATISTICS_REQUESTS_PER_MINUTE`.

## Ingestao SportMonks Advanced (arquitetura por dominio)
Novos dominios implementados no pipeline:
1. `group_competition_structure`:
- `ingest_competition_structure_bronze`
- `bronze_to_silver_competition_structure`
- `silver_to_postgres_competition_structure`
- `ingest_standings_bronze`
- `bronze_to_silver_standings`
- `silver_to_postgres_standings`
2. `group_fixture_enrichment`:
- fluxo existente de fixtures/statistics/events
3. `group_player_layer`:
- `ingest_lineups_bronze` -> `bronze_to_silver_lineups` -> `silver_to_postgres_lineups`
- `ingest_fixture_player_statistics_bronze` -> `bronze_to_silver_fixture_player_statistics` -> `silver_to_postgres_fixture_player_statistics`
- `ingest_player_season_statistics_bronze` -> `bronze_to_silver_player_season_statistics` -> `silver_to_postgres_player_season_statistics`
4. `group_context_extras`:
- `ingest_player_transfers_bronze` -> `bronze_to_silver_player_transfers` -> `silver_to_postgres_player_transfers`
- `ingest_team_sidelined_bronze` -> `bronze_to_silver_team_sidelined` -> `silver_to_postgres_team_sidelined`
- `ingest_team_coaches_bronze` -> `bronze_to_silver_team_coaches` -> `silver_to_postgres_team_coaches`
- `ingest_head_to_head_bronze` -> `bronze_to_silver_head_to_head` -> `silver_to_postgres_head_to_head`

Execucao ponta-a-ponta recomendada:
```powershell
$conf='{"league_id":648,"season":2024,"provider":"sportmonks"}'
docker compose exec -T airflow-webserver airflow dags test pipeline_brasileirao 2026-02-19 -c $conf
```

Novas variaveis de rate limit no `.env`:
- `INGEST_COMPETITION_REQUESTS_PER_MINUTE`
- `INGEST_STANDINGS_REQUESTS_PER_MINUTE`
- `INGEST_LINEUPS_REQUESTS_PER_MINUTE`
- `INGEST_PLAYER_STATS_REQUESTS_PER_MINUTE`
- `INGEST_PLAYER_SEASON_REQUESTS_PER_MINUTE`
- `INGEST_TRANSFERS_REQUESTS_PER_MINUTE`
- `INGEST_SIDELINED_REQUESTS_PER_MINUTE`
- `INGEST_COACHES_REQUESTS_PER_MINUTE`
- `INGEST_H2H_REQUESTS_PER_MINUTE`

Selecionar provider (PowerShell):
```powershell
$env:ACTIVE_PROVIDER='sportmonks'
$env:SPORTMONKS_DEFAULT_LEAGUE_ID='648'
$env:API_KEY_SPORTMONKS='sua_chave'
$env:SPORTMONKS_BASE_URL='https://api.sportmonks.com/v3/football'
$env:INGEST_FIXTURES_REQUESTS_PER_MINUTE='0'
$env:INGEST_STATISTICS_REQUESTS_PER_MINUTE='0'
$env:INGEST_EVENTS_REQUESTS_PER_MINUTE='0'
```

Obs.: `league_id` no `dag_run.conf` e ID do provider ativo. `season` deve ser o ano da temporada (ex.: `2024`).

Provider legado opcional:
```powershell
$env:ACTIVE_PROVIDER='api_football'
$env:APIFOOTBALL_DEFAULT_LEAGUE_ID='71'
$env:APIFOOTBALL_API_KEY='sua_chave'
$env:APIFOOTBALL_BASE_URL='https://v3.football.api-sports.io'
```

## Reingestao SportMonks sem duplicidade
Se ja houve ingestao via `api_football` para a mesma temporada, limpe o recorte antigo antes de reprocessar em `sportmonks` para evitar duplicidade analitica entre providers.

Exemplo (temporada 2024):
```powershell
Get-Content 'warehouse/queries/reset_provider_api_football_brasileirao_2024.sql' | docker compose exec -T postgres psql -U football -d football_dw
```

Depois rode a ingestao SportMonks com `league_id=648`.

Fluxo interno da DAG:
1. Ingestao: `ingest_brasileirao_2024_backfill`, `ingest_statistics_bronze`, `ingest_match_events_bronze`
2. Bronze -> Silver -> Raw:
- `bronze_to_silver_fixtures_backfill` -> `silver_to_postgres_fixtures`
- `bronze_to_silver_statistics` -> `silver_to_postgres_statistics`
- `bronze_to_silver_match_events` -> `silver_to_postgres_match_events`
3. Transformacao: `dbt_run`
4. Quality gates: `great_expectations_checks` -> `data_quality_checks`

## Rodar dbt (local)
Dentro do container Airflow (mesmo ambiente usado pelas DAGs):

```powershell
docker compose exec -T airflow-webserver dbt deps --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt
docker compose exec -T airflow-webserver dbt run --select marts.core --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt
docker compose exec -T airflow-webserver dbt run --select marts.analytics --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt
docker compose exec -T airflow-webserver dbt test --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt
```

## Rodar documentacao dbt
Atalho:
```powershell
make dbt-docs
```

Arquivos gerados:
- `dbt/target/index.html`
- `dbt/target/manifest.json`
- `dbt/target/catalog.json`

Abrir localmente:
```powershell
python -m http.server 8088 --directory dbt/target
```
Depois acesse `http://localhost:8088`.

No CI, docs sao geradas e publicadas como artifact `dbt-docs`.

## Rodar quality gates isoladamente
Great Expectations:
```powershell
docker compose exec -T airflow-webserver airflow dags test great_expectations_checks 2026-02-17
```

SQL checks:
```powershell
docker compose exec -T airflow-webserver airflow dags test data_quality_checks 2026-02-17
```

## Lint, testes e CI local
```powershell
python -m pip install -r requirements-dev.txt
make lint
make test
```

## Backend/BFF + dados release/demo readiness
Instalacao minima local:
```powershell
python -m pip install -r requirements-dev.txt -r api/requirements.txt
```

Gate minimo local a partir da raiz do repo:
```powershell
python tools/backend_data_readiness_gate.py
```

Gate completo com stack live:
```powershell
docker compose up -d postgres dbmate airflow-init airflow-webserver
python tools/backend_data_readiness_gate.py --mode full
```

Atalhos `make`:
```powershell
make backend-data-gate
make backend-data-gate-full
```

Checklist curto de validacao/release tecnica:
- `docs/BACKEND_DATA_RELEASE_READINESS.md`

## Frontend local (BFF)
No diretorio `frontend/`:

```powershell
Copy-Item .env.example .env.local
```

Ajuste `NEXT_PUBLIC_BFF_BASE_URL` para a URL da BFF (default local: `http://127.0.0.1:8010`).

## Frontend E2E (Playwright)
No diretorio `frontend/`:

```powershell
pnpm exec playwright install chromium
pnpm run test:e2e
```

Os cenarios E2E usam interceptacao de `/api/*` para nao depender de backend real.

## Frontend release/demo readiness
Gate minimo local a partir da raiz do repo:
```powershell
python tools/frontend_release_gate.py
```

Gate completo com regressao E2E:
```powershell
python tools/frontend_release_gate.py --mode full
```

Atalhos `make`:
```powershell
make frontend-release
make frontend-release-full
```

O gate minimo executa `pnpm validate:release` + `pnpm build` dentro de `frontend/` e grava um resumo em `artifacts/frontend_release_gate_<timestamp_utc>/summary.txt`.

Checklist curto de demo/release e bloqueantes reais:
- `docs/FRONTEND_RELEASE_READINESS.md`

## Como validar P1
Comando unico:
```powershell
make quality-p1
```

Se nao tiver `make` no Windows:
```powershell
python tools/quality_p1.py
```

O alvo `quality-p1` executa, nesta ordem:
1. `pytest -q -m "not integration"`
2. `dbt run -s standings_evolution`
3. `dbt test -s standings_evolution`

No final, imprime resumo com status (`PASS`/`FAIL`) e tempo por etapa + tempo total.

## Como rodar P2 verify
Comando unico:
```powershell
make p2-verify
```

Se nao tiver `make` no Windows:
```powershell
python tools/p2_verify.py
```

O alvo `p2-verify` executa, nesta ordem:
1. `pytest -q -m "not integration"`
2. Queries de diagnostico em `warehouse/queries/`:
- `fixtures_missing_stats.sql`
- `stats_duplicates.sql`
- `coverage_by_season.sql`
3. `dbt test -s stg_match_statistics+`

Artefatos:
- outputs das queries em `artifacts/p2_verify_<timestamp_utc>/`.
- resumo final no terminal com status (`PASS`/`FAIL`) e tempo por etapa + tempo total.

Escopo atual de CI (`.github/workflows/ci.yml`):
- lint (`ruff`)
- unit tests (`pytest`)
- dbt validations (`dbt deps`, `dbt compile`, `dbt docs generate`)

## Metabase e dashboards versionados
Acesso:
- `http://localhost:3000`

Conexao do Metabase ao DW:
- Host: `football-postgres`
- Port: `5432`
- User: `POSTGRES_USER`
- Password: `POSTGRES_PASSWORD`
- Database: `POSTGRES_DB`

Versionamento de dashboards:
- Guia: `bi/metabase/README.md`
- Export: `bi/metabase/scripts/export_metabase.py`
- Import/restore: `bi/metabase/scripts/import_metabase.py`
- Artefatos versionados: `bi/metabase/exports/`

## Referencias
- Guia mestre da aplicacao: `docs/GUIA_MESTRE_APLICACAO.md`
- Contratos de dados: `docs/contracts/data_contracts.md`
- Contratos frontend/BFF: `docs/MART_FRONTEND_BFF_CONTRACTS.md`
- Contrato publico do BFF: `docs/BFF_API_CONTRACT.md`
- Cobertura Copa do Mundo: `docs/WORLD_CUP_DATA_READY_BY_EDITION.md`
- DDL legado (somente referencia): `warehouse/ddl/`



