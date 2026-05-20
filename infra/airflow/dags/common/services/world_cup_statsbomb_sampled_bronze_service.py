from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.observability import StepMetrics, log_event
from common.services.world_cup_bronze_service import _build_statsbomb_rows, _replace_table_rows
from common.services.world_cup_config import (
    STATSBOMB_SOURCE,
    fetch_active_world_cup_snapshot,
    get_world_cup_statsbomb_sampled_edition_configs,
)

EXPECTED_LINEUP_ROWS = {
    "fifa_world_cup_mens__1958": 88,
    "fifa_world_cup_mens__1962": 44,
    "fifa_world_cup_mens__1970": 264,
    "fifa_world_cup_mens__1974": 264,
    "fifa_world_cup_mens__1986": 132,
    "fifa_world_cup_mens__1990": 44,
}

EXPECTED_EVENT_ROWS = {
    "fifa_world_cup_mens__1958": 7341,
    "fifa_world_cup_mens__1962": 3754,
    "fifa_world_cup_mens__1970": 20029,
    "fifa_world_cup_mens__1974": 19259,
    "fifa_world_cup_mens__1986": 8466,
    "fifa_world_cup_mens__1990": 3140,
}

EXPECTED_LINEUP_TEAM_ROWS = {
    config.edition_key: config.expected_statsbomb_lineup_match_files * 2
    for config in get_world_cup_statsbomb_sampled_edition_configs()
}


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_output(conn) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for config in get_world_cup_statsbomb_sampled_edition_configs():
        params = {"edition_key": config.edition_key}
        match_count = int(
            conn.execute(
                text("SELECT count(*) FROM bronze.statsbomb_wc_matches WHERE edition_key = :edition_key"),
                params,
            ).scalar_one()
        )
        event_match_count = int(
            conn.execute(
                text("SELECT count(DISTINCT match_id) FROM bronze.statsbomb_wc_events WHERE edition_key = :edition_key"),
                params,
            ).scalar_one()
        )
        lineup_match_count = int(
            conn.execute(
                text("SELECT count(DISTINCT match_id) FROM bronze.statsbomb_wc_lineups WHERE edition_key = :edition_key"),
                params,
            ).scalar_one()
        )
        three_sixty_count = int(
            conn.execute(
                text("SELECT count(*) FROM bronze.statsbomb_wc_three_sixty WHERE edition_key = :edition_key"),
                params,
            ).scalar_one()
        )
        event_row_count = int(
            conn.execute(
                text("SELECT COALESCE(sum(payload_item_count), 0) FROM bronze.statsbomb_wc_events WHERE edition_key = :edition_key"),
                params,
            ).scalar_one()
        )
        lineup_row_count = int(
            conn.execute(
                text("SELECT COALESCE(sum(payload_item_count), 0) FROM bronze.statsbomb_wc_lineups WHERE edition_key = :edition_key"),
                params,
            ).scalar_one()
        )
        bad_lineup_payloads = int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM bronze.statsbomb_wc_lineups
                    WHERE edition_key = :edition_key
                      AND payload_item_count <> 2
                    """
                ),
                params,
            ).scalar_one()
        )
        versions = conn.execute(
            text(
                """
                SELECT table_name, array_agg(DISTINCT source_version ORDER BY source_version) AS versions
                FROM (
                  SELECT 'statsbomb_wc_matches'::text AS table_name, source_version
                  FROM bronze.statsbomb_wc_matches
                  WHERE edition_key = :edition_key
                  UNION ALL
                  SELECT 'statsbomb_wc_events'::text AS table_name, source_version
                  FROM bronze.statsbomb_wc_events
                  WHERE edition_key = :edition_key
                  UNION ALL
                  SELECT 'statsbomb_wc_lineups'::text AS table_name, source_version
                  FROM bronze.statsbomb_wc_lineups
                  WHERE edition_key = :edition_key
                ) src
                GROUP BY table_name
                ORDER BY table_name
                """
            ),
            params,
        ).mappings().all()

        if match_count != config.expected_matches:
            raise RuntimeError(
                f"Bronze sampled StatsBomb invalido para {config.edition_key}: "
                f"matches esperado={config.expected_matches} atual={match_count}"
            )
        if event_match_count != config.expected_statsbomb_event_match_files:
            raise RuntimeError(
                f"Bronze sampled StatsBomb invalido para {config.edition_key}: "
                f"event_match_files esperado={config.expected_statsbomb_event_match_files} atual={event_match_count}"
            )
        if lineup_match_count != config.expected_statsbomb_lineup_match_files:
            raise RuntimeError(
                f"Bronze sampled StatsBomb invalido para {config.edition_key}: "
                f"lineup_match_files esperado={config.expected_statsbomb_lineup_match_files} atual={lineup_match_count}"
            )
        if three_sixty_count != 0:
            raise RuntimeError(
                f"Bronze sampled StatsBomb invalido para {config.edition_key}: three_sixty deveria ser 0 e veio {three_sixty_count}"
            )
        if lineup_row_count != EXPECTED_LINEUP_TEAM_ROWS[config.edition_key]:
            raise RuntimeError(
                f"Bronze sampled StatsBomb invalido para {config.edition_key}: "
                f"lineup_team_rows esperado={EXPECTED_LINEUP_TEAM_ROWS[config.edition_key]} atual={lineup_row_count}"
            )
        if event_row_count != EXPECTED_EVENT_ROWS[config.edition_key]:
            raise RuntimeError(
                f"Bronze sampled StatsBomb invalido para {config.edition_key}: "
                f"event_rows esperado={EXPECTED_EVENT_ROWS[config.edition_key]} atual={event_row_count}"
            )
        if bad_lineup_payloads != 0:
            raise RuntimeError(
                f"Bronze sampled StatsBomb invalido para {config.edition_key}: "
                f"arquivos de lineup com payload_item_count <> 2 = {bad_lineup_payloads}"
            )
        for row in versions:
            if list(row["versions"]) != [row["versions"][0]]:
                raise RuntimeError(
                    f"Bronze sampled StatsBomb com multiplas versions em {config.edition_key} / {row['table_name']}: {row['versions']}"
                )

        summary[config.edition_key] = {
            "matches": match_count,
            "event_match_files": event_match_count,
            "lineup_match_files": lineup_match_count,
            "event_rows": event_row_count,
            "lineup_team_rows": lineup_row_count,
        }
    return summary


def ingest_world_cup_statsbomb_sampled_bronze() -> dict[str, Any]:
    context = get_current_context()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    sampled_configs = get_world_cup_statsbomb_sampled_edition_configs()

    with StepMetrics(
        service="airflow",
        module="world_cup_statsbomb_sampled_bronze_service",
        step="load_world_cup_statsbomb_sampled_bronze",
        context=context,
        dataset="bronze.world_cup_statsbomb_sampled",
        table="bronze.statsbomb_wc_*",
    ):
        with engine.begin() as conn:
            for config in sampled_configs:
                snapshot = fetch_active_world_cup_snapshot(
                    engine,
                    source_name=STATSBOMB_SOURCE,
                    edition_key=config.edition_key,
                )
                statsbomb_rows = _build_statsbomb_rows(snapshot, config)
                for table_name, rows in statsbomb_rows.items():
                    if rows:
                        _replace_table_rows(conn, table_name, rows, edition_key=config.edition_key)
                    else:
                        conn.execute(
                            text(f"DELETE FROM bronze.{table_name} WHERE edition_key = :edition_key"),
                            {"edition_key": config.edition_key},
                        )

            summary = _validate_output(conn)

    log_event(
        service="airflow",
        module="world_cup_statsbomb_sampled_bronze_service",
        step="summary",
        status="success",
        context=context,
        dataset="bronze.world_cup_statsbomb_sampled",
        row_count=sum(item["event_rows"] + item["lineup_team_rows"] + item["matches"] for item in summary.values()),
        message=(
            "Bronze sampled StatsBomb da Copa carregado | "
            + " | ".join(
                f"{edition} matches={item['matches']} events={item['event_rows']} lineup_team_rows={item['lineup_team_rows']}"
                for edition, item in summary.items()
            )
        ),
    )
    return summary
