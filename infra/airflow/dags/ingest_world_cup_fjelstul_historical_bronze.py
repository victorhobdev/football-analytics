from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from common.observability import DEFAULT_DAG_ARGS
from common.services.world_cup_bronze_service import ingest_world_cup_fjelstul_historical_bronze


with DAG(
    dag_id="ingest_world_cup_fjelstul_historical_bronze",
    start_date=datetime(2026, 4, 11),
    schedule_interval=None,
    catchup=False,
    render_template_as_native_obj=True,
    default_args=DEFAULT_DAG_ARGS,
    tags=["bronze", "world_cup", "historical", "fjelstul"],
) as dag:
    PythonOperator(
        task_id="load_world_cup_fjelstul_historical_snapshots_to_bronze",
        python_callable=ingest_world_cup_fjelstul_historical_bronze,
        execution_timeout=timedelta(hours=1),
    )
