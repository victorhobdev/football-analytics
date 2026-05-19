from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from common.observability import DEFAULT_DAG_ARGS
from common.services.world_cup_config import DEFAULT_WORLD_CUP_EDITION_KEY
from common.services.world_cup_raw_publish_service import publish_world_cup_to_raw


with DAG(
    dag_id="publish_world_cup_raw",
    start_date=datetime(2026, 4, 10),
    schedule_interval=None,
    catchup=False,
    render_template_as_native_obj=True,
    default_args=DEFAULT_DAG_ARGS,
    params={"edition_key": DEFAULT_WORLD_CUP_EDITION_KEY},
    tags=["world_cup", "raw", "publish"],
) as dag:
    PythonOperator(
        task_id="publish_world_cup_silver_to_raw",
        python_callable=publish_world_cup_to_raw,
        execution_timeout=timedelta(hours=1),
    )
