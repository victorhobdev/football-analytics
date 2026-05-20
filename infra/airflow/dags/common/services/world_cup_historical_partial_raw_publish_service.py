from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.observability import StepMetrics, log_event
from common.services.warehouse_service import FIXTURE_LINEUPS_TARGET_COLUMNS
from common.services.world_cup_config import FJELSTUL_SOURCE, WORLD_CUP_COMPETITION_KEY
from common.services.world_cup_raw_publish_service import (
    DEFAULT_WORLD_CUP_EDITION_KEY,
    FIXTURE_ID_BASE,
    LEAGUE_ID_BASE,
    LINEUP_ID_BASE,
    PLAYER_ID_BASE,
    RAW_WC_MATCH_EVENTS_TARGET_COLUMNS,
    SEASON_ID_BASE,
    TEAM_ID_BASE,
    _stable_bigint,
    _upsert_dataframe,
    _upsert_wc_match_events,
)

WORLD_CUP_EDITION_PATTERN = "fifa_world_cup_mens__%"
WORLD_CUP_2018_EDITION_KEY = "fifa_world_cup_mens__2018"
WORLD_CUP_PROVIDER_PATTERN = "world_cup_%"


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


def _world_cup_ids(edition_key: str) -> dict[str, int]:
    return {
        "league_id": _stable_bigint(f"league|{WORLD_CUP_COMPETITION_KEY}", base=LEAGUE_ID_BASE),
        "season_id": _stable_bigint(f"season|{edition_key}", base=SEASON_ID_BASE),
    }


def _lineup_id(provider: str, fixture_id: int, team_id: int, player_id: int) -> int:
    return _stable_bigint(
        f"lineup|provider={provider}|fixture={fixture_id}|team={team_id}|player={player_id}",
        base=LINEUP_ID_BASE,
    )


def _validate_prerequisites(conn) -> dict[str, Any]:
    params = {
        "edition_pattern": WORLD_CUP_EDITION_PATTERN,
        "edition_2018": WORLD_CUP_2018_EDITION_KEY,
        "edition_2022": DEFAULT_WORLD_CUP_EDITION_KEY,
        "source_name": FJELSTUL_SOURCE,
    }
    source_lineup_rows = conn.execute(
        text(
            """
            SELECT count(*)
            FROM bronze.fjelstul_wc_player_appearances
            WHERE edition_key LIKE :edition_pattern
              AND edition_key <> :edition_2018
              AND edition_key <> :edition_2022
            """
        ),
        params,
    ).scalar_one()
    source_event_rows = conn.execute(
        text(
            """
            SELECT
              (SELECT count(*)
               FROM bronze.fjelstul_wc_goals
               WHERE edition_key LIKE :edition_pattern
                 AND edition_key <> :edition_2018
                 AND edition_key <> :edition_2022)
              +
              (SELECT count(*)
               FROM bronze.fjelstul_wc_bookings
               WHERE edition_key LIKE :edition_pattern
                 AND edition_key <> :edition_2018
                 AND edition_key <> :edition_2022)
              +
              (SELECT count(*)
               FROM bronze.fjelstul_wc_substitutions
               WHERE edition_key LIKE :edition_pattern
                 AND edition_key <> :edition_2018
                 AND edition_key <> :edition_2022)
            """
        ),
        params,
    ).scalar_one()
    silver_lineup_rows = conn.execute(
        text(
            """
            SELECT count(*)
            FROM silver.wc_lineups
            WHERE source_name = :source_name
              AND edition_key LIKE :edition_pattern
              AND edition_key <> :edition_2018
              AND edition_key <> :edition_2022
            """
        ),
        params,
    ).scalar_one()
    silver_event_rows = conn.execute(
        text(
            """
            SELECT count(*)
            FROM silver.wc_match_events
            WHERE source_name = :source_name
              AND edition_key LIKE :edition_pattern
              AND edition_key <> :edition_2018
              AND edition_key <> :edition_2022
            """
        ),
        params,
    ).scalar_one()
    silver_lineup_editions = conn.execute(
        text(
            """
            SELECT count(DISTINCT edition_key)
            FROM silver.wc_lineups
            WHERE source_name = :source_name
              AND edition_key LIKE :edition_pattern
              AND edition_key <> :edition_2018
              AND edition_key <> :edition_2022
            """
        ),
        params,
    ).scalar_one()
    silver_event_editions = conn.execute(
        text(
            """
            SELECT count(DISTINCT edition_key)
            FROM silver.wc_match_events
            WHERE source_name = :source_name
              AND edition_key LIKE :edition_pattern
              AND edition_key <> :edition_2018
              AND edition_key <> :edition_2022
            """
        ),
        params,
    ).scalar_one()
    historical_player_map = conn.execute(
        text(
            """
            SELECT count(*)
            FROM raw.provider_entity_map
            WHERE provider = :source_name
              AND entity_type = 'player'
            """
        ),
        params,
    ).scalar_one()
    raw_fixture_lineups_2022 = conn.execute(
        text(
            """
            SELECT count(*)
            FROM raw.fixture_lineups
            WHERE provider = 'world_cup_2022'
              AND competition_key = :competition_key
              AND season_label = '2022'
            """
        ),
        {"competition_key": WORLD_CUP_COMPETITION_KEY},
    ).scalar_one()
    raw_wc_match_events_2022 = conn.execute(
        text(
            """
            SELECT count(*)
            FROM raw.wc_match_events
            WHERE edition_key = :edition_2022
            """
        ),
        params,
    ).scalar_one()
    raw_match_events_world_cup = conn.execute(
        text(
            """
            SELECT count(*)
            FROM raw.match_events
            WHERE provider LIKE :provider_pattern
               OR provider IN ('statsbomb_open_data', 'fjelstul_worldcup')
            """
        ),
        {"provider_pattern": WORLD_CUP_PROVIDER_PATTERN},
    ).scalar_one()

    expected = {
        "source_lineup_rows": 16833,
        "source_event_rows": 10255,
        "silver_lineup_editions": 12,
        "silver_event_editions": 20,
        "raw_fixture_lineups_2022": 3244,
        "raw_wc_match_events_2022": 234652,
        "raw_match_events_world_cup": 0,
    }
    results = {
        "source_lineup_rows": int(source_lineup_rows),
        "source_event_rows": int(source_event_rows),
        "silver_lineup_rows": int(silver_lineup_rows),
        "silver_event_rows": int(silver_event_rows),
        "silver_lineup_editions": int(silver_lineup_editions),
        "silver_event_editions": int(silver_event_editions),
        "historical_player_map": int(historical_player_map),
        "raw_fixture_lineups_2022": int(raw_fixture_lineups_2022),
        "raw_wc_match_events_2022": int(raw_wc_match_events_2022),
        "raw_match_events_world_cup": int(raw_match_events_world_cup),
    }
    for key, expected_value in expected.items():
        if results[key] != expected_value:
            raise RuntimeError(
                f"Precondicao do raw parcial historico invalida para {key}: esperado={expected_value} atual={results[key]}"
            )
    if results["silver_lineup_rows"] <= 0 or results["silver_lineup_rows"] > results["source_lineup_rows"]:
        raise RuntimeError(
            "Precondicao do raw parcial historico invalida para silver_lineup_rows: "
            f"source={results['source_lineup_rows']} silver={results['silver_lineup_rows']}"
        )
    if results["silver_event_rows"] <= 0 or results["silver_event_rows"] > results["source_event_rows"]:
        raise RuntimeError(
            "Precondicao do raw parcial historico invalida para silver_event_rows: "
            f"source={results['source_event_rows']} silver={results['silver_event_rows']}"
        )
    if results["historical_player_map"] <= 0:
        raise RuntimeError("Mapa historico de player do Fjelstul ausente para publish parcial.")
    return results


def _read_lineups_frame(conn, run_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          l.edition_key,
          l.internal_match_id,
          l.team_internal_id,
          l.player_internal_id,
          l.source_name,
          l.source_version,
          l.source_match_id,
          l.source_team_id,
          l.source_player_id,
          l.team_name,
          l.player_name,
          l.player_nickname,
          l.jersey_number,
          l.is_starter,
          l.start_reason,
          l.first_position_name,
          l.first_position_id,
          l.payload
        FROM silver.wc_lineups l
        WHERE l.source_name = :source_name
          AND l.edition_key LIKE :edition_pattern
          AND l.edition_key <> :edition_2018
          AND l.edition_key <> :edition_2022
          AND NOT EXISTS (
            SELECT 1
            FROM silver.wc_lineups sb
            WHERE sb.source_name = 'statsbomb_open_data'
              AND sb.edition_key = l.edition_key
              AND sb.internal_match_id = l.internal_match_id
          )
        ORDER BY l.edition_key, l.internal_match_id, l.team_internal_id, l.player_internal_id
        """
    )
    df = pd.read_sql_query(
        sql,
        conn,
        params={
            "source_name": FJELSTUL_SOURCE,
            "edition_pattern": WORLD_CUP_EDITION_PATTERN,
            "edition_2018": WORLD_CUP_2018_EDITION_KEY,
            "edition_2022": DEFAULT_WORLD_CUP_EDITION_KEY,
        },
    )
    if df.empty:
        raise RuntimeError("Nenhum lineup silver historico parcial encontrado para publish raw.")

    df["season_label"] = df["edition_key"].map(_season_label_from_edition)
    df["provider"] = df["edition_key"].map(_provider_for_edition)
    df["provider_ids"] = df["edition_key"].map(_world_cup_ids)
    df["fixture_id"] = df["internal_match_id"].map(lambda value: _stable_bigint(value, base=FIXTURE_ID_BASE))
    df["team_id"] = df["team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["player_id"] = df["player_internal_id"].map(lambda value: _stable_bigint(value, base=PLAYER_ID_BASE))
    df["lineup_id"] = df.apply(
        lambda row: _lineup_id(row["provider"], int(row["fixture_id"]), int(row["team_id"]), int(row["player_id"])),
        axis=1,
    )
    df["position_id"] = pd.to_numeric(df["first_position_id"], errors="coerce").astype("Int64")
    df["position_name"] = df["first_position_name"].astype("string")
    df["lineup_type_id"] = df["is_starter"].map(lambda value: 1 if bool(value) else 2).astype("Int64")
    df["formation_field"] = pd.Series(pd.NA, index=df.index, dtype="string")
    df["formation_position"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    df["jersey_number"] = pd.to_numeric(df["jersey_number"], errors="coerce").astype("Int64")
    df["details"] = df.apply(
        lambda row: _json_text(
            {
                "start_reason": row["start_reason"],
                "position_name": row["first_position_name"],
                "source_team_id": row["source_team_id"],
                "source_player_id": row["source_player_id"],
            }
        ),
        axis=1,
    )
    df["payload"] = df.apply(
        lambda row: _json_text(
            {
                "edition_key": row["edition_key"],
                "source_name": row["source_name"],
                "source_version": row["source_version"],
                "internal_match_id": row["internal_match_id"],
                "team_internal_id": row["team_internal_id"],
                "player_internal_id": row["player_internal_id"],
                "team_name": row["team_name"],
                "player_name": row["player_name"],
                "player_nickname": row["player_nickname"],
                "source_payload": row["payload"],
            }
        ),
        axis=1,
    )
    df["provider_league_id"] = df["provider_ids"].map(lambda value: value["league_id"])
    df["competition_key"] = WORLD_CUP_COMPETITION_KEY
    df["provider_season_id"] = df["provider_ids"].map(lambda value: value["season_id"])
    df["source_run_id"] = run_id
    df["ingested_run"] = run_id
    df.drop(columns=["provider_ids"], inplace=True)
    return df[FIXTURE_LINEUPS_TARGET_COLUMNS]


def _derive_outcome_label(payload: Any, event_type: str) -> str | None:
    raw = payload if isinstance(payload, dict) else {}
    if event_type == "goal":
        if bool(raw.get("own_goal")):
            return "own_goal"
        if bool(raw.get("penalty")):
            return "penalty_goal"
        return "goal"
    if event_type in {"yellow_card", "red_card", "second_yellow_red", "substitution"}:
        return event_type
    return None


def _derive_play_pattern_label(payload: Any) -> str:
    raw = payload if isinstance(payload, dict) else {}
    dataset = raw.get("dataset")
    if dataset == "goals":
        return "historical_goal_registry"
    if dataset == "bookings":
        return "historical_booking_registry"
    if dataset == "substitutions":
        return "historical_substitution_registry"
    return "historical_discrete_event"


def _read_wc_match_events_frame(conn) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          edition_key,
          internal_match_id,
          source_name,
          source_version,
          source_match_id,
          source_event_id,
          event_index,
          team_internal_id,
          player_internal_id,
          event_type,
          period,
          minute,
          second,
          location_x,
          location_y,
          has_three_sixty_frame,
          payload
        FROM silver.wc_match_events
        WHERE source_name = :source_name
          AND edition_key LIKE :edition_pattern
          AND edition_key <> :edition_2018
          AND edition_key <> :edition_2022
        ORDER BY edition_key, source_match_id, event_index, source_event_id
        """
    )
    df = pd.read_sql_query(
        sql,
        conn,
        params={
            "source_name": FJELSTUL_SOURCE,
            "edition_pattern": WORLD_CUP_EDITION_PATTERN,
            "edition_2018": WORLD_CUP_2018_EDITION_KEY,
            "edition_2022": DEFAULT_WORLD_CUP_EDITION_KEY,
        },
    )
    if df.empty:
        raise RuntimeError("Nenhum match_event silver historico parcial encontrado para publish raw.")

    df["fixture_id"] = df["internal_match_id"].map(lambda value: _stable_bigint(value, base=FIXTURE_ID_BASE))
    df["outcome_label"] = df.apply(lambda row: _derive_outcome_label(row["payload"], row["event_type"]), axis=1)
    df["play_pattern_label"] = df["payload"].map(_derive_play_pattern_label)
    df["is_three_sixty_backed"] = df["has_three_sixty_frame"].fillna(False).astype(bool)
    df["event_payload"] = df.apply(
        lambda row: _json_text(
            {
                "edition_key": row["edition_key"],
                "source_name": row["source_name"],
                "source_version": row["source_version"],
                "internal_match_id": row["internal_match_id"],
                "team_internal_id": row["team_internal_id"],
                "player_internal_id": row["player_internal_id"],
                "source_payload": row["payload"],
            }
        ),
        axis=1,
    )
    return df[RAW_WC_MATCH_EVENTS_TARGET_COLUMNS]


def _validate_outputs(conn, *, expected_lineup_rows: int, expected_event_rows: int) -> dict[str, Any]:
    params = {
        "competition_key": WORLD_CUP_COMPETITION_KEY,
        "provider_pattern": WORLD_CUP_PROVIDER_PATTERN,
        "source_name": FJELSTUL_SOURCE,
        "edition_pattern": WORLD_CUP_EDITION_PATTERN,
        "edition_2018": WORLD_CUP_2018_EDITION_KEY,
        "edition_2022": DEFAULT_WORLD_CUP_EDITION_KEY,
    }
    results = {
        "raw_historical_lineups": conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.fixture_lineups
                WHERE provider LIKE :provider_pattern
                  AND competition_key = :competition_key
                  AND season_label NOT IN ('2018', '2022')
                  AND payload->>'source_name' = :source_name
                """
            ),
            params,
        ).scalar_one(),
        "raw_historical_lineup_editions": conn.execute(
            text(
                """
                SELECT count(DISTINCT season_label)
                FROM raw.fixture_lineups
                WHERE provider LIKE :provider_pattern
                  AND competition_key = :competition_key
                  AND season_label NOT IN ('2018', '2022')
                  AND payload->>'source_name' = :source_name
                """
            ),
            params,
        ).scalar_one(),
        "raw_historical_events": conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.wc_match_events
                WHERE source_name = :source_name
                  AND edition_key LIKE :edition_pattern
                  AND edition_key <> :edition_2018
                  AND edition_key <> :edition_2022
                """
            ),
            params,
        ).scalar_one(),
        "raw_historical_event_editions": conn.execute(
            text(
                """
                SELECT count(DISTINCT edition_key)
                FROM raw.wc_match_events
                WHERE source_name = :source_name
                  AND edition_key LIKE :edition_pattern
                  AND edition_key <> :edition_2018
                  AND edition_key <> :edition_2022
                """
            ),
            params,
        ).scalar_one(),
        "raw_lineup_duplicates": conn.execute(
            text(
                """
                SELECT count(*)
                FROM (
                  SELECT provider, fixture_id, team_id, lineup_id, count(*) AS row_count
                  FROM raw.fixture_lineups
                  WHERE provider LIKE :provider_pattern
                    AND competition_key = :competition_key
                    AND season_label NOT IN ('2018', '2022')
                  GROUP BY 1,2,3,4
                  HAVING count(*) > 1
                ) dup
                """
            ),
            params,
        ).scalar_one(),
        "raw_event_duplicates": conn.execute(
            text(
                """
                SELECT count(*)
                FROM (
                  SELECT source_name, source_match_id, source_event_id, count(*) AS row_count
                  FROM raw.wc_match_events
                  WHERE source_name = :source_name
                    AND edition_key LIKE :edition_pattern
                    AND edition_key <> :edition_2018
                    AND edition_key <> :edition_2022
                  GROUP BY 1,2,3
                  HAVING count(*) > 1
                ) dup
                """
            ),
            params,
        ).scalar_one(),
        "raw_lineup_bad_matches": conn.execute(
            text(
                """
                SELECT count(*)
                FROM (
                  SELECT provider, fixture_id
                  FROM raw.fixture_lineups
                  WHERE provider LIKE :provider_pattern
                    AND competition_key = :competition_key
                    AND season_label NOT IN ('2018', '2022')
                  GROUP BY provider, fixture_id
                  HAVING count(DISTINCT team_id) <> 2
                ) bad
                """
            ),
            params,
        ).scalar_one(),
        "raw_lineup_bad_starters": conn.execute(
            text(
                """
                SELECT count(*)
                FROM (
                  SELECT provider, fixture_id, team_id
                  FROM raw.fixture_lineups
                  WHERE provider LIKE :provider_pattern
                    AND competition_key = :competition_key
                    AND season_label NOT IN ('2018', '2022')
                  GROUP BY provider, fixture_id, team_id
                  HAVING count(*) FILTER (WHERE lineup_type_id = 1) <> 11
                ) bad
                """
            ),
            params,
        ).scalar_one(),
        "raw_lineup_orphan_fixtures": conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.fixture_lineups l
                LEFT JOIN raw.fixtures f
                  ON f.fixture_id = l.fixture_id
                 AND f.provider = l.provider
                 AND f.competition_key = l.competition_key
                 AND f.season_label = l.season_label
                WHERE l.provider LIKE :provider_pattern
                  AND l.competition_key = :competition_key
                  AND l.season_label NOT IN ('2018', '2022')
                  AND f.fixture_id IS NULL
                """
            ),
            params,
        ).scalar_one(),
        "raw_event_null_fixture_id": conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.wc_match_events
                WHERE source_name = :source_name
                  AND edition_key LIKE :edition_pattern
                  AND edition_key <> :edition_2018
                  AND edition_key <> :edition_2022
                  AND fixture_id IS NULL
                """
            ),
            params,
        ).scalar_one(),
        "raw_event_orphan_fixtures": conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.wc_match_events e
                LEFT JOIN raw.fixtures f
                  ON f.fixture_id = e.fixture_id
                 AND f.provider = ('world_cup_' || substring(e.edition_key from '([0-9]{4})$'))
                 AND f.competition_key = :competition_key
                 AND f.season_label = substring(e.edition_key from '([0-9]{4})$')
                WHERE e.source_name = :source_name
                  AND e.edition_key LIKE :edition_pattern
                  AND e.edition_key <> :edition_2018
                  AND e.edition_key <> :edition_2022
                  AND f.fixture_id IS NULL
                """
            ),
            params,
        ).scalar_one(),
        "raw_rich_lineup_contamination": conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.fixture_lineups
                WHERE provider IN ('world_cup_2018', 'world_cup_2022')
                  AND competition_key = :competition_key
                  AND payload::text LIKE '%fjelstul_worldcup%'
                """
            ),
            params,
        ).scalar_one(),
        "raw_rich_event_contamination": conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.wc_match_events
                WHERE source_name = :source_name
                  AND (
                    edition_key = :edition_2018
                    OR edition_key = :edition_2022
                  )
                """
            ),
            params,
        ).scalar_one(),
        "raw_match_events_world_cup": conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.match_events
                WHERE provider LIKE :provider_pattern
                   OR provider IN ('statsbomb_open_data', 'fjelstul_worldcup')
                """
            ),
            {"provider_pattern": WORLD_CUP_PROVIDER_PATTERN},
        ).scalar_one(),
        "raw_fixture_lineups_2022": conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.fixture_lineups
                WHERE provider = 'world_cup_2022'
                  AND competition_key = :competition_key
                  AND season_label = '2022'
                """
            ),
            params,
        ).scalar_one(),
        "raw_wc_match_events_2022": conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.wc_match_events
                WHERE edition_key = :edition_2022
                """
            ),
            params,
        ).scalar_one(),
    }

    expected = {
        "raw_historical_lineups": expected_lineup_rows,
        "raw_historical_lineup_editions": 12,
        "raw_historical_events": expected_event_rows,
        "raw_historical_event_editions": 20,
        "raw_lineup_duplicates": 0,
        "raw_event_duplicates": 0,
        "raw_lineup_bad_matches": 0,
        "raw_lineup_bad_starters": 0,
        "raw_lineup_orphan_fixtures": 0,
        "raw_event_null_fixture_id": 0,
        "raw_event_orphan_fixtures": 0,
        "raw_rich_lineup_contamination": 0,
        "raw_rich_event_contamination": 0,
        "raw_match_events_world_cup": 0,
        "raw_fixture_lineups_2022": 3244,
        "raw_wc_match_events_2022": 234652,
    }
    for key, expected_value in expected.items():
        if int(results[key]) != expected_value:
            raise RuntimeError(
                f"Validacao do raw historico parcial invalida para {key}: esperado={expected_value} atual={results[key]}"
            )
    return {key: int(value) for key, value in results.items()}


def publish_world_cup_historical_partial_to_raw() -> dict[str, Any]:
    context = get_current_context()
    now_utc = _utc_now()
    run_id = f"world_cup_historical_partial_raw__{now_utc.strftime('%Y%m%dT%H%M%SZ')}"
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    with StepMetrics(
        service="airflow",
        module="world_cup_historical_partial_raw_publish_service",
        step="publish_world_cup_historical_partial_to_raw",
        context=context,
        dataset="raw.world_cup_historical_partial",
        table="raw.fixture_lineups/raw.wc_match_events",
    ):
        with engine.begin() as conn:
            prerequisites = _validate_prerequisites(conn)
            lineups_df = _read_lineups_frame(conn, run_id)
            wc_match_events_df = _read_wc_match_events_frame(conn)

            lineups_counts = _upsert_dataframe(
                conn,
                target_table="fixture_lineups",
                df=lineups_df,
                target_columns=FIXTURE_LINEUPS_TARGET_COLUMNS,
                conflict_keys=["provider", "fixture_id", "team_id", "lineup_id"],
                compare_columns=[
                    col
                    for col in FIXTURE_LINEUPS_TARGET_COLUMNS
                    if col not in {"provider", "fixture_id", "team_id", "lineup_id", "ingested_run", "source_run_id"}
                ],
            )
            wc_events_counts = _upsert_wc_match_events(conn, wc_match_events_df)
            validations = _validate_outputs(
                conn,
                expected_lineup_rows=len(lineups_df),
                expected_event_rows=int(prerequisites["source_event_rows"]),
            )

    summary = {
        "prerequisites": prerequisites,
        "lineups_upsert": {"inserted": lineups_counts[0], "updated": lineups_counts[1], "ignored": lineups_counts[2]},
        "wc_match_events_upsert": {
            "inserted": wc_events_counts[0],
            "updated": wc_events_counts[1],
            "ignored": wc_events_counts[2],
        },
        "validations": validations,
        "run_id": run_id,
    }
    log_event(
        service="airflow",
        module="world_cup_historical_partial_raw_publish_service",
        step="summary",
        status="success",
        context=context,
        dataset="raw.world_cup_historical_partial",
        row_count=len(lineups_df) + len(wc_match_events_df),
        message=(
            "Raw historico parcial da Copa publicado | "
            f"lineups={summary['validations']['raw_historical_lineups']} | "
            f"events={summary['validations']['raw_historical_events']} | "
            f"lineup_editions={summary['validations']['raw_historical_lineup_editions']} | "
            f"event_editions={summary['validations']['raw_historical_event_editions']}"
        ),
    )
    return summary
