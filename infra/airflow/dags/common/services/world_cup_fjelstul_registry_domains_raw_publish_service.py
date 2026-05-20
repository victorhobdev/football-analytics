from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.observability import StepMetrics, log_event
from common.services.world_cup_config import FJELSTUL_SOURCE, WORLD_CUP_COMPETITION_KEY
from common.services.world_cup_raw_publish_service import (
    FIXTURE_ID_BASE,
    PLAYER_ID_BASE,
    TEAM_ID_BASE,
    _stable_bigint,
    _upsert_dataframe,
)

RAW_WC_SQUADS_TARGET_COLUMNS = [
    "edition_key",
    "provider",
    "competition_key",
    "season_label",
    "source_name",
    "source_version",
    "source_row_id",
    "source_team_id",
    "source_player_id",
    "team_internal_id",
    "player_internal_id",
    "team_id",
    "player_id",
    "team_name",
    "team_code",
    "player_name",
    "jersey_number",
    "position_name",
    "position_code",
    "payload",
    "source_run_id",
    "ingested_run",
]

RAW_WC_GOALS_TARGET_COLUMNS = [
    "fixture_id",
    "internal_match_id",
    "edition_key",
    "provider",
    "competition_key",
    "season_label",
    "source_name",
    "source_version",
    "source_match_id",
    "source_goal_id",
    "source_team_id",
    "source_player_id",
    "source_player_team_id",
    "team_internal_id",
    "player_internal_id",
    "player_team_internal_id",
    "team_id",
    "player_id",
    "player_team_id",
    "team_name",
    "player_name",
    "player_team_name",
    "minute_regulation",
    "minute_stoppage",
    "match_period",
    "minute_label",
    "is_penalty",
    "is_own_goal",
    "payload",
    "source_run_id",
    "ingested_run",
]

RAW_WC_BOOKINGS_TARGET_COLUMNS = [
    "fixture_id",
    "internal_match_id",
    "edition_key",
    "provider",
    "competition_key",
    "season_label",
    "source_name",
    "source_version",
    "source_match_id",
    "source_booking_id",
    "source_team_id",
    "source_player_id",
    "team_internal_id",
    "player_internal_id",
    "team_id",
    "player_id",
    "team_name",
    "player_name",
    "minute_regulation",
    "minute_stoppage",
    "match_period",
    "minute_label",
    "is_yellow_card",
    "is_red_card",
    "is_second_yellow_card",
    "is_sending_off",
    "payload",
    "source_run_id",
    "ingested_run",
]

RAW_WC_SUBSTITUTIONS_TARGET_COLUMNS = [
    "fixture_id",
    "internal_match_id",
    "edition_key",
    "provider",
    "competition_key",
    "season_label",
    "source_name",
    "source_version",
    "source_match_id",
    "source_substitution_id",
    "source_team_id",
    "source_player_id",
    "team_internal_id",
    "player_internal_id",
    "team_id",
    "player_id",
    "team_name",
    "player_name",
    "minute_regulation",
    "minute_stoppage",
    "match_period",
    "minute_label",
    "is_going_off",
    "is_coming_on",
    "substitution_role",
    "payload",
    "source_run_id",
    "ingested_run",
]


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _season_label_from_edition(edition_key: str) -> str:
    return edition_key.rsplit("__", 1)[1]


def _provider_for_edition(edition_key: str) -> str:
    return f"world_cup_{_season_label_from_edition(edition_key)}"


def _validate_prerequisites(conn) -> dict[str, int]:
    checks = {
        "silver_squads_rows": "SELECT count(*) FROM silver.wc_squads WHERE source_name = :source_name",
        "silver_goals_rows": "SELECT count(*) FROM silver.wc_goals WHERE source_name = :source_name",
        "silver_bookings_rows": "SELECT count(*) FROM silver.wc_bookings WHERE source_name = :source_name",
        "silver_substitutions_rows": "SELECT count(*) FROM silver.wc_substitutions WHERE source_name = :source_name",
        "fixture_editions": """
            SELECT count(DISTINCT season_label)
            FROM raw.fixtures
            WHERE competition_key = :competition_key
        """,
        "raw_match_events_world_cup": """
            SELECT count(*)
            FROM raw.match_events
            WHERE provider LIKE 'world_cup_%'
               OR provider IN ('statsbomb_open_data', 'fjelstul_worldcup')
        """,
    }
    params = {"source_name": FJELSTUL_SOURCE, "competition_key": WORLD_CUP_COMPETITION_KEY}
    results = {name: int(conn.execute(text(sql), params).scalar_one()) for name, sql in checks.items()}
    for key in ("silver_squads_rows", "silver_goals_rows", "silver_bookings_rows", "silver_substitutions_rows"):
        if results[key] <= 0:
            raise RuntimeError(f"Precondicao raw invalida para {key}: atual={results[key]}")
    if results["fixture_editions"] != 22:
        raise RuntimeError(f"Precondicao raw invalida: raw.fixtures deveria cobrir 22 edicoes, atual={results['fixture_editions']}")
    if results["raw_match_events_world_cup"] != 0:
        raise RuntimeError(
            f"Precondicao raw invalida: raw.match_events da Copa deveria seguir zerado, atual={results['raw_match_events_world_cup']}"
        )
    return results


def _read_wc_squads_frame(conn, run_id: str) -> pd.DataFrame:
    df = pd.read_sql_query(
        text(
            """
            SELECT
              edition_key,
              team_internal_id,
              player_internal_id,
              source_name,
              source_version,
              source_row_id,
              source_team_id,
              source_player_id,
              team_name,
              team_code,
              player_name,
              jersey_number,
              position_name,
              position_code,
              payload
            FROM silver.wc_squads
            WHERE source_name = :source_name
            ORDER BY edition_key, team_internal_id, player_internal_id
            """
        ),
        conn,
        params={"source_name": FJELSTUL_SOURCE},
    )
    if df.empty:
        raise RuntimeError("Nenhum squad silver encontrado para publish raw.")
    df["provider"] = df["edition_key"].map(_provider_for_edition)
    df["competition_key"] = WORLD_CUP_COMPETITION_KEY
    df["season_label"] = df["edition_key"].map(_season_label_from_edition)
    df["team_id"] = df["team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["player_id"] = df["player_internal_id"].map(lambda value: _stable_bigint(value, base=PLAYER_ID_BASE))
    df["payload"] = df.apply(
        lambda row: _json_text(
            {
                "edition_key": row["edition_key"],
                "source_name": row["source_name"],
                "source_version": row["source_version"],
                "team_internal_id": row["team_internal_id"],
                "player_internal_id": row["player_internal_id"],
                "source_payload": row["payload"],
            }
        ),
        axis=1,
    )
    df["source_run_id"] = run_id
    df["ingested_run"] = run_id
    return df[RAW_WC_SQUADS_TARGET_COLUMNS]


def _read_wc_goals_frame(conn, run_id: str) -> pd.DataFrame:
    df = pd.read_sql_query(
        text(
            """
            SELECT
              edition_key,
              internal_match_id,
              team_internal_id,
              player_internal_id,
              player_team_internal_id,
              source_name,
              source_version,
              source_match_id,
              source_goal_id,
              source_team_id,
              source_player_id,
              source_player_team_id,
              team_name,
              player_name,
              player_team_name,
              minute_regulation,
              minute_stoppage,
              match_period,
              minute_label,
              is_penalty,
              is_own_goal,
              payload
            FROM silver.wc_goals
            WHERE source_name = :source_name
            ORDER BY edition_key, internal_match_id, source_goal_id
            """
        ),
        conn,
        params={"source_name": FJELSTUL_SOURCE},
    )
    if df.empty:
        raise RuntimeError("Nenhum goal silver encontrado para publish raw.")
    df["provider"] = df["edition_key"].map(_provider_for_edition)
    df["competition_key"] = WORLD_CUP_COMPETITION_KEY
    df["season_label"] = df["edition_key"].map(_season_label_from_edition)
    df["fixture_id"] = df["internal_match_id"].map(lambda value: _stable_bigint(value, base=FIXTURE_ID_BASE))
    df["team_id"] = df["team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["player_id"] = df["player_internal_id"].map(lambda value: _stable_bigint(value, base=PLAYER_ID_BASE))
    df["player_team_id"] = df["player_team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["payload"] = df.apply(
        lambda row: _json_text(
            {
                "edition_key": row["edition_key"],
                "source_name": row["source_name"],
                "source_version": row["source_version"],
                "team_internal_id": row["team_internal_id"],
                "player_internal_id": row["player_internal_id"],
                "player_team_internal_id": row["player_team_internal_id"],
                "source_payload": row["payload"],
            }
        ),
        axis=1,
    )
    df["source_run_id"] = run_id
    df["ingested_run"] = run_id
    return df[RAW_WC_GOALS_TARGET_COLUMNS]


def _read_wc_bookings_frame(conn, run_id: str) -> pd.DataFrame:
    df = pd.read_sql_query(
        text(
            """
            SELECT
              edition_key,
              internal_match_id,
              team_internal_id,
              player_internal_id,
              source_name,
              source_version,
              source_match_id,
              source_booking_id,
              source_team_id,
              source_player_id,
              team_name,
              player_name,
              minute_regulation,
              minute_stoppage,
              match_period,
              minute_label,
              is_yellow_card,
              is_red_card,
              is_second_yellow_card,
              is_sending_off,
              payload
            FROM silver.wc_bookings
            WHERE source_name = :source_name
            ORDER BY edition_key, internal_match_id, source_booking_id
            """
        ),
        conn,
        params={"source_name": FJELSTUL_SOURCE},
    )
    if df.empty:
        raise RuntimeError("Nenhum booking silver encontrado para publish raw.")
    df["provider"] = df["edition_key"].map(_provider_for_edition)
    df["competition_key"] = WORLD_CUP_COMPETITION_KEY
    df["season_label"] = df["edition_key"].map(_season_label_from_edition)
    df["fixture_id"] = df["internal_match_id"].map(lambda value: _stable_bigint(value, base=FIXTURE_ID_BASE))
    df["team_id"] = df["team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["player_id"] = df["player_internal_id"].map(lambda value: _stable_bigint(value, base=PLAYER_ID_BASE))
    df["payload"] = df.apply(
        lambda row: _json_text(
            {
                "edition_key": row["edition_key"],
                "source_name": row["source_name"],
                "source_version": row["source_version"],
                "team_internal_id": row["team_internal_id"],
                "player_internal_id": row["player_internal_id"],
                "source_payload": row["payload"],
            }
        ),
        axis=1,
    )
    df["source_run_id"] = run_id
    df["ingested_run"] = run_id
    return df[RAW_WC_BOOKINGS_TARGET_COLUMNS]


def _read_wc_substitutions_frame(conn, run_id: str) -> pd.DataFrame:
    df = pd.read_sql_query(
        text(
            """
            SELECT
              edition_key,
              internal_match_id,
              team_internal_id,
              player_internal_id,
              source_name,
              source_version,
              source_match_id,
              source_substitution_id,
              source_team_id,
              source_player_id,
              team_name,
              player_name,
              minute_regulation,
              minute_stoppage,
              match_period,
              minute_label,
              is_going_off,
              is_coming_on,
              substitution_role,
              payload
            FROM silver.wc_substitutions
            WHERE source_name = :source_name
            ORDER BY edition_key, internal_match_id, source_substitution_id
            """
        ),
        conn,
        params={"source_name": FJELSTUL_SOURCE},
    )
    if df.empty:
        raise RuntimeError("Nenhuma substitution silver encontrada para publish raw.")
    df["provider"] = df["edition_key"].map(_provider_for_edition)
    df["competition_key"] = WORLD_CUP_COMPETITION_KEY
    df["season_label"] = df["edition_key"].map(_season_label_from_edition)
    df["fixture_id"] = df["internal_match_id"].map(lambda value: _stable_bigint(value, base=FIXTURE_ID_BASE))
    df["team_id"] = df["team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["player_id"] = df["player_internal_id"].map(lambda value: _stable_bigint(value, base=PLAYER_ID_BASE))
    df["payload"] = df.apply(
        lambda row: _json_text(
            {
                "edition_key": row["edition_key"],
                "source_name": row["source_name"],
                "source_version": row["source_version"],
                "team_internal_id": row["team_internal_id"],
                "player_internal_id": row["player_internal_id"],
                "source_payload": row["payload"],
            }
        ),
        axis=1,
    )
    df["source_run_id"] = run_id
    df["ingested_run"] = run_id
    return df[RAW_WC_SUBSTITUTIONS_TARGET_COLUMNS]


def _validate_raw_outputs(conn, *, silver_counts: dict[str, int]) -> dict[str, int]:
    queries = {
        "raw_squads_rows": "SELECT count(*) FROM raw.wc_squads WHERE source_name = :source_name",
        "raw_goals_rows": "SELECT count(*) FROM raw.wc_goals WHERE source_name = :source_name",
        "raw_bookings_rows": "SELECT count(*) FROM raw.wc_bookings WHERE source_name = :source_name",
        "raw_substitutions_rows": "SELECT count(*) FROM raw.wc_substitutions WHERE source_name = :source_name",
        "raw_squads_editions": "SELECT count(DISTINCT edition_key) FROM raw.wc_squads WHERE source_name = :source_name",
        "raw_goals_editions": "SELECT count(DISTINCT edition_key) FROM raw.wc_goals WHERE source_name = :source_name",
        "raw_bookings_editions": "SELECT count(DISTINCT edition_key) FROM raw.wc_bookings WHERE source_name = :source_name",
        "raw_substitutions_editions": "SELECT count(DISTINCT edition_key) FROM raw.wc_substitutions WHERE source_name = :source_name",
        "raw_goals_orphan_fixtures": """
            SELECT count(*)
            FROM raw.wc_goals g
            LEFT JOIN raw.fixtures f
              ON f.fixture_id = g.fixture_id
             AND f.provider = g.provider
             AND f.competition_key = g.competition_key
             AND f.season_label = g.season_label
            WHERE g.source_name = :source_name
              AND f.fixture_id IS NULL
        """,
        "raw_bookings_orphan_fixtures": """
            SELECT count(*)
            FROM raw.wc_bookings b
            LEFT JOIN raw.fixtures f
              ON f.fixture_id = b.fixture_id
             AND f.provider = b.provider
             AND f.competition_key = b.competition_key
             AND f.season_label = b.season_label
            WHERE b.source_name = :source_name
              AND f.fixture_id IS NULL
        """,
        "raw_substitutions_orphan_fixtures": """
            SELECT count(*)
            FROM raw.wc_substitutions s
            LEFT JOIN raw.fixtures f
              ON f.fixture_id = s.fixture_id
             AND f.provider = s.provider
             AND f.competition_key = s.competition_key
             AND f.season_label = s.season_label
            WHERE s.source_name = :source_name
              AND f.fixture_id IS NULL
        """,
        "raw_squads_null_ids": """
            SELECT count(*)
            FROM raw.wc_squads
            WHERE source_name = :source_name
              AND (team_id IS NULL OR player_id IS NULL)
        """,
        "raw_substitutions_invalid_flags": """
            SELECT count(*)
            FROM raw.wc_substitutions
            WHERE source_name = :source_name
              AND (
                (CASE WHEN is_going_off THEN 1 ELSE 0 END) +
                (CASE WHEN is_coming_on THEN 1 ELSE 0 END)
              ) <> 1
        """,
        "raw_match_events_world_cup": """
            SELECT count(*)
            FROM raw.match_events
            WHERE provider LIKE 'world_cup_%'
               OR provider IN ('statsbomb_open_data', 'fjelstul_worldcup')
        """,
    }
    params = {"source_name": FJELSTUL_SOURCE}
    results = {name: int(conn.execute(text(sql), params).scalar_one()) for name, sql in queries.items()}
    expected = {
        "raw_squads_rows": silver_counts["silver_squads_rows"],
        "raw_goals_rows": silver_counts["silver_goals_rows"],
        "raw_bookings_rows": silver_counts["silver_bookings_rows"],
        "raw_substitutions_rows": silver_counts["silver_substitutions_rows"],
        "raw_squads_editions": silver_counts["silver_squads_editions"],
        "raw_goals_editions": silver_counts["silver_goals_editions"],
        "raw_bookings_editions": silver_counts["silver_bookings_editions"],
        "raw_substitutions_editions": silver_counts["silver_substitutions_editions"],
        "raw_goals_orphan_fixtures": 0,
        "raw_bookings_orphan_fixtures": 0,
        "raw_substitutions_orphan_fixtures": 0,
        "raw_squads_null_ids": 0,
        "raw_substitutions_invalid_flags": 0,
        "raw_match_events_world_cup": 0,
    }
    for key, expected_value in expected.items():
        if results[key] != expected_value:
            raise RuntimeError(f"Validacao raw invalida para {key}: esperado={expected_value} atual={results[key]}")
    return results


def publish_world_cup_fjelstul_registry_domains_to_raw() -> dict[str, Any]:
    context = get_current_context()
    now_utc = _utc_now()
    run_id = f"world_cup_fjelstul_registry_domains_raw__{now_utc.strftime('%Y%m%dT%H%M%SZ')}"
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    with StepMetrics(
        service="airflow",
        module="world_cup_fjelstul_registry_domains_raw_publish_service",
        step="publish_world_cup_fjelstul_registry_domains_to_raw",
        context=context,
        dataset="raw.world_cup_fjelstul_registry_domains",
        table="raw.wc_squads/raw.wc_goals/raw.wc_bookings/raw.wc_substitutions",
    ):
        with engine.begin() as conn:
            prereq = _validate_prerequisites(conn)
            squads_df = _read_wc_squads_frame(conn, run_id)
            goals_df = _read_wc_goals_frame(conn, run_id)
            bookings_df = _read_wc_bookings_frame(conn, run_id)
            substitutions_df = _read_wc_substitutions_frame(conn, run_id)

            squads_counts = _upsert_dataframe(
                conn,
                target_table="wc_squads",
                df=squads_df,
                target_columns=RAW_WC_SQUADS_TARGET_COLUMNS,
                conflict_keys=["source_name", "edition_key", "source_row_id"],
                compare_columns=[
                    col
                    for col in RAW_WC_SQUADS_TARGET_COLUMNS
                    if col not in {"source_name", "edition_key", "source_row_id", "source_run_id", "ingested_run"}
                ],
            )
            goals_counts = _upsert_dataframe(
                conn,
                target_table="wc_goals",
                df=goals_df,
                target_columns=RAW_WC_GOALS_TARGET_COLUMNS,
                conflict_keys=["source_name", "edition_key", "source_goal_id"],
                compare_columns=[
                    col
                    for col in RAW_WC_GOALS_TARGET_COLUMNS
                    if col not in {"source_name", "edition_key", "source_goal_id", "source_run_id", "ingested_run"}
                ],
            )
            bookings_counts = _upsert_dataframe(
                conn,
                target_table="wc_bookings",
                df=bookings_df,
                target_columns=RAW_WC_BOOKINGS_TARGET_COLUMNS,
                conflict_keys=["source_name", "edition_key", "source_booking_id"],
                compare_columns=[
                    col
                    for col in RAW_WC_BOOKINGS_TARGET_COLUMNS
                    if col not in {"source_name", "edition_key", "source_booking_id", "source_run_id", "ingested_run"}
                ],
            )
            substitutions_counts = _upsert_dataframe(
                conn,
                target_table="wc_substitutions",
                df=substitutions_df,
                target_columns=RAW_WC_SUBSTITUTIONS_TARGET_COLUMNS,
                conflict_keys=["source_name", "edition_key", "source_substitution_id"],
                compare_columns=[
                    col
                    for col in RAW_WC_SUBSTITUTIONS_TARGET_COLUMNS
                    if col not in {"source_name", "edition_key", "source_substitution_id", "source_run_id", "ingested_run"}
                ],
            )

            validations = _validate_raw_outputs(
                conn,
                silver_counts={
                    "silver_squads_rows": prereq["silver_squads_rows"],
                    "silver_goals_rows": prereq["silver_goals_rows"],
                    "silver_bookings_rows": prereq["silver_bookings_rows"],
                    "silver_substitutions_rows": prereq["silver_substitutions_rows"],
                    "silver_squads_editions": int(
                        conn.execute(text("SELECT count(DISTINCT edition_key) FROM silver.wc_squads WHERE source_name = :source_name"), {"source_name": FJELSTUL_SOURCE}).scalar_one()
                    ),
                    "silver_goals_editions": int(
                        conn.execute(text("SELECT count(DISTINCT edition_key) FROM silver.wc_goals WHERE source_name = :source_name"), {"source_name": FJELSTUL_SOURCE}).scalar_one()
                    ),
                    "silver_bookings_editions": int(
                        conn.execute(text("SELECT count(DISTINCT edition_key) FROM silver.wc_bookings WHERE source_name = :source_name"), {"source_name": FJELSTUL_SOURCE}).scalar_one()
                    ),
                    "silver_substitutions_editions": int(
                        conn.execute(text("SELECT count(DISTINCT edition_key) FROM silver.wc_substitutions WHERE source_name = :source_name"), {"source_name": FJELSTUL_SOURCE}).scalar_one()
                    ),
                },
            )

    summary = {
        "prerequisites": prereq,
        "wc_squads_upsert": {"inserted": squads_counts[0], "updated": squads_counts[1], "ignored": squads_counts[2]},
        "wc_goals_upsert": {"inserted": goals_counts[0], "updated": goals_counts[1], "ignored": goals_counts[2]},
        "wc_bookings_upsert": {"inserted": bookings_counts[0], "updated": bookings_counts[1], "ignored": bookings_counts[2]},
        "wc_substitutions_upsert": {
            "inserted": substitutions_counts[0],
            "updated": substitutions_counts[1],
            "ignored": substitutions_counts[2],
        },
        "validations": validations,
        "run_id": run_id,
    }
    log_event(
        service="airflow",
        module="world_cup_fjelstul_registry_domains_raw_publish_service",
        step="summary",
        status="success",
        context=context,
        dataset="raw.world_cup_fjelstul_registry_domains",
        row_count=(
            validations["raw_squads_rows"]
            + validations["raw_goals_rows"]
            + validations["raw_bookings_rows"]
            + validations["raw_substitutions_rows"]
        ),
        message=(
            "Raw World Cup Fjelstul registry domains publicado | "
            f"squads={validations['raw_squads_rows']} | "
            f"goals={validations['raw_goals_rows']} | "
            f"bookings={validations['raw_bookings_rows']} | "
            f"substitutions={validations['raw_substitutions_rows']}"
        ),
    )
    return summary
