from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import os
import re
from io import BytesIO

import boto3
import pandas as pd
from sqlalchemy import create_engine, text


SILVER_BUCKET = "football-silver"
LEAGUE_ID = 71
SEASON = 2024

TARGET_COLUMNS = [
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
    "ingested_run",
]

REQUIRED_INPUT_COLUMNS = [
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

INT_COLUMNS = [
    "fixture_id",
    "time_elapsed",
    "time_extra",
    "team_id",
    "player_id",
    "assist_id",
]

TEXT_COLUMNS = [
    "event_id",
    "team_name",
    "player_name",
    "assist_name",
    "type",
    "detail",
    "comments",
]


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _s3():
    return boto3.client(
        "s3",
        endpoint_url=_get_required_env("MINIO_ENDPOINT_URL"),
        aws_access_key_id=_get_required_env("MINIO_ACCESS_KEY"),
        aws_secret_access_key=_get_required_env("MINIO_SECRET_KEY"),
    )


def _list_all_keys(s3, bucket: str, prefix: str) -> list[str]:
    keys = []
    token = None

    while True:
        params = {"Bucket": bucket, "Prefix": prefix}
        if token:
            params["ContinuationToken"] = token

        resp = s3.list_objects_v2(**params)
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
        raise RuntimeError("Nao encontrei run=... nas chaves do silver/events.")
    return sorted(set(runs))[-1]


def _assert_required_input_columns(df: pd.DataFrame, source_key: str):
    missing = sorted(set(REQUIRED_INPUT_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(
            f"Schema invalido no parquet {source_key}. Colunas ausentes: {missing}. "
            f"Esperadas (minimas): {REQUIRED_INPUT_COLUMNS}"
        )


def _assert_target_columns(conn):
    sql = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'raw' AND table_name = 'match_events'
        """
    )
    found = {row[0] for row in conn.execute(sql)}
    missing = sorted(set(TARGET_COLUMNS) - found)
    if missing:
        raise ValueError(
            f"Tabela raw.match_events sem colunas esperadas: {missing}. "
            "Aplique warehouse/ddl/003_raw_match_events.sql."
        )


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in REQUIRED_INPUT_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    for col in INT_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    for col in TEXT_COLUMNS:
        out[col] = out[col].astype("string")

    return out


def load_match_events_silver_to_postgres():
    s3 = _s3()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    prefix = f"events/league={LEAGUE_ID}/season={SEASON}/"
    keys = _list_all_keys(s3, SILVER_BUCKET, prefix)
    if not keys:
        raise RuntimeError(f"Nenhum parquet encontrado no silver com prefixo {prefix}")

    parquet_keys = [key for key in keys if key.endswith("match_events.parquet")]
    if not parquet_keys:
        raise RuntimeError("Nenhum match_events.parquet encontrado no silver.")

    run_id = _latest_run(parquet_keys)
    run_keys = sorted([key for key in parquet_keys if f"/run={run_id}/" in key])
    if not run_keys:
        raise RuntimeError(f"Nao encontrei match_events.parquet para run={run_id}")

    print(f"Carregando match_events run={run_id} | arquivos={len(run_keys)}")

    read_rows = 0
    frames = []

    for key in run_keys:
        obj = s3.get_object(Bucket=SILVER_BUCKET, Key=key)
        df = pd.read_parquet(BytesIO(obj["Body"].read()))
        _assert_required_input_columns(df, key)
        read_rows += len(df)
        frames.append(df)
        print(f"Lido: {key} | rows={len(df)}")

    load_df = pd.concat(frames, ignore_index=True)
    load_df = _normalize_dataframe(load_df)

    invalid_mask = load_df["event_id"].isna() | load_df["fixture_id"].isna()
    invalid_rows = int(invalid_mask.sum())
    if invalid_rows:
        load_df = load_df[~invalid_mask].copy()

    before_dedup = len(load_df)
    load_df = load_df.drop_duplicates(subset=["event_id"], keep="last").copy()
    duplicated_rows = before_dedup - len(load_df)

    load_df["ingested_run"] = run_id
    load_df = load_df[TARGET_COLUMNS]

    compare_columns = [col for col in TARGET_COLUMNS if col != "event_id"]
    distinct_predicate = " OR ".join([f"t.{col} IS DISTINCT FROM s.{col}" for col in compare_columns])

    insert_cols = ", ".join(TARGET_COLUMNS)
    select_cols = ", ".join([f"s.{col}" for col in TARGET_COLUMNS])
    update_set = ", ".join([f"{col} = EXCLUDED.{col}" for col in compare_columns] + ["updated_at = now()"])
    conflict_where = " OR ".join([f"raw.match_events.{col} IS DISTINCT FROM EXCLUDED.{col}" for col in compare_columns])

    with engine.begin() as conn:
        _assert_target_columns(conn)

        conn.execute(
            text(
                "CREATE TEMP TABLE staging_match_events (LIKE raw.match_events INCLUDING DEFAULTS) ON COMMIT DROP"
            )
        )

        load_df.to_sql(
            "staging_match_events",
            con=conn,
            if_exists="append",
            index=False,
            method="multi",
        )

        inserted = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM staging_match_events s
                LEFT JOIN raw.match_events t ON t.event_id = s.event_id
                WHERE t.event_id IS NULL
                """
            )
        ).scalar_one()

        updated = conn.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM staging_match_events s
                JOIN raw.match_events t ON t.event_id = s.event_id
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
                ON CONFLICT (event_id) DO UPDATE
                SET {update_set}
                WHERE {conflict_where}
                """
            )
        )

        ignored = len(load_df) - inserted - updated

    print(
        "Load match_events concluido | "
        f"run={run_id} | lidas={read_rows} | validas={len(load_df)} | "
        f"inseridas={inserted} | atualizadas={updated} | ignoradas={ignored} | "
        f"invalidas_sem_chave={invalid_rows} | duplicadas_no_lote={duplicated_rows}"
    )


with DAG(
    dag_id="silver_to_postgres_match_events",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["warehouse", "load", "events"],
) as dag:
    PythonOperator(
        task_id="load_match_events_silver_to_postgres",
        python_callable=load_match_events_silver_to_postgres,
    )
