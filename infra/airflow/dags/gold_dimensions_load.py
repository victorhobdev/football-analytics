from airflow import DAG
from airflow.operators.python import PythonOperator, get_current_context
from datetime import date, datetime, timedelta
import os
from sqlalchemy import create_engine, text


DEFAULT_DATE_START = "2023-01-01"
DEFAULT_DATE_END = "2025-12-31"


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _safe_date(value: str, field_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Parametro invalido para {field_name}: {value}. Use YYYY-MM-DD.") from exc


def _read_run_params() -> tuple[date, date]:
    context = get_current_context()
    params = context.get("params") or {}
    dag_run = context.get("dag_run")
    conf = dag_run.conf if dag_run and dag_run.conf else {}

    start_raw = conf.get("date_start", params.get("date_start", DEFAULT_DATE_START))
    end_raw = conf.get("date_end", params.get("date_end", DEFAULT_DATE_END))
    date_start = _safe_date(str(start_raw), "date_start")
    date_end = _safe_date(str(end_raw), "date_end")
    if date_end < date_start:
        raise ValueError(f"Intervalo invalido: date_end ({date_end}) menor que date_start ({date_start}).")
    return date_start, date_end


def _assert_gold_objects(conn):
    schema_exists = conn.execute(
        text("SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'gold')")
    ).scalar_one()
    if not schema_exists:
        raise ValueError("Schema gold nao existe. Aplique warehouse/ddl/020_gold_dimensions.sql.")

    required_tables = {"dim_team", "dim_venue", "dim_competition", "dim_player", "dim_date"}
    found_tables = {
        row[0]
        for row in conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'gold'
                """
            )
        )
    }
    missing_tables = sorted(required_tables - found_tables)
    if missing_tables:
        raise ValueError(
            f"Tabelas gold ausentes: {missing_tables}. "
            "Aplique warehouse/ddl/020_gold_dimensions.sql."
        )


def _build_dim_team_sql() -> str:
    return """
    WITH source_rows AS (
        SELECT DISTINCT home_team_id AS team_id, home_team_name AS team_name
        FROM raw.fixtures
        WHERE home_team_id IS NOT NULL AND home_team_name IS NOT NULL
        UNION
        SELECT DISTINCT away_team_id AS team_id, away_team_name AS team_name
        FROM raw.fixtures
        WHERE away_team_id IS NOT NULL AND away_team_name IS NOT NULL
    ),
    upserted AS (
        INSERT INTO gold.dim_team (team_id, team_name, updated_at)
        SELECT team_id, team_name, now()
        FROM source_rows
        ON CONFLICT (team_id) DO UPDATE
        SET
            team_name = EXCLUDED.team_name,
            updated_at = now()
        WHERE gold.dim_team.team_name IS DISTINCT FROM EXCLUDED.team_name
        RETURNING (xmax = 0) AS inserted
    )
    SELECT
        COALESCE(SUM(CASE WHEN inserted THEN 1 ELSE 0 END), 0)::INT AS inserted,
        COALESCE(SUM(CASE WHEN NOT inserted THEN 1 ELSE 0 END), 0)::INT AS updated
    FROM upserted
    """


def _build_dim_venue_sql() -> str:
    return """
    WITH source_rows AS (
        SELECT DISTINCT venue_id, venue_name, venue_city
        FROM raw.fixtures
        WHERE venue_id IS NOT NULL
          AND venue_name IS NOT NULL
    ),
    upserted AS (
        INSERT INTO gold.dim_venue (venue_id, venue_name, venue_city, updated_at)
        SELECT venue_id, venue_name, venue_city, now()
        FROM source_rows
        ON CONFLICT (venue_id) DO UPDATE
        SET
            venue_name = EXCLUDED.venue_name,
            venue_city = EXCLUDED.venue_city,
            updated_at = now()
        WHERE gold.dim_venue.venue_name IS DISTINCT FROM EXCLUDED.venue_name
           OR gold.dim_venue.venue_city IS DISTINCT FROM EXCLUDED.venue_city
        RETURNING (xmax = 0) AS inserted
    )
    SELECT
        COALESCE(SUM(CASE WHEN inserted THEN 1 ELSE 0 END), 0)::INT AS inserted,
        COALESCE(SUM(CASE WHEN NOT inserted THEN 1 ELSE 0 END), 0)::INT AS updated
    FROM upserted
    """


def _build_dim_competition_sql() -> str:
    return """
    WITH source_rows AS (
        SELECT DISTINCT league_id, league_name
        FROM raw.fixtures
        WHERE league_id IS NOT NULL
          AND league_name IS NOT NULL
    ),
    upserted AS (
        INSERT INTO gold.dim_competition (league_id, league_name, country, updated_at)
        SELECT league_id, league_name, NULL::TEXT AS country, now()
        FROM source_rows
        ON CONFLICT (league_id) DO UPDATE
        SET
            league_name = EXCLUDED.league_name,
            updated_at = now()
        WHERE gold.dim_competition.league_name IS DISTINCT FROM EXCLUDED.league_name
        RETURNING (xmax = 0) AS inserted
    )
    SELECT
        COALESCE(SUM(CASE WHEN inserted THEN 1 ELSE 0 END), 0)::INT AS inserted,
        COALESCE(SUM(CASE WHEN NOT inserted THEN 1 ELSE 0 END), 0)::INT AS updated
    FROM upserted
    """


def _build_dim_player_sql() -> str:
    return """
    WITH source_rows AS (
        SELECT DISTINCT player_id, player_name
        FROM raw.match_events
        WHERE player_id IS NOT NULL
          AND player_name IS NOT NULL
    ),
    upserted AS (
        INSERT INTO gold.dim_player (player_id, player_name, updated_at)
        SELECT player_id, player_name, now()
        FROM source_rows
        ON CONFLICT (player_id) DO UPDATE
        SET
            player_name = EXCLUDED.player_name,
            updated_at = now()
        WHERE gold.dim_player.player_name IS DISTINCT FROM EXCLUDED.player_name
        RETURNING (xmax = 0) AS inserted
    )
    SELECT
        COALESCE(SUM(CASE WHEN inserted THEN 1 ELSE 0 END), 0)::INT AS inserted,
        COALESCE(SUM(CASE WHEN NOT inserted THEN 1 ELSE 0 END), 0)::INT AS updated
    FROM upserted
    """


def _generate_dim_date_rows(date_start: date, date_end: date) -> list[dict]:
    rows = []
    current = date_start
    while current <= date_end:
        rows.append(
            {
                "date_day": current,
                "year": current.year,
                "month": current.month,
                "day": current.day,
                "day_of_week_name": current.strftime("%A"),
                "is_weekend": current.weekday() >= 5,
            }
        )
        current += timedelta(days=1)
    return rows


def load_gold_dimensions():
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    date_start, date_end = _read_run_params()

    dim_team_sql = text(_build_dim_team_sql())
    dim_venue_sql = text(_build_dim_venue_sql())
    dim_competition_sql = text(_build_dim_competition_sql())
    dim_player_sql = text(_build_dim_player_sql())

    dim_date_rows = _generate_dim_date_rows(date_start, date_end)
    dim_date_insert_sql = text(
        """
        INSERT INTO gold.dim_date (
            date_day, year, month, day, day_of_week_name, is_weekend
        )
        VALUES (
            :date_day, :year, :month, :day, :day_of_week_name, :is_weekend
        )
        ON CONFLICT (date_day) DO NOTHING
        """
    )

    with engine.begin() as conn:
        _assert_gold_objects(conn)

        team_stats = conn.execute(dim_team_sql).mappings().one()
        venue_stats = conn.execute(dim_venue_sql).mappings().one()
        competition_stats = conn.execute(dim_competition_sql).mappings().one()
        player_stats = conn.execute(dim_player_sql).mappings().one()

        inserted_dates = 0
        for row in dim_date_rows:
            result = conn.execute(dim_date_insert_sql, row)
            inserted_dates += int(result.rowcount or 0)

    ignored_dates = len(dim_date_rows) - inserted_dates
    print(
        "Gold dimensions load concluido | "
        f"date_range={date_start}..{date_end} | "
        f"dim_team: inseridas={team_stats['inserted']}, atualizadas={team_stats['updated']} | "
        f"dim_venue: inseridas={venue_stats['inserted']}, atualizadas={venue_stats['updated']} | "
        f"dim_competition: inseridas={competition_stats['inserted']}, atualizadas={competition_stats['updated']} | "
        f"dim_player: inseridas={player_stats['inserted']}, atualizadas={player_stats['updated']} | "
        f"dim_date: inseridas={inserted_dates}, ignoradas={ignored_dates}"
    )


# Deprecated: legacy SQL-based gold dimensions loader. Prefer `dbt_run` DAG.
with DAG(
    dag_id="gold_dimensions_load",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    params={"date_start": DEFAULT_DATE_START, "date_end": DEFAULT_DATE_END},
    tags=["gold", "dimensions", "warehouse", "deprecated"],
) as dag:
    PythonOperator(
        task_id="load_gold_dimensions",
        python_callable=load_gold_dimensions,
    )
