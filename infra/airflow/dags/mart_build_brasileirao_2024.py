from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.python import get_current_context
from datetime import datetime
import os
from pathlib import Path
from sqlalchemy import create_engine, text


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _assert_mart_objects(conn):
    schema_exists = conn.execute(
        text("SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'mart')")
    ).scalar_one()
    if not schema_exists:
        raise ValueError("Schema mart nao existe. Aplique warehouse/ddl/010_mart_schema.sql.")

    required_tables = {"team_match_goals_monthly", "league_summary", "standings_evolution"}
    found_tables = {
        row[0]
        for row in conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'mart'
                """
            )
        )
    }
    missing_tables = sorted(required_tables - found_tables)
    if missing_tables:
        raise ValueError(
            f"Tabelas mart ausentes: {missing_tables}. "
            "Aplique warehouse/ddl/011_mart_tables.sql."
        )

    required_team_cols = {"points", "goal_diff"}
    found_team_cols = {
        row[0]
        for row in conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'mart' AND table_name = 'team_match_goals_monthly'
                """
            )
        )
    }
    missing_team_cols = sorted(required_team_cols - found_team_cols)
    if missing_team_cols:
        raise ValueError(
            f"Colunas mart.team_match_goals_monthly ausentes: {missing_team_cols}. "
            "Aplique warehouse/ddl/011_mart_tables.sql atualizado."
        )


def _safe_int(value, default_value: int, field_name: str) -> int:
    if value is None:
        return default_value
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Parametro invalido para {field_name}: {value}") from exc


def _read_run_params() -> tuple[int, int]:
    context = get_current_context()
    params = context.get("params") or {}
    dag_run = context.get("dag_run")
    conf = dag_run.conf if dag_run and dag_run.conf else {}

    league_id = _safe_int(conf.get("league_id", params.get("league_id", 71)), 71, "league_id")
    season = _safe_int(conf.get("season", params.get("season", 2024)), 2024, "season")
    return league_id, season


def _read_sql(filename: str) -> str:
    candidates = []

    configured_dir = os.getenv("WAREHOUSE_QUERIES_DIR")
    if configured_dir:
        candidates.append(Path(configured_dir) / filename)

    # Repo local path: <repo>/infra/airflow/dags -> <repo>/warehouse/queries
    candidates.append(Path(__file__).resolve().parents[3] / "warehouse" / "queries" / filename)
    # Container path fallback if warehouse is mounted into /opt/airflow/warehouse
    candidates.append(Path("/opt/airflow/warehouse/queries") / filename)
    # Last fallback for local executions from repo root
    candidates.append(Path.cwd() / "warehouse" / "queries" / filename)

    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")

    checked_paths = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        f"Arquivo SQL nao encontrado: {filename}. Caminhos verificados: {checked_paths}"
    )


def build_mart():
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    league_id, season = _read_run_params()
    sql_params = {"league_id": league_id, "season": season}

    team_monthly_sql = text(_read_sql("mart_team_monthly_upsert.sql"))
    league_summary_sql = text(_read_sql("mart_league_summary_upsert.sql"))
    standings_sql = text(_read_sql("mart_standings_evolution_upsert.sql"))

    with engine.begin() as conn:
        _assert_mart_objects(conn)

        team_stats = conn.execute(team_monthly_sql, sql_params).mappings().one()
        league_stats = conn.execute(league_summary_sql, sql_params).mappings().one()
        conn.execute(standings_sql, sql_params)

    print(
        "MART build concluido | "
        f"league_id={league_id} | season={season} | "
        f"team_match_goals_monthly: inseridas={team_stats['inserted']}, atualizadas={team_stats['updated']} | "
        f"league_summary: inseridas={league_stats['inserted']}, atualizadas={league_stats['updated']} | "
        "standings_evolution: executado"
    )


with DAG(
    dag_id="mart_build_brasileirao_2024",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    params={"league_id": 71, "season": 2024},
    tags=["mart", "gold", "warehouse"],
) as dag:
    PythonOperator(
        task_id="build_mart_tables",
        python_callable=build_mart,
    )
