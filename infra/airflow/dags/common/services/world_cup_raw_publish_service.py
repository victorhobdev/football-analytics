from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd
from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.observability import StepMetrics, log_event
from common.services.world_cup_config import (
    DEFAULT_WORLD_CUP_EDITION_KEY,
    FJELSTUL_SOURCE,
    WORLD_CUP_COMPETITION_KEY,
    WORLD_CUP_COMPETITION_NAME,
    WORLD_CUP_COMPETITION_TYPE,
    WorldCupEditionConfig,
    get_world_cup_edition_config,
    get_world_cup_edition_config_from_context,
)
from common.services.warehouse_service import (
    FIXTURE_LINEUPS_TARGET_COLUMNS,
    STANDINGS_SNAPSHOTS_TARGET_COLUMNS,
    TEAM_COACHES_TARGET_COLUMNS,
    _assert_target_columns,
    _stage_and_upsert_with_classified_counts,
)

LEAGUE_ID_BASE = 7_000_000_000_000_000_000
SEASON_ID_BASE = 7_010_000_000_000_000_000
FIXTURE_ID_BASE = 7_020_000_000_000_000_000
TEAM_ID_BASE = 7_030_000_000_000_000_000
PLAYER_ID_BASE = 7_040_000_000_000_000_000
STAGE_ID_BASE = 7_050_000_000_000_000_000
ROUND_ID_BASE = 7_060_000_000_000_000_000
COACH_ID_BASE = 7_070_000_000_000_000_000
COACH_TENURE_ID_BASE = 7_080_000_000_000_000_000
LINEUP_ID_BASE = 7_090_000_000_000_000_000
HASH_MOD = 1_000_000_000_000_000

RAW_FIXTURES_TARGET_COLUMNS = [
    "fixture_id",
    "date_utc",
    "timestamp",
    "timezone",
    "referee",
    "venue_id",
    "venue_name",
    "venue_city",
    "status_short",
    "status_long",
    "league_id",
    "league_name",
    "season",
    "round",
    "home_team_id",
    "home_team_name",
    "away_team_id",
    "away_team_name",
    "home_goals",
    "away_goals",
    "year",
    "month",
    "ingested_run",
    "date",
    "source_provider",
    "referee_id",
    "stage_id",
    "round_id",
    "attendance",
    "weather_description",
    "weather_temperature_c",
    "weather_wind_kph",
    "home_goals_ht",
    "away_goals_ht",
    "home_goals_ft",
    "away_goals_ft",
    "provider",
    "provider_league_id",
    "competition_key",
    "competition_type",
    "season_label",
    "provider_season_id",
    "season_name",
    "season_start_date",
    "season_end_date",
    "stage_name",
    "round_name",
    "group_name",
    "leg",
    "ingested_at",
    "source_run_id",
]

RAW_WC_MATCH_EVENTS_TARGET_COLUMNS = [
    "fixture_id",
    "internal_match_id",
    "edition_key",
    "source_name",
    "source_version",
    "source_match_id",
    "source_event_id",
    "event_index",
    "team_internal_id",
    "player_internal_id",
    "event_type",
    "period",
    "minute",
    "second",
    "location_x",
    "location_y",
    "outcome_label",
    "play_pattern_label",
    "is_three_sixty_backed",
    "event_payload",
]

def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _run_id(config: WorldCupEditionConfig, now_utc: datetime) -> str:
    return f"world_cup_raw_publish__{config.season_label}__{now_utc.strftime('%Y%m%dT%H%M%SZ')}"


def _json_text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _stable_bigint(seed: str, *, base: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return base + (int(digest[:15], 16) % HASH_MOD)


def _lineup_id(config: WorldCupEditionConfig, fixture_id: int, team_id: int, player_id: int) -> int:
    return _stable_bigint(
        f"lineup|provider={config.provider}|fixture={fixture_id}|team={team_id}|player={player_id}",
        base=LINEUP_ID_BASE,
    )


def _world_cup_ids(config: WorldCupEditionConfig) -> dict[str, int]:
    return {
        "league_id": _stable_bigint(f"league|{WORLD_CUP_COMPETITION_KEY}", base=LEAGUE_ID_BASE),
        "season_id": _stable_bigint(f"season|{config.edition_key}", base=SEASON_ID_BASE),
    }


def _kickoff_to_utc(config: WorldCupEditionConfig, match_date: date, kick_off: str | None) -> datetime:
    if not config.kickoff_timezone_label or config.kickoff_timezone_offset_hours is None:
        raise RuntimeError(
            f"Edicao {config.edition_key} ainda nao tem estrategia de timezone de kickoff fechada para raw publish."
        )
    time_part = kick_off or "00:00:00.000"
    local_dt = datetime.strptime(f"{match_date.isoformat()} {time_part}", "%Y-%m-%d %H:%M:%S.%f").replace(
        tzinfo=timezone(
            timedelta(hours=config.kickoff_timezone_offset_hours),
            name=config.kickoff_timezone_label,
        )
    )
    return local_dt.astimezone(timezone.utc)


def _read_fixtures_frame(conn, config: WorldCupEditionConfig, run_id: str, now_utc: datetime) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          f.internal_match_id,
          f.source_match_id,
          f.source_version,
          f.supporting_source_match_id,
          f.supporting_source_version,
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
          f.home_team_score,
          f.away_team_score,
          f.home_penalty_score,
          f.away_penalty_score,
          f.penalty_shootout,
          f.extra_time,
          sb.payload->>'kick_off' AS kick_off,
          sb.payload->'stadium'->>'id' AS venue_id,
          sb.payload->'stadium'->>'name' AS venue_name,
          COALESCE(sb.payload->'stadium'->>'country', bf.payload->>'city_name') AS venue_city,
          sb.payload->'referee'->>'id' AS referee_id,
          sb.payload->'referee'->>'name' AS referee_name
        FROM silver.wc_fixtures f
        JOIN silver.wc_stages s
          ON s.edition_key = f.edition_key
         AND s.stage_internal_id = f.stage_internal_id
        LEFT JOIN bronze.statsbomb_wc_matches sb
          ON sb.edition_key = f.edition_key
         AND sb.match_id::text = f.supporting_source_match_id
        LEFT JOIN bronze.fjelstul_wc_matches bf
          ON bf.edition_key = f.edition_key
         AND bf.match_id = f.source_match_id
        WHERE f.edition_key = :edition_key
        ORDER BY f.match_date, f.internal_match_id
        """
    )
    df = pd.read_sql_query(sql, conn, params={"edition_key": config.edition_key})
    if df.empty:
        raise RuntimeError("Nenhum fixture silver encontrado para publicar em raw.fixtures.")

    ids = _world_cup_ids(config)
    season_start = pd.to_datetime(df["match_date"]).dt.date.min()
    season_end = pd.to_datetime(df["match_date"]).dt.date.max()

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
    df["date_utc"] = df.apply(
        lambda row: _kickoff_to_utc(config, pd.Timestamp(row["match_date"]).date(), row["kick_off"]),
        axis=1,
    )
    df["timestamp"] = df["date_utc"].map(lambda value: int(value.timestamp()))
    df["timezone"] = config.kickoff_timezone_label
    df["referee"] = df["referee_name"]
    df["venue_id"] = pd.to_numeric(df["venue_id"], errors="coerce").astype("Int64")
    df["referee_id"] = pd.to_numeric(df["referee_id"], errors="coerce").astype("Int64")
    df["league_id"] = ids["league_id"]
    df["provider_league_id"] = ids["league_id"]
    df["league_name"] = WORLD_CUP_COMPETITION_NAME
    df["season"] = config.season_year
    df["round"] = df.apply(
        lambda row: f"Group {row['group_key']}" if pd.notna(row["group_key"]) else row["stage_name"],
        axis=1,
    )
    df["home_goals"] = df["home_team_score"].astype("Int64")
    df["away_goals"] = df["away_team_score"].astype("Int64")
    df["year"] = df["match_date"].astype(str).str.slice(0, 4)
    df["month"] = df["match_date"].astype(str).str.slice(5, 7)
    df["date"] = pd.to_datetime(df["match_date"]).dt.date
    df["source_provider"] = FJELSTUL_SOURCE
    df["attendance"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    df["weather_description"] = pd.Series(pd.NA, index=df.index, dtype="string")
    df["weather_temperature_c"] = pd.Series([None] * len(df), index=df.index, dtype="float64")
    df["weather_wind_kph"] = pd.Series([None] * len(df), index=df.index, dtype="float64")
    df["home_goals_ht"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    df["away_goals_ht"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    df["home_goals_ft"] = df["home_team_score"].astype("Int64")
    df["away_goals_ft"] = df["away_team_score"].astype("Int64")
    df["provider"] = config.provider
    df["competition_key"] = WORLD_CUP_COMPETITION_KEY
    df["competition_type"] = WORLD_CUP_COMPETITION_TYPE
    df["season_label"] = config.season_label
    df["provider_season_id"] = ids["season_id"]
    df["season_name"] = config.season_name
    df["season_start_date"] = season_start
    df["season_end_date"] = season_end
    df["round_name"] = df["round"]
    df["group_name"] = df["group_key"].map(lambda value: f"Group {value}" if pd.notna(value) else None)
    df["leg"] = 1
    df["ingested_at"] = now_utc
    df["source_run_id"] = run_id
    df["ingested_run"] = run_id
    df["status_short"] = "FT"
    df["status_long"] = "Match Finished"
    df["venue_city"] = df["venue_city"].astype("string")
    return df[RAW_FIXTURES_TARGET_COLUMNS]


def _read_lineups_frame(conn, config: WorldCupEditionConfig, run_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
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
        WHERE edition_key = :edition_key
        ORDER BY internal_match_id, team_internal_id, player_internal_id
        """
    )
    df = pd.read_sql_query(sql, conn, params={"edition_key": config.edition_key})
    if df.empty:
        raise RuntimeError("Nenhum lineup silver encontrado para publicar em raw.fixture_lineups.")

    ids = _world_cup_ids(config)
    df["fixture_id"] = df["internal_match_id"].map(lambda value: _stable_bigint(value, base=FIXTURE_ID_BASE))
    df["team_id"] = df["team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["player_id"] = df["player_internal_id"].map(lambda value: _stable_bigint(value, base=PLAYER_ID_BASE))
    df["lineup_id"] = df.apply(
        lambda row: _lineup_id(config, int(row["fixture_id"]), int(row["team_id"]), int(row["player_id"])),
        axis=1,
    )
    df["provider"] = config.provider
    df["position_id"] = pd.to_numeric(df["first_position_id"], errors="coerce").astype("Int64")
    df["position_name"] = df["first_position_name"].astype("string")
    df["lineup_type_id"] = df["is_starter"].map(lambda value: 1 if bool(value) else 2).astype("Int64")
    df["formation_field"] = pd.Series(pd.NA, index=df.index, dtype="string")
    df["formation_position"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    df["jersey_number"] = pd.to_numeric(df["jersey_number"], errors="coerce").astype("Int64")
    df["details"] = df["payload"].map(lambda payload: _json_text((payload or {}).get("positions") or []))
    df["payload"] = df.apply(
        lambda row: _json_text(
            {
                "edition_key": config.edition_key,
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
    df["provider_league_id"] = ids["league_id"]
    df["competition_key"] = WORLD_CUP_COMPETITION_KEY
    df["season_label"] = config.season_label
    df["provider_season_id"] = ids["season_id"]
    df["source_run_id"] = run_id
    df["ingested_run"] = run_id
    return df[FIXTURE_LINEUPS_TARGET_COLUMNS]


def _read_standings_frame(conn, config: WorldCupEditionConfig, run_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
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
        WHERE edition_key = :edition_key
        ORDER BY stage_key, group_key, final_position
        """
    )
    df = pd.read_sql_query(sql, conn, params={"edition_key": config.edition_key})
    if df.empty:
        raise RuntimeError("Nenhum group standing silver encontrado para publicar em raw.standings_snapshots.")

    ids = _world_cup_ids(config)
    df["provider"] = config.provider
    df["league_id"] = ids["league_id"]
    df["provider_league_id"] = ids["league_id"]
    df["competition_key"] = WORLD_CUP_COMPETITION_KEY
    df["season_label"] = config.season_label
    df["provider_season_id"] = ids["season_id"]
    df["season_id"] = ids["season_id"]
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
                "edition_key": config.edition_key,
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
    df["source_run_id"] = run_id
    df["ingested_run"] = run_id
    return df[STANDINGS_SNAPSHOTS_TARGET_COLUMNS]


def _read_team_coaches_frame(conn, config: WorldCupEditionConfig, run_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
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
          ON pm_team.provider = 'fjelstul_worldcup'
         AND pm_team.entity_type = 'team'
         AND pm_team.source_id = m.team_id
        WHERE m.edition_key = :edition_key
        ORDER BY m.key_id
        """
    )
    df = pd.read_sql_query(sql, conn, params={"edition_key": config.edition_key})
    if df.empty:
        raise RuntimeError("Nenhum manager_appointment bronze encontrado para team_coaches da Copa.")

    df["provider"] = config.provider
    df["coach_tenure_id"] = df["key_id"].map(
        lambda value: _stable_bigint(
            f"coach_tenure|edition={config.edition_key}|source_key={value}",
            base=COACH_TENURE_ID_BASE,
        )
    )
    df["team_id"] = df["team_internal_id"].map(lambda value: _stable_bigint(value, base=TEAM_ID_BASE))
    df["coach_id"] = df["source_manager_id"].map(
        lambda value: _stable_bigint(
            f"coach_source|provider={FJELSTUL_SOURCE}|manager_id={value}",
            base=COACH_ID_BASE,
        )
    )
    df["position_id"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    df["active"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
    df["temporary"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
    df["start_date"] = pd.Series(pd.NaT, index=df.index)
    df["end_date"] = pd.Series(pd.NaT, index=df.index)
    df["payload"] = df.apply(
        lambda row: _json_text(
            {
                "edition_key": config.edition_key,
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


def _read_wc_match_events_frame(conn, config: WorldCupEditionConfig) -> pd.DataFrame:
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
        WHERE edition_key = :edition_key
        ORDER BY internal_match_id, event_index, source_event_id
        """
    )
    df = pd.read_sql_query(sql, conn, params={"edition_key": config.edition_key})
    if df.empty:
        raise RuntimeError("Nenhum match_event silver encontrado para publicar em raw.wc_match_events.")

    df["fixture_id"] = df["internal_match_id"].map(lambda value: _stable_bigint(value, base=FIXTURE_ID_BASE))
    df["event_payload"] = df["event_payload"].map(_json_text)
    return df[RAW_WC_MATCH_EVENTS_TARGET_COLUMNS]


def _validate_prerequisites(conn, config: WorldCupEditionConfig) -> dict[str, Any]:
    checks = {
        "silver_fixtures": ("SELECT count(*) FROM silver.wc_fixtures WHERE edition_key = :edition_key", config.expected_matches),
        "silver_stages": ("SELECT count(*) FROM silver.wc_stages WHERE edition_key = :edition_key", config.expected_stages),
        "silver_groups": ("SELECT count(*) FROM silver.wc_groups WHERE edition_key = :edition_key", config.expected_groups),
        "silver_group_standings": (
            "SELECT count(*) FROM silver.wc_group_standings WHERE edition_key = :edition_key",
            config.expected_group_standings,
        ),
        "silver_lineups_matches": (
            "SELECT count(DISTINCT internal_match_id) FROM silver.wc_lineups WHERE edition_key = :edition_key",
            config.expected_statsbomb_lineup_match_files,
        ),
        "silver_match_events_matches": (
            "SELECT count(DISTINCT internal_match_id) FROM silver.wc_match_events WHERE edition_key = :edition_key",
            config.expected_statsbomb_event_match_files,
        ),
        "blocking_divergences": (
            "SELECT count(*) FROM silver.wc_source_divergences WHERE edition_key = :edition_key AND severity = 'blocking'",
            0,
        ),
    }
    results: dict[str, Any] = {}
    for name, (sql, expected) in checks.items():
        actual = conn.execute(text(sql), {"edition_key": config.edition_key}).scalar_one()
        results[name] = actual
        if actual != expected:
            raise RuntimeError(f"Precondicao do Bloco 6 invalida para {name}: esperado={expected} atual={actual}")

    coach_gate = conn.execute(
        text(
            """
            SELECT
              count(*) AS total_rows,
              count(DISTINCT key_id) AS distinct_key_id,
              count(DISTINCT team_id) AS distinct_team_id,
              count(DISTINCT manager_id) AS distinct_manager_id,
              count(*) FILTER (WHERE team_id IS NULL OR manager_id IS NULL) AS null_team_or_manager
            FROM bronze.fjelstul_wc_manager_appointments
            WHERE edition_key = :edition_key
            """
        ),
        {"edition_key": config.edition_key},
    ).mappings().one()
    results["team_coaches_gate"] = dict(coach_gate)
    expected_coaches = config.expected_groups * 4
    if int(coach_gate["total_rows"]) != expected_coaches or int(coach_gate["distinct_key_id"]) != expected_coaches:
        raise RuntimeError(f"Gate de team_coaches invalido no bronze: {dict(coach_gate)}")
    if int(coach_gate["null_team_or_manager"]) != 0:
        raise RuntimeError(f"Gate de team_coaches com ids nulos: {dict(coach_gate)}")
    return results


def _assert_no_fixture_id_collision(conn, config: WorldCupEditionConfig, fixture_ids: list[int]) -> None:
    if not fixture_ids:
        return
    collisions = conn.execute(
        text(
            """
            SELECT count(*)
            FROM raw.fixtures
            WHERE fixture_id = ANY(:fixture_ids)
              AND coalesce(provider, '') <> :provider
            """
        ),
        {"fixture_ids": fixture_ids, "provider": config.provider},
    ).scalar_one()
    if collisions:
        raise RuntimeError(f"Fixture IDs sinteticos da Copa colidem com raw.fixtures existente: {collisions}")


def _assert_stable_id_uniqueness(df: pd.DataFrame, id_column: str, natural_column: str, label: str) -> None:
    if df[id_column].isna().any():
        raise RuntimeError(f"{label} gerou IDs nulos em {id_column}.")
    if int(df[id_column].nunique()) != int(df[natural_column].nunique()):
        raise RuntimeError(
            f"{label} gerou colisao de surrogate em {id_column}: "
            f"distinct_ids={df[id_column].nunique()} distinct_natural={df[natural_column].nunique()}"
        )


def _upsert_dataframe(
    conn,
    *,
    target_table: str,
    df: pd.DataFrame,
    target_columns: list[str],
    conflict_keys: list[str],
    compare_columns: list[str],
) -> tuple[int, int, int]:
    _assert_target_columns(conn, schema="raw", table=target_table, expected=target_columns)
    return _stage_and_upsert_with_classified_counts(
        conn,
        target_table=target_table,
        load_df=df,
        target_columns=target_columns,
        conflict_keys=conflict_keys,
        compare_columns=compare_columns,
    )


def _upsert_dataframe_without_updated_at(
    conn,
    *,
    target_table: str,
    df: pd.DataFrame,
    target_columns: list[str],
    conflict_keys: list[str],
    compare_columns: list[str],
) -> tuple[int, int, int]:
    _assert_target_columns(conn, schema="raw", table=target_table, expected=target_columns)
    staging_table = f"staging_{target_table}"
    distinct_predicate = " OR ".join([f"t.{col} IS DISTINCT FROM s.{col}" for col in compare_columns]) or "FALSE"
    join_predicate = " AND ".join([f"t.{col} = s.{col}" for col in conflict_keys])
    first_key = conflict_keys[0]
    insert_cols = ", ".join(target_columns)
    staged_select_cols = ", ".join([f"c.{col}" for col in target_columns])
    update_columns = list(compare_columns)
    if "ingested_run" in target_columns and "ingested_run" not in conflict_keys:
        update_columns.append("ingested_run")
    update_set = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
    conflict_where = (
        " OR ".join([f"raw.{target_table}.{col} IS DISTINCT FROM EXCLUDED.{col}" for col in compare_columns]) or "FALSE"
    )
    action_sql = text(
        f"""
        WITH classified AS MATERIALIZED (
            SELECT
                {", ".join([f"s.{col}" for col in target_columns])},
                CASE
                    WHEN t.{first_key} IS NULL THEN 'inserted'
                    WHEN {distinct_predicate} THEN 'updated'
                    ELSE 'ignored'
                END AS row_action
            FROM {staging_table} s
            LEFT JOIN raw.{target_table} t
              ON {join_predicate}
        ),
        upserted AS (
            INSERT INTO raw.{target_table} ({insert_cols})
            SELECT {staged_select_cols}
            FROM classified c
            WHERE c.row_action IN ('inserted', 'updated')
            ON CONFLICT ({", ".join(conflict_keys)}) DO UPDATE
            SET {update_set}
            WHERE {conflict_where}
            RETURNING 1
        )
        SELECT
            COUNT(*) FILTER (WHERE row_action = 'inserted')::bigint AS inserted,
            COUNT(*) FILTER (WHERE row_action = 'updated')::bigint AS updated,
            COUNT(*) FILTER (WHERE row_action = 'ignored')::bigint AS ignored,
            (SELECT COUNT(*)::bigint FROM upserted) AS changed_rows
        FROM classified
        """
    )

    conn.execute(text(f"CREATE TEMP TABLE {staging_table} (LIKE raw.{target_table} INCLUDING DEFAULTS) ON COMMIT DROP"))
    df.to_sql(staging_table, con=conn, if_exists="append", index=False, method="multi")
    counts = conn.execute(action_sql).mappings().one()
    inserted = int(counts["inserted"] or 0)
    updated = int(counts["updated"] or 0)
    ignored = int(counts["ignored"] or 0)
    changed_rows = int(counts["changed_rows"] or 0)
    if inserted + updated != changed_rows:
        raise RuntimeError(
            f"Contagem classificada divergente no upsert de raw.{target_table}: "
            f"inserted={inserted} updated={updated} changed_rows={changed_rows}"
        )
    return inserted, updated, ignored


def _upsert_wc_match_events(conn, df: pd.DataFrame) -> tuple[int, int, int]:
    return _upsert_dataframe(
        conn,
        target_table="wc_match_events",
        df=df,
        target_columns=RAW_WC_MATCH_EVENTS_TARGET_COLUMNS,
        conflict_keys=["source_name", "source_match_id", "source_event_id"],
        compare_columns=[
            col
            for col in RAW_WC_MATCH_EVENTS_TARGET_COLUMNS
            if col not in {"source_name", "source_match_id", "source_event_id"}
        ],
    )


def _validate_raw_outputs(
    conn,
    config: WorldCupEditionConfig,
    *,
    expected_fixture_lineups_rows: int,
    expected_standings_rows: int,
    expected_team_coaches_rows: int,
    expected_wc_match_event_rows: int,
    team_coaches_published: bool,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    checks = {
        "raw_fixtures": (
            """
            SELECT count(*)
            FROM raw.fixtures
            WHERE provider = :provider
              AND competition_key = :competition_key
              AND season_label = :season_label
            """,
            config.expected_matches,
        ),
        "raw_fixture_lineups": (
            """
            SELECT count(*)
            FROM raw.fixture_lineups
            WHERE provider = :provider
              AND competition_key = :competition_key
              AND season_label = :season_label
            """,
            expected_fixture_lineups_rows,
        ),
        "raw_standings_snapshots": (
            """
            SELECT count(*)
            FROM raw.standings_snapshots
            WHERE provider = :provider
              AND competition_key = :competition_key
              AND season_label = :season_label
            """,
            expected_standings_rows,
        ),
        "raw_wc_match_events": (
            """
            SELECT count(*)
            FROM raw.wc_match_events
            WHERE edition_key = :edition_key
            """,
            expected_wc_match_event_rows,
        ),
        "raw_match_events_wc": (
            """
            SELECT count(*)
            FROM raw.match_events
            WHERE provider IN (:provider, 'statsbomb_open_data', 'fjelstul_worldcup')
            """,
            0,
        ),
    }
    params = {
        "provider": config.provider,
        "competition_key": WORLD_CUP_COMPETITION_KEY,
        "season_label": config.season_label,
        "edition_key": config.edition_key,
    }
    for name, (sql, expected) in checks.items():
        actual = conn.execute(text(sql), params).scalar_one()
        results[name] = actual
        if actual != expected:
            raise RuntimeError(f"Validacao raw invalida para {name}: esperado={expected} atual={actual}")

    lineup_bad_matches = conn.execute(
        text(
            """
            SELECT count(*)
            FROM (
              SELECT fixture_id
              FROM raw.fixture_lineups
              WHERE provider = :provider
                AND competition_key = :competition_key
                AND season_label = :season_label
              GROUP BY fixture_id
              HAVING count(DISTINCT team_id) <> 2
            ) bad
            """
        ),
        params,
    ).scalar_one()
    if lineup_bad_matches != 0:
        raise RuntimeError(f"raw.fixture_lineups da Copa sem 2 times por fixture: {lineup_bad_matches}")
    results["raw_fixture_lineups_bad_matches"] = lineup_bad_matches

    lineup_bad_starters = conn.execute(
        text(
            """
            SELECT count(*)
            FROM (
              SELECT fixture_id, team_id
              FROM raw.fixture_lineups
              WHERE provider = :provider
                AND competition_key = :competition_key
                AND season_label = :season_label
              GROUP BY fixture_id, team_id
              HAVING count(*) FILTER (WHERE lineup_type_id = 1) <> 11
            ) bad
            """
        ),
        params,
    ).scalar_one()
    if lineup_bad_starters != 0:
        raise RuntimeError(f"raw.fixture_lineups da Copa com titulares invalidos: {lineup_bad_starters}")
    results["raw_fixture_lineups_bad_starters"] = lineup_bad_starters

    raw_fixtures_nulls = conn.execute(
        text(
            """
            SELECT count(*)
            FROM raw.fixtures
            WHERE provider = :provider
              AND competition_key = :competition_key
              AND season_label = :season_label
              AND (
                fixture_id IS NULL OR league_id IS NULL OR season IS NULL OR
                home_team_id IS NULL OR away_team_id IS NULL OR stage_id IS NULL
              )
            """
        ),
        params,
    ).scalar_one()
    if raw_fixtures_nulls != 0:
        raise RuntimeError(f"raw.fixtures da Copa com chaves/nulos invalidos: {raw_fixtures_nulls}")
    results["raw_fixtures_nulls"] = raw_fixtures_nulls

    raw_wc_match_events_null_fixture = conn.execute(
        text(
            """
            SELECT count(*)
            FROM raw.wc_match_events
            WHERE edition_key = :edition_key
              AND fixture_id IS NULL
            """
        ),
        params,
    ).scalar_one()
    if raw_wc_match_events_null_fixture != 0:
        raise RuntimeError(f"raw.wc_match_events da Copa com fixture_id nulo: {raw_wc_match_events_null_fixture}")
    results["raw_wc_match_events_null_fixture_id"] = raw_wc_match_events_null_fixture

    raw_wc_match_events_orphan_fixture = conn.execute(
        text(
            """
            SELECT count(*)
            FROM raw.wc_match_events e
            LEFT JOIN raw.fixtures f
              ON f.fixture_id = e.fixture_id
             AND f.provider = :provider
             AND f.competition_key = :competition_key
             AND f.season_label = :season_label
            WHERE e.edition_key = :edition_key
              AND f.fixture_id IS NULL
            """
        ),
        params,
    ).scalar_one()
    if raw_wc_match_events_orphan_fixture != 0:
        raise RuntimeError(
            f"raw.wc_match_events da Copa sem fixture navegavel em raw.fixtures: {raw_wc_match_events_orphan_fixture}"
        )
    results["raw_wc_match_events_orphan_fixture_links"] = raw_wc_match_events_orphan_fixture

    if team_coaches_published:
        coaches_rows = conn.execute(
            text("SELECT count(*) FROM raw.team_coaches WHERE provider = :provider"),
            {"provider": config.provider},
        ).scalar_one()
        if coaches_rows != expected_team_coaches_rows:
            raise RuntimeError(
                "raw.team_coaches da Copa invalido: "
                f"esperado={expected_team_coaches_rows} atual={coaches_rows}"
            )
        coach_nulls = conn.execute(
            text(
                """
                SELECT count(*)
                FROM raw.team_coaches
                WHERE provider = :provider
                  AND (coach_tenure_id IS NULL OR team_id IS NULL OR coach_id IS NULL)
                """
            ),
            {"provider": config.provider},
        ).scalar_one()
        if coach_nulls != 0:
            raise RuntimeError(f"raw.team_coaches da Copa com ids nulos: {coach_nulls}")
        results["raw_team_coaches"] = coaches_rows
        results["raw_team_coaches_nulls"] = coach_nulls

    return results


def publish_world_cup_to_raw(edition_key: str | None = None) -> dict[str, Any]:
    context = get_current_context()
    now_utc = _utc_now()
    config = (
        get_world_cup_edition_config(edition_key)
        if edition_key
        else get_world_cup_edition_config_from_context(default=DEFAULT_WORLD_CUP_EDITION_KEY)
    )
    run_id = _run_id(config, now_utc)
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    with StepMetrics(
        service="airflow",
        module="world_cup_raw_publish_service",
        step="publish_world_cup_to_raw",
        context=context,
        dataset=f"raw.world_cup_{config.season_label}",
        table="raw.*",
    ):
        with engine.begin() as conn:
            prereq = _validate_prerequisites(conn, config)

            fixtures_df = _read_fixtures_frame(conn, config, run_id, now_utc)
            lineups_df = _read_lineups_frame(conn, config, run_id)
            standings_df = _read_standings_frame(conn, config, run_id)
            coaches_df = _read_team_coaches_frame(conn, config, run_id)
            wc_match_events_df = _read_wc_match_events_frame(conn, config)

            _assert_no_fixture_id_collision(conn, config, fixtures_df["fixture_id"].astype(int).tolist())

            fixtures_counts = _upsert_dataframe_without_updated_at(
                conn,
                target_table="fixtures",
                df=fixtures_df,
                target_columns=RAW_FIXTURES_TARGET_COLUMNS,
                conflict_keys=["fixture_id"],
                compare_columns=[
                    col for col in RAW_FIXTURES_TARGET_COLUMNS if col not in {"fixture_id", "ingested_run", "ingested_at", "source_run_id"}
                ],
            )
            lineups_counts = _upsert_dataframe(
                conn,
                target_table="fixture_lineups",
                df=lineups_df,
                target_columns=FIXTURE_LINEUPS_TARGET_COLUMNS,
                conflict_keys=["provider", "fixture_id", "team_id", "lineup_id"],
                compare_columns=[
                    col for col in FIXTURE_LINEUPS_TARGET_COLUMNS
                    if col not in {"provider", "fixture_id", "team_id", "lineup_id", "ingested_run", "source_run_id"}
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
                compare_columns=[col for col in TEAM_COACHES_TARGET_COLUMNS if col not in {"provider", "coach_tenure_id", "ingested_run"}],
            )
            wc_events_counts = _upsert_wc_match_events(conn, wc_match_events_df)

            validations = _validate_raw_outputs(
                conn,
                config,
                expected_fixture_lineups_rows=len(lineups_df),
                expected_standings_rows=len(standings_df),
                expected_team_coaches_rows=len(coaches_df),
                expected_wc_match_event_rows=len(wc_match_events_df),
                team_coaches_published=True,
            )

    summary = {
        "prerequisites": prereq,
        "fixtures_upsert": {"inserted": fixtures_counts[0], "updated": fixtures_counts[1], "ignored": fixtures_counts[2]},
        "lineups_upsert": {"inserted": lineups_counts[0], "updated": lineups_counts[1], "ignored": lineups_counts[2]},
        "standings_upsert": {"inserted": standings_counts[0], "updated": standings_counts[1], "ignored": standings_counts[2]},
        "team_coaches_upsert": {"inserted": coaches_counts[0], "updated": coaches_counts[1], "ignored": coaches_counts[2]},
        "wc_match_events_upsert": {"inserted": wc_events_counts[0], "updated": wc_events_counts[1], "ignored": wc_events_counts[2]},
        "validations": validations,
        "run_id": run_id,
        "team_coaches_decision": "published_from_bronze_plus_team_map_as_edition_scoped_provider_rows",
    }

    log_event(
        service="airflow",
        module="world_cup_raw_publish_service",
        step="summary",
        status="success",
        context=context,
        dataset=f"raw.world_cup_{config.season_label}",
        row_count=(
            config.expected_matches
            + len(lineups_df)
            + len(standings_df)
            + len(coaches_df)
            + len(wc_match_events_df)
        ),
        message=(
            "Raw World Cup publicado | "
            f"edition={config.edition_key} | "
            f"fixtures={summary['validations']['raw_fixtures']} | "
            f"lineups={summary['validations']['raw_fixture_lineups']} | "
            f"standings={summary['validations']['raw_standings_snapshots']} | "
            f"team_coaches={summary['validations']['raw_team_coaches']} | "
            f"wc_match_events={summary['validations']['raw_wc_match_events']}"
        ),
    )
    return summary


def publish_world_cup_2022_to_raw() -> dict[str, Any]:
    return publish_world_cup_to_raw(DEFAULT_WORLD_CUP_EDITION_KEY)
