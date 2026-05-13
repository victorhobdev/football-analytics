from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from common.observability import DEFAULT_DAG_ARGS
from common.providers import get_default_provider
from common.services.mapping_service import map_fixtures_raw_to_silver


with DAG(
    dag_id="bronze_to_silver_fixtures_backfill",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    params={"league_id": 71, "season": 2024, "provider": get_default_provider()},
    render_template_as_native_obj=True,
    default_args=DEFAULT_DAG_ARGS,
    tags=["silver", "backfill"],
) as dag:
    PythonOperator(
        task_id="bronze_to_silver_latest_run",
        python_callable=map_fixtures_raw_to_silver,
        execution_timeout=timedelta(minutes=20),
    )
