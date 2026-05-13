# football-analytics

## Pipeline (local)
Stack: Airflow + MinIO + Postgres via `docker compose`.

## DDLs
- `warehouse/ddl/001_raw_fixtures.sql`
- `warehouse/ddl/010_mart_schema.sql`
- `warehouse/ddl/011_mart_tables.sql`

## Execucao ponta-a-ponta
1. Crie o arquivo de ambiente:
```powershell
Copy-Item .env.example .env
```
2. Preencha os segredos no `.env` (`POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`, `MINIO_SECRET_KEY`, `AIRFLOW__WEBSERVER__SECRET_KEY`, `APIFOOTBALL_API_KEY`).
3. Suba os servicos:
```bash
docker compose up -d
```
4. Airflow UI: `http://localhost:8080` (`admin` / `admin`).
5. Aplique o DDL da camada raw (PowerShell):
```powershell
Get-Content 'warehouse/ddl/001_raw_fixtures.sql' | docker compose exec -T postgres psql -U football -d football_dw
```
6. Rode os DAGs nesta ordem:
- `ingest_brasileirao_2024_backfill`
- `bronze_to_silver_fixtures_backfill`
- `silver_to_postgres_fixtures`

Opcional: use o orquestrador `pipeline_brasileirao` para rodar tudo em sequencia (inclui o mart).

### Orquestrador unico (pipeline_brasileirao)
1. Rodar com defaults (`league_id=71`, `season=2024`):
```bash
docker compose exec -T airflow-webserver airflow dags test pipeline_brasileirao 2026-02-16
```
2. Rodar com params (PowerShell):
```powershell
$conf='{\"league_id\":71,\"season\":2024}'
docker compose exec -T airflow-webserver airflow dags test pipeline_brasileirao 2026-02-16 -c $conf
```
3. Se uma etapa falhar, as proximas nao executam (dependencia `all_success` no DAG orquestrador).

## Validacao no Airflow UI
- Abra `silver_to_postgres_fixtures` -> task `load_silver_to_postgres` -> Log.
- Verifique linha final com contadores:
  - `lidas`
  - `validas`
  - `inseridas`
  - `atualizadas`
  - `ignoradas`
  - `invalidas_sem_fixture_id`
  - `duplicadas_no_lote`

Re-run seguro: execute novamente `silver_to_postgres_fixtures`; o esperado e `inseridas=0`, `atualizadas=0` e `ignoradas=validas` quando nao houve mudanca de dados.

## MART (gold) no Postgres
1. Aplicar DDLs (PowerShell):
```powershell
Get-Content 'warehouse/ddl/010_mart_schema.sql' | docker compose exec -T postgres psql -U football -d football_dw
Get-Content 'warehouse/ddl/011_mart_tables.sql' | docker compose exec -T postgres psql -U football -d football_dw
```
2. Rodar DAG do mart (defaults: `league_id=71`, `season=2024`):
```bash
docker compose exec -T airflow-webserver airflow dags test mart_build_brasileirao_2024 2026-02-16
```
3. Rodar DAG do mart com params (override por conf):
```bash
docker compose exec -T airflow-webserver airflow dags test mart_build_brasileirao_2024 2026-02-16 --conf "{\"league_id\":71,\"season\":2024}"
```
4. Re-run idempotente: rode o mesmo comando novamente e confira no log `inseridas=0` e `atualizadas=0` quando nao houver mudanca na `raw.fixtures`.

## Validacao no Postgres (psql)
Abra shell:
```bash
docker compose exec -it postgres psql -U football -d football_dw
```

1) Total por mes (2024):
```sql
SELECT year, month, COUNT(*) AS fixtures
FROM raw.fixtures
GROUP BY year, month
ORDER BY year, month;
```

2) Top times por gols marcados:
```sql
SELECT team_name, SUM(goals) AS total_goals
FROM (
  SELECT home_team_name AS team_name, COALESCE(home_goals, 0) AS goals FROM raw.fixtures
  UNION ALL
  SELECT away_team_name AS team_name, COALESCE(away_goals, 0) AS goals FROM raw.fixtures
) t
GROUP BY team_name
ORDER BY total_goals DESC
LIMIT 10;
```

3) Sanidade de unicidade:
```sql
SELECT COUNT(*) AS total_rows,
       COUNT(DISTINCT fixture_id) AS distinct_fixture_id
FROM raw.fixtures;
```

4) MART mensal por time (com points/goal_diff):
```sql
SELECT season, year, month, team_name, matches, wins, draws, losses, points, goal_diff
FROM mart.team_match_goals_monthly
ORDER BY year, month, team_name
LIMIT 20;
```

5) Top 10 por points em um mes:
```sql
SELECT season, year, month, team_name, points, goal_diff, wins, draws, losses
FROM mart.team_match_goals_monthly
WHERE year = '2024' AND month = '12'
ORDER BY points DESC, goal_diff DESC, team_name
LIMIT 10;
```

6) Sanity check de contagens no mart:
```sql
SELECT COUNT(*) AS rows_team_monthly,
       COUNT(DISTINCT season || '-' || year || '-' || month || '-' || team_name) AS rows_team_monthly_distinct
FROM mart.team_match_goals_monthly;
```

7) MART resumo da liga:
```sql
SELECT league_id, league_name, season, total_matches, total_goals, avg_goals_per_match, first_match_date, last_match_date
FROM mart.league_summary;
```

8) Validacao ponta-a-ponta apos `pipeline_brasileirao`:
```sql
SELECT COUNT(*) AS raw_fixtures, COUNT(DISTINCT fixture_id) AS raw_distinct_fixture_id
FROM raw.fixtures;

SELECT COUNT(*) AS mart_team_rows
FROM mart.team_match_goals_monthly
WHERE season = 2024;
```

## Docs
- `docs/ARCHITECTURE.md` — current + target architecture
- `docs/ROADMAP.md` — phased plan of work (what’s next)
- `AGENTS.md` — instructions for coding agents (source of truth for contributions)

## Visualizacao (Metabase)
- Acesso: `http://localhost:3000`
- O servico do Metabase sobe via `docker compose` junto com os demais containers.

### Conectar o Metabase ao Data Warehouse
Na tela de configuracao de banco (PostgreSQL), use:
- Host: `football-postgres`
- Port: `5432`
- User: valor de `POSTGRES_USER` no `.env` (default local: `football`)
- Password: valor de `POSTGRES_PASSWORD` no `.env` (default local: `football`)
- Database: valor de `POSTGRES_DB` no `.env` (default local: `football_dw`)
