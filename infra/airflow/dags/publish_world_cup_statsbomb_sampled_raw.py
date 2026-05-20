from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from common.observability import DEFAULT_DAG_ARGS
from common.services.world_cup_statsbomb_sampled_raw_publish_service import (
    publish_world_cup_statsbomb_sampled_to_raw,
)


with DAG(
    dag_id="publish_world_cup_statsbomb_sampled_raw",
    start_date=datetime(2026, 4, 11),
    schedule_interval=None,
    catchup=False,
    render_template_as_native_obj=True,
    default_args=DEFAULT_DAG_ARGS,
    tags=["world_cup", "raw", "statsbomb", "historical", "sampled"],
) as dag:
    PythonOperator(
        task_id="publish_world_cup_statsbomb_sampled_to_raw",
        python_callable=publish_world_cup_statsbomb_sampled_to_raw,
        execution_timeout=timedelta(hours=1),
    )
