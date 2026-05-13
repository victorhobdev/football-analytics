from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import hashlib
import json
import os
import re
from io import BytesIO

import boto3
import pandas as pd


BRONZE_BUCKET = "football-bronze"
SILVER_BUCKET = "football-silver"
LEAGUE_ID = 71
SEASON = 2024


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


def _extract_fixture_and_run(key: str) -> tuple[int, str] | None:
    match = re.search(r"/fixture_id=(\d+)/run=([^/]+)/data\.json$", key)
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def _as_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_id(
    fixture_id: int,
    time_elapsed: int | None,
    team_id: int | None,
    event_type: str | None,
    detail: str | None,
    player_id: int | None,
) -> str:
    raw = "|".join(
        [
            str(fixture_id),
            str(time_elapsed or ""),
            str(team_id or ""),
            str(event_type or ""),
            str(detail or ""),
            str(player_id or ""),
        ]
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def bronze_to_silver_match_events_latest_per_fixture():
    s3 = _s3()
    prefix = f"events/league={LEAGUE_ID}/season={SEASON}/"
    keys = _list_all_keys(s3, BRONZE_BUCKET, prefix)
    if not keys:
        raise RuntimeError(f"Nenhum arquivo encontrado no bronze com prefixo: {prefix}")

    data_keys = [key for key in keys if key.endswith("/data.json")]
    if not data_keys:
        raise RuntimeError("Nenhum data.json encontrado para match events no bronze.")

    latest_by_fixture = {}
    for key in data_keys:
        parsed = _extract_fixture_and_run(key)
        if not parsed:
            continue
        fixture_id, run_id = parsed
        current = latest_by_fixture.get(fixture_id)
        if current is None or run_id > current[0]:
            latest_by_fixture[fixture_id] = (run_id, key)

    if not latest_by_fixture:
        raise RuntimeError("Nao foi possivel extrair fixture_id/run dos arquivos de events.")

    selected_items = sorted(
        [(fixture_id, run_id, key) for fixture_id, (run_id, key) in latest_by_fixture.items()],
        key=lambda item: item[0],
    )

    print(
        "Selecionados latest runs por fixture (events) | "
        f"fixtures={len(selected_items)} | arquivos_bronze={len(data_keys)}"
    )

    rows = []
    for fixture_id, run_id, key in selected_items:
        obj = s3.get_object(Bucket=BRONZE_BUCKET, Key=key)
        payload = json.loads(obj["Body"].read().decode("utf-8"))
        errors = payload.get("errors")
        if errors:
            print(f"fixture_id={fixture_id} com erros no payload: {errors}. Pulando.")
            continue

        response_rows = payload.get("response", []) or []
        if not isinstance(response_rows, list):
            print(f"fixture_id={fixture_id} com response invalido. Pulando.")
            continue

        for event in response_rows:
            time_info = (event or {}).get("time") or {}
            team = (event or {}).get("team") or {}
            player = (event or {}).get("player") or {}
            assist = (event or {}).get("assist") or {}

            time_elapsed = _as_int(time_info.get("elapsed"))
            team_id = _as_int(team.get("id"))
            player_id = _as_int(player.get("id"))
            event_type = (event or {}).get("type")
            detail = (event or {}).get("detail")

            rows.append(
                {
                    "event_id": _event_id(fixture_id, time_elapsed, team_id, event_type, detail, player_id),
                    "fixture_id": fixture_id,
                    "time_elapsed": time_elapsed,
                    "time_extra": _as_int(time_info.get("extra")),
                    "team_id": team_id,
                    "team_name": team.get("name"),
                    "player_id": player_id,
                    "player_name": player.get("name"),
                    "assist_id": _as_int(assist.get("id")),
                    "assist_name": assist.get("name"),
                    "type": event_type,
                    "detail": detail,
                    "comments": (event or {}).get("comments"),
                }
            )

    if not rows:
        raise RuntimeError("Nenhuma linha de match events foi gerada apos processamento do bronze.")

    df = pd.DataFrame(rows)
    df["fixture_id"] = pd.to_numeric(df["fixture_id"], errors="coerce").astype("Int64")
    df["time_elapsed"] = pd.to_numeric(df["time_elapsed"], errors="coerce").astype("Int64")
    df["time_extra"] = pd.to_numeric(df["time_extra"], errors="coerce").astype("Int64")
    df["team_id"] = pd.to_numeric(df["team_id"], errors="coerce").astype("Int64")
    df["player_id"] = pd.to_numeric(df["player_id"], errors="coerce").astype("Int64")
    df["assist_id"] = pd.to_numeric(df["assist_id"], errors="coerce").astype("Int64")

    text_cols = ["event_id", "team_name", "player_name", "assist_name", "type", "detail", "comments"]
    for col in text_cols:
        df[col] = df[col].astype("string")

    before_dedup = len(df)
    df = df.drop_duplicates(subset=["event_id"], keep="last").copy()
    duplicated_rows = before_dedup - len(df)

    run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    out_key = (
        f"events/league={LEAGUE_ID}/season={SEASON}"
        f"/run={run_utc}/match_events.parquet"
    )

    buf = BytesIO()
    df.to_parquet(buf, index=False)
    buf.seek(0)
    s3.upload_fileobj(buf, SILVER_BUCKET, out_key)

    print(
        "Bronze->Silver match events concluido | "
        f"rows={len(df)} | duplicadas_removidas={duplicated_rows} | colunas={len(df.columns)} | "
        f"silver=s3://{SILVER_BUCKET}/{out_key}"
    )


with DAG(
    dag_id="bronze_to_silver_match_events",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["silver", "events"],
) as dag:
    PythonOperator(
        task_id="bronze_to_silver_match_events_latest_per_fixture",
        python_callable=bronze_to_silver_match_events_latest_per_fixture,
    )
