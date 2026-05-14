# Data Contracts

## Scope and source of truth
This document is the single contract reference for the active flow:
`ingestao -> silver/raw -> dbt_run -> quality`.

Contract sources used:
- Raw physical schema: `db/migrations/*.sql`
- Silver schemas and partitions: `infra/airflow/dags/bronze_to_silver_*.py`
- Mart models: `dbt/models/**`
- Quality rules: `dbt/models/**/schema.yml`, `dbt/tests/*.sql`, `quality/great_expectations/expectations/*.json`, `infra/airflow/dags/data_quality_checks.py`

Detailed dbt field docs stay in dbt docs and model YAMLs. This file defines the end-to-end contract and ownership.

## Global quality SLA
- Gate order in orchestrator (`infra/airflow/dags/pipeline_brasileirao.py`):
  `dbt_run -> great_expectations_checks -> data_quality_checks`
- A pipeline run is valid only when all 3 gates pass.
- dbt output schema default: `mart` (`dbt/profiles.yml`, `DBT_TARGET_SCHEMA`).

---

## Raw contracts (Postgres)

### `raw.fixtures`
- Grain: 1 row per fixture (`fixture_id`).
- Primary key: `fixture_id`.
- Origin: Silver parquet `football-silver/fixtures/league=71/season=2024/year=YYYY/month=MM/run=.../fixtures.parquet`.
- Mandatory fields (contract): `fixture_id`.

Relevant fields and types:

| Field | Type | Required | Notes |
|---|---|---|---|
| fixture_id | BIGINT | Yes | Business key of match |
| date_utc | TIMESTAMPTZ | No | Match UTC datetime |
| status_short | TEXT | No | Match status (FT, PEN, AET, etc.) |
| league_id | BIGINT | No | Competition id |
| season | INT | No | Season |
| round | TEXT | No | Round label from API |
| home_team_id / away_team_id | BIGINT | No | Home and away teams |
| home_goals / away_goals | INT | No | Final score |
| year / month | TEXT | No | Derived from `date_utc` in Silver |
| ingested_run | TEXT | No | Pipeline run id |

Quality rules applied:
- GE suite: `raw_fixtures_suite` (not null + unique `fixture_id`, season range)
- Loader contract checks: required input columns + explicit target columns (`silver_to_postgres_fixtures.py`)
- DB constraints/indexes: `fixture_id` PK, `league_id` + `season` NOT NULL, indexes em `league_id`, `season` e `(league_id, season)`.

### `raw.match_statistics`
- Grain: 1 row per (`fixture_id`, `team_id`).
- Primary key: (`fixture_id`, `team_id`).
- Foreign key: `fixture_id -> raw.fixtures.fixture_id` (`fk_match_statistics_fixture`, rollout with `NOT VALID`).
- Origin: Silver parquet `football-silver/statistics/league=71/season=2024/run=.../statistics.parquet`.
- Mandatory fields (contract): `fixture_id`, `team_id`.

Relevant fields and types:

| Field | Type | Required | Notes |
|---|---|---|---|
| fixture_id | BIGINT | Yes | FK to fixtures |
| team_id | BIGINT | Yes | Team key |
| team_name | TEXT | No | Team name |
| shots_on_goal | INT | No | Pivoted metric |
| total_shots | INT | No | Pivoted metric |
| ball_possession | INT | No | Percent normalized to integer |
| fouls, corner_kicks, offsides | INT | No | Pivoted metrics |
| yellow_cards, red_cards | INT | No | Pivoted metrics |
| total_passes, passes_accurate | INT | No | Pivoted metrics |
| passes_pct | NUMERIC(5,2) | No | Pass accuracy percentage |
| ingested_run | TEXT | No | Pipeline run id |
| updated_at | TIMESTAMPTZ | Yes | Managed in upsert |

Quality rules applied:
- GE suite: `raw_match_statistics_suite` (not null keys, compound uniqueness, ball possession range)
- Loader contract checks + idempotent upsert with `IS DISTINCT FROM`
- DB constraints/indexes: PK (`fixture_id`, `team_id`) + FK para `raw.fixtures`; IDs `fixture_id`/`team_id` NOT NULL; indexes em `fixture_id` e `team_id`.

### `raw.match_events` (partitioned)
- Grain: 1 row per technical event (`event_id`, `season`).
- Primary key: (`event_id`, `season`).
- Partition strategy: `PARTITION BY LIST (season)` with `raw.match_events_2024`.
- Foreign key: `fixture_id -> raw.fixtures.fixture_id`.
- Origin: Silver parquet `football-silver/events/season=2024/league_id=71/run=.../match_events.parquet`.
- Mandatory fields (contract): `event_id`, `season`, `fixture_id`.

Relevant fields and types:

| Field | Type | Required | Notes |
|---|---|---|---|
| event_id | TEXT | Yes | MD5 surrogate from event attributes |
| season | INT | Yes | Partition key |
| fixture_id | BIGINT | Yes | FK to fixtures |
| time_elapsed / time_extra | INT | No | Minute data (`time_elapsed < 0` is normalized to `NULL`) |
| is_time_elapsed_anomalous | BOOLEAN | Yes | `TRUE` when raw source had negative elapsed minute |
| team_id / player_id / assist_id | BIGINT | No | Actor ids |
| team_name / player_name / assist_name | TEXT | No | Actor labels |
| type / detail / comments | TEXT | No | Event attributes |
| ingested_run | TEXT | No | Pipeline run id |
| updated_at | TIMESTAMPTZ | Yes | Managed in upsert |

Quality rules applied:
- GE suite: `raw_match_events_suite` (not null keys, uniqueness, time range)
- SQL check: `raw_events_orphan` in `data_quality_checks.py`
- Loader contract checks + idempotent upsert with `IS DISTINCT FROM`
- DB constraints/indexes: PK (`event_id`, `season`), IDs `event_id`/`season`/`fixture_id` NOT NULL, indexes em `fixture_id`, `team_id`, `player_id`, `assist_id`.

---

## Silver contracts (MinIO Parquet)

### Dataset `fixtures`
- Grain: 1 row per fixture (`fixture_id`) after dedup.
- Partition path: `fixtures/league=71/season=2024/year=YYYY/month=MM/run=<latest_run>/fixtures.parquet`.
- Required input from Bronze flattening: fixture/league/team/goal attributes.
- Derived fields: `date` (tmp), `year`, `month`.

Main schema (written):
`fixture_id, date_utc, timestamp, timezone, referee, venue_id, venue_name, venue_city, status_short, status_long, league_id, league_name, season, round, home_team_id, home_team_name, away_team_id, away_team_name, home_goals, away_goals, date, year, month`.

### Dataset `statistics`
- Grain: 1 row per (`fixture_id`, `team_id`) after dedup.
- Partition path: `statistics/league=71/season=2024/run=<run_utc>/statistics.parquet`.
- Required fields: `fixture_id`, `team_id`, `team_name`.
- Derived/normalized fields:
  - pivoted metric columns from API `statistics[].type`
  - `%` values converted to integer (`ball_possession`, etc.)

### Dataset `events`
- Grain: 1 row per event (`event_id`) after dedup.
- Partition path: `events/season=2024/league_id=71/run=<run_utc>/match_events.parquet`.
- Required fields: `fixture_id` + flattened event attributes.
- Derived fields:
  - `event_id` (MD5 of fixture/time/team/type/detail/player)
  - numeric coercion for ids and time fields

---

## Gold/Marts contracts (dbt models in schema `mart`)

Note: legacy SQL marts in `warehouse/` are historical reference only. Active contract is dbt output.

### Core dimensions

#### `dim_team`
- Grain: 1 row per team (`team_id`).
- Key: `team_sk` (hash surrogate, unique), natural key `team_id`.
- Required: `team_sk`, `team_id`, `team_name`.
- Source: `stg_matches` (home/away union).
- Quality: dbt `not_null` + `unique` on keys (`dbt/models/marts/core/schema.yml`).

#### `dim_player`
- Grain: 1 row per player (`player_id`).
- Key: `player_sk`.
- Required: `player_sk`, `player_id`, `player_name`.
- Source: `stg_match_events`.
- Quality: dbt `not_null` + `unique` on keys.

#### `dim_competition`
- Grain: 1 row per competition (`league_id`).
- Key: `competition_sk`.
- Required: `competition_sk`, `league_id`, `league_name`.
- Source: `stg_matches`.
- Quality: dbt `not_null` + `unique` on keys.

#### `dim_date`
- Grain: 1 row per calendar day (`date_day`).
- Key: `date_sk`.
- Required: `date_sk`, `date_day`, `year`, `month`, `day`, `is_weekend`.
- Source: generated by `generate_series` bounded by fixture dates.
- Quality: dbt key tests + accepted values for `is_weekend`.

#### `dim_venue`
- Grain: 1 row per venue (`venue_id`).
- Key: `venue_sk`.
- Required: `venue_sk`, `venue_id`, `venue_name`.
- Source: `stg_matches`.
- Quality: dbt key tests.

### Core facts

#### `fact_matches`
- Grain: 1 row per match (`match_id` = fixture id).
- Key: `match_id`.
- Logical FK keys: `competition_sk`, `date_sk`, `home_team_sk`, `away_team_sk`, `venue_sk`.
- Required: `match_id`, all non-null dimension links except `venue_sk` optional, plus `season`, `date_day`, `result`.
- Business fields: score, total_goals, home/away statistics.
- Incremental policy: by `date_day` watermark (`is_incremental()`).

Quality rules applied:
- dbt schema tests: PK uniqueness/not null + relationships + accepted `result`
- dbt singular tests:
  - non-negative score
  - result consistency
  - total_goals consistency
- GE suite: `gold_fact_matches_suite`

#### `fact_match_events`
- Grain: 1 row per event (`event_id`).
- Key: `event_id`.
- Logical FK keys: `match_id`, `team_sk`, `player_sk`, `assist_player_sk`.
- Required: `event_id`, `match_id`, `is_goal`.
- Business fields: `event_type`, `event_detail`, time fields, actor links.
- Anomaly field: `is_time_elapsed_anomalous` (`TRUE` when source elapsed minute was negative and normalized to `NULL`).
- Incremental policy: by `updated_at` watermark (`is_incremental()`).

Quality rules applied:
- dbt schema tests: PK + relationships + `is_goal` accepted values
- dbt singular tests:
  - event time range
  - `is_goal` consistency with `event_type`
  - goal event requires team

### Analytics marts

#### `team_monthly_stats`
- Grain: (`season`, `year`, `month`, `team_sk`).
- Key: unique combination (`season`, `year`, `month`, `team_sk`).
- Required: `season`, `year`, `month`, `team_sk`, `team_id`, `team_name`, `matches`.
- Metrics: `goals_for`, `goals_against`, `wins`, `draws`, `losses`, `points`, `goal_diff`.
- Source: `int_team_match_rows` + `dim_team`.
- Quality: dbt schema tests + singular consistency test.

#### `standings_evolution`
- Grain: (`season`, `round`, `team_sk`).
- Key: unique combination (`season`, `round`, `team_sk`).
- Required: `season`, `round`, `team_sk`, `points_accumulated`, `goals_for_accumulated`, `goal_diff_accumulated`, `position`.
- Metrics logic: cumulative windows + ranking by points/wins/goal_diff/goals_for.
- Source: `int_team_match_rows`.
- Quality: dbt schema tests + singular monotonic points test + GE suite `mart_standings_evolution_suite`.

#### `league_summary`
- Grain: (`competition_sk`, `season`).
- Key: unique combination (`competition_sk`, `season`).
- Required: `competition_sk`, `season`, `total_matches`, `total_goals`, `avg_goals_per_match`.
- Metrics: first/last match date and goal averages.
- Source: `fact_matches` + `dim_competition`.
- Quality: dbt schema tests + singular consistency test + SQL assertion `mart_score_mismatch`.

---

## Contract change policy
- Schema evolution must go only through `dbmate` migrations (`db/migrations` + `dbmate up`).
- dbt model contract changes must include:
  - model SQL update
  - `schema.yml` updates (description/tests)
  - this document update (`docs/contracts/data_contracts.md`) when grain/keys/mandatory fields change.
- Any quality rule added in dbt/GE/SQL should be linked here under affected entity.
