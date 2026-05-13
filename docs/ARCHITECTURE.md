# Architecture - football-analytics

## Overview
Current architecture is dbt-first for transformations, with Airflow as orchestrator and explicit quality gates.

Official runtime flow:
`ingestao -> silver/raw -> dbt_run -> great_expectations_checks -> data_quality_checks`

## Layers

### Bronze (MinIO JSON)
- Source: provider-agnostic adapters (`sportmonks` default, `api_football` fallback).
- Stored as raw JSON payloads for replay and audit.
- Main ingestion DAGs:
  - `ingest_brasileirao_2024_backfill`
  - `ingest_statistics_bronze`
  - `ingest_match_events_bronze`

### Silver (MinIO Parquet)
- Normalized and typed parquet datasets.
- Key DAGs:
  - `bronze_to_silver_fixtures_backfill`
  - `bronze_to_silver_statistics`
  - `bronze_to_silver_match_events`
- Partitioning currently used:
  - fixtures: `fixtures/league=71/season=2024/year=YYYY/month=MM/run=...`
  - statistics: `statistics/league=71/season=2024/run=...`
  - events: `events/season=2024/league_id=71/run=...`

### Raw (Postgres)
- Loaded from Silver with explicit schema contracts and idempotent upsert.
- Main tables:
  - `raw.fixtures`
  - `raw.match_statistics`
  - `raw.match_events` (list partitioned by `season`)
- Load DAGs:
  - `silver_to_postgres_fixtures`
  - `silver_to_postgres_statistics`
  - `silver_to_postgres_match_events`

### Marts (dbt output in schema `mart`)
- dbt models organized as:
  - `stg_*` in `dbt/models/staging/`
  - `int_*` in `dbt/models/intermediate/`
  - final marts in `dbt/models/marts/core/` and `dbt/models/marts/analytics/`
- Core entities:
  - dims: `dim_team`, `dim_player`, `dim_competition`, `dim_date`, `dim_venue`
  - facts: `fact_matches`, `fact_match_events`
  - analytics: `team_monthly_stats`, `standings_evolution`, `league_summary`

## Orchestration flow (main DAG)
Main DAG: `pipeline_brasileirao`.

Execution groups:
1. Ingestion group
2. Bronze/Silver/Raw group
3. Transform + quality group:
- `dbt_run`
- `great_expectations_checks`
- `data_quality_checks`

`TriggerDagRunOperator` is used with `wait_for_completion=True` and propagated `conf` (`league_id`, `season`).

## Quality gates

### dbt tests
- Schema tests and singular tests in `dbt/models/**/schema.yml` and `dbt/tests/*.sql`.
- Executed in DAG `dbt_run` (`dbt test`).

### Great Expectations
- DAG: `great_expectations_checks`.
- Sequence: `ge_raw -> ge_gold_marts`.
- Suites in `quality/great_expectations/expectations/`.

### SQL assertions
- DAG: `data_quality_checks`.
- Current checks include:
  - orphan events in raw
  - suspicious mart score mismatch

## Observability and logs
- Shared observability helper: `infra/airflow/dags/common/observability.py`.
- Structured JSON logs include: `ts`, `level`, `service`, `module`, `dag_id`, `task_id`, `run_id`, `step`, `dataset`, `row_count`, `rows_in`, `rows_out`, `duration_ms`, `status`, `error_type`, `error_msg`.
- Metrics helper: `StepMetrics` context manager (start/end/fail events + duration and counts).
- Runtime log location: Airflow task logs (container logs and Airflow log backend).

## Design decisions

### 1. dbt-first transformations
- Gold/Mart legacy DAGs are deprecated:
  - `deprecated_gold_dimensions_load`
  - `deprecated_gold_facts_load`
  - `deprecated_mart_build_brasileirao_2024`
- Active transformation engine is only `dbt_run`.

### 2. Idempotency and contracts
- Raw loaders enforce explicit `TARGET_COLUMNS` and validate input schema.
- Upserts use `ON CONFLICT ... DO UPDATE` with `IS DISTINCT FROM` to avoid unnecessary writes.

### 3. Surrogate keys
- dbt dimensional keys use stable hashed surrogate keys (`md5(...)`) for joins between facts and dimensions.

### 4. Incremental strategy
- `fact_matches`: incremental by `date_day` watermark.
- `fact_match_events`: incremental by `updated_at` watermark.

### 5. Single schema migration path
- Physical schema evolves only through dbmate migrations in `db/migrations/`.
- Legacy DDL in `warehouse/ddl/` is historical reference, not execution path.

## BI layer
- Metabase service in `docker-compose.yml` on `http://localhost:3000`.
- Dashboard metadata versioning in `bi/metabase/` with export/import scripts.

## Related docs
- Contracts: `docs/contracts/data_contracts.md`
- Roadmap status: `docs/ROADMAP.md`

