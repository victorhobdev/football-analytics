from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import os
import json
import time
from io import BytesIO

import boto3
import requests
from sqlalchemy import create_engine, text


LEAGUE_ID = 71
SEASON = 2024
BRONZE_BUCKET = "football-bronze"
FINAL_STATUSES = ("FT", "PEN", "AET")


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


def _api_get_match_events(session: requests.Session, base_url: str, api_key: str, fixture_id: int):
    url = f"{base_url}/fixtures/events"
    headers = {"x-apisports-key": api_key}
    params = {"fixture": fixture_id}

    response = session.get(url, headers=headers, params=params, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Erro API fixture_id={fixture_id}: {response.status_code} - {response.text}")

    data = response.json()
    errors = data.get("errors")
    if errors:
        raise RuntimeError(f"API errors fixture_id={fixture_id}: {errors}")

    return data, response.headers


def _fetch_finished_fixture_ids(engine, league_id: int, season: int) -> list[int]:
    sql = text(
        """
        SELECT DISTINCT fixture_id
        FROM raw.fixtures
        WHERE league_id = :league_id
          AND season = :season
          AND fixture_id IS NOT NULL
          AND status_short IN ('FT', 'PEN', 'AET')
        ORDER BY fixture_id
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"league_id": league_id, "season": season}).fetchall()
    return [int(row[0]) for row in rows]


def ingest_match_events_bronze():
    api_key = _get_required_env("APIFOOTBALL_API_KEY")
    base_url = os.getenv("APIFOOTBALL_BASE_URL", "https://v3.football.api-sports.io")
    pg_dsn = _get_required_env("FOOTBALL_PG_DSN")
    sleep_seconds = float(os.getenv("APIFOOTBALL_EVENTS_SLEEP_SECONDS", "0.35"))

    engine = create_engine(pg_dsn)
    fixture_ids = _fetch_finished_fixture_ids(engine, LEAGUE_ID, SEASON)

    if not fixture_ids:
        print(
            "Nenhum fixture finalizado encontrado em raw.fixtures | "
            f"league_id={LEAGUE_ID} | season={SEASON} | statuses={FINAL_STATUSES}"
        )
        return

    run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    s3 = _s3_client()
    session = requests.Session()

    succeeded = 0
    failed = 0
    total_events = 0

    for idx, fixture_id in enumerate(fixture_ids, start=1):
        try:
            data, headers = _api_get_match_events(session, base_url, api_key, fixture_id)

            events_count = len(data.get("response", []) or [])
            total_events += events_count

            key = (
                f"events/league={LEAGUE_ID}/season={SEASON}"
                f"/fixture_id={fixture_id}/run={run_utc}/data.json"
            )
            payload = BytesIO(json.dumps(data).encode("utf-8"))
            s3.upload_fileobj(payload, BRONZE_BUCKET, key)
            succeeded += 1

            rate_headers = {
                k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()
            }
            print(
                f"[{idx}/{len(fixture_ids)}] fixture_id={fixture_id} eventos={events_count} salvo em "
                f"s3://{BRONZE_BUCKET}/{key} | rate_headers={rate_headers}"
            )
        except Exception as exc:
            failed += 1
            print(f"[{idx}/{len(fixture_ids)}] erro fixture_id={fixture_id}: {exc}")

        if idx < len(fixture_ids) and sleep_seconds > 0:
            time.sleep(sleep_seconds)

    print(
        "Ingestao de match events concluida | "
        f"league_id={LEAGUE_ID} | season={SEASON} | fixtures={len(fixture_ids)} | "
        f"sucesso={succeeded} | falhas={failed} | eventos_ingeridos={total_events}"
    )


with DAG(
    dag_id="ingest_match_events_bronze",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["bronze", "events"],
) as dag:
    PythonOperator(
        task_id="ingest_match_events_from_finished_fixtures",
        python_callable=ingest_match_events_bronze,
    )
