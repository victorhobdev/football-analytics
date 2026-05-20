from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from airflow.operators.python import get_current_context
from sqlalchemy import bindparam, create_engine, text

from common.observability import StepMetrics, log_event
from common.services.warehouse_service import FIXTURE_LINEUPS_TARGET_COLUMNS
from common.services.world_cup_config import (
    STATSBOMB_SOURCE,
    WORLD_CUP_COMPETITION_KEY,
    get_world_cup_statsbomb_sampled_edition_configs,
)
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
from common.services.world_cup_statsbomb_sampled_bronze_service import (
    EXPECTED_EVENT_ROWS,
    EXPECTED_LINEUP_ROWS,
)

WORLD_CUP_PROVIDER_PATTERN = "world_cup_%"
SAMPLED_CONFIGS = get_world_cup_statsbomb_sampled_edition_configs()
SAMPLED_EDITION_KEYS = [config.edition_key for config in SAMPLED_CONFIGS]
EXPECTED_SAMPLED_LINEUP_TOTAL = sum(EXPECTED_LINEUP_ROWS.values())
EXPECTED_SAMPLED_EVENT_TOTAL = sum(EXPECTED_EVENT_ROWS.values())
EXPECTED_RAW_HISTORICAL_LINEUPS_TOTAL = 17_274
EXPECTED_RAW_HISTORICAL_EVENTS_TOTAL = 72_244


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


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


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
    results: dict[str, Any] = {}
    for config in SAMPLED_CONFIGS:
        params = {"edition_key": config.edition_key, "source_name": STATSBOMB_SOURCE}
        lineup_rows = int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM silver.wc_lineups
                    WHERE source_name = :source_name
                      AND edition_key = :edition_key
                    """
                ),
                params,
            ).scalar_one()
        )
        event_rows = int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM silver.wc_match_events
                    WHERE source_name = :source_name
                      AND edition_key = :edition_key
                    """
                ),
                params,
            ).scalar_one()
        )
        lineup_matches = int(
            conn.execute(
                text(
                    """
                    SELECT count(DISTINCT internal_match_id)
                    FROM silver.wc_lineups
                    WHERE source_name = :source_name
                      AND edition_key = :edition_key
                    """
                ),
                params,
            ).scalar_one()
        )
        event_matches = int(
            conn.execute(
                text(
                    """
                    SELECT count(DISTINCT internal_match_id)
                    FROM silver.wc_match_events
                    WHERE source_name = :source_name
                      AND edition_key = :edition_key
                    """
                ),
                params,
            ).scalar_one()
        )
        if lineup_rows != EXPECTED_LINEUP_ROWS[config.edition_key]:
            raise RuntimeError(
                f"Precondicao sampled raw invalida para {config.edition_key}: "
                f"lineup_rows esperado={EXPECTED_LINEUP_ROWS[config.edition_key]} atual={lineup_rows}"
            )
        if event_rows != EXPECTED_EVENT_ROWS[config.edition_key]:
            raise RuntimeError(
                f"Precondicao sampled raw invalida para {config.edition_key}: "
                f"event_rows esperado={EXPECTED_EVENT_ROWS[config.edition_key]} atual={event_rows}"
            )
        if lineup_matches != config.expected_statsbomb_lineup_match_files:
            raise RuntimeError(
                f"Precondicao sampled raw invalida para {config.edition_key}: "
                f"lineup_matches esperado={config.expected_statsbomb_lineup_match_files} atual={lineup_matches}"
            )
        if event_matches != config.expected_statsbomb_event_match_files:
            raise RuntimeError(
                f"Precondicao sampled raw invalida para {config.edition_key}: "
                f"event_matches esperado={config.expected_statsbomb_event_match_files} atual={event_matches}"
            )
        results[config.edition_key] = {
            "lineup_rows": lineup_rows,
            "event_rows": event_rows,
            "lineup_matches": lineup_matches,
            "event_matches": event_matches,
        }

    shared = {
        "edition_keys": SAMPLED_EDITION_KEYS,
        "source_name": STATSBOMB_SOURCE,
        "edition_2022": DEFAULT_WORLD_CUP_EDITION_KEY,
        "competition_key": WORLD_CUP_COMPETITION_KEY,
        "provider_pattern": WORLD_CUP_PROVIDER_PATTERN,
    }
    raw_match_events_world_cup = int(
        conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.match_events
                WHERE provider LIKE :provider_pattern
                   OR provider IN ('statsbomb_open_data', 'fjelstul_worldcup')
                """
            ),
            shared,
        ).scalar_one()
    )
    raw_fixture_lineups_2022 = int(
        conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.fixture_lineups
                WHERE provider = 'world_cup_2022'
                  AND competition_key = :competition_key
                  AND season_label = '2022'
                """
            ),
            shared,
        ).scalar_one()
    )
    raw_wc_match_events_2022 = int(
        conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.wc_match_events
                WHERE edition_key = :edition_2022
                """
            ),
            shared,
        ).scalar_one()
    )
    if raw_match_events_world_cup != 0:
        raise RuntimeError(f"Precondicao sampled raw invalida: raw.match_events da Copa deveria ser 0 e veio {raw_match_events_world_cup}")
    if raw_fixture_lineups_2022 != 3244:
        raise RuntimeError(
            f"Precondicao sampled raw invalida: raw.fixture_lineups 2022 esperado=3244 atual={raw_fixture_lineups_2022}"
        )
    if raw_wc_match_events_2022 != 234652:
        raise RuntimeError(
            f"Precondicao sampled raw invalida: raw.wc_match_events 2022 esperado=234652 atual={raw_wc_match_events_2022}"
        )
    results["raw_match_events_world_cup"] = raw_match_events_world_cup
    results["raw_fixture_lineups_2022"] = raw_fixture_lineups_2022
    results["raw_wc_match_events_2022"] = raw_wc_match_events_2022
    return results


def _read_lineups_frame(conn, run_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          edition_key,
          internal_match_id,
          team_internal_id,
          player_internal_id,
          source_name,
          source_version,
          source_match_id,
          source_team_id,
          source_player_id,
          team_name,
          player_name,
          player_nickname,
          jersey_number,
          is_starter,
          start_reason,
          first_position_name,
          first_position_id,
          payload
        FROM silver.wc_lineups
        WHERE source_name = :source_name
          AND edition_key IN :edition_keys
        ORDER BY edition_key, internal_match_id, team_internal_id, player_internal_id
        """
    ).bindparams(bindparam("edition_keys", expanding=True))
    df = pd.read_sql_query(
        sql,
        conn,
        params={"source_name": STATSBOMB_SOURCE, "edition_keys": SAMPLED_EDITION_KEYS},
    )
    if df.empty:
        raise RuntimeError("Nenhum lineup silver sampled do StatsBomb encontrado para publish raw.")

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
    df["details"] = df["payload"].map(lambda payload: _json_text((_json_object(payload).get("positions") or [])))
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
                "source_payload": _json_object(row["payload"]),
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


def _read_wc_match_events_frame(conn) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          internal_match_id,
          edition_key,
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
          COALESCE(
            payload #>> '{pass,outcome,name}',
            payload #>> '{shot,outcome,name}',
            payload #>> '{dribble,outcome,name}',
            payload #>> '{goalkeeper,outcome,name}',
            payload #>> '{duel,outcome,name}',
            payload #>> '{interception,outcome,name}',
            payload #>> '{50_50,outcome,name}',
            payload #>> '{ball_receipt,outcome,name}'
          ) AS outcome_label,
          play_pattern AS play_pattern_label,
          has_three_sixty_frame AS is_three_sixty_backed,
          payload AS event_payload
        FROM silver.wc_match_events
        WHERE source_name = :source_name
          AND edition_key IN :edition_keys
        ORDER BY edition_key, internal_match_id, event_index, source_event_id
        """
    ).bindparams(bindparam("edition_keys", expanding=True))
    df = pd.read_sql_query(
        sql,
        conn,
        params={"source_name": STATSBOMB_SOURCE, "edition_keys": SAMPLED_EDITION_KEYS},
    )
    if df.empty:
        raise RuntimeError("Nenhum match_event silver sampled do StatsBomb encontrado para publish raw.")

    df["fixture_id"] = df["internal_match_id"].map(lambda value: _stable_bigint(value, base=FIXTURE_ID_BASE))
    df["event_payload"] = df["event_payload"].map(_json_text)
    return df[RAW_WC_MATCH_EVENTS_TARGET_COLUMNS]


def _validate_outputs(conn) -> dict[str, Any]:
    params = {
        "source_name": STATSBOMB_SOURCE,
        "edition_keys": SAMPLED_EDITION_KEYS,
        "provider_pattern": WORLD_CUP_PROVIDER_PATTERN,
        "competition_key": WORLD_CUP_COMPETITION_KEY,
        "edition_2022": DEFAULT_WORLD_CUP_EDITION_KEY,
    }
    results: dict[str, Any] = {
        "raw_historical_lineups_total": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM raw.fixture_lineups
                    WHERE provider LIKE :provider_pattern
                      AND competition_key = :competition_key
                      AND season_label NOT IN ('2018', '2022')
                    """
                ),
                params,
            ).scalar_one()
        ),
        "raw_historical_events_total": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM raw.wc_match_events
                    WHERE edition_key LIKE 'fifa_world_cup_mens__%'
                      AND edition_key <> :edition_2022
                      AND edition_key <> 'fifa_world_cup_mens__2018'
                    """
                ),
                params,
            ).scalar_one()
        ),
        "raw_lineup_duplicates": int(
            conn.execute(
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
            ).scalar_one()
        ),
        "raw_event_duplicates": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM (
                      SELECT source_name, source_match_id, source_event_id, count(*) AS row_count
                      FROM raw.wc_match_events
                      WHERE source_name = :source_name
                        AND edition_key IN :edition_keys
                      GROUP BY 1,2,3
                      HAVING count(*) > 1
                    ) dup
                    """
                ).bindparams(bindparam("edition_keys", expanding=True)),
                params,
            ).scalar_one()
        ),
        "raw_lineup_orphan_fixtures": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM raw.fixture_lineups l
                    LEFT JOIN raw.fixtures f
                      ON f.fixture_id = l.fixture_id
                     AND f.provider = l.provider
                     AND f.competition_key = l.competition_key
                     AND f.season_label = l.season_label
                    WHERE l.payload->>'source_name' = :source_name
                      AND l.provider LIKE :provider_pattern
                      AND l.competition_key = :competition_key
                      AND l.season_label NOT IN ('2018', '2022')
                      AND f.fixture_id IS NULL
                    """
                ),
                params,
            ).scalar_one()
        ),
        "raw_event_orphan_fixtures": int(
            conn.execute(
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
                      AND e.edition_key IN :edition_keys
                      AND f.fixture_id IS NULL
                    """
                ).bindparams(bindparam("edition_keys", expanding=True)),
                params,
            ).scalar_one()
        ),
        "raw_match_events_world_cup": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM raw.match_events
                    WHERE provider LIKE :provider_pattern
                       OR provider IN ('statsbomb_open_data', 'fjelstul_worldcup')
                    """
                ),
                params,
            ).scalar_one()
        ),
        "raw_fixture_lineups_2022": int(
            conn.execute(
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
            ).scalar_one()
        ),
        "raw_wc_match_events_2022": int(
            conn.execute(
                text("SELECT count(*) FROM raw.wc_match_events WHERE edition_key = :edition_2022"),
                params,
            ).scalar_one()
        ),
    }

    sampled_lineups_by_edition = conn.execute(
        text(
            """
            SELECT 'fifa_world_cup_mens__' || season_label AS edition_key, count(*) AS row_count
            FROM raw.fixture_lineups
            WHERE payload->>'source_name' = :source_name
              AND season_label IN ('1958', '1962', '1970', '1974', '1986', '1990')
              AND competition_key = :competition_key
            GROUP BY season_label
            ORDER BY season_label
            """
        ),
        params,
    ).mappings().all()
    sampled_events_by_edition = conn.execute(
        text(
            """
            SELECT edition_key, count(*) AS row_count, count(DISTINCT fixture_id) AS match_count
            FROM raw.wc_match_events
            WHERE source_name = :source_name
              AND edition_key IN :edition_keys
            GROUP BY edition_key
            ORDER BY edition_key
            """
        ).bindparams(bindparam("edition_keys", expanding=True)),
        params,
    ).mappings().all()
    results["sampled_lineups_by_edition"] = {
        str(row["edition_key"]): int(row["row_count"]) for row in sampled_lineups_by_edition
    }
    results["sampled_events_by_edition"] = {
        str(row["edition_key"]): {
            "row_count": int(row["row_count"]),
            "match_count": int(row["match_count"]),
        }
        for row in sampled_events_by_edition
    }

    if results["raw_historical_lineups_total"] != EXPECTED_RAW_HISTORICAL_LINEUPS_TOTAL:
        raise RuntimeError(
            "raw.fixture_lineups historico da Copa ficou fora do esperado apos sampled publish: "
            f"esperado={EXPECTED_RAW_HISTORICAL_LINEUPS_TOTAL} atual={results['raw_historical_lineups_total']}"
        )
    if results["raw_historical_events_total"] != EXPECTED_RAW_HISTORICAL_EVENTS_TOTAL:
        raise RuntimeError(
            "raw.wc_match_events historico da Copa ficou fora do esperado apos sampled publish: "
            f"esperado={EXPECTED_RAW_HISTORICAL_EVENTS_TOTAL} atual={results['raw_historical_events_total']}"
        )
    for key in (
        "raw_lineup_duplicates",
        "raw_event_duplicates",
        "raw_lineup_orphan_fixtures",
        "raw_event_orphan_fixtures",
        "raw_match_events_world_cup",
    ):
        if results[key] != 0:
            raise RuntimeError(f"Validacao sampled raw invalida para {key}: atual={results[key]}")
    if results["raw_fixture_lineups_2022"] != 3244:
        raise RuntimeError(
            f"Validacao sampled raw invalida para raw_fixture_lineups_2022: atual={results['raw_fixture_lineups_2022']}"
        )
    if results["raw_wc_match_events_2022"] != 234652:
        raise RuntimeError(
            f"Validacao sampled raw invalida para raw_wc_match_events_2022: atual={results['raw_wc_match_events_2022']}"
        )

    for config in SAMPLED_CONFIGS:
        lineup_actual = results["sampled_lineups_by_edition"].get(config.edition_key, 0)
        event_actual = results["sampled_events_by_edition"].get(config.edition_key, {}).get("row_count", 0)
        match_actual = results["sampled_events_by_edition"].get(config.edition_key, {}).get("match_count", 0)
        if lineup_actual != EXPECTED_LINEUP_ROWS[config.edition_key]:
            raise RuntimeError(
                f"Validacao sampled raw invalida para {config.edition_key} lineups: "
                f"esperado={EXPECTED_LINEUP_ROWS[config.edition_key]} atual={lineup_actual}"
            )
        if event_actual != EXPECTED_EVENT_ROWS[config.edition_key]:
            raise RuntimeError(
                f"Validacao sampled raw invalida para {config.edition_key} events: "
                f"esperado={EXPECTED_EVENT_ROWS[config.edition_key]} atual={event_actual}"
            )
        if match_actual != config.expected_matches:
            raise RuntimeError(
                f"Validacao sampled raw invalida para {config.edition_key} match coverage: "
                f"esperado={config.expected_matches} atual={match_actual}"
            )
    return results


def publish_world_cup_statsbomb_sampled_to_raw() -> dict[str, Any]:
    context = get_current_context()
    now_utc = _utc_now()
    run_id = f"world_cup_statsbomb_sampled_raw__{now_utc.strftime('%Y%m%dT%H%M%SZ')}"
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    with StepMetrics(
        service="airflow",
        module="world_cup_statsbomb_sampled_raw_publish_service",
        step="publish_world_cup_statsbomb_sampled_to_raw",
        context=context,
        dataset="raw.world_cup_statsbomb_sampled",
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
            validations = _validate_outputs(conn)

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
        module="world_cup_statsbomb_sampled_raw_publish_service",
        step="summary",
        status="success",
        context=context,
        dataset="raw.world_cup_statsbomb_sampled",
        row_count=len(lineups_df) + len(wc_match_events_df),
        message=(
            "Raw sampled StatsBomb historico publicado | "
            f"lineups={summary['validations']['raw_historical_lineups_total']} | "
            f"events={summary['validations']['raw_historical_events_total']} | "
            f"sampled_lineups={EXPECTED_SAMPLED_LINEUP_TOTAL} | "
            f"sampled_events={EXPECTED_SAMPLED_EVENT_TOTAL}"
        ),
    )
    return summary
