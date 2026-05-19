from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.observability import StepMetrics, log_event
from common.services.world_cup_config import (
    DEFAULT_WORLD_CUP_EDITION_KEY,
    FJELSTUL_SOURCE,
    STATSBOMB_SOURCE,
    WorldCupEditionConfig,
    fetch_active_world_cup_snapshots,
    get_world_cup_edition_config,
    get_world_cup_edition_config_from_context,
)

WORLD_CUP_DATA_MOUNT_ROOT_ENV = "WORLD_CUP_DATA_MOUNT_ROOT"
DEFAULT_WORLD_CUP_DATA_MOUNT_ROOT = "/opt/airflow/data"


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_runtime_snapshot_path(registered_path: str) -> Path:
    registered = Path(registered_path)
    if registered.exists():
        return registered

    normalized = registered_path.replace("\\", "/")
    data_marker = "/data/"
    marker_index = normalized.lower().find(data_marker)
    if marker_index < 0:
        raise RuntimeError(
            "Nao consegui resolver o caminho do snapshot para runtime. "
            f"Path registrado: {registered_path}"
        )

    suffix = normalized[marker_index + len(data_marker) :]
    mount_root = os.getenv(WORLD_CUP_DATA_MOUNT_ROOT_ENV, DEFAULT_WORLD_CUP_DATA_MOUNT_ROOT).rstrip("/\\")
    candidate = Path(mount_root) / Path(suffix.replace("/", os.sep))
    if candidate.exists():
        return candidate

    raise RuntimeError(
        "Snapshot registrado existe no banco, mas nao esta acessivel no runtime atual. "
        f"Path registrado: {registered_path} | path tentado: {candidate}"
    )


def _require_file(root: Path, relative_path: str) -> Path:
    target = root / Path(relative_path.replace("/", os.sep))
    if not target.exists():
        raise RuntimeError(f"Arquivo obrigatorio ausente no snapshot: {target}")
    return target


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_hash(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def _serialize_payload(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def _build_statsbomb_rows(snapshot: dict[str, Any], config: WorldCupEditionConfig) -> dict[str, list[dict[str, Any]]]:
    runtime_root = _resolve_runtime_snapshot_path(snapshot["local_path"])
    manifest_path = _require_file(runtime_root, "CHECKSUMS.sha256")
    if _manifest_hash(manifest_path) != snapshot["checksum_sha256"]:
        raise RuntimeError(
            "Checksum do manifesto do snapshot StatsBomb diverge do valor registrado em control.wc_source_snapshots."
        )

    _require_file(runtime_root, "README.md")
    _require_file(runtime_root, "ATTRIBUTION.md")
    competitions_path = _require_file(runtime_root, "data/competitions.json")
    competitions = _read_json(competitions_path)
    competition = next(
        (
            item
            for item in competitions
            if item.get("competition_name") == "FIFA World Cup"
            and item.get("season_name") == config.statsbomb_season_name
            and "male" in str(item.get("competition_gender", "")).lower()
        ),
        None,
    )
    if competition is None:
        raise RuntimeError(
            f"Nao encontrei FIFA World Cup masculina {config.season_label} em competitions.json do StatsBomb."
        )

    source_version = snapshot["source_version"]
    source_name = snapshot["source_name"]
    snapshot_path = snapshot["local_path"]
    snapshot_checksum = snapshot["checksum_sha256"]
    matches_relative = f"data/matches/{competition['competition_id']}/{competition['season_id']}.json"
    matches_path = _require_file(runtime_root, matches_relative)
    matches_payload = _read_json(matches_path)
    if len(matches_payload) != config.expected_matches:
        raise RuntimeError(
            f"StatsBomb {config.season_label} deveria ter {config.expected_matches} matches. "
            f"Encontrei {len(matches_payload)}."
        )

    rows: dict[str, list[dict[str, Any]]] = {
        "statsbomb_wc_matches": [],
        "statsbomb_wc_events": [],
        "statsbomb_wc_lineups": [],
        "statsbomb_wc_three_sixty": [],
    }
    match_ids: list[int] = []

    for item in matches_payload:
        match_id = int(item["match_id"])
        match_ids.append(match_id)
        rows["statsbomb_wc_matches"].append(
            {
                "source_name": source_name,
                "source_version": source_version,
                "edition_key": config.edition_key,
                "snapshot_path": snapshot_path,
                "snapshot_checksum_sha256": snapshot_checksum,
                "source_file": matches_relative,
                "competition_id": int(competition["competition_id"]),
                "season_id": int(competition["season_id"]),
                "match_id": match_id,
                "match_date": item.get("match_date"),
                "payload": _serialize_payload(item),
                "ingested_at": _utc_now(),
            }
        )

        for dataset_name, relative_template in (
            ("statsbomb_wc_events", "data/events/{match_id}.json"),
            ("statsbomb_wc_lineups", "data/lineups/{match_id}.json"),
        ):
            relative = relative_template.format(match_id=match_id)
            payload_path = _require_file(runtime_root, relative)
            payload = _read_json(payload_path)
            rows[dataset_name].append(
                {
                    "source_name": source_name,
                    "source_version": source_version,
                    "edition_key": config.edition_key,
                    "snapshot_path": snapshot_path,
                    "snapshot_checksum_sha256": snapshot_checksum,
                    "source_file": relative,
                    "match_id": match_id,
                    "payload_item_count": len(payload),
                    "payload": _serialize_payload(payload),
                    "ingested_at": _utc_now(),
                }
            )

        three_sixty_relative = f"data/three-sixty/{match_id}.json"
        three_sixty_path = runtime_root / Path(three_sixty_relative.replace("/", os.sep))
        if config.expected_statsbomb_three_sixty_match_files > 0:
            payload_path = _require_file(runtime_root, three_sixty_relative)
            payload = _read_json(payload_path)
            rows["statsbomb_wc_three_sixty"].append(
                {
                    "source_name": source_name,
                    "source_version": source_version,
                    "edition_key": config.edition_key,
                    "snapshot_path": snapshot_path,
                    "snapshot_checksum_sha256": snapshot_checksum,
                    "source_file": three_sixty_relative,
                    "match_id": match_id,
                    "payload_item_count": len(payload),
                    "payload": _serialize_payload(payload),
                    "ingested_at": _utc_now(),
                }
            )
        elif three_sixty_path.exists():
            payload = _read_json(three_sixty_path)
            rows["statsbomb_wc_three_sixty"].append(
                {
                    "source_name": source_name,
                    "source_version": source_version,
                    "edition_key": config.edition_key,
                    "snapshot_path": snapshot_path,
                    "snapshot_checksum_sha256": snapshot_checksum,
                    "source_file": three_sixty_relative,
                    "match_id": match_id,
                    "payload_item_count": len(payload),
                    "payload": _serialize_payload(payload),
                    "ingested_at": _utc_now(),
                }
            )

    distinct_event_matches = len({row["match_id"] for row in rows["statsbomb_wc_events"]})
    distinct_lineup_matches = len({row["match_id"] for row in rows["statsbomb_wc_lineups"]})
    distinct_three_sixty_matches = len({row["match_id"] for row in rows["statsbomb_wc_three_sixty"]})
    if distinct_event_matches != config.expected_statsbomb_event_match_files:
        raise RuntimeError(f"Coverage StatsBomb events invalida: {distinct_event_matches} matches.")
    if distinct_lineup_matches != config.expected_statsbomb_lineup_match_files:
        raise RuntimeError(f"Coverage StatsBomb lineups invalida: {distinct_lineup_matches} matches.")
    if distinct_three_sixty_matches != config.expected_statsbomb_three_sixty_match_files:
        raise RuntimeError(f"Coverage StatsBomb three-sixty invalida: {distinct_three_sixty_matches} matches.")

    return rows


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _build_fjelstul_rows(snapshot: dict[str, Any], config: WorldCupEditionConfig) -> dict[str, list[dict[str, Any]]]:
    runtime_root = _resolve_runtime_snapshot_path(snapshot["local_path"])
    manifest_path = _require_file(runtime_root, "CHECKSUMS.sha256")
    if _manifest_hash(manifest_path) != snapshot["checksum_sha256"]:
        raise RuntimeError(
            "Checksum do manifesto do snapshot Fjelstul diverge do valor registrado em control.wc_source_snapshots."
        )

    _require_file(runtime_root, "README.md")
    _require_file(runtime_root, "ATTRIBUTION.md")
    _require_file(runtime_root, "UPSTREAM_LICENSE_EQUIVALENT.md")
    _require_file(runtime_root, "codebook/csv/datasets.csv")
    _require_file(runtime_root, "codebook/csv/variables.csv")

    source_version = snapshot["source_version"]
    source_name = snapshot["source_name"]
    snapshot_path = snapshot["local_path"]
    snapshot_checksum = snapshot["checksum_sha256"]

    dataset_specs = {
        "fjelstul_wc_matches": {
            "relative_path": "data-csv/matches.csv",
            "required_count": config.expected_matches,
            "row_builder": lambda item, relative_path: {
                "source_name": source_name,
                "source_version": source_version,
                "edition_key": config.edition_key,
                "snapshot_path": snapshot_path,
                "snapshot_checksum_sha256": snapshot_checksum,
                "source_file": relative_path,
                "key_id": item["key_id"],
                "tournament_id": item["tournament_id"],
                "match_id": item["match_id"],
                "stage_name": item.get("stage_name"),
                "group_name": item.get("group_name"),
                "home_team_id": item.get("home_team_id"),
                "away_team_id": item.get("away_team_id"),
                "match_date": item.get("match_date"),
                "payload": _serialize_payload(item),
                "ingested_at": _utc_now(),
            },
        },
        "fjelstul_wc_groups": {
            "relative_path": "data-csv/groups.csv",
            "required_count": config.expected_groups,
            "row_builder": lambda item, relative_path: {
                "source_name": source_name,
                "source_version": source_version,
                "edition_key": config.edition_key,
                "snapshot_path": snapshot_path,
                "snapshot_checksum_sha256": snapshot_checksum,
                "source_file": relative_path,
                "key_id": item["key_id"],
                "tournament_id": item["tournament_id"],
                "stage_number": item.get("stage_number"),
                "stage_name": item.get("stage_name"),
                "group_name": item.get("group_name"),
                "count_teams": item.get("count_teams"),
                "payload": _serialize_payload(item),
                "ingested_at": _utc_now(),
            },
        },
        "fjelstul_wc_group_standings": {
            "relative_path": "data-csv/group_standings.csv",
            "required_count": config.expected_group_standings,
            "row_builder": lambda item, relative_path: {
                "source_name": source_name,
                "source_version": source_version,
                "edition_key": config.edition_key,
                "snapshot_path": snapshot_path,
                "snapshot_checksum_sha256": snapshot_checksum,
                "source_file": relative_path,
                "key_id": item["key_id"],
                "tournament_id": item["tournament_id"],
                "stage_number": item.get("stage_number"),
                "stage_name": item.get("stage_name"),
                "group_name": item.get("group_name"),
                "position": item.get("position"),
                "team_id": item.get("team_id"),
                "team_name": item.get("team_name"),
                "team_code": item.get("team_code"),
                "advanced": item.get("advanced"),
                "payload": _serialize_payload(item),
                "ingested_at": _utc_now(),
            },
        },
        "fjelstul_wc_manager_appointments": {
            "relative_path": "data-csv/manager_appointments.csv",
            "required_count": None,
            "row_builder": lambda item, relative_path: {
                "source_name": source_name,
                "source_version": source_version,
                "edition_key": config.edition_key,
                "snapshot_path": snapshot_path,
                "snapshot_checksum_sha256": snapshot_checksum,
                "source_file": relative_path,
                "key_id": item["key_id"],
                "tournament_id": item["tournament_id"],
                "team_id": item.get("team_id"),
                "team_name": item.get("team_name"),
                "team_code": item.get("team_code"),
                "manager_id": item.get("manager_id"),
                "family_name": item.get("family_name"),
                "given_name": item.get("given_name"),
                "country_name": item.get("country_name"),
                "payload": _serialize_payload(item),
                "ingested_at": _utc_now(),
            },
        },
    }

    rows: dict[str, list[dict[str, Any]]] = {}
    for table_name, spec in dataset_specs.items():
        relative_path = spec["relative_path"]
        csv_path = _require_file(runtime_root, relative_path)
        dataset_rows = [
            item for item in _read_csv_rows(csv_path) if item.get("tournament_id") == config.fjelstul_tournament_id
        ]
        required_count = spec["required_count"]
        if required_count is not None and len(dataset_rows) != required_count:
            raise RuntimeError(
                f"{table_name} deveria ter {required_count} rows para {config.fjelstul_tournament_id}. "
                f"Encontrei {len(dataset_rows)}."
            )
        rows[table_name] = [spec["row_builder"](item, relative_path) for item in dataset_rows]

    return rows


def _build_insert_sql(table_name: str, columns: list[str]) -> Any:
    rendered_columns: list[str] = []
    for column in columns:
        if column == "payload":
            rendered_columns.append("CAST(:payload AS jsonb)")
        else:
            rendered_columns.append(f":{column}")
    columns_sql = ", ".join(columns)
    values_sql = ", ".join(rendered_columns)
    return text(f"INSERT INTO bronze.{table_name} ({columns_sql}) VALUES ({values_sql})")


def _replace_table_rows(conn, table_name: str, rows: list[dict[str, Any]], *, edition_key: str) -> None:
    if not rows:
        raise RuntimeError(f"Nenhuma row preparada para bronze.{table_name}.")

    columns = list(rows[0].keys())
    conn.execute(
        text(f"DELETE FROM bronze.{table_name} WHERE edition_key = :edition_key"),
        {"edition_key": edition_key},
    )
    conn.execute(_build_insert_sql(table_name, columns), rows)


def ingest_world_cup_bronze(edition_key: str | None = None) -> dict[str, Any]:
    context = get_current_context()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    config = (
        get_world_cup_edition_config(edition_key)
        if edition_key
        else get_world_cup_edition_config_from_context(default=DEFAULT_WORLD_CUP_EDITION_KEY)
    )

    with StepMetrics(
        service="airflow",
        module="world_cup_bronze_service",
        step="load_world_cup_bronze",
        context=context,
        dataset=f"bronze.world_cup_{config.season_label}",
        table="bronze.*",
    ):
        snapshots = fetch_active_world_cup_snapshots(engine, edition_key=config.edition_key)
        statsbomb_rows = _build_statsbomb_rows(snapshots[STATSBOMB_SOURCE], config)
        fjelstul_rows = _build_fjelstul_rows(snapshots[FJELSTUL_SOURCE], config)

        with engine.begin() as conn:
            for table_name, rows in statsbomb_rows.items():
                _replace_table_rows(conn, table_name, rows, edition_key=config.edition_key)
            for table_name, rows in fjelstul_rows.items():
                _replace_table_rows(conn, table_name, rows, edition_key=config.edition_key)

        summary = {
            "statsbomb_matches": len(statsbomb_rows["statsbomb_wc_matches"]),
            "statsbomb_events_match_files": len(statsbomb_rows["statsbomb_wc_events"]),
            "statsbomb_lineups_match_files": len(statsbomb_rows["statsbomb_wc_lineups"]),
            "statsbomb_three_sixty_match_files": len(statsbomb_rows["statsbomb_wc_three_sixty"]),
            "fjelstul_matches": len(fjelstul_rows["fjelstul_wc_matches"]),
            "fjelstul_groups": len(fjelstul_rows["fjelstul_wc_groups"]),
            "fjelstul_group_standings": len(fjelstul_rows["fjelstul_wc_group_standings"]),
            "fjelstul_manager_appointments": len(fjelstul_rows["fjelstul_wc_manager_appointments"]),
        }

    log_event(
        service="airflow",
        module="world_cup_bronze_service",
        step="summary",
        status="success",
        context=context,
        dataset=f"bronze.world_cup_{config.season_label}",
        row_count=sum(summary.values()),
        message=(
            f"Bronze World Cup {config.season_label} carregado com sucesso | "
            f"statsbomb_matches={summary['statsbomb_matches']} | "
            f"statsbomb_events={summary['statsbomb_events_match_files']} | "
            f"statsbomb_lineups={summary['statsbomb_lineups_match_files']} | "
            f"statsbomb_three_sixty={summary['statsbomb_three_sixty_match_files']} | "
            f"fjelstul_matches={summary['fjelstul_matches']} | "
            f"fjelstul_groups={summary['fjelstul_groups']} | "
            f"fjelstul_group_standings={summary['fjelstul_group_standings']} | "
            f"fjelstul_manager_appointments={summary['fjelstul_manager_appointments']}"
        ),
    )
    return summary


def ingest_world_cup_2022_bronze() -> dict[str, Any]:
    return ingest_world_cup_bronze(DEFAULT_WORLD_CUP_EDITION_KEY)
