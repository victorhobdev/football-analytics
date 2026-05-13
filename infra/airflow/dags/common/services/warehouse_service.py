from __future__ import annotations

import os
import re
from io import BytesIO

import boto3
import pandas as pd
from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.observability import StepMetrics, log_event
from common.runtime import resolve_runtime_params


SILVER_BUCKET = "football-silver"

FIXTURES_TARGET_COLUMNS = [
    "fixture_id",
    "date_utc",
    "timestamp",
    "timezone",
    "referee",
    "venue_id",
    "venue_name",
    "venue_city",
    "status_short",
    "status_long",
    "league_id",
    "league_name",
    "season",
    "round",
    "home_team_id",
    "home_team_name",
    "away_team_id",
    "away_team_name",
    "home_goals",
    "away_goals",
    "year",
    "month",
    "ingested_run",
]
FIXTURES_REQUIRED_COLUMNS = [c for c in FIXTURES_TARGET_COLUMNS if c != "ingested_run"]

STATISTICS_TARGET_COLUMNS = [
    "fixture_id",
    "team_id",
    "team_name",
    "shots_on_goal",
    "shots_off_goal",
    "total_shots",
    "blocked_shots",
    "shots_inside_box",
    "shots_outside_box",
    "fouls",
    "corner_kicks",
    "offsides",
    "ball_possession",
    "yellow_cards",
    "red_cards",
    "goalkeeper_saves",
    "total_passes",
    "passes_accurate",
    "passes_pct",
    "ingested_run",
]
STATISTICS_REQUIRED_COLUMNS = ["fixture_id", "team_id", "team_name"]
STATISTICS_INT_COLUMNS = [
    "fixture_id",
    "team_id",
    "shots_on_goal",
    "shots_off_goal",
    "total_shots",
    "blocked_shots",
    "shots_inside_box",
    "shots_outside_box",
    "fouls",
    "corner_kicks",
    "offsides",
    "ball_possession",
    "yellow_cards",
    "red_cards",
    "goalkeeper_saves",
    "total_passes",
    "passes_accurate",
]

EVENTS_TARGET_COLUMNS = [
    "event_id",
    "season",
    "fixture_id",
    "time_elapsed",
    "time_extra",
    "team_id",
    "team_name",
    "player_id",
    "player_name",
    "assist_id",
    "assist_name",
    "type",
    "detail",
    "comments",
    "ingested_run",
]
EVENTS_REQUIRED_COLUMNS = [
    "event_id",
    "fixture_id",
    "time_elapsed",
    "time_extra",
    "team_id",
    "team_name",
    "player_id",
    "player_name",
    "assist_id",
    "assist_name",
    "type",
    "detail",
    "comments",
]
EVENTS_INT_COLUMNS = ["season", "fixture_id", "time_elapsed", "time_extra", "team_id", "player_id", "assist_id"]
EVENTS_TEXT_COLUMNS = ["event_id", "team_name", "player_name", "assist_name", "type", "detail", "comments"]


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=_get_required_env("MINIO_ENDPOINT_URL"),
        aws_access_key_id=_get_required_env("MINIO_ACCESS_KEY"),
        aws_secret_access_key=_get_required_env("MINIO_SECRET_KEY"),
    )


def _list_all_keys(s3_client, *, bucket: str, prefix: str) -> list[str]:
    keys = []
    token = None
    while True:
        params = {"Bucket": bucket, "Prefix": prefix}
        if token:
            params["ContinuationToken"] = token
        resp = s3_client.list_objects_v2(**params)
        keys.extend([obj["Key"] for obj in resp.get("Contents", [])])
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return keys


def _latest_run(keys: list[str]) -> str:
    runs = []
    for key in keys:
        match = re.search(r"/run=([^/]+)/", key)
        if match:
            runs.append(match.group(1))
    if not runs:
        raise RuntimeError("Nao encontrei run=... nas chaves do silver.")
    return sorted(set(runs))[-1]


def _assert_columns(df: pd.DataFrame, expected: list[str], source_key: str):
    missing = sorted(set(expected) - set(df.columns))
    if missing:
        raise ValueError(f"Schema invalido no parquet {source_key}. Colunas ausentes: {missing}.")


def _assert_target_columns(conn, *, schema: str, table: str, expected: list[str]):
    sql = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :schema
          AND table_name = :table
        """
    )
    found = {row[0] for row in conn.execute(sql, {"schema": schema, "table": table})}
    missing = sorted(set(expected) - found)
    if missing:
        raise ValueError(f"Tabela {schema}.{table} sem colunas esperadas: {missing}.")


def load_fixtures_silver_to_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]

    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    prefix = f"fixtures/league={league_id}/season={season}/"
    keys = _list_all_keys(s3_client, bucket=SILVER_BUCKET, prefix=prefix)
    parquet_keys = [key for key in keys if key.endswith("fixtures.parquet")]
    if not parquet_keys:
        raise RuntimeError(f"Nenhum fixtures.parquet encontrado com prefixo {prefix}")

    run_id = _latest_run(parquet_keys)
    run_keys = sorted([key for key in parquet_keys if f"/run={run_id}/" in key])

    read_rows = 0
    frames = []
    with StepMetrics(
        service="airflow",
        module="warehouse_service",
        step="load_fixtures_silver_to_raw",
        context=context,
        dataset="raw.fixtures",
        table="raw.fixtures",
    ) as metric:
        for key in run_keys:
            obj = s3_client.get_object(Bucket=SILVER_BUCKET, Key=key)
            df = pd.read_parquet(BytesIO(obj["Body"].read()))
            _assert_columns(df, FIXTURES_REQUIRED_COLUMNS, key)
            read_rows += len(df)
            frames.append(df)

        load_df = pd.concat(frames, ignore_index=True)
        load_df["fixture_id"] = pd.to_numeric(load_df["fixture_id"], errors="coerce").astype("Int64")
        for col in ["timestamp", "venue_id", "league_id", "season", "home_team_id", "away_team_id", "home_goals", "away_goals"]:
            load_df[col] = pd.to_numeric(load_df[col], errors="coerce").astype("Int64")
        load_df["date_utc"] = pd.to_datetime(load_df["date_utc"], errors="coerce", utc=True)
        load_df["year"] = load_df["year"].astype("string")
        load_df["month"] = load_df["month"].astype("string")

        invalid_mask = load_df["fixture_id"].isna()
        invalid_rows = int(invalid_mask.sum())
        if invalid_rows:
            load_df = load_df[~invalid_mask].copy()
        load_df = load_df.drop_duplicates(subset=["fixture_id"], keep="last").copy()

        load_df["ingested_run"] = run_id
        load_df = load_df[FIXTURES_TARGET_COLUMNS]

        compare_columns = [col for col in FIXTURES_TARGET_COLUMNS if col != "fixture_id"]
        distinct_predicate = " OR ".join([f"t.{col} IS DISTINCT FROM s.{col}" for col in compare_columns])
        insert_cols = ", ".join(FIXTURES_TARGET_COLUMNS)
        select_cols = ", ".join([f"s.{col}" for col in FIXTURES_TARGET_COLUMNS])
        update_set = ", ".join([f"{col} = EXCLUDED.{col}" for col in compare_columns])
        conflict_where = " OR ".join([f"raw.fixtures.{col} IS DISTINCT FROM EXCLUDED.{col}" for col in compare_columns])

        with engine.begin() as conn:
            _assert_target_columns(conn, schema="raw", table="fixtures", expected=FIXTURES_TARGET_COLUMNS)
            conn.execute(text("CREATE TEMP TABLE staging_fixtures (LIKE raw.fixtures INCLUDING DEFAULTS) ON COMMIT DROP"))
            load_df.to_sql("staging_fixtures", con=conn, if_exists="append", index=False, method="multi")

            inserted = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM staging_fixtures s
                    LEFT JOIN raw.fixtures t ON t.fixture_id = s.fixture_id
                    WHERE t.fixture_id IS NULL
                    """
                )
            ).scalar_one()
            updated = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM staging_fixtures s
                    JOIN raw.fixtures t ON t.fixture_id = s.fixture_id
                    WHERE {distinct_predicate}
                    """
                )
            ).scalar_one()
            conn.execute(
                text(
                    f"""
                    INSERT INTO raw.fixtures ({insert_cols})
                    SELECT {select_cols}
                    FROM staging_fixtures s
                    ON CONFLICT (fixture_id) DO UPDATE
                    SET {update_set}
                    WHERE {conflict_where}
                    """
                )
            )
            ignored = len(load_df) - inserted - updated

        metric.set_counts(rows_in=read_rows, rows_out=len(load_df), row_count=len(load_df))

    log_event(
        service="airflow",
        module="warehouse_service",
        step="summary",
        status="success",
        context=context,
        dataset="raw.fixtures",
        rows_in=read_rows,
        rows_out=len(load_df),
        row_count=len(load_df),
        message=(
            f"Load fixtures concluido | league_id={league_id} | season={season} | run={run_id} "
            f"| inseridas={inserted} | atualizadas={updated} | ignoradas={ignored}"
        ),
    )


def load_statistics_silver_to_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]

    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    prefix = f"statistics/league={league_id}/season={season}/"
    keys = _list_all_keys(s3_client, bucket=SILVER_BUCKET, prefix=prefix)
    parquet_keys = [key for key in keys if key.endswith("statistics.parquet")]
    if not parquet_keys:
        raise RuntimeError(f"Nenhum statistics.parquet encontrado com prefixo {prefix}")

    run_id = _latest_run(parquet_keys)
    run_keys = sorted([key for key in parquet_keys if f"/run={run_id}/" in key])

    read_rows = 0
    frames = []
    with StepMetrics(
        service="airflow",
        module="warehouse_service",
        step="load_statistics_silver_to_raw",
        context=context,
        dataset="raw.match_statistics",
        table="raw.match_statistics",
    ) as metric:
        for key in run_keys:
            obj = s3_client.get_object(Bucket=SILVER_BUCKET, Key=key)
            df = pd.read_parquet(BytesIO(obj["Body"].read()))
            _assert_columns(df, STATISTICS_REQUIRED_COLUMNS, key)
            read_rows += len(df)
            frames.append(df)

        load_df = pd.concat(frames, ignore_index=True)
        for col in STATISTICS_TARGET_COLUMNS:
            if col not in load_df.columns and col != "ingested_run":
                load_df[col] = pd.NA
        for col in STATISTICS_INT_COLUMNS:
            load_df[col] = pd.to_numeric(load_df[col], errors="coerce").astype("Int64")
        load_df["team_name"] = load_df["team_name"].astype("string")
        load_df["passes_pct"] = pd.to_numeric(load_df["passes_pct"], errors="coerce")

        invalid_mask = load_df["fixture_id"].isna() | load_df["team_id"].isna()
        if int(invalid_mask.sum()):
            load_df = load_df[~invalid_mask].copy()
        load_df = load_df.drop_duplicates(subset=["fixture_id", "team_id"], keep="last").copy()
        load_df["ingested_run"] = run_id
        load_df = load_df[STATISTICS_TARGET_COLUMNS]

        compare_columns = [col for col in STATISTICS_TARGET_COLUMNS if col not in ("fixture_id", "team_id")]
        distinct_predicate = " OR ".join([f"t.{col} IS DISTINCT FROM s.{col}" for col in compare_columns])
        insert_cols = ", ".join(STATISTICS_TARGET_COLUMNS)
        select_cols = ", ".join([f"s.{col}" for col in STATISTICS_TARGET_COLUMNS])
        update_set = ", ".join([f"{col} = EXCLUDED.{col}" for col in compare_columns] + ["updated_at = now()"])
        conflict_where = " OR ".join([f"raw.match_statistics.{col} IS DISTINCT FROM EXCLUDED.{col}" for col in compare_columns])

        with engine.begin() as conn:
            _assert_target_columns(conn, schema="raw", table="match_statistics", expected=STATISTICS_TARGET_COLUMNS)
            conn.execute(text("CREATE TEMP TABLE staging_statistics (LIKE raw.match_statistics INCLUDING DEFAULTS) ON COMMIT DROP"))
            load_df.to_sql("staging_statistics", con=conn, if_exists="append", index=False, method="multi")

            inserted = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM staging_statistics s
                    LEFT JOIN raw.match_statistics t
                      ON t.fixture_id = s.fixture_id
                     AND t.team_id = s.team_id
                    WHERE t.fixture_id IS NULL
                    """
                )
            ).scalar_one()
            updated = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM staging_statistics s
                    JOIN raw.match_statistics t
                      ON t.fixture_id = s.fixture_id
                     AND t.team_id = s.team_id
                    WHERE {distinct_predicate}
                    """
                )
            ).scalar_one()
            conn.execute(
                text(
                    f"""
                    INSERT INTO raw.match_statistics ({insert_cols})
                    SELECT {select_cols}
                    FROM staging_statistics s
                    ON CONFLICT (fixture_id, team_id) DO UPDATE
                    SET {update_set}
                    WHERE {conflict_where}
                    """
                )
            )
            ignored = len(load_df) - inserted - updated

        metric.set_counts(rows_in=read_rows, rows_out=len(load_df), row_count=len(load_df))

    log_event(
        service="airflow",
        module="warehouse_service",
        step="summary",
        status="success",
        context=context,
        dataset="raw.match_statistics",
        rows_in=read_rows,
        rows_out=len(load_df),
        row_count=len(load_df),
        message=(
            f"Load statistics concluido | league_id={league_id} | season={season} | run={run_id} "
            f"| inseridas={inserted} | atualizadas={updated} | ignoradas={ignored}"
        ),
    )


def load_match_events_silver_to_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]

    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    prefix = f"events/season={season}/league_id={league_id}/"
    keys = _list_all_keys(s3_client, bucket=SILVER_BUCKET, prefix=prefix)
    parquet_keys = [key for key in keys if key.endswith("match_events.parquet")]
    if not parquet_keys:
        raise RuntimeError(f"Nenhum match_events.parquet encontrado com prefixo {prefix}")

    run_id = _latest_run(parquet_keys)
    run_keys = sorted([key for key in parquet_keys if f"/run={run_id}/" in key])

    read_rows = 0
    frames = []
    with StepMetrics(
        service="airflow",
        module="warehouse_service",
        step="load_match_events_silver_to_raw",
        context=context,
        dataset="raw.match_events",
        table="raw.match_events",
    ) as metric:
        for key in run_keys:
            obj = s3_client.get_object(Bucket=SILVER_BUCKET, Key=key)
            df = pd.read_parquet(BytesIO(obj["Body"].read()))
            _assert_columns(df, EVENTS_REQUIRED_COLUMNS, key)
            read_rows += len(df)
            frames.append(df)

        load_df = pd.concat(frames, ignore_index=True)
        if "season" not in load_df.columns:
            load_df["season"] = season
        for col in EVENTS_INT_COLUMNS:
            load_df[col] = pd.to_numeric(load_df[col], errors="coerce").astype("Int64")
        for col in EVENTS_TEXT_COLUMNS:
            load_df[col] = load_df[col].astype("string")

        invalid_mask = load_df["event_id"].isna() | load_df["fixture_id"].isna() | load_df["season"].isna()
        if int(invalid_mask.sum()):
            load_df = load_df[~invalid_mask].copy()
        load_df = load_df.drop_duplicates(subset=["event_id", "season"], keep="last").copy()
        load_df["ingested_run"] = run_id
        load_df = load_df[EVENTS_TARGET_COLUMNS]

        compare_columns = [col for col in EVENTS_TARGET_COLUMNS if col not in ("event_id", "season")]
        distinct_predicate = " OR ".join([f"t.{col} IS DISTINCT FROM s.{col}" for col in compare_columns])
        insert_cols = ", ".join(EVENTS_TARGET_COLUMNS)
        select_cols = ", ".join([f"s.{col}" for col in EVENTS_TARGET_COLUMNS])
        update_set = ", ".join([f"{col} = EXCLUDED.{col}" for col in compare_columns] + ["updated_at = now()"])
        conflict_where = " OR ".join([f"raw.match_events.{col} IS DISTINCT FROM EXCLUDED.{col}" for col in compare_columns])

        with engine.begin() as conn:
            _assert_target_columns(conn, schema="raw", table="match_events", expected=EVENTS_TARGET_COLUMNS)
            conn.execute(text("CREATE TEMP TABLE staging_match_events (LIKE raw.match_events INCLUDING DEFAULTS) ON COMMIT DROP"))
            load_df.to_sql("staging_match_events", con=conn, if_exists="append", index=False, method="multi")

            inserted = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM staging_match_events s
                    LEFT JOIN raw.match_events t
                      ON t.event_id = s.event_id
                     AND t.season = s.season
                    WHERE t.event_id IS NULL
                    """
                )
            ).scalar_one()
            updated = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM staging_match_events s
                    JOIN raw.match_events t
                      ON t.event_id = s.event_id
                     AND t.season = s.season
                    WHERE {distinct_predicate}
                    """
                )
            ).scalar_one()
            conn.execute(
                text(
                    f"""
                    INSERT INTO raw.match_events ({insert_cols})
                    SELECT {select_cols}
                    FROM staging_match_events s
                    ON CONFLICT (event_id, season) DO UPDATE
                    SET {update_set}
                    WHERE {conflict_where}
                    """
                )
            )
            ignored = len(load_df) - inserted - updated

        metric.set_counts(rows_in=read_rows, rows_out=len(load_df), row_count=len(load_df))

    log_event(
        service="airflow",
        module="warehouse_service",
        step="summary",
        status="success",
        context=context,
        dataset="raw.match_events",
        rows_in=read_rows,
        rows_out=len(load_df),
        row_count=len(load_df),
        message=(
            f"Load match_events concluido | league_id={league_id} | season={season} | run={run_id} "
            f"| inseridas={inserted} | atualizadas={updated} | ignoradas={ignored}"
        ),
    )
