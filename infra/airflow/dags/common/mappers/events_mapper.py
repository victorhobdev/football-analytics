from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_id(
    fixture_id: int,
    time_elapsed: int | None,
    team_id: int | None,
    event_type: str | None,
    detail: str | None,
    player_id: int | None,
) -> str:
    raw = "|".join(
        [
            str(fixture_id),
            str(time_elapsed or ""),
            str(team_id or ""),
            str(event_type or ""),
            str(detail or ""),
            str(player_id or ""),
        ]
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _payload_fixture_id(payload: dict[str, Any]) -> int | None:
    source_params = payload.get("source_params", {}) or {}
    fixture_raw = source_params.get("fixture")
    if fixture_raw is None:
        return None
    try:
        return int(fixture_raw)
    except (TypeError, ValueError):
        return None


def _flatten_events_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("errors"):
        return []
    fixture_id = _payload_fixture_id(payload)
    if fixture_id is None:
        return []

    response_rows = payload.get("response", []) or []
    if not isinstance(response_rows, list):
        return []

    rows: list[dict[str, Any]] = []
    for event in response_rows:
        time_info = (event or {}).get("time") or {}
        team = (event or {}).get("team") or {}
        player = (event or {}).get("player") or {}
        assist = (event or {}).get("assist") or {}

        time_elapsed = _as_int(time_info.get("elapsed"))
        team_id = _as_int(team.get("id"))
        player_id = _as_int(player.get("id"))
        event_type = (event or {}).get("type")
        detail = (event or {}).get("detail")

        rows.append(
            {
                "event_id": _event_id(fixture_id, time_elapsed, team_id, event_type, detail, player_id),
                "fixture_id": fixture_id,
                "time_elapsed": time_elapsed,
                "time_extra": _as_int(time_info.get("extra")),
                "team_id": team_id,
                "team_name": team.get("name"),
                "player_id": player_id,
                "player_name": player.get("name"),
                "assist_id": _as_int(assist.get("id")),
                "assist_name": assist.get("name"),
                "type": event_type,
                "detail": detail,
                "comments": (event or {}).get("comments"),
            }
        )
    return rows


def build_match_events_dataframe(payloads: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        rows.extend(_flatten_events_payload(payload))

    if not rows:
        raise RuntimeError("Nenhuma linha de match events gerada a partir dos payloads raw.")

    df = pd.DataFrame(rows)
    for col in ["fixture_id", "time_elapsed", "time_extra", "team_id", "player_id", "assist_id"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    text_cols = ["event_id", "team_name", "player_name", "assist_name", "type", "detail", "comments"]
    for col in text_cols:
        df[col] = df[col].astype("string")

    df = df.drop_duplicates(subset=["event_id"], keep="last").copy()
    return df
