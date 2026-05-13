from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from common.observability import DEFAULT_DAG_ARGS
from common.providers import get_default_provider
from common.services.warehouse_service import load_statistics_silver_to_raw


with DAG(
    dag_id="silver_to_postgres_statistics",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    params={"league_id": 71, "season": 2024, "provider": get_default_provider()},
    render_template_as_native_obj=True,
    default_args=DEFAULT_DAG_ARGS,
    tags=["warehouse", "load", "statistics"],
) as dag:
    PythonOperator(
        task_id="load_statistics_silver_to_postgres",
        python_callable=load_statistics_silver_to_raw,
        execution_timeout=timedelta(minutes=25),
    )
