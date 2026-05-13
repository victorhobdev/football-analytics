from __future__ import annotations

import re
from typing import Any

import pandas as pd


def _to_metric_column(stat_type: str | None) -> str | None:
    if not stat_type:
        return None
    normalized = stat_type.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or None


def _normalize_stat_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.endswith("%"):
            number = stripped[:-1].strip()
            if re.fullmatch(r"-?\d+", number):
                return int(number)
            return None
        if re.fullmatch(r"-?\d+", stripped):
            return int(stripped)
        return stripped
    return value


def _payload_fixture_id(payload: dict[str, Any]) -> int | None:
    source_params = payload.get("source_params", {}) or {}
    fixture_raw = source_params.get("fixture")
    if fixture_raw is None:
        return None
    try:
        return int(fixture_raw)
    except (TypeError, ValueError):
        return None


def _flatten_statistics_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("errors"):
        return []
    fixture_id = _payload_fixture_id(payload)
    if fixture_id is None:
        return []

    response_rows = payload.get("response", []) or []
    if not isinstance(response_rows, list):
        return []

    rows: list[dict[str, Any]] = []
    for team_stats in response_rows:
        team = (team_stats or {}).get("team") or {}
        stats = (team_stats or {}).get("statistics") or []

        row = {
            "fixture_id": fixture_id,
            "team_id": team.get("id"),
            "team_name": team.get("name"),
        }
        for stat in stats:
            metric_name = _to_metric_column((stat or {}).get("type"))
            if metric_name:
                row[metric_name] = _normalize_stat_value((stat or {}).get("value"))
        rows.append(row)
    return rows


def build_statistics_dataframe(payloads: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        rows.extend(_flatten_statistics_payload(payload))

    if not rows:
        raise RuntimeError("Nenhuma linha de statistics gerada a partir dos payloads raw.")

    df = pd.DataFrame(rows)
    df["fixture_id"] = pd.to_numeric(df["fixture_id"], errors="coerce").astype("Int64")
    df["team_id"] = pd.to_numeric(df["team_id"], errors="coerce").astype("Int64")
    df["team_name"] = df["team_name"].astype("string")
    df = df.dropna(subset=["fixture_id", "team_id"]).drop_duplicates(subset=["fixture_id", "team_id"], keep="last")
    return df
