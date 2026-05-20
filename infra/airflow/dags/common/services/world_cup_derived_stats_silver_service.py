from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from airflow.operators.python import get_current_context
from sqlalchemy import bindparam, create_engine, text

from common.observability import StepMetrics, log_event
from common.services.world_cup_config import (
    DEFAULT_WORLD_CUP_EDITION_KEY,
    STATSBOMB_SOURCE,
    WORLD_CUP_COMPETITION_KEY,
)

SUPPORTED_EDITIONS = ("fifa_world_cup_mens__2018", DEFAULT_WORLD_CUP_EDITION_KEY)
SOURCE_NAME = STATSBOMB_SOURCE
STATS_DERIVATION_METHOD = "statsbomb_event_rollup_v1"
PLAYER_PARTICIPATION_SCOPE = "starting_xi_plus_substitution_replacements"
MATCH_STATS_COLUMNS = [
    "edition_key",
    "internal_match_id",
    "team_internal_id",
    "source_name",
    "source_version",
    "source_match_id",
    "team_name",
    "shots_on_goal",
    "shots_off_goal",
    "total_shots",
    "blocked_shots",
    "shots_inside_box",
    "shots_outside_box",
    "fouls",
    "corner_kicks",
    "offsides",
    "ball_possession",
    "yellow_cards",
    "red_cards",
    "goalkeeper_saves",
    "total_passes",
    "passes_accurate",
    "passes_pct",
    "payload",
    "materialized_at",
]
PLAYER_MATCH_STATS_COLUMNS = [
    "edition_key",
    "internal_match_id",
    "team_internal_id",
    "player_internal_id",
    "source_name",
    "source_version",
    "source_match_id",
    "source_team_id",
    "source_player_id",
    "team_name",
    "player_name",
    "player_nickname",
    "jersey_number",
    "is_starter",
    "minutes_played",
    "statistics",
    "payload",
    "materialized_at",
]


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _payload_get(payload: Any, *path: str) -> Any:
    current: Any = _json_object(payload)
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _nullable_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stat_entry(metric_type: str, raw_type_name: str, developer_name: str, value: int | float | None) -> dict[str, Any]:
    return {
        "type": metric_type,
        "value": None,
        "raw_value": {"value": value},
        "raw_type_name": raw_type_name,
        "developer_name": developer_name,
    }


def _load_events_df(conn) -> pd.DataFrame:
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
          source_event_id,
          event_index,
          event_type,
          possession,
          minute,
          second,
          location_x,
          location_y,
          payload
        FROM silver.wc_match_events
        WHERE source_name = :source_name
          AND edition_key IN :edition_keys
        ORDER BY edition_key, internal_match_id, event_index
        """
    ).bindparams(bindparam("edition_keys", expanding=True))
    return pd.read_sql_query(
        sql,
        conn,
        params={"source_name": SOURCE_NAME, "edition_keys": list(SUPPORTED_EDITIONS)},
    )


def _load_lineups_df(conn) -> pd.DataFrame:
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
          payload
        FROM silver.wc_lineups
        WHERE source_name = :source_name
          AND edition_key IN :edition_keys
        ORDER BY edition_key, internal_match_id, team_internal_id, player_internal_id
        """
    ).bindparams(bindparam("edition_keys", expanding=True))
    return pd.read_sql_query(
        sql,
        conn,
        params={"source_name": SOURCE_NAME, "edition_keys": list(SUPPORTED_EDITIONS)},
    )


def _validate_prerequisites(conn) -> dict[str, int]:
    checks = {
        "events_2018_matches": (
            """
            SELECT count(DISTINCT internal_match_id)
            FROM silver.wc_match_events
            WHERE source_name = :source_name
              AND edition_key = 'fifa_world_cup_mens__2018'
            """,
            64,
        ),
        "events_2022_matches": (
            """
            SELECT count(DISTINCT internal_match_id)
            FROM silver.wc_match_events
            WHERE source_name = :source_name
              AND edition_key = :edition_2022
            """,
            64,
        ),
        "lineups_2018_matches": (
            """
            SELECT count(DISTINCT internal_match_id)
            FROM silver.wc_lineups
            WHERE source_name = :source_name
              AND edition_key = 'fifa_world_cup_mens__2018'
            """,
            64,
        ),
        "lineups_2022_matches": (
            """
            SELECT count(DISTINCT internal_match_id)
            FROM silver.wc_lineups
            WHERE source_name = :source_name
              AND edition_key = :edition_2022
            """,
            64,
        ),
        "raw_fixtures_2018": (
            """
            SELECT count(*)
            FROM raw.fixtures
            WHERE competition_key = :competition_key
              AND provider = 'world_cup_2018'
              AND season_label = '2018'
            """,
            64,
        ),
        "raw_fixtures_2022": (
            """
            SELECT count(*)
            FROM raw.fixtures
            WHERE competition_key = :competition_key
              AND provider = 'world_cup_2022'
              AND season_label = '2022'
            """,
            64,
        ),
    }
    params = {
        "source_name": SOURCE_NAME,
        "edition_2022": DEFAULT_WORLD_CUP_EDITION_KEY,
        "competition_key": WORLD_CUP_COMPETITION_KEY,
    }
    results: dict[str, int] = {}
    for key, (sql, expected) in checks.items():
        actual = int(conn.execute(text(sql), params).scalar_one())
        results[key] = actual
        if actual != expected:
            raise RuntimeError(f"Precondicao do B7 invalida para {key}: esperado={expected} atual={actual}")
    return results


def _enrich_events_df(events_df: pd.DataFrame) -> pd.DataFrame:
    df = events_df.copy()
    df["minute"] = pd.to_numeric(df["minute"], errors="coerce").fillna(0).astype(int)
    df["second"] = pd.to_numeric(df["second"], errors="coerce").fillna(0.0)
    df["location_x"] = pd.to_numeric(df["location_x"], errors="coerce")
    df["location_y"] = pd.to_numeric(df["location_y"], errors="coerce")
    df["event_second"] = (df["minute"] * 60) + df["second"]
    df["duration_seconds"] = df["payload"].map(lambda payload: _nullable_float(_payload_get(payload, "duration")) or 0.0)
    df["shot_outcome"] = df["payload"].map(lambda payload: _payload_get(payload, "shot", "outcome", "name"))
    df["pass_outcome"] = df["payload"].map(lambda payload: _payload_get(payload, "pass", "outcome", "name"))
    df["pass_type"] = df["payload"].map(lambda payload: _payload_get(payload, "pass", "type", "name"))
    df["foul_card"] = df["payload"].map(lambda payload: _payload_get(payload, "foul_committed", "card", "name"))
    df["bad_behaviour_card"] = df["payload"].map(lambda payload: _payload_get(payload, "bad_behaviour", "card", "name"))
    df["goalkeeper_type"] = df["payload"].map(lambda payload: _payload_get(payload, "goalkeeper", "type", "name"))
    df["key_pass_id"] = df["payload"].map(lambda payload: _payload_get(payload, "shot", "key_pass_id"))
    df["replacement_source_player_id"] = df["payload"].map(
        lambda payload: (
            str(_payload_get(payload, "substitution", "replacement", "id"))
            if _payload_get(payload, "substitution", "replacement", "id") is not None
            else None
        )
    )
    return df


def _derive_match_durations(events_df: pd.DataFrame) -> pd.DataFrame:
    durations = (
        events_df.groupby(["edition_key", "internal_match_id"], as_index=False)["minute"]
        .max()
        .rename(columns={"minute": "match_duration_minutes"})
    )
    durations["match_duration_minutes"] = durations["match_duration_minutes"].clip(lower=90).astype(int)
    return durations


def _derive_possession_share(events_df: pd.DataFrame) -> pd.DataFrame:
    possession_events = events_df[
        events_df["team_internal_id"].notna()
        & events_df["possession"].notna()
    ][
        [
            "edition_key",
            "internal_match_id",
            "team_internal_id",
            "possession",
            "event_second",
            "duration_seconds",
        ]
    ].copy()
    if possession_events.empty:
        return pd.DataFrame(columns=["edition_key", "internal_match_id", "team_internal_id", "ball_possession"])

    possession_windows = (
        possession_events.groupby(
            ["edition_key", "internal_match_id", "team_internal_id", "possession"],
            as_index=False,
        )
        .agg(
            possession_start=("event_second", "min"),
            possession_end=("event_second", "max"),
            duration_tail=("duration_seconds", "max"),
        )
    )
    possession_windows["possession_seconds"] = (
        possession_windows["possession_end"] + possession_windows["duration_tail"] - possession_windows["possession_start"]
    ).clip(lower=1.0)

    team_durations = (
        possession_windows.groupby(["edition_key", "internal_match_id", "team_internal_id"], as_index=False)[
            "possession_seconds"
        ]
        .sum()
    )
    match_totals = (
        team_durations.groupby(["edition_key", "internal_match_id"], as_index=False)["possession_seconds"]
        .sum()
        .rename(columns={"possession_seconds": "match_possession_seconds"})
    )
    team_durations = team_durations.merge(match_totals, on=["edition_key", "internal_match_id"], how="left")
    team_durations["ball_possession_float"] = (
        100.0 * team_durations["possession_seconds"] / team_durations["match_possession_seconds"]
    )
    team_durations["ball_possession"] = team_durations["ball_possession_float"].round().astype(int)

    normalized_rows: list[pd.DataFrame] = []
    for _, group in team_durations.groupby(["edition_key", "internal_match_id"], sort=False):
        current = group.copy()
        delta = 100 - int(current["ball_possession"].sum())
        if delta != 0 and not current.empty:
            adjust_idx = current["ball_possession_float"].idxmax()
            current.loc[adjust_idx, "ball_possession"] = int(current.loc[adjust_idx, "ball_possession"]) + delta
        normalized_rows.append(current)

    normalized = pd.concat(normalized_rows, ignore_index=True)
    return normalized[["edition_key", "internal_match_id", "team_internal_id", "ball_possession"]]


def _team_dimension(lineups_df: pd.DataFrame) -> pd.DataFrame:
    dim = (
        lineups_df.sort_values(["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"])
        .drop_duplicates(subset=["edition_key", "internal_match_id", "team_internal_id"], keep="first")
        .copy()
    )
    return dim[
        [
            "edition_key",
            "internal_match_id",
            "team_internal_id",
            "source_version",
            "source_match_id",
            "team_name",
        ]
    ]


def _derive_match_stats(events_df: pd.DataFrame, lineups_df: pd.DataFrame, materialized_at: datetime) -> pd.DataFrame:
    team_dim = _team_dimension(lineups_df)
    df = events_df.copy()
    saved_shot_outcomes = {"Saved", "Saved to Post", "Saved Off Target"}
    on_target_outcomes = {"Goal", "Saved", "Saved to Post"}
    off_target_outcomes = {"Off T", "Wayward", "Post", "Saved Off Target"}
    card_name = df["bad_behaviour_card"].fillna(df["foul_card"])

    df["is_shot"] = df["event_type"].eq("Shot")
    df["is_shot_on_goal"] = df["is_shot"] & df["shot_outcome"].isin(on_target_outcomes)
    df["is_shot_off_goal"] = df["is_shot"] & df["shot_outcome"].isin(off_target_outcomes)
    df["is_blocked_shot"] = df["is_shot"] & df["shot_outcome"].eq("Blocked")
    df["is_shot_inside_box"] = (
        df["is_shot"]
        & df["location_x"].ge(102)
        & df["location_y"].between(18, 62, inclusive="both")
    )
    df["is_shot_outside_box"] = df["is_shot"] & ~df["is_shot_inside_box"]
    df["is_foul"] = df["event_type"].eq("Foul Committed")
    df["is_corner"] = df["event_type"].eq("Pass") & df["pass_type"].eq("Corner")
    df["is_offside"] = df["event_type"].eq("Offside")
    df["is_yellow_card"] = card_name.eq("Yellow Card")
    df["is_red_card"] = card_name.isin(["Red Card", "Second Yellow"])
    df["is_pass"] = df["event_type"].eq("Pass")
    df["is_accurate_pass"] = df["is_pass"] & df["pass_outcome"].isna()
    df["is_saved_shot"] = df["is_shot"] & df["shot_outcome"].isin(saved_shot_outcomes)

    aggregates = (
        df.groupby(["edition_key", "internal_match_id", "team_internal_id"], as_index=False)
        .agg(
            shots_on_goal=("is_shot_on_goal", "sum"),
            shots_off_goal=("is_shot_off_goal", "sum"),
            total_shots=("is_shot", "sum"),
            blocked_shots=("is_blocked_shot", "sum"),
            shots_inside_box=("is_shot_inside_box", "sum"),
            shots_outside_box=("is_shot_outside_box", "sum"),
            fouls=("is_foul", "sum"),
            corner_kicks=("is_corner", "sum"),
            offsides=("is_offside", "sum"),
            yellow_cards=("is_yellow_card", "sum"),
            red_cards=("is_red_card", "sum"),
            total_passes=("is_pass", "sum"),
            passes_accurate=("is_accurate_pass", "sum"),
            saved_shots_by_attacking_team=("is_saved_shot", "sum"),
        )
    )

    match_saved_totals = (
        aggregates.groupby(["edition_key", "internal_match_id"], as_index=False)["saved_shots_by_attacking_team"]
        .sum()
        .rename(columns={"saved_shots_by_attacking_team": "saved_shots_in_match"})
    )
    aggregates = aggregates.merge(match_saved_totals, on=["edition_key", "internal_match_id"], how="left")
    aggregates["goalkeeper_saves"] = (
        aggregates["saved_shots_in_match"] - aggregates["saved_shots_by_attacking_team"]
    ).clip(lower=0)
    aggregates["passes_pct"] = (
        100.0 * aggregates["passes_accurate"] / aggregates["total_passes"].where(aggregates["total_passes"] > 0)
    ).round(2)
    aggregates = aggregates.drop(columns=["saved_shots_by_attacking_team", "saved_shots_in_match"])

    possession = _derive_possession_share(df)
    result = team_dim.merge(aggregates, on=["edition_key", "internal_match_id", "team_internal_id"], how="left")
    result = result.merge(possession, on=["edition_key", "internal_match_id", "team_internal_id"], how="left")

    int_columns = [
        "shots_on_goal",
        "shots_off_goal",
        "total_shots",
        "blocked_shots",
        "shots_inside_box",
        "shots_outside_box",
        "fouls",
        "corner_kicks",
        "offsides",
        "ball_possession",
        "yellow_cards",
        "red_cards",
        "goalkeeper_saves",
        "total_passes",
        "passes_accurate",
    ]
    for column in int_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)

    result["passes_pct"] = pd.to_numeric(result["passes_pct"], errors="coerce").fillna(0.0).round(2)
    result["source_name"] = SOURCE_NAME
    result["payload"] = result.apply(
        lambda row: _json_text(
            {
                "edition_key": row["edition_key"],
                "source_name": SOURCE_NAME,
                "source_version": row["source_version"],
                "source_match_id": row["source_match_id"],
                "internal_match_id": row["internal_match_id"],
                "team_internal_id": row["team_internal_id"],
                "team_name": row["team_name"],
                "derivation_method": STATS_DERIVATION_METHOD,
                "ball_possession_method": "possession_duration_share_from_statsbomb_events",
            }
        ),
        axis=1,
    )
    result["materialized_at"] = materialized_at
    return result[MATCH_STATS_COLUMNS]


def _derive_player_participants(events_df: pd.DataFrame, lineups_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    player_dim = (
        lineups_df.sort_values(["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"])
        .drop_duplicates(subset=["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"], keep="first")
        .copy()
    )
    starters = player_dim[player_dim["is_starter"].fillna(False)].copy()

    replacements = events_df[
        events_df["event_type"].eq("Substitution") & events_df["replacement_source_player_id"].notna()
    ][
        [
            "edition_key",
            "internal_match_id",
            "team_internal_id",
            "replacement_source_player_id",
            "minute",
        ]
    ].copy()
    replacements["replacement_source_player_id"] = replacements["replacement_source_player_id"].astype("string")

    replacement_players = replacements.merge(
        player_dim[
            [
                "edition_key",
                "internal_match_id",
                "team_internal_id",
                "player_internal_id",
                "source_player_id",
                "source_match_id",
                "source_team_id",
                "team_name",
                "player_name",
                "player_nickname",
                "jersey_number",
                "source_version",
                "is_starter",
            ]
        ],
        left_on=["edition_key", "internal_match_id", "team_internal_id", "replacement_source_player_id"],
        right_on=["edition_key", "internal_match_id", "team_internal_id", "source_player_id"],
        how="inner",
    )

    minute_on = (
        replacement_players.groupby(
            ["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"],
            as_index=False,
        )["minute"]
        .min()
        .rename(columns={"minute": "minute_on"})
    )

    minute_off = (
        events_df[events_df["event_type"].eq("Substitution") & events_df["player_internal_id"].notna()][
            ["edition_key", "internal_match_id", "team_internal_id", "player_internal_id", "minute"]
        ]
        .groupby(["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"], as_index=False)["minute"]
        .min()
        .rename(columns={"minute": "minute_off"})
    )

    participant_keys = pd.concat(
        [
            starters[["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"]],
            replacement_players[["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"]],
        ],
        ignore_index=True,
    ).drop_duplicates()

    participants = participant_keys.merge(
        player_dim[
            [
                "edition_key",
                "internal_match_id",
                "team_internal_id",
                "player_internal_id",
                "source_version",
                "source_match_id",
                "source_team_id",
                "source_player_id",
                "team_name",
                "player_name",
                "player_nickname",
                "jersey_number",
                "is_starter",
            ]
        ],
        on=["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"],
        how="left",
    )
    return participants, minute_on, minute_off


def _derive_player_event_rollups(events_df: pd.DataFrame) -> pd.DataFrame:
    player_events = events_df[events_df["player_internal_id"].notna()].copy()
    if player_events.empty:
        raise RuntimeError("Silver StatsBomb sem player_internal_id em wc_match_events. B7 nao pode derivar player stats.")

    card_name = player_events["bad_behaviour_card"].fillna(player_events["foul_card"])
    saved_goalkeeper_types = {"Shot Saved", "Penalty Saved"}
    on_target_outcomes = {"Goal", "Saved", "Saved to Post"}
    off_target_outcomes = {"Off T", "Wayward", "Post", "Saved Off Target"}

    player_events["is_goal"] = player_events["event_type"].eq("Shot") & player_events["shot_outcome"].eq("Goal")
    player_events["is_shot"] = player_events["event_type"].eq("Shot")
    player_events["is_shot_on_goal"] = player_events["event_type"].eq("Shot") & player_events["shot_outcome"].isin(on_target_outcomes)
    player_events["is_shot_off_goal"] = player_events["event_type"].eq("Shot") & player_events["shot_outcome"].isin(off_target_outcomes)
    player_events["is_pass"] = player_events["event_type"].eq("Pass")
    player_events["is_accurate_pass"] = player_events["is_pass"] & player_events["pass_outcome"].isna()
    player_events["is_foul"] = player_events["event_type"].eq("Foul Committed")
    player_events["is_foul_won"] = player_events["event_type"].eq("Foul Won")
    player_events["is_interception"] = player_events["event_type"].eq("Interception")
    player_events["is_yellow_card"] = card_name.eq("Yellow Card")
    player_events["is_red_card"] = card_name.isin(["Red Card", "Second Yellow"])
    player_events["is_offside"] = player_events["event_type"].eq("Offside")
    player_events["is_goalkeeper_save"] = player_events["event_type"].eq("Goal Keeper") & player_events["goalkeeper_type"].isin(saved_goalkeeper_types)

    rollup = (
        player_events.groupby(
            ["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"],
            as_index=False,
        )
        .agg(
            goals=("is_goal", "sum"),
            total_shots=("is_shot", "sum"),
            shots_on_goal=("is_shot_on_goal", "sum"),
            shots_off_goal=("is_shot_off_goal", "sum"),
            total_passes=("is_pass", "sum"),
            accurate_passes=("is_accurate_pass", "sum"),
            fouls=("is_foul", "sum"),
            fouls_drawn=("is_foul_won", "sum"),
            interceptions=("is_interception", "sum"),
            yellow_cards=("is_yellow_card", "sum"),
            red_cards=("is_red_card", "sum"),
            offsides=("is_offside", "sum"),
            goalkeeper_saves=("is_goalkeeper_save", "sum"),
        )
    )

    shot_key_passes = player_events[
        player_events["event_type"].eq("Shot") & player_events["key_pass_id"].notna()
    ][["edition_key", "internal_match_id", "key_pass_id", "shot_outcome"]].copy()
    passes = player_events[player_events["event_type"].eq("Pass")][
        [
            "edition_key",
            "internal_match_id",
            "team_internal_id",
            "player_internal_id",
            "source_event_id",
        ]
    ].rename(columns={"source_event_id": "key_pass_id"})
    pass_contributions = passes.merge(
        shot_key_passes,
        on=["edition_key", "internal_match_id", "key_pass_id"],
        how="inner",
    )
    if pass_contributions.empty:
        key_pass_rollup = pd.DataFrame(
            columns=["edition_key", "internal_match_id", "team_internal_id", "player_internal_id", "key_passes", "assists"]
        )
    else:
        pass_contributions["is_assist"] = pass_contributions["shot_outcome"].eq("Goal")
        key_pass_rollup = (
            pass_contributions.groupby(
                ["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"],
                as_index=False,
            )
            .agg(
                key_passes=("key_pass_id", "count"),
                assists=("is_assist", "sum"),
            )
        )

    rollup = rollup.merge(
        key_pass_rollup,
        on=["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"],
        how="left",
    )
    rollup["key_passes"] = pd.to_numeric(rollup["key_passes"], errors="coerce").fillna(0).astype(int)
    rollup["assists"] = pd.to_numeric(rollup["assists"], errors="coerce").fillna(0).astype(int)
    rollup["accurate_passes_percentage"] = (
        100.0 * rollup["accurate_passes"] / rollup["total_passes"].where(rollup["total_passes"] > 0)
    ).fillna(0.0).round().astype(int)
    return rollup


def _derive_player_stats(events_df: pd.DataFrame, lineups_df: pd.DataFrame, materialized_at: datetime) -> pd.DataFrame:
    participants, minute_on, minute_off = _derive_player_participants(events_df, lineups_df)
    match_durations = _derive_match_durations(events_df)
    rollup = _derive_player_event_rollups(events_df)

    result = participants.merge(match_durations, on=["edition_key", "internal_match_id"], how="left")
    result = result.merge(minute_on, on=["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"], how="left")
    result = result.merge(minute_off, on=["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"], how="left")
    result = result.merge(rollup, on=["edition_key", "internal_match_id", "team_internal_id", "player_internal_id"], how="left")

    result["is_starter"] = result["is_starter"].fillna(False).astype(bool)
    result["match_duration_minutes"] = pd.to_numeric(result["match_duration_minutes"], errors="coerce").fillna(90).astype(int)
    result["minute_on"] = pd.to_numeric(result["minute_on"], errors="coerce")
    result["minute_off"] = pd.to_numeric(result["minute_off"], errors="coerce")

    starter_minutes = result["minute_off"].fillna(result["match_duration_minutes"])
    substitute_minutes = result["match_duration_minutes"] - result["minute_on"].fillna(result["match_duration_minutes"])
    result["minutes_played"] = starter_minutes.where(result["is_starter"], substitute_minutes)
    result["minutes_played"] = pd.to_numeric(result["minutes_played"], errors="coerce").fillna(0).clip(lower=0).round().astype(int)

    int_columns = [
        "goals",
        "assists",
        "total_shots",
        "shots_on_goal",
        "shots_off_goal",
        "total_passes",
        "accurate_passes",
        "accurate_passes_percentage",
        "key_passes",
        "fouls",
        "fouls_drawn",
        "interceptions",
        "yellow_cards",
        "red_cards",
        "offsides",
        "goalkeeper_saves",
    ]
    for column in int_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)

    result["statistics"] = result.apply(
        lambda row: _json_text(
            [
                _stat_entry("minutes_played", "Minutes Played", "MINUTES_PLAYED", int(row["minutes_played"])),
                _stat_entry("goals", "Goals", "GOALS", int(row["goals"])),
                _stat_entry("assists", "Assists", "ASSISTS", int(row["assists"])),
                _stat_entry("total_shots", "Shots Total", "SHOTS_TOTAL", int(row["total_shots"])),
                _stat_entry("shots_on_goal", "Shots On Target", "SHOTS_ON_TARGET", int(row["shots_on_goal"])),
                _stat_entry("shots_off_goal", "Shots Off Target", "SHOTS_OFF_TARGET", int(row["shots_off_goal"])),
                _stat_entry("total_passes", "Passes", "PASSES", int(row["total_passes"])),
                _stat_entry("accurate_passes", "Accurate Passes", "ACCURATE_PASSES", int(row["accurate_passes"])),
                _stat_entry(
                    "accurate_passes_percentage",
                    "Accurate Passes Percentage",
                    "ACCURATE_PASSES_PERCENTAGE",
                    int(row["accurate_passes_percentage"]),
                ),
                _stat_entry("key_passes", "Key Passes", "KEY_PASSES", int(row["key_passes"])),
                _stat_entry("fouls", "Fouls", "FOULS", int(row["fouls"])),
                _stat_entry("fouls_drawn", "Fouls Drawn", "FOULS_DRAWN", int(row["fouls_drawn"])),
                _stat_entry("interceptions", "Interceptions", "INTERCEPTIONS", int(row["interceptions"])),
                _stat_entry("yellow_cards", "Yellow Cards", "YELLOWCARDS", int(row["yellow_cards"])),
                _stat_entry("red_cards", "Red Cards", "REDCARDS", int(row["red_cards"])),
                _stat_entry("offsides", "Offsides", "OFFSIDES", int(row["offsides"])),
                _stat_entry("goalkeeper_saves", "Saves", "SAVES", int(row["goalkeeper_saves"])),
            ]
        ),
        axis=1,
    )
    result["payload"] = result.apply(
        lambda row: _json_text(
            {
                "edition_key": row["edition_key"],
                "source_name": SOURCE_NAME,
                "source_version": row["source_version"],
                "source_match_id": row["source_match_id"],
                "source_team_id": row["source_team_id"],
                "source_player_id": row["source_player_id"],
                "internal_match_id": row["internal_match_id"],
                "team_internal_id": row["team_internal_id"],
                "player_internal_id": row["player_internal_id"],
                "team_name": row["team_name"],
                "player_name": row["player_name"],
                "player_nickname": row["player_nickname"],
                "is_starter": bool(row["is_starter"]),
                "minutes_played": int(row["minutes_played"]),
                "participant_scope": PLAYER_PARTICIPATION_SCOPE,
                "derivation_method": STATS_DERIVATION_METHOD,
            }
        ),
        axis=1,
    )
    result["source_name"] = SOURCE_NAME
    result["materialized_at"] = materialized_at
    return result[PLAYER_MATCH_STATS_COLUMNS]


def _build_coverage_rows(match_stats_df: pd.DataFrame, player_stats_df: pd.DataFrame, computed_at: datetime) -> pd.DataFrame:
    match_rows = (
        match_stats_df.groupby("edition_key", as_index=False)
        .agg(actual_match_count=("internal_match_id", "nunique"), actual_row_count=("internal_match_id", "size"))
        .assign(
            domain_name="match_statistics",
            source_name=SOURCE_NAME,
            coverage_status="FULL_TOURNAMENT",
            expected_match_count=64,
            expected_row_count=128,
            notes="Derived from StatsBomb events with possession share from possession-window durations.",
            computed_at=computed_at,
        )
    )

    participant_expected = (
        player_stats_df.groupby("edition_key", as_index=False)
        .agg(actual_match_count=("internal_match_id", "nunique"), actual_row_count=("player_internal_id", "size"))
        .rename(columns={"actual_row_count": "expected_row_count"})
    )
    player_rows = participant_expected.assign(
        domain_name="fixture_player_statistics",
        source_name=SOURCE_NAME,
        coverage_status="FULL_TOURNAMENT",
        expected_match_count=64,
        actual_row_count=participant_expected["expected_row_count"],
        notes="Derived from StatsBomb events for effective participants only (starting XI plus substitution replacements).",
        computed_at=computed_at,
    )
    return pd.concat([match_rows, player_rows], ignore_index=True)[
        [
            "edition_key",
            "domain_name",
            "source_name",
            "coverage_status",
            "expected_match_count",
            "actual_match_count",
            "expected_row_count",
            "actual_row_count",
            "notes",
            "computed_at",
        ]
    ]


def _delete_previous_rows(conn) -> None:
    delete_params = {"source_name": SOURCE_NAME, "edition_keys": list(SUPPORTED_EDITIONS)}
    conn.execute(
        text(
            """
            DELETE FROM silver.wc_match_stats
            WHERE source_name = :source_name
              AND edition_key IN :edition_keys
            """
        ).bindparams(bindparam("edition_keys", expanding=True)),
        delete_params,
    )
    conn.execute(
        text(
            """
            DELETE FROM silver.wc_player_match_stats
            WHERE source_name = :source_name
              AND edition_key IN :edition_keys
            """
        ).bindparams(bindparam("edition_keys", expanding=True)),
        delete_params,
    )
    conn.execute(
        text(
            """
            DELETE FROM silver.wc_coverage_manifest
            WHERE source_name = :source_name
              AND domain_name IN ('match_statistics', 'fixture_player_statistics')
              AND edition_key IN :edition_keys
            """
        ).bindparams(bindparam("edition_keys", expanding=True)),
        delete_params,
    )


def _validate_outputs(conn, *, expected_match_rows: int, expected_player_rows: int) -> dict[str, int]:
    params = {"source_name": SOURCE_NAME, "edition_keys": list(SUPPORTED_EDITIONS)}
    expanding_params = text(
        """
        SELECT count(*)
        FROM silver.wc_match_stats
        WHERE source_name = :source_name
          AND edition_key IN :edition_keys
        """
    ).bindparams(bindparam("edition_keys", expanding=True))

    results = {
        "match_stats_rows": int(conn.execute(expanding_params, params).scalar_one()),
        "match_stats_distinct_matches": int(
            conn.execute(
                text(
                    """
                    SELECT count(DISTINCT edition_key || '|' || internal_match_id || '|' || team_internal_id)
                    FROM silver.wc_match_stats
                    WHERE source_name = :source_name
                      AND edition_key IN :edition_keys
                    """
                ).bindparams(bindparam("edition_keys", expanding=True)),
                params,
            ).scalar_one()
        ),
        "match_stats_duplicates": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM (
                      SELECT edition_key, internal_match_id, team_internal_id, source_name, count(*)
                      FROM silver.wc_match_stats
                      WHERE source_name = :source_name
                        AND edition_key IN :edition_keys
                      GROUP BY 1, 2, 3, 4
                      HAVING count(*) > 1
                    ) d
                    """
                ).bindparams(bindparam("edition_keys", expanding=True)),
                params,
            ).scalar_one()
        ),
        "match_stats_bad_possession": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM silver.wc_match_stats
                    WHERE source_name = :source_name
                      AND edition_key IN :edition_keys
                      AND (ball_possession < 0 OR ball_possession > 100)
                    """
                ).bindparams(bindparam("edition_keys", expanding=True)),
                params,
            ).scalar_one()
        ),
        "player_match_stats_rows": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM silver.wc_player_match_stats
                    WHERE source_name = :source_name
                      AND edition_key IN :edition_keys
                    """
                ).bindparams(bindparam("edition_keys", expanding=True)),
                params,
            ).scalar_one()
        ),
        "player_match_stats_duplicates": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM (
                      SELECT edition_key, internal_match_id, team_internal_id, player_internal_id, source_name, count(*)
                      FROM silver.wc_player_match_stats
                      WHERE source_name = :source_name
                        AND edition_key IN :edition_keys
                      GROUP BY 1, 2, 3, 4, 5
                      HAVING count(*) > 1
                    ) d
                    """
                ).bindparams(bindparam("edition_keys", expanding=True)),
                params,
            ).scalar_one()
        ),
        "coverage_rows": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM silver.wc_coverage_manifest
                    WHERE source_name = :source_name
                      AND edition_key IN :edition_keys
                      AND domain_name IN ('match_statistics', 'fixture_player_statistics')
                    """
                ).bindparams(bindparam("edition_keys", expanding=True)),
                params,
            ).scalar_one()
        ),
        "match_stats_possession_sum_mismatches": int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM (
                      SELECT edition_key, internal_match_id, sum(ball_possession) AS possession_sum
                      FROM silver.wc_match_stats
                      WHERE source_name = :source_name
                        AND edition_key IN :edition_keys
                      GROUP BY 1, 2
                    ) sums
                    WHERE possession_sum <> 100
                    """
                ).bindparams(bindparam("edition_keys", expanding=True)),
                params,
            ).scalar_one()
        ),
    }

    expected = {
        "match_stats_rows": expected_match_rows,
        "match_stats_distinct_matches": expected_match_rows,
        "match_stats_duplicates": 0,
        "match_stats_bad_possession": 0,
        "player_match_stats_rows": expected_player_rows,
        "player_match_stats_duplicates": 0,
        "coverage_rows": 4,
        "match_stats_possession_sum_mismatches": 0,
    }
    for key, expected_value in expected.items():
        if results[key] != expected_value:
            raise RuntimeError(f"Validacao do B7 silver falhou em {key}: esperado={expected_value} atual={results[key]}")
    return results


def normalize_world_cup_derived_stats_to_silver() -> dict[str, Any]:
    context = get_current_context()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    materialized_at = _utc_now()
    run_id = f"world_cup_derived_stats_silver__{materialized_at.strftime('%Y%m%dT%H%M%SZ')}"

    with StepMetrics(
        service="airflow",
        module="world_cup_derived_stats_silver_service",
        step="normalize_world_cup_derived_stats_to_silver",
        context=context,
        dataset="silver.world_cup_derived_stats",
        table="silver.wc_match_stats",
    ):
        with engine.begin() as conn:
            prerequisites = _validate_prerequisites(conn)
            events_df = _enrich_events_df(_load_events_df(conn))
            lineups_df = _load_lineups_df(conn)
            match_stats_df = _derive_match_stats(events_df, lineups_df, materialized_at)
            player_stats_df = _derive_player_stats(events_df, lineups_df, materialized_at)
            coverage_df = _build_coverage_rows(match_stats_df, player_stats_df, materialized_at)

            _delete_previous_rows(conn)
            match_stats_df.to_sql("wc_match_stats", schema="silver", con=conn, if_exists="append", index=False, method="multi")
            player_stats_df.to_sql(
                "wc_player_match_stats",
                schema="silver",
                con=conn,
                if_exists="append",
                index=False,
                method="multi",
            )
            coverage_df.to_sql("wc_coverage_manifest", schema="silver", con=conn, if_exists="append", index=False, method="multi")
            validations = _validate_outputs(
                conn,
                expected_match_rows=len(match_stats_df),
                expected_player_rows=len(player_stats_df),
            )

    summary = {
        "prerequisites": prerequisites,
        "match_stats_rows": len(match_stats_df),
        "player_match_stats_rows": len(player_stats_df),
        "coverage_rows": len(coverage_df),
        "validations": validations,
        "run_id": run_id,
    }
    log_event(
        service="airflow",
        module="world_cup_derived_stats_silver_service",
        step="summary",
        status="success",
        context=context,
        dataset="silver.world_cup_derived_stats",
        row_count=len(match_stats_df) + len(player_stats_df),
        message=(
            "Silver derivado da Copa materializado | "
            f"match_stats={len(match_stats_df)} | "
            f"player_match_stats={len(player_stats_df)} | "
            f"coverage_rows={len(coverage_df)}"
        ),
    )
    return summary
