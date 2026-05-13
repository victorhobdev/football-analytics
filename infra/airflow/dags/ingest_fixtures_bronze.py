from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from common.observability import DEFAULT_DAG_ARGS
from common.providers import get_default_provider
from common.services.ingestion_service import ingest_fixtures_raw


with DAG(
    dag_id="ingest_brasileirao_2024_backfill",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    params={"league_id": 71, "season": 2024, "provider": get_default_provider()},
    render_template_as_native_obj=True,
    default_args=DEFAULT_DAG_ARGS,
    tags=["bronze", "backfill"],
) as dag:
    PythonOperator(
        task_id="ingest_fixtures_2024_in_windows",
        python_callable=ingest_fixtures_raw,
        execution_timeout=timedelta(minutes=20),
    )
