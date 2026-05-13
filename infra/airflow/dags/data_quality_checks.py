from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import os
from sqlalchemy import create_engine, text


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


CHECKS = [
    {
        "check_name": "raw_fixtures_null_pk",
        "description": "raw.fixtures possui fixture_id nulo.",
        "sql": """
            SELECT *
            FROM raw.fixtures
            WHERE fixture_id IS NULL
        """,
    },
    {
        "check_name": "raw_events_orphan",
        "description": "raw.match_events possui eventos com fixture_id inexistente em raw.fixtures.",
        "sql": """
            SELECT e.*
            FROM raw.match_events e
            LEFT JOIN raw.fixtures f
              ON e.fixture_id = f.fixture_id
            WHERE f.fixture_id IS NULL
        """,
    },
    {
        "check_name": "gold_fact_matches_no_date",
        "description": "gold.fact_matches possui linhas com date_day nulo.",
        "sql": """
            SELECT *
            FROM gold.fact_matches
            WHERE date_day IS NULL
        """,
    },
    {
        "check_name": "mart_score_mismatch",
        "description": "mart.league_summary possui total_matches > 0 com total_goals = 0.",
        "sql": """
            SELECT *
            FROM mart.league_summary
            WHERE total_matches > 0
              AND total_goals = 0
        """,
    },
]


def run_data_quality_checks():
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    failed = []

    with engine.begin() as conn:
        for check in CHECKS:
            rows = conn.execute(text(check["sql"])).fetchall()
            bad_count = len(rows)

            if bad_count == 0:
                print(
                    f"[DQ PASS] check={check['check_name']} | bad_rows=0 | "
                    f"description={check['description']}"
                )
            else:
                print(
                    f"[DQ FAIL] check={check['check_name']} | bad_rows={bad_count} | "
                    f"description={check['description']}"
                )
                failed.append((check["check_name"], bad_count, check["description"]))

    if failed:
        summary = "; ".join(
            [
                f"{name}(bad_rows={count}): {desc}"
                for name, count, desc in failed
            ]
        )
        raise ValueError(f"Data quality checks falharam: {summary}")

    print(f"Data quality checks concluido com sucesso | checks={len(CHECKS)} | failed=0")


with DAG(
    dag_id="data_quality_checks",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["quality", "validation", "warehouse"],
) as dag:
    PythonOperator(
        task_id="run_data_quality_checks",
        python_callable=run_data_quality_checks,
    )
