from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


DBT_PROJECT_DIR = "/opt/airflow/dbt"
DBT_PROFILES_DIR = "/opt/airflow/dbt"


with DAG(
    dag_id="dbt_run",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["dbt", "gold", "analytics"],
) as dag:
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=(
            "dbt deps "
            f"--project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    dbt_run_core = BashOperator(
        task_id="dbt_run_core",
        bash_command=(
            "dbt run --select marts.core "
            f"--project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    dbt_run_analytics = BashOperator(
        task_id="dbt_run_analytics",
        bash_command=(
            "dbt run --select marts.analytics "
            f"--project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            "dbt test "
            f"--project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    dbt_deps >> dbt_run_core >> dbt_run_analytics >> dbt_test
