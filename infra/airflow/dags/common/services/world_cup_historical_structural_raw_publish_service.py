from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.observability import StepMetrics, log_event
from common.services.warehouse_service import (
    STANDINGS_SNAPSHOTS_TARGET_COLUMNS,
    TEAM_COACHES_TARGET_COLUMNS,
)
from common.services.world_cup_config import FJELSTUL_SOURCE, WORLD_CUP_COMPETITION_KEY, WORLD_CUP_COMPETITION_NAME
from common.services.world_cup_raw_publish_service import (
    COACH_ID_BASE,
    COACH_TENURE_ID_BASE,
    DEFAULT_WORLD_CUP_EDITION_KEY,
    FIXTURE_ID_BASE,
    RAW_FIXTURES_TARGET_COLUMNS,
    ROUND_ID_BASE,
    SEASON_ID_BASE,
    STAGE_ID_BASE,
    TEAM_ID_BASE,
    _stable_bigint,
    _upsert_dataframe,
    _upsert_dataframe_without_updated_at,
)

WORLD_CUP_EDITION_PATTERN = "fifa_world_cup_mens__%"
WORLD_CUP_PROVIDER_PATTERN = "world_cup_%"


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_text(value: Any) -> str | None:
    if value is None:
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
        "league_id": _stable_bigint(f"league|{WORLD_CUP_COMPETITION_KEY}", base=7_000_000_000_000_000_000),
        "season_id": _stable_bigint(f"season|{edition_key}", base=SEASON_ID_BASE),
    }


def _assert_no_fixture_id_collision_outside_world_cup(conn, fixture_ids: list[int]) -> None:
    if not fixture_ids:
        return
    collisions = conn.execute(
        text(
            """
            SELECT count(*)
            FROM raw.fixtures
            WHERE fixture_id = ANY(:fixture_ids)
              AND (
                competition_key IS DISTINCT FROM :competition_key
                OR provider NOT LIKE :provider_pattern
              )
            """
        ),
        {
            "fixture_ids": fixture_ids,
            "competition_key": WORLD_CUP_COMPETITION_KEY,
            "provider_pattern": WORLD_CUP_PROVIDER_PATTERN,
        },
    ).scalar_one()
    if int(collisions) != 0:
        raise RuntimeError(f"Fixture IDs sinteticos da Copa colidem fora do escopo World Cup: {collisions}")


def _validate_prerequisites(conn) -> None:
    checks = {
        "silver_fixtures": (
            """
            SELECT count(DISTINCT edition_key) AS editions, count(*) AS rows
            FROM silver.wc_fixtures
            WHERE edition_key LIKE :edition_pattern
            """,
            (22, 964),
        ),
        "silver_group_standings": (
            """
            SELECT count(DISTINCT edition_key) AS editions, count(*) AS rows
            FROM silver.wc_group_standings
            WHERE edition_key LIKE :edition_pattern
            """,
            (20, 490),
        ),
        "bronze_team_coaches": (
            """
            SELECT count(DISTINCT edition_key) AS editions, count(*) AS rows
            FROM bronze.fjelstul_wc_manager_appointments
            WHERE edition_key LIKE :edition_pattern
            """,
            (22, 501),
        ),
        "raw_fixtures_2022": (
            """
            SELECT count(*) AS editions, count(*) AS rows
            FROM raw.fixtures
            WHERE provider = :provider_2022
              AND competition_key = :competition_key
              AND season_label = '2022'
            """,
            (64, 64),
        ),
        "raw_standings_2022": (
            """
            SELECT count(*) AS editions, count(*) AS rows
            FROM raw.standings_snapshots
            WHERE provider = :provider_2022
              AND competition_key = :competition_key
              AND season_label = '2022'
            """,
            (32, 32),
        ),
        "raw_team_coaches_2022": (
            """
            SELECT count(*) AS editions, count(*) AS rows
            FROM raw.team_coaches
            WHERE provider = :provider_2022
            """,
            (32, 32),
        ),
    }
    for name, (sql, expected) in checks.items():
        row = conn.execute(
            text(sql),
            {
                "edition_pattern": WORLD_CUP_EDITION_PATTERN,
                "provider_2022": _provider_for_edition(DEFAULT_WORLD_CUP_EDITION_KEY),
                "competition_key": WORLD_CUP_COMPETITION_KEY,
            },
        ).mappings().one()
        actual = tuple(int(value) for value in row.values())
        if actual != expected:
            raise RuntimeError(f"Precondicao historica raw invalida para {name}: esperado={expected} atual={actual}")


def _read_fixtures_frame(conn, now_utc: datetime, run_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          f.edition_key,
          f.internal_match_id,
          f.source_match_id,
          f.source_version,
          f.stage_internal_id,
          f.stage_key,
          s.stage_name,
          f.group_internal_id,
          f.group_key,
          f.match_date,
          f.home_team_internal_id,
          f.away_team_internal_id,
          bf.payload->>'home_team_name' AS home_team_name,
          bf.payload->>'away_team_name' AS away_team_name,
          bf.payload->>'stadium_name' AS venue_name,
          bf.payload->>'city_name' AS venue_city,
          f.home_team_score,
          f.away_team_score,
          f.home_penalty_score,
          f.away_penalty_score,
          f.penalty_shootout,
          f.extra_time
        FROM silver.wc_fixtures f
        JOIN silver.wc_stages s
          ON s.edition_key = f.edition_key
         AND s.stage_internal_id = f.stage_internal_id
        LEFT JOIN bronze.fjelstul_wc_matches bf
          ON bf.edition_key = f.edition_key
         AND bf.match_id = f.source_match_id
        WHERE f.edition_key LIKE :edition_pattern
          AND f.edition_key <> :skip_edition
        ORDER BY f.edition_key, f.match_date, f.internal_match_id
        """
    )
    df = pd.read_sql_query(
        sql,
        conn,
        params={"edition_pattern": WORLD_CUP_EDITION_PATTERN, "skip_edition": DEFAULT_WORLD_CUP_EDITION_KEY},
    )
    if df.empty:
        raise RuntimeError("Nenhum fixture silver historico encontrado para raw publish.")

    df["season_label"] = df["edition_key"].map(_season_label_from_edition)
    df["provider"] = df["edition_key"].map(_provider_for_edition)
    df["season"] = df["season_label"].astype(int)
    df["provider_ids"] = df["edition_key"].map(_world_cup_ids)
    df["league_id"] = df["provider_ids"].map(lambda value: value["league_id"])
    df["provider_league_id"] = df["league_id"]
    df["provider_season_id"] = df["provider_ids"].map(lambda value: value["season_id"])
    df["fixture_id"] = df["internal_match_id"].map(lambda value: _stable_bigint(value, base=FIXTURE_ID_BASE))
    df["home_team_id"] = df["home_team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["away_team_id"] = df["away_team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["stage_id"] = df["stage_internal_id"].map(lambda value: _stable_bigint(value, base=STAGE_ID_BASE))
    df["round_id"] = df.apply(
        lambda row: _stable_bigint(
            row["group_internal_id"] if pd.notna(row["group_internal_id"]) else f"{row['stage_internal_id']}::round",
            base=ROUND_ID_BASE,
        ),
        axis=1,
    )
    season_bounds = (
        df.groupby("edition_key")["match_date"]
        .agg(["min", "max"])
        .rename(columns={"min": "season_start_date", "max": "season_end_date"})
        .reset_index()
    )
    df = df.merge(season_bounds, on="edition_key", how="left")
    df["date_utc"] = pd.Series([None] * len(df), index=df.index, dtype="object")
    df["timestamp"] = pd.Series([pd.NA] * len(df), index=df.index, dtype="Int64")
    df["timezone"] = pd.Series([None] * len(df), index=df.index, dtype="object")
    df["referee"] = pd.Series([None] * len(df), index=df.index, dtype="object")
    df["venue_id"] = pd.Series([pd.NA] * len(df), index=df.index, dtype="Int64")
    df["status_short"] = "FT"
    df["status_long"] = "Match Finished"
    df["league_name"] = WORLD_CUP_COMPETITION_NAME
    df["round"] = df.apply(
        lambda row: f"Group {row['group_key']}" if pd.notna(row["group_key"]) else row["stage_name"],
        axis=1,
    )
    df["home_goals"] = df["home_team_score"].astype("Int64")
    df["away_goals"] = df["away_team_score"].astype("Int64")
    df["year"] = df["season_label"]
    df["month"] = pd.to_datetime(df["match_date"]).dt.strftime("%m")
    df["ingested_run"] = run_id
    df["date"] = pd.to_datetime(df["match_date"]).dt.date
    df["source_provider"] = FJELSTUL_SOURCE
    df["referee_id"] = pd.Series([pd.NA] * len(df), index=df.index, dtype="Int64")
    df["attendance"] = pd.Series([pd.NA] * len(df), index=df.index, dtype="Int64")
    df["weather_description"] = pd.Series([None] * len(df), index=df.index, dtype="object")
    df["weather_temperature_c"] = pd.Series([None] * len(df), index=df.index, dtype="object")
    df["weather_wind_kph"] = pd.Series([None] * len(df), index=df.index, dtype="object")
    df["home_goals_ht"] = pd.Series([pd.NA] * len(df), index=df.index, dtype="Int64")
    df["away_goals_ht"] = pd.Series([pd.NA] * len(df), index=df.index, dtype="Int64")
    df["home_goals_ft"] = df["home_team_score"].astype("Int64")
    df["away_goals_ft"] = df["away_team_score"].astype("Int64")
    df["competition_key"] = WORLD_CUP_COMPETITION_KEY
    df["competition_type"] = "international_cup"
    df["season_name"] = df["season_label"].map(lambda value: f"{value} FIFA Men's World Cup")
    df["round_name"] = df["round"]
    df["group_name"] = df["group_key"].map(lambda value: f"Group {value}" if pd.notna(value) else None)
    df["leg"] = 1
    df["ingested_at"] = now_utc
    df["source_run_id"] = run_id
    fixture_id_duplicates = int(df.duplicated(subset=["fixture_id"]).sum())
    if fixture_id_duplicates != 0:
        raise RuntimeError(f"Fixture IDs sinteticos duplicados no publish historico: {fixture_id_duplicates}")
    fixture_id_cardinality = int(df["fixture_id"].nunique())
    internal_match_cardinality = int(df["internal_match_id"].nunique())
    if fixture_id_cardinality != internal_match_cardinality:
        raise RuntimeError(
            "Mapeamento instavel de internal_match_id para fixture_id no publish historico: "
            f"fixture_ids={fixture_id_cardinality} internal_match_ids={internal_match_cardinality}"
        )
    df.drop(columns=["provider_ids"], inplace=True)
    return df[RAW_FIXTURES_TARGET_COLUMNS]


def _read_standings_frame(conn, run_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          edition_key,
          stage_internal_id,
          stage_key,
          group_internal_id,
          group_key,
          team_internal_id,
          source_name,
          source_version,
          source_row_id,
          final_position,
          team_name,
          team_code,
          played,
          wins,
          draws,
          losses,
          goals_for,
          goals_against,
          goal_difference,
          points,
          advanced
        FROM silver.wc_group_standings
        WHERE edition_key LIKE :edition_pattern
          AND edition_key <> :skip_edition
        ORDER BY edition_key, stage_key, group_key, final_position
        """
    )
    df = pd.read_sql_query(
        sql,
        conn,
        params={"edition_pattern": WORLD_CUP_EDITION_PATTERN, "skip_edition": DEFAULT_WORLD_CUP_EDITION_KEY},
    )
    if df.empty:
        raise RuntimeError("Nenhum standing silver historico encontrado para raw publish.")

    df["season_label"] = df["edition_key"].map(_season_label_from_edition)
    df["provider"] = df["edition_key"].map(_provider_for_edition)
    df["provider_ids"] = df["edition_key"].map(_world_cup_ids)
    df["league_id"] = df["provider_ids"].map(lambda value: value["league_id"])
    df["provider_league_id"] = df["league_id"]
    df["provider_season_id"] = df["provider_ids"].map(lambda value: value["season_id"])
    df["season_id"] = df["provider_season_id"]
    df["competition_key"] = WORLD_CUP_COMPETITION_KEY
    df["stage_id"] = df["stage_internal_id"].map(lambda value: _stable_bigint(value, base=STAGE_ID_BASE))
    df["round_id"] = df["group_internal_id"].map(lambda value: _stable_bigint(value, base=ROUND_ID_BASE))
    df["team_id"] = df["team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["position"] = pd.to_numeric(df["final_position"], errors="coerce").astype("Int64")
    df["games_played"] = pd.to_numeric(df["played"], errors="coerce").astype("Int64")
    df["won"] = pd.to_numeric(df["wins"], errors="coerce").astype("Int64")
    df["draw"] = pd.to_numeric(df["draws"], errors="coerce").astype("Int64")
    df["lost"] = pd.to_numeric(df["losses"], errors="coerce").astype("Int64")
    df["goal_diff"] = pd.to_numeric(df["goal_difference"], errors="coerce").astype("Int64")
    df["payload"] = df.apply(
        lambda row: _json_text(
            {
                "edition_key": row["edition_key"],
                "source_name": row["source_name"],
                "source_version": row["source_version"],
                "source_row_id": row["source_row_id"],
                "stage_internal_id": row["stage_internal_id"],
                "group_internal_id": row["group_internal_id"],
                "team_internal_id": row["team_internal_id"],
                "stage_key": row["stage_key"],
                "group_key": row["group_key"],
                "team_name": row["team_name"],
                "team_code": row["team_code"],
                "advanced": bool(row["advanced"]),
            }
        ),
        axis=1,
    )
    df["ingested_run"] = run_id
    df["ingested_at"] = _utc_now()
    df["source_run_id"] = run_id
    df.drop(columns=["provider_ids"], inplace=True)
    return df[STANDINGS_SNAPSHOTS_TARGET_COLUMNS]


def _read_team_coaches_frame(conn, run_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          m.edition_key,
          m.key_id,
          m.team_id AS source_team_id,
          m.team_name,
          m.team_code,
          m.manager_id AS source_manager_id,
          m.family_name,
          m.given_name,
          m.country_name,
          m.source_name,
          m.source_version,
          m.payload,
          pm_team.canonical_id AS team_internal_id
        FROM bronze.fjelstul_wc_manager_appointments m
        JOIN raw.provider_entity_map pm_team
          ON pm_team.provider = :source_name
         AND pm_team.entity_type = 'team'
         AND pm_team.source_id = m.team_id
        WHERE m.edition_key LIKE :edition_pattern
          AND m.edition_key <> :skip_edition
        ORDER BY m.edition_key, m.key_id
        """
    )
    df = pd.read_sql_query(
        sql,
        conn,
        params={
            "source_name": FJELSTUL_SOURCE,
            "edition_pattern": WORLD_CUP_EDITION_PATTERN,
            "skip_edition": DEFAULT_WORLD_CUP_EDITION_KEY,
        },
    )
    if df.empty:
        raise RuntimeError("Nenhum team_coach historico encontrado para raw publish.")

    df["provider"] = df["edition_key"].map(_provider_for_edition)
    df["coach_tenure_id"] = df.apply(
        lambda row: _stable_bigint(
            f"coach_tenure|edition={row['edition_key']}|source_key={row['key_id']}",
            base=COACH_TENURE_ID_BASE,
        ),
        axis=1,
    )
    df["team_id"] = df["team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["coach_id"] = df["source_manager_id"].map(
        lambda value: _stable_bigint(
            f"coach_source|provider={FJELSTUL_SOURCE}|manager_id={value}",
            base=COACH_ID_BASE,
        )
    )
    df["position_id"] = pd.Series([pd.NA] * len(df), index=df.index, dtype="Int64")
    df["active"] = pd.Series([pd.NA] * len(df), index=df.index, dtype="boolean")
    df["temporary"] = pd.Series([pd.NA] * len(df), index=df.index, dtype="boolean")
    df["start_date"] = pd.Series([pd.NaT] * len(df), index=df.index)
    df["end_date"] = pd.Series([pd.NaT] * len(df), index=df.index)
    df["payload"] = df.apply(
        lambda row: _json_text(
            {
                "edition_key": row["edition_key"],
                "source_name": row["source_name"],
                "source_version": row["source_version"],
                "coach_identity_scope": "source_scoped_fjelstul_manager_id",
                "coach_tenure_scope": "edition_scoped_manager_appointment",
                "team_internal_id": row["team_internal_id"],
                "source_team_id": row["source_team_id"],
                "source_manager_id": row["source_manager_id"],
                "team_name": row["team_name"],
                "team_code": row["team_code"],
                "family_name": row["family_name"],
                "given_name": row["given_name"],
                "country_name": row["country_name"],
                "source_payload": row["payload"],
            }
        ),
        axis=1,
    )
    df["ingested_run"] = run_id
    return df[TEAM_COACHES_TARGET_COLUMNS]


def _validate_outputs(conn) -> dict[str, Any]:
    results = {
        "raw_fixtures_total": conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.fixtures
                WHERE competition_key = :competition_key
                  AND provider LIKE :provider_pattern
                """
            ),
            {"competition_key": WORLD_CUP_COMPETITION_KEY, "provider_pattern": WORLD_CUP_PROVIDER_PATTERN},
        ).scalar_one(),
        "raw_fixtures_editions": conn.execute(
            text(
                """
                SELECT count(DISTINCT season_label)
                FROM raw.fixtures
                WHERE competition_key = :competition_key
                  AND provider LIKE :provider_pattern
                """
            ),
            {"competition_key": WORLD_CUP_COMPETITION_KEY, "provider_pattern": WORLD_CUP_PROVIDER_PATTERN},
        ).scalar_one(),
        "raw_standings_total": conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.standings_snapshots
                WHERE competition_key = :competition_key
                  AND provider LIKE :provider_pattern
                """
            ),
            {"competition_key": WORLD_CUP_COMPETITION_KEY, "provider_pattern": WORLD_CUP_PROVIDER_PATTERN},
        ).scalar_one(),
        "raw_standings_editions": conn.execute(
            text(
                """
                SELECT count(DISTINCT season_label)
                FROM raw.standings_snapshots
                WHERE competition_key = :competition_key
                  AND provider LIKE :provider_pattern
                """
            ),
            {"competition_key": WORLD_CUP_COMPETITION_KEY, "provider_pattern": WORLD_CUP_PROVIDER_PATTERN},
        ).scalar_one(),
        "raw_team_coaches_total": conn.execute(
            text("SELECT count(*) FROM raw.team_coaches WHERE provider LIKE :provider_pattern"),
            {"provider_pattern": WORLD_CUP_PROVIDER_PATTERN},
        ).scalar_one(),
        "raw_team_coaches_editions": conn.execute(
            text(
                """
                SELECT count(DISTINCT substring(provider from 'world_cup_(.*)$'))
                FROM raw.team_coaches
                WHERE provider LIKE :provider_pattern
                """
            ),
            {"provider_pattern": WORLD_CUP_PROVIDER_PATTERN},
        ).scalar_one(),
        "raw_wc_match_events_total": conn.execute(
            text("SELECT count(*) FROM raw.wc_match_events WHERE edition_key = :edition_key"),
            {"edition_key": DEFAULT_WORLD_CUP_EDITION_KEY},
        ).scalar_one(),
        "raw_match_events_world_cup": conn.execute(
            text("SELECT count(*) FROM raw.match_events WHERE provider LIKE :provider_pattern"),
            {"provider_pattern": WORLD_CUP_PROVIDER_PATTERN},
        ).scalar_one(),
    }
    expected = {
        "raw_fixtures_total": 964,
        "raw_fixtures_editions": 22,
        "raw_standings_total": 490,
        "raw_standings_editions": 20,
        "raw_team_coaches_total": 501,
        "raw_team_coaches_editions": 22,
        "raw_wc_match_events_total": 234652,
        "raw_match_events_world_cup": 0,
    }
    for key, expected_value in expected.items():
        if int(results[key]) != expected_value:
            raise RuntimeError(f"Raw historico invalido para {key}: esperado={expected_value} atual={results[key]}")

    duplicate_checks = {
        "raw_fixture_duplicates": """
            SELECT count(*)
            FROM (
              SELECT fixture_id, count(*) AS row_count
              FROM raw.fixtures
              WHERE competition_key = :competition_key
                AND provider LIKE :provider_pattern
              GROUP BY fixture_id
              HAVING count(*) > 1
            ) dup
        """,
        "raw_standings_duplicates": """
            SELECT count(*)
            FROM (
              SELECT provider, season_id, stage_id, round_id, team_id, count(*) AS row_count
              FROM raw.standings_snapshots
              WHERE competition_key = :competition_key
                AND provider LIKE :provider_pattern
              GROUP BY 1,2,3,4,5
              HAVING count(*) > 1
            ) dup
        """,
        "raw_team_coaches_duplicates": """
            SELECT count(*)
            FROM (
              SELECT provider, coach_tenure_id, count(*) AS row_count
              FROM raw.team_coaches
              WHERE provider LIKE :provider_pattern
              GROUP BY 1,2
              HAVING count(*) > 1
            ) dup
        """,
    }
    for key, sql in duplicate_checks.items():
        actual = conn.execute(
            text(sql),
            {"competition_key": WORLD_CUP_COMPETITION_KEY, "provider_pattern": WORLD_CUP_PROVIDER_PATTERN},
        ).scalar_one()
        results[key] = actual
        if int(actual) != 0:
            raise RuntimeError(f"Raw historico invalido para {key}: atual={actual}")
    return results


def publish_world_cup_historical_structural_to_raw() -> dict[str, Any]:
    context = get_current_context()
    now_utc = _utc_now()
    run_id = f"world_cup_historical_structural_raw__{now_utc.strftime('%Y%m%dT%H%M%SZ')}"
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    with StepMetrics(
        service="airflow",
        module="world_cup_historical_structural_raw_publish_service",
        step="publish_world_cup_historical_structural_to_raw",
        context=context,
        dataset="raw.world_cup_historical_structural",
        table="raw.fixtures/raw.standings_snapshots/raw.team_coaches",
    ):
        with engine.begin() as conn:
            _validate_prerequisites(conn)

            fixtures_df = _read_fixtures_frame(conn, now_utc, run_id)
            standings_df = _read_standings_frame(conn, run_id)
            coaches_df = _read_team_coaches_frame(conn, run_id)

            _assert_no_fixture_id_collision_outside_world_cup(conn, fixtures_df["fixture_id"].astype(int).tolist())

            fixtures_counts = _upsert_dataframe_without_updated_at(
                conn,
                target_table="fixtures",
                df=fixtures_df,
                target_columns=RAW_FIXTURES_TARGET_COLUMNS,
                conflict_keys=["fixture_id"],
                compare_columns=[
                    col
                    for col in RAW_FIXTURES_TARGET_COLUMNS
                    if col not in {"fixture_id", "ingested_run", "ingested_at", "source_run_id"}
                ],
            )
            standings_counts = _upsert_dataframe(
                conn,
                target_table="standings_snapshots",
                df=standings_df,
                target_columns=STANDINGS_SNAPSHOTS_TARGET_COLUMNS,
                conflict_keys=["provider", "season_id", "stage_id", "round_id", "team_id"],
                compare_columns=[
                    col
                    for col in STANDINGS_SNAPSHOTS_TARGET_COLUMNS
                    if col not in {"provider", "season_id", "stage_id", "round_id", "team_id", "ingested_run", "source_run_id"}
                ],
            )
            coaches_counts = _upsert_dataframe(
                conn,
                target_table="team_coaches",
                df=coaches_df,
                target_columns=TEAM_COACHES_TARGET_COLUMNS,
                conflict_keys=["provider", "coach_tenure_id"],
                compare_columns=[
                    col
                    for col in TEAM_COACHES_TARGET_COLUMNS
                    if col not in {"provider", "coach_tenure_id", "ingested_run"}
                ],
            )

            validations = _validate_outputs(conn)

    summary = {
        "fixtures_upsert": {"inserted": fixtures_counts[0], "updated": fixtures_counts[1], "ignored": fixtures_counts[2]},
        "standings_upsert": {"inserted": standings_counts[0], "updated": standings_counts[1], "ignored": standings_counts[2]},
        "team_coaches_upsert": {"inserted": coaches_counts[0], "updated": coaches_counts[1], "ignored": coaches_counts[2]},
        "validations": validations,
        "run_id": run_id,
    }
    log_event(
        service="airflow",
        module="world_cup_historical_structural_raw_publish_service",
        step="summary",
        status="success",
        context=context,
        dataset="raw.world_cup_historical_structural",
        row_count=len(fixtures_df) + len(standings_df) + len(coaches_df),
        message=(
            "Raw historico estrutural da Copa publicado | "
            f"fixtures={summary['validations']['raw_fixtures_total']} | "
            f"standings={summary['validations']['raw_standings_total']} | "
            f"team_coaches={summary['validations']['raw_team_coaches_total']}"
        ),
    )
    return summary
