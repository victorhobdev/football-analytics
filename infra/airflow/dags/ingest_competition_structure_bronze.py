from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from common.observability import DEFAULT_DAG_ARGS
from common.providers import get_default_league_id, get_default_provider
from common.services.ingestion_service import ingest_competition_structure_raw

DEFAULT_PROVIDER = get_default_provider()
DEFAULT_LEAGUE_ID = get_default_league_id(DEFAULT_PROVIDER)


with DAG(
    dag_id="ingest_competition_structure_bronze",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    max_active_runs=1,
    catchup=False,
    params={"league_id": DEFAULT_LEAGUE_ID, "season": 2024, "provider": DEFAULT_PROVIDER},
    render_template_as_native_obj=True,
    default_args=DEFAULT_DAG_ARGS,
    tags=["bronze", "competition", "structure"],
) as dag:
    PythonOperator(
        task_id="ingest_competition_structure",
        python_callable=ingest_competition_structure_raw,
        execution_timeout=timedelta(minutes=30),
    )
