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
- Airflow: `http://localhost:8080` (`admin` / `admin`)
- MinIO Console: `http://localhost:9001`
- Metabase: `http://localhost:3000`

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
$conf='{"league_id":71,"season":2024,"provider":"sportmonks"}'
docker compose exec -T airflow-webserver airflow dags test pipeline_brasileirao 2026-02-17 -c $conf
```

Selecionar provider (PowerShell):
```powershell
$env:ACTIVE_PROVIDER='sportmonks'
$env:API_KEY_SPORTMONKS='sua_chave'
$env:SPORTMONKS_BASE_URL='https://api.sportmonks.com/v3/football'
```

Obs.: `league_id` no `dag_run.conf` e ID do provider ativo. `season` deve ser o ano da temporada (ex.: `2024`).

Provider legado opcional:
```powershell
$env:ACTIVE_PROVIDER='api_football'
$env:APIFOOTBALL_API_KEY='sua_chave'
$env:APIFOOTBALL_BASE_URL='https://v3.football.api-sports.io'
```

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
- Contratos de dados: `docs/contracts/data_contracts.md`
- Arquitetura: `docs/ARCHITECTURE.md`
- Roadmap: `docs/ROADMAP.md`
- DDL legado (somente referencia): `warehouse/ddl/`



