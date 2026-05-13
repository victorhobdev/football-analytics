from datetime import datetime

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator, get_current_context
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.task_group import TaskGroup


DEFAULT_LEAGUE_ID = 71
DEFAULT_SEASON = 2024


def _safe_int(value, default_value: int, field_name: str) -> int:
    if value is None:
        return default_value
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Parametro invalido para {field_name}: {value}") from exc


def resolve_params() -> dict:
    context = get_current_context()
    params = context.get("params") or {}
    dag_run = context.get("dag_run")
    conf = dag_run.conf if dag_run and dag_run.conf else {}

    resolved = {
        "league_id": _safe_int(conf.get("league_id", params.get("league_id", DEFAULT_LEAGUE_ID)), DEFAULT_LEAGUE_ID, "league_id"),
        "season": _safe_int(conf.get("season", params.get("season", DEFAULT_SEASON)), DEFAULT_SEASON, "season"),
    }
    print(f"[pipeline_brasileirao] Params resolvidos: {resolved}")
    return resolved


def log_stage(stage: str, action: str):
    context = get_current_context()
    run_id = context.get("run_id")
    print(f"[pipeline_brasileirao] {action} | stage={stage} | run_id={run_id}")


with DAG(
    dag_id="pipeline_brasileirao",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    params={"league_id": DEFAULT_LEAGUE_ID, "season": DEFAULT_SEASON},
    render_template_as_native_obj=True,
    tags=["pipeline", "orchestrator", "brasileirao"],
) as dag:
    resolve_runtime_params = PythonOperator(
        task_id="resolve_runtime_params",
        python_callable=resolve_params,
    )

    def trigger_task(task_id: str, dag_id: str) -> TriggerDagRunOperator:
        return TriggerDagRunOperator(
            task_id=task_id,
            trigger_dag_id=dag_id,
            conf="{{ ti.xcom_pull(task_ids='resolve_runtime_params') }}",
            wait_for_completion=True,
            poke_interval=10,
            reset_dag_run=True,
            allowed_states=["success"],
            failed_states=["failed"],
        )

    with TaskGroup(group_id="group_1_ingestion") as group_1_ingestion:
        run_ingest_fixtures = trigger_task(
            task_id="run_ingest_brasileirao_2024_backfill",
            dag_id="ingest_brasileirao_2024_backfill",
        )
        run_ingest_statistics = trigger_task(
            task_id="run_ingest_statistics_bronze",
            dag_id="ingest_statistics_bronze",
        )
        run_ingest_match_events = trigger_task(
            task_id="run_ingest_match_events_bronze",
            dag_id="ingest_match_events_bronze",
        )

    with TaskGroup(group_id="group_2_lake_raw") as group_2_lake_raw:
        run_bronze_to_silver_fixtures = trigger_task(
            task_id="run_bronze_to_silver_fixtures_backfill",
            dag_id="bronze_to_silver_fixtures_backfill",
        )
        run_silver_to_postgres_fixtures = trigger_task(
            task_id="run_silver_to_postgres_fixtures",
            dag_id="silver_to_postgres_fixtures",
        )
        run_bronze_to_silver_fixtures >> run_silver_to_postgres_fixtures

        run_bronze_to_silver_statistics = trigger_task(
            task_id="run_bronze_to_silver_statistics",
            dag_id="bronze_to_silver_statistics",
        )
        run_silver_to_postgres_statistics = trigger_task(
            task_id="run_silver_to_postgres_statistics",
            dag_id="silver_to_postgres_statistics",
        )
        run_bronze_to_silver_statistics >> run_silver_to_postgres_statistics

        run_bronze_to_silver_match_events = trigger_task(
            task_id="run_bronze_to_silver_match_events",
            dag_id="bronze_to_silver_match_events",
        )
        run_silver_to_postgres_match_events = trigger_task(
            task_id="run_silver_to_postgres_match_events",
            dag_id="silver_to_postgres_match_events",
        )
        run_bronze_to_silver_match_events >> run_silver_to_postgres_match_events

    with TaskGroup(group_id="group_3_gold") as group_3_gold:
        run_gold_dimensions = trigger_task(
            task_id="run_gold_dimensions_load",
            dag_id="gold_dimensions_load",
        )
        run_gold_facts = trigger_task(
            task_id="run_gold_facts_load",
            dag_id="gold_facts_load",
        )
        run_gold_dimensions >> run_gold_facts

    with TaskGroup(group_id="group_4_mart_quality") as group_4_mart_quality:
        run_mart = trigger_task(
            task_id="run_mart_build_brasileirao_2024",
            dag_id="mart_build_brasileirao_2024",
        )
        run_quality = trigger_task(
            task_id="run_data_quality_checks",
            dag_id="data_quality_checks",
        )
        run_mart >> run_quality

    start_pipeline = PythonOperator(
        task_id="start_pipeline",
        python_callable=log_stage,
        op_kwargs={"stage": "pipeline_brasileirao", "action": "START"},
    )
    end_pipeline = PythonOperator(
        task_id="end_pipeline",
        python_callable=log_stage,
        op_kwargs={"stage": "pipeline_brasileirao", "action": "END"},
    )

    group_1_done = EmptyOperator(task_id="group_1_done")
    group_2_done = EmptyOperator(task_id="group_2_done")
    group_3_done = EmptyOperator(task_id="group_3_done")

    resolve_runtime_params >> start_pipeline >> group_1_ingestion >> group_1_done
    group_1_done >> group_2_lake_raw >> group_2_done
    group_2_done >> group_3_gold >> group_3_done
    group_3_done >> group_4_mart_quality >> end_pipeline
