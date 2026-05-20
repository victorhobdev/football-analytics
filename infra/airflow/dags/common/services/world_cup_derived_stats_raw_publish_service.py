from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from airflow.operators.python import get_current_context
from sqlalchemy import bindparam, create_engine, text

from common.observability import StepMetrics, log_event
from common.services.warehouse_service import (
    FIXTURE_PLAYER_STATISTICS_TARGET_COLUMNS,
    STATISTICS_TARGET_COLUMNS,
)
from common.services.world_cup_config import (
    DEFAULT_WORLD_CUP_EDITION_KEY,
    WORLD_CUP_COMPETITION_KEY,
)
from common.services.world_cup_raw_publish_service import (
    FIXTURE_ID_BASE,
    LEAGUE_ID_BASE,
    PLAYER_ID_BASE,
    SEASON_ID_BASE,
    TEAM_ID_BASE,
    _stable_bigint,
    _upsert_dataframe,
)

SUPPORTED_EDITIONS = ("fifa_world_cup_mens__2018", DEFAULT_WORLD_CUP_EDITION_KEY)


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _season_label_from_edition(edition_key: str) -> str:
    return edition_key.rsplit("__", 1)[1]


def _provider_for_edition(edition_key: str) -> str:
    return f"world_cup_{_season_label_from_edition(edition_key)}"


def _world_cup_ids(edition_key: str) -> dict[str, int]:
    return {
        "league_id": _stable_bigint(f"league|{WORLD_CUP_COMPETITION_KEY}", base=LEAGUE_ID_BASE),
        "season_id": _stable_bigint(f"season|{edition_key}", base=SEASON_ID_BASE),
    }


def _validate_prerequisites(conn) -> dict[str, int]:
    params = {"edition_keys": list(SUPPORTED_EDITIONS)}
    checks = {
        "silver_match_stats_rows": (
            """
            SELECT count(*)
            FROM silver.wc_match_stats
            WHERE edition_key IN :edition_keys
            """,
            256,
        ),
        "silver_match_stats_editions": (
            """
            SELECT count(DISTINCT edition_key)
            FROM silver.wc_match_stats
            WHERE edition_key IN :edition_keys
            """,
            2,
        ),
        "silver_player_match_stats_rows": (
            """
            SELECT count(*)
            FROM silver.wc_player_match_stats
            WHERE edition_key IN :edition_keys
            """,
            3785,
        ),
        "silver_player_match_stats_editions": (
            """
            SELECT count(DISTINCT edition_key)
            FROM silver.wc_player_match_stats
            WHERE edition_key IN :edition_keys
            """,
            2,
        ),
        "raw_fixtures_rows": (
            """
            SELECT count(*)
            FROM raw.fixtures
            WHERE competition_key = :competition_key
              AND season_label IN ('2018', '2022')
            """,
            128,
        ),
        "raw_match_events_world_cup": (
            """
            SELECT count(*)
            FROM raw.match_events
            WHERE provider IN ('world_cup_2018', 'world_cup_2022', 'statsbomb_open_data', 'fjelstul_worldcup')
            """,
            0,
        ),
    }
    exec_params = {**params, "competition_key": WORLD_CUP_COMPETITION_KEY}
    results: dict[str, int] = {}
    for key, (sql, expected) in checks.items():
        actual = int(
            conn.execute(
                text(sql).bindparams(bindparam("edition_keys", expanding=True)) if ":edition_keys" in sql else text(sql),
                exec_params,
            ).scalar_one()
        )
        results[key] = actual
        if actual != expected:
            raise RuntimeError(f"Precondicao do B7 raw falhou em {key}: esperado={expected} atual={actual}")
    return results


def _load_match_stats_df(conn, run_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          edition_key,
          internal_match_id,
          team_internal_id,
          team_name,
          shots_on_goal,
          shots_off_goal,
          total_shots,
          blocked_shots,
          shots_inside_box,
          shots_outside_box,
          fouls,
          corner_kicks,
          offsides,
          ball_possession,
          yellow_cards,
          red_cards,
          goalkeeper_saves,
          total_passes,
          passes_accurate,
          passes_pct
        FROM silver.wc_match_stats
        WHERE edition_key IN :edition_keys
        ORDER BY edition_key, internal_match_id, team_internal_id
        """
    ).bindparams(bindparam("edition_keys", expanding=True))
    df = pd.read_sql_query(sql, conn, params={"edition_keys": list(SUPPORTED_EDITIONS)})
    if df.empty:
        raise RuntimeError("Silver `wc_match_stats` vazio. B7 nao pode publicar `raw.match_statistics`.")

    df["fixture_id"] = df["internal_match_id"].map(lambda value: _stable_bigint(value, base=FIXTURE_ID_BASE))
    df["team_id"] = df["team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["provider"] = df["edition_key"].map(_provider_for_edition)
    df["season_label"] = df["edition_key"].map(_season_label_from_edition)
    df["provider_league_id"] = df["edition_key"].map(lambda value: _world_cup_ids(value)["league_id"])
    df["provider_season_id"] = df["edition_key"].map(lambda value: _world_cup_ids(value)["season_id"])
    df["competition_key"] = WORLD_CUP_COMPETITION_KEY
    df["source_run_id"] = run_id
    df["ingested_run"] = run_id
    df["passes_pct"] = pd.to_numeric(df["passes_pct"], errors="coerce").round(2)
    return df[STATISTICS_TARGET_COLUMNS]


def _load_player_match_stats_df(conn, run_id: str) -> pd.DataFrame:
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
          is_starter,
          minutes_played,
          statistics,
          payload
        FROM silver.wc_player_match_stats
        WHERE edition_key IN :edition_keys
        ORDER BY edition_key, internal_match_id, team_internal_id, player_internal_id
        """
    ).bindparams(bindparam("edition_keys", expanding=True))
    df = pd.read_sql_query(sql, conn, params={"edition_keys": list(SUPPORTED_EDITIONS)})
    if df.empty:
        raise RuntimeError("Silver `wc_player_match_stats` vazio. B7 nao pode publicar `raw.fixture_player_statistics`.")

    df["fixture_id"] = df["internal_match_id"].map(lambda value: _stable_bigint(value, base=FIXTURE_ID_BASE))
    df["team_id"] = df["team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["player_id"] = df["player_internal_id"].map(lambda value: _stable_bigint(value, base=PLAYER_ID_BASE))
    df["provider"] = df["edition_key"].map(_provider_for_edition)
    df["season_label"] = df["edition_key"].map(_season_label_from_edition)
    df["provider_league_id"] = df["edition_key"].map(lambda value: _world_cup_ids(value)["league_id"])
    df["provider_season_id"] = df["edition_key"].map(lambda value: _world_cup_ids(value)["season_id"])
    df["competition_key"] = WORLD_CUP_COMPETITION_KEY
    df["source_run_id"] = run_id
    df["ingested_run"] = run_id
    df["statistics"] = df["statistics"].map(lambda value: _json_text(_json_value(value)))
    df["payload"] = df.apply(
        lambda row: _json_text(
            {
                "fixture_id": int(row["fixture_id"]),
                "edition_key": row["edition_key"],
                "source_name": row["source_name"],
                "source_version": row["source_version"],
                "source_match_id": row["source_match_id"],
                "team": {
                    "id": int(row["team_id"]),
                    "name": row["team_name"],
                    "internal_id": row["team_internal_id"],
                    "source_id": row["source_team_id"],
                },
                "player": {
                    "id": int(row["player_id"]),
                    "name": row["player_name"],
                    "nickname": row["player_nickname"],
                    "internal_id": row["player_internal_id"],
                    "source_id": row["source_player_id"],
                },
                "is_starter": bool(row["is_starter"]),
                "minutes_played": int(row["minutes_played"]),
                "statistics": _json_value(row["statistics"]),
                "payload": _json_value(row["payload"]),
            }
        ),
        axis=1,
    )
    return df[FIXTURE_PLAYER_STATISTICS_TARGET_COLUMNS]


def _validate_outputs(conn, *, expected_match_rows: int, expected_player_rows: int) -> dict[str, int]:
    results = {
        "raw_match_statistics_rows": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM raw.match_statistics
                    WHERE competition_key = :competition_key
                      AND season_label IN ('2018', '2022')
                    """
                ),
                {"competition_key": WORLD_CUP_COMPETITION_KEY},
            ).scalar_one()
        ),
        "raw_fixture_player_statistics_rows": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM raw.fixture_player_statistics
                    WHERE competition_key = :competition_key
                      AND season_label IN ('2018', '2022')
                    """
                ),
                {"competition_key": WORLD_CUP_COMPETITION_KEY},
            ).scalar_one()
        ),
        "raw_match_statistics_duplicates": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM (
                      SELECT fixture_id, team_id, count(*)
                      FROM raw.match_statistics
                      WHERE competition_key = :competition_key
                        AND season_label IN ('2018', '2022')
                      GROUP BY 1, 2
                      HAVING count(*) > 1
                    ) d
                    """
                ),
                {"competition_key": WORLD_CUP_COMPETITION_KEY},
            ).scalar_one()
        ),
        "raw_fixture_player_statistics_duplicates": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM (
                      SELECT provider, fixture_id, team_id, player_id, count(*)
                      FROM raw.fixture_player_statistics
                      WHERE competition_key = :competition_key
                        AND season_label IN ('2018', '2022')
                      GROUP BY 1, 2, 3, 4
                      HAVING count(*) > 1
                    ) d
                    """
                ),
                {"competition_key": WORLD_CUP_COMPETITION_KEY},
            ).scalar_one()
        ),
        "raw_match_statistics_orphan_fixtures": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM raw.match_statistics s
                    LEFT JOIN raw.fixtures f
                      ON f.fixture_id = s.fixture_id
                    WHERE s.competition_key = :competition_key
                      AND s.season_label IN ('2018', '2022')
                      AND f.fixture_id IS NULL
                    """
                ),
                {"competition_key": WORLD_CUP_COMPETITION_KEY},
            ).scalar_one()
        ),
        "raw_fixture_player_statistics_orphan_fixtures": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM raw.fixture_player_statistics s
                    LEFT JOIN raw.fixtures f
                      ON f.fixture_id = s.fixture_id
                    WHERE s.competition_key = :competition_key
                      AND s.season_label IN ('2018', '2022')
                      AND f.fixture_id IS NULL
                    """
                ),
                {"competition_key": WORLD_CUP_COMPETITION_KEY},
            ).scalar_one()
        ),
        "raw_match_statistics_bad_possession": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM raw.match_statistics
                    WHERE competition_key = :competition_key
                      AND season_label IN ('2018', '2022')
                      AND (ball_possession < 0 OR ball_possession > 100)
                    """
                ),
                {"competition_key": WORLD_CUP_COMPETITION_KEY},
            ).scalar_one()
        ),
        "raw_match_statistics_possession_sum_mismatches": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM (
                      SELECT fixture_id, sum(ball_possession) AS possession_sum
                      FROM raw.match_statistics
                      WHERE competition_key = :competition_key
                        AND season_label IN ('2018', '2022')
                      GROUP BY 1
                    ) sums
                    WHERE possession_sum <> 100
                    """
                ),
                {"competition_key": WORLD_CUP_COMPETITION_KEY},
            ).scalar_one()
        ),
        "raw_match_events_world_cup": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM raw.match_events
                    WHERE provider IN ('world_cup_2018', 'world_cup_2022', 'statsbomb_open_data', 'fjelstul_worldcup')
                    """
                )
            ).scalar_one()
        ),
    }
    expected = {
        "raw_match_statistics_rows": expected_match_rows,
        "raw_fixture_player_statistics_rows": expected_player_rows,
        "raw_match_statistics_duplicates": 0,
        "raw_fixture_player_statistics_duplicates": 0,
        "raw_match_statistics_orphan_fixtures": 0,
        "raw_fixture_player_statistics_orphan_fixtures": 0,
        "raw_match_statistics_bad_possession": 0,
        "raw_match_statistics_possession_sum_mismatches": 0,
        "raw_match_events_world_cup": 0,
    }
    for key, expected_value in expected.items():
        if results[key] != expected_value:
            raise RuntimeError(f"Validacao do B7 raw falhou em {key}: esperado={expected_value} atual={results[key]}")
    return results


def publish_world_cup_derived_stats_to_raw() -> dict[str, Any]:
    context = get_current_context()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    now_utc = _utc_now()
    run_id = f"world_cup_derived_stats_raw__{now_utc.strftime('%Y%m%dT%H%M%SZ')}"

    with StepMetrics(
        service="airflow",
        module="world_cup_derived_stats_raw_publish_service",
        step="publish_world_cup_derived_stats_to_raw",
        context=context,
        dataset="raw.world_cup_derived_stats",
        table="raw.match_statistics",
    ):
        with engine.begin() as conn:
            prerequisites = _validate_prerequisites(conn)
            match_stats_df = _load_match_stats_df(conn, run_id)
            player_stats_df = _load_player_match_stats_df(conn, run_id)

            match_counts = _upsert_dataframe(
                conn,
                target_table="match_statistics",
                df=match_stats_df,
                target_columns=STATISTICS_TARGET_COLUMNS,
                conflict_keys=["fixture_id", "team_id"],
                compare_columns=[
                    column
                    for column in STATISTICS_TARGET_COLUMNS
                    if column not in {"fixture_id", "team_id", "ingested_run", "source_run_id"}
                ],
            )
            player_counts = _upsert_dataframe(
                conn,
                target_table="fixture_player_statistics",
                df=player_stats_df,
                target_columns=FIXTURE_PLAYER_STATISTICS_TARGET_COLUMNS,
                conflict_keys=["provider", "fixture_id", "team_id", "player_id"],
                compare_columns=[
                    column
                    for column in FIXTURE_PLAYER_STATISTICS_TARGET_COLUMNS
                    if column not in {"provider", "fixture_id", "team_id", "player_id", "ingested_run", "source_run_id"}
                ],
            )
            validations = _validate_outputs(
                conn,
                expected_match_rows=len(match_stats_df),
                expected_player_rows=len(player_stats_df),
            )

    summary = {
        "prerequisites": prerequisites,
        "match_statistics_upsert": {"inserted": match_counts[0], "updated": match_counts[1], "ignored": match_counts[2]},
        "fixture_player_statistics_upsert": {
            "inserted": player_counts[0],
            "updated": player_counts[1],
            "ignored": player_counts[2],
        },
        "validations": validations,
        "run_id": run_id,
    }
    log_event(
        service="airflow",
        module="world_cup_derived_stats_raw_publish_service",
        step="summary",
        status="success",
        context=context,
        dataset="raw.world_cup_derived_stats",
        row_count=len(match_stats_df) + len(player_stats_df),
        message=(
            "Raw derivado da Copa publicado | "
            f"match_statistics={len(match_stats_df)} | "
            f"fixture_player_statistics={len(player_stats_df)}"
        ),
    )
    return summary
