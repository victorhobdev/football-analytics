from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from common.observability import DEFAULT_DAG_ARGS
from common.services.world_cup_historical_partial_silver_service import (
    normalize_world_cup_historical_partial_silver,
)


with DAG(
    dag_id="normalize_world_cup_historical_partial_silver",
    start_date=datetime(2026, 4, 11),
    schedule_interval=None,
    catchup=False,
    render_template_as_native_obj=True,
    default_args=DEFAULT_DAG_ARGS,
    tags=["world_cup", "silver", "historical", "partial"],
) as dag:
    PythonOperator(
        task_id="normalize_world_cup_historical_partial_silver",
        python_callable=normalize_world_cup_historical_partial_silver,
        execution_timeout=timedelta(hours=1),
    )
