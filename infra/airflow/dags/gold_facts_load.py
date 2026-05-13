from airflow import DAG
from airflow.operators.python import PythonOperator, get_current_context
from datetime import datetime
import os
from sqlalchemy import create_engine, text


DEFAULT_LEAGUE_ID = 71
DEFAULT_SEASON = 2024


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


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

    league_id = _safe_int(conf.get("league_id", params.get("league_id", DEFAULT_LEAGUE_ID)), DEFAULT_LEAGUE_ID, "league_id")
    season = _safe_int(conf.get("season", params.get("season", DEFAULT_SEASON)), DEFAULT_SEASON, "season")
    return league_id, season


def _assert_gold_fact_objects(conn):
    schema_exists = conn.execute(
        text("SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'gold')")
    ).scalar_one()
    if not schema_exists:
        raise ValueError("Schema gold nao existe. Aplique warehouse/ddl/020_gold_dimensions.sql e 021_gold_facts.sql.")

    required_tables = {"fact_matches", "fact_match_events"}
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
            f"Tabelas fact ausentes em gold: {missing_tables}. "
            "Aplique warehouse/ddl/021_gold_facts.sql."
        )


FACT_MATCHES_UPSERT_SQL = text(
    """
    WITH source_rows AS (
        SELECT
            f.fixture_id AS match_id,
            f.league_id,
            f.season,
            f.date_utc::date AS date_day,
            f.home_team_id,
            f.away_team_id,
            f.venue_id,
            f.home_goals,
            f.away_goals,
            COALESCE(f.home_goals, 0) + COALESCE(f.away_goals, 0) AS total_goals,
            CASE
                WHEN COALESCE(f.home_goals, 0) > COALESCE(f.away_goals, 0) THEN 'Home Win'
                WHEN COALESCE(f.home_goals, 0) < COALESCE(f.away_goals, 0) THEN 'Away Win'
                ELSE 'Draw'
            END AS result,
            s_home.total_shots AS home_shots,
            s_home.shots_on_goal AS home_shots_on_target,
            s_home.ball_possession AS home_possession,
            s_home.corner_kicks AS home_corners,
            s_home.fouls AS home_fouls,
            s_away.total_shots AS away_shots,
            s_away.shots_on_goal AS away_shots_on_target,
            s_away.ball_possession AS away_possession,
            s_away.corner_kicks AS away_corners,
            s_away.fouls AS away_fouls
        FROM raw.fixtures f
        LEFT JOIN raw.match_statistics s_home
          ON f.fixture_id = s_home.fixture_id
         AND f.home_team_id = s_home.team_id
        LEFT JOIN raw.match_statistics s_away
          ON f.fixture_id = s_away.fixture_id
         AND f.away_team_id = s_away.team_id
        WHERE f.league_id = :league_id
          AND f.season = :season
          AND f.fixture_id IS NOT NULL
          AND f.date_utc IS NOT NULL
          AND f.home_team_id IS NOT NULL
          AND f.away_team_id IS NOT NULL
    ),
    upserted AS (
        INSERT INTO gold.fact_matches (
            match_id, league_id, season, date_day, home_team_id, away_team_id, venue_id,
            home_goals, away_goals, total_goals, result,
            home_shots, home_shots_on_target, home_possession, home_corners, home_fouls,
            away_shots, away_shots_on_target, away_possession, away_corners, away_fouls,
            updated_at
        )
        SELECT
            match_id, league_id, season, date_day, home_team_id, away_team_id, venue_id,
            home_goals, away_goals, total_goals, result,
            home_shots, home_shots_on_target, home_possession, home_corners, home_fouls,
            away_shots, away_shots_on_target, away_possession, away_corners, away_fouls,
            now()
        FROM source_rows
        ON CONFLICT (match_id) DO UPDATE
        SET
            league_id = EXCLUDED.league_id,
            season = EXCLUDED.season,
            date_day = EXCLUDED.date_day,
            home_team_id = EXCLUDED.home_team_id,
            away_team_id = EXCLUDED.away_team_id,
            venue_id = EXCLUDED.venue_id,
            home_goals = EXCLUDED.home_goals,
            away_goals = EXCLUDED.away_goals,
            total_goals = EXCLUDED.total_goals,
            result = EXCLUDED.result,
            home_shots = EXCLUDED.home_shots,
            home_shots_on_target = EXCLUDED.home_shots_on_target,
            home_possession = EXCLUDED.home_possession,
            home_corners = EXCLUDED.home_corners,
            home_fouls = EXCLUDED.home_fouls,
            away_shots = EXCLUDED.away_shots,
            away_shots_on_target = EXCLUDED.away_shots_on_target,
            away_possession = EXCLUDED.away_possession,
            away_corners = EXCLUDED.away_corners,
            away_fouls = EXCLUDED.away_fouls,
            updated_at = now()
        WHERE gold.fact_matches.league_id IS DISTINCT FROM EXCLUDED.league_id
           OR gold.fact_matches.season IS DISTINCT FROM EXCLUDED.season
           OR gold.fact_matches.date_day IS DISTINCT FROM EXCLUDED.date_day
           OR gold.fact_matches.home_team_id IS DISTINCT FROM EXCLUDED.home_team_id
           OR gold.fact_matches.away_team_id IS DISTINCT FROM EXCLUDED.away_team_id
           OR gold.fact_matches.venue_id IS DISTINCT FROM EXCLUDED.venue_id
           OR gold.fact_matches.home_goals IS DISTINCT FROM EXCLUDED.home_goals
           OR gold.fact_matches.away_goals IS DISTINCT FROM EXCLUDED.away_goals
           OR gold.fact_matches.total_goals IS DISTINCT FROM EXCLUDED.total_goals
           OR gold.fact_matches.result IS DISTINCT FROM EXCLUDED.result
           OR gold.fact_matches.home_shots IS DISTINCT FROM EXCLUDED.home_shots
           OR gold.fact_matches.home_shots_on_target IS DISTINCT FROM EXCLUDED.home_shots_on_target
           OR gold.fact_matches.home_possession IS DISTINCT FROM EXCLUDED.home_possession
           OR gold.fact_matches.home_corners IS DISTINCT FROM EXCLUDED.home_corners
           OR gold.fact_matches.home_fouls IS DISTINCT FROM EXCLUDED.home_fouls
           OR gold.fact_matches.away_shots IS DISTINCT FROM EXCLUDED.away_shots
           OR gold.fact_matches.away_shots_on_target IS DISTINCT FROM EXCLUDED.away_shots_on_target
           OR gold.fact_matches.away_possession IS DISTINCT FROM EXCLUDED.away_possession
           OR gold.fact_matches.away_corners IS DISTINCT FROM EXCLUDED.away_corners
           OR gold.fact_matches.away_fouls IS DISTINCT FROM EXCLUDED.away_fouls
        RETURNING (xmax = 0) AS inserted
    )
    SELECT
        COALESCE(SUM(CASE WHEN inserted THEN 1 ELSE 0 END), 0)::INT AS inserted,
        COALESCE(SUM(CASE WHEN NOT inserted THEN 1 ELSE 0 END), 0)::INT AS updated
    FROM upserted
    """
)


FACT_MATCH_EVENTS_UPSERT_SQL = text(
    """
    WITH source_rows AS (
        SELECT
            e.event_id,
            e.fixture_id AS match_id,
            e.team_id,
            e.player_id,
            e.assist_id AS assist_player_id,
            e.time_elapsed,
            e.time_extra,
            e.type AS event_type,
            e.detail AS event_detail,
            CASE WHEN e.type = 'Goal' THEN TRUE ELSE FALSE END AS is_goal
        FROM raw.match_events e
        JOIN raw.fixtures f
          ON f.fixture_id = e.fixture_id
        WHERE f.league_id = :league_id
          AND f.season = :season
          AND e.event_id IS NOT NULL
          AND e.fixture_id IS NOT NULL
    ),
    upserted AS (
        INSERT INTO gold.fact_match_events (
            event_id, match_id, team_id, player_id, assist_player_id,
            time_elapsed, time_extra, event_type, event_detail, is_goal, updated_at
        )
        SELECT
            event_id, match_id, team_id, player_id, assist_player_id,
            time_elapsed, time_extra, event_type, event_detail, is_goal, now()
        FROM source_rows
        ON CONFLICT (event_id) DO UPDATE
        SET
            match_id = EXCLUDED.match_id,
            team_id = EXCLUDED.team_id,
            player_id = EXCLUDED.player_id,
            assist_player_id = EXCLUDED.assist_player_id,
            time_elapsed = EXCLUDED.time_elapsed,
            time_extra = EXCLUDED.time_extra,
            event_type = EXCLUDED.event_type,
            event_detail = EXCLUDED.event_detail,
            is_goal = EXCLUDED.is_goal,
            updated_at = now()
        WHERE gold.fact_match_events.match_id IS DISTINCT FROM EXCLUDED.match_id
           OR gold.fact_match_events.team_id IS DISTINCT FROM EXCLUDED.team_id
           OR gold.fact_match_events.player_id IS DISTINCT FROM EXCLUDED.player_id
           OR gold.fact_match_events.assist_player_id IS DISTINCT FROM EXCLUDED.assist_player_id
           OR gold.fact_match_events.time_elapsed IS DISTINCT FROM EXCLUDED.time_elapsed
           OR gold.fact_match_events.time_extra IS DISTINCT FROM EXCLUDED.time_extra
           OR gold.fact_match_events.event_type IS DISTINCT FROM EXCLUDED.event_type
           OR gold.fact_match_events.event_detail IS DISTINCT FROM EXCLUDED.event_detail
           OR gold.fact_match_events.is_goal IS DISTINCT FROM EXCLUDED.is_goal
        RETURNING (xmax = 0) AS inserted
    )
    SELECT
        COALESCE(SUM(CASE WHEN inserted THEN 1 ELSE 0 END), 0)::INT AS inserted,
        COALESCE(SUM(CASE WHEN NOT inserted THEN 1 ELSE 0 END), 0)::INT AS updated
    FROM upserted
    """
)


def load_gold_facts():
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    league_id, season = _read_run_params()
    sql_params = {"league_id": league_id, "season": season}

    with engine.begin() as conn:
        _assert_gold_fact_objects(conn)

        matches_stats = conn.execute(FACT_MATCHES_UPSERT_SQL, sql_params).mappings().one()
        events_stats = conn.execute(FACT_MATCH_EVENTS_UPSERT_SQL, sql_params).mappings().one()

    print(
        "Gold facts load concluido | "
        f"league_id={league_id} | season={season} | "
        f"fact_matches: inseridas={matches_stats['inserted']}, atualizadas={matches_stats['updated']} | "
        f"fact_match_events: inseridas={events_stats['inserted']}, atualizadas={events_stats['updated']}"
    )


# Deprecated: legacy SQL-based gold facts loader. Prefer `dbt_run` DAG.
with DAG(
    dag_id="gold_facts_load",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    params={"league_id": DEFAULT_LEAGUE_ID, "season": DEFAULT_SEASON},
    tags=["gold", "facts", "warehouse", "deprecated"],
) as dag:
    PythonOperator(
        task_id="load_gold_facts",
        python_callable=load_gold_facts,
    )
