from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from common.observability import DEFAULT_DAG_ARGS
from common.services.world_cup_identity_bootstrap_service import bootstrap_world_cup_historical_player_identity_map


with DAG(
    dag_id="bootstrap_world_cup_historical_player_identity_map",
    start_date=datetime(2026, 4, 11),
    schedule_interval=None,
    catchup=False,
    render_template_as_native_obj=True,
    default_args=DEFAULT_DAG_ARGS,
    tags=["world_cup", "identity", "bootstrap", "historical"],
) as dag:
    PythonOperator(
        task_id="bootstrap_historical_fjelstul_player_identity_map",
        python_callable=bootstrap_world_cup_historical_player_identity_map,
        execution_timeout=timedelta(hours=1),
    )
