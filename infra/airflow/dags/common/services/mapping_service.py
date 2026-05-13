from __future__ import annotations

from datetime import datetime
import json
import os
import re
from io import BytesIO
from typing import Any

import boto3
import pandas as pd
from airflow.operators.python import get_current_context

from common.mappers import (
    build_fixtures_dataframe,
    build_match_events_dataframe,
    build_statistics_dataframe,
)
from common.observability import StepMetrics, log_event
from common.runtime import resolve_runtime_params


BRONZE_BUCKET = "football-bronze"
SILVER_BUCKET = "football-silver"
RUN_PATTERN = re.compile(r"/run=([^/]+)/")
FIXTURE_RUN_PATTERN = re.compile(r"/fixture_id=(\d+)/run=([^/]+)/")


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
    keys: list[str] = []
    token = None
    while True:
        params: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
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
        match = RUN_PATTERN.search(key)
        if match:
            runs.append(match.group(1))
    if not runs:
        raise RuntimeError("Nao encontrei run=... nas chaves do bronze.")
    return sorted(set(runs))[-1]


def _load_json_payloads(s3_client, *, bucket: str, keys: list[str]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for key in keys:
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        payloads.append(json.loads(obj["Body"].read().decode("utf-8")))
    return payloads


def _latest_key_by_fixture(data_keys: list[str]) -> list[str]:
    latest_by_fixture: dict[int, tuple[str, str]] = {}
    for key in data_keys:
        match = FIXTURE_RUN_PATTERN.search(key)
        if not match:
            continue
        fixture_id = int(match.group(1))
        run_id = match.group(2)
        current = latest_by_fixture.get(fixture_id)
        if current is None or run_id > current[0]:
            latest_by_fixture[fixture_id] = (run_id, key)
    return [key for _, key in sorted((v for v in latest_by_fixture.values()), key=lambda item: item[1])]


def map_fixtures_raw_to_silver():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]

    s3_client = _s3_client()
    prefix = f"fixtures/league={league_id}/season={season}/"
    keys = _list_all_keys(s3_client, bucket=BRONZE_BUCKET, prefix=prefix)
    data_keys = [key for key in keys if key.endswith("/data.json")]
    if not data_keys:
        raise RuntimeError(f"Nenhum data.json encontrado no bronze com prefixo {prefix}")

    latest_run = _latest_run(data_keys)
    selected_keys = [key for key in data_keys if f"/run={latest_run}/" in key]
    payloads = _load_json_payloads(s3_client, bucket=BRONZE_BUCKET, keys=selected_keys)

    with StepMetrics(
        service="airflow",
        module="mapping_service",
        step="map_fixtures_raw_to_silver",
        context=context,
        dataset="fixtures",
        table="football-silver",
    ) as metric:
        df = build_fixtures_dataframe(payloads)
        months = sorted(df[["year", "month"]].dropna().drop_duplicates().itertuples(index=False, name=None))
        written_rows = 0
        for year, month in months:
            part = df[(df["year"] == year) & (df["month"] == month)].copy()
            out_key = (
                f"fixtures/league={league_id}/season={season}"
                f"/year={year}/month={month}/run={latest_run}/fixtures.parquet"
            )
            buf = BytesIO()
            part.to_parquet(buf, index=False)
            buf.seek(0)
            s3_client.upload_fileobj(buf, SILVER_BUCKET, out_key)
            written_rows += len(part)
        metric.set_counts(rows_in=len(payloads), rows_out=written_rows, row_count=written_rows)

    log_event(
        service="airflow",
        module="mapping_service",
        step="summary",
        status="success",
        context=context,
        dataset="fixtures",
        rows_in=len(payloads),
        rows_out=len(df),
        row_count=len(df),
        message=f"Raw->Silver fixtures concluido | league_id={league_id} | season={season} | rows={len(df)}",
    )


def map_statistics_raw_to_silver():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]

    s3_client = _s3_client()
    prefix = f"statistics/league={league_id}/season={season}/"
    keys = _list_all_keys(s3_client, bucket=BRONZE_BUCKET, prefix=prefix)
    data_keys = [key for key in keys if key.endswith("/data.json")]
    if not data_keys:
        raise RuntimeError(f"Nenhum data.json encontrado no bronze com prefixo {prefix}")

    selected_keys = _latest_key_by_fixture(data_keys)
    payloads = _load_json_payloads(s3_client, bucket=BRONZE_BUCKET, keys=selected_keys)

    with StepMetrics(
        service="airflow",
        module="mapping_service",
        step="map_statistics_raw_to_silver",
        context=context,
        dataset="statistics",
        table="football-silver",
    ) as metric:
        df = build_statistics_dataframe(payloads)
        run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
        out_key = f"statistics/league={league_id}/season={season}/run={run_utc}/statistics.parquet"
        buf = BytesIO()
        df.to_parquet(buf, index=False)
        buf.seek(0)
        s3_client.upload_fileobj(buf, SILVER_BUCKET, out_key)
        metric.set_counts(rows_in=len(payloads), rows_out=len(df), row_count=len(df))

    log_event(
        service="airflow",
        module="mapping_service",
        step="summary",
        status="success",
        context=context,
        dataset="statistics",
        rows_in=len(payloads),
        rows_out=len(df),
        row_count=len(df),
        message=f"Raw->Silver statistics concluido | league_id={league_id} | season={season} | rows={len(df)}",
    )


def map_match_events_raw_to_silver():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]

    s3_client = _s3_client()
    prefix = f"events/league={league_id}/season={season}/"
    keys = _list_all_keys(s3_client, bucket=BRONZE_BUCKET, prefix=prefix)
    data_keys = [key for key in keys if key.endswith("/data.json")]
    if not data_keys:
        raise RuntimeError(f"Nenhum data.json encontrado no bronze com prefixo {prefix}")

    selected_keys = _latest_key_by_fixture(data_keys)
    payloads = _load_json_payloads(s3_client, bucket=BRONZE_BUCKET, keys=selected_keys)

    with StepMetrics(
        service="airflow",
        module="mapping_service",
        step="map_match_events_raw_to_silver",
        context=context,
        dataset="match_events",
        table="football-silver",
    ) as metric:
        df = build_match_events_dataframe(payloads)
        run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
        out_key = f"events/season={season}/league_id={league_id}/run={run_utc}/match_events.parquet"
        buf = BytesIO()
        df.to_parquet(buf, index=False)
        buf.seek(0)
        s3_client.upload_fileobj(buf, SILVER_BUCKET, out_key)
        metric.set_counts(rows_in=len(payloads), rows_out=len(df), row_count=len(df))

    log_event(
        service="airflow",
        module="mapping_service",
        step="summary",
        status="success",
        context=context,
        dataset="match_events",
        rows_in=len(payloads),
        rows_out=len(df),
        row_count=len(df),
        message=f"Raw->Silver match_events concluido | league_id={league_id} | season={season} | rows={len(df)}",
    )
