from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from airflow.operators.python import get_current_context
from sqlalchemy import text


DEFAULT_WORLD_CUP_EDITION_KEY = "fifa_world_cup_mens__2022"
WORLD_CUP_COMPETITION_KEY = "fifa_world_cup_mens"
WORLD_CUP_COMPETITION_NAME = "FIFA Men's World Cup"
WORLD_CUP_COMPETITION_TYPE = "international_cup"
WORLD_CUP_TEAM_TYPE = "national_team"

STATSBOMB_SOURCE = "statsbomb_open_data"
FJELSTUL_SOURCE = "fjelstul_worldcup"


@dataclass(frozen=True)
class WorldCupEditionConfig:
    edition_key: str
    season_label: str
    season_year: int
    fjelstul_tournament_id: str
    statsbomb_season_name: str
    provider: str
    season_name: str
    kickoff_timezone_label: str | None = None
    kickoff_timezone_offset_hours: int | None = None
    expected_matches: int = 64
    expected_groups: int = 8
    expected_group_standings: int = 32
    expected_stages: int = 6
    expected_statsbomb_event_match_files: int = 64
    expected_statsbomb_lineup_match_files: int = 64
    expected_statsbomb_three_sixty_match_files: int = 0


WORLD_CUP_EDITIONS: dict[str, WorldCupEditionConfig] = {
    "fifa_world_cup_mens__2018": WorldCupEditionConfig(
        edition_key="fifa_world_cup_mens__2018",
        season_label="2018",
        season_year=2018,
        fjelstul_tournament_id="WC-2018",
        statsbomb_season_name="2018",
        provider="world_cup_2018",
        season_name="2018 FIFA Men's World Cup",
        expected_statsbomb_three_sixty_match_files=0,
    ),
    "fifa_world_cup_mens__2022": WorldCupEditionConfig(
        edition_key="fifa_world_cup_mens__2022",
        season_label="2022",
        season_year=2022,
        fjelstul_tournament_id="WC-2022",
        statsbomb_season_name="2022",
        provider="world_cup_2022",
        season_name="2022 FIFA Men's World Cup",
        kickoff_timezone_label="Asia/Qatar",
        kickoff_timezone_offset_hours=3,
        expected_statsbomb_three_sixty_match_files=64,
    ),
}


STATSBOMB_STAGE_KEY_MAP = {
    "Group Stage": "group_stage_1",
    "Round of 16": "round_of_16",
    "Quarter-finals": "quarter_final",
    "Semi-finals": "semi_final",
    "3rd Place Final": "third_place",
    "Final": "final",
}

FJELSTUL_STAGE_KEY_MAP = {
    "group stage": "group_stage_1",
    "round of 16": "round_of_16",
    "quarter-finals": "quarter_final",
    "semi-finals": "semi_final",
    "third-place match": "third_place",
    "final": "final",
}


def get_world_cup_edition_config(edition_key: str) -> WorldCupEditionConfig:
    try:
        return WORLD_CUP_EDITIONS[edition_key]
    except KeyError as exc:
        supported = ", ".join(sorted(WORLD_CUP_EDITIONS))
        raise RuntimeError(
            f"Edicao da Copa ainda nao suportada nesta fundacao: {edition_key}. "
            f"Suportadas agora: {supported}"
        ) from exc


def get_world_cup_edition_key_from_context(*, default: str = DEFAULT_WORLD_CUP_EDITION_KEY) -> str:
    context = get_current_context()
    dag_run = context.get("dag_run")
    dag_run_conf = dag_run.conf if dag_run and dag_run.conf else {}
    params = context.get("params") or {}
    return str(dag_run_conf.get("edition_key") or params.get("edition_key") or default)


def get_world_cup_edition_config_from_context(*, default: str = DEFAULT_WORLD_CUP_EDITION_KEY) -> WorldCupEditionConfig:
    edition_key = get_world_cup_edition_key_from_context(default=default)
    return get_world_cup_edition_config(edition_key)


def fetch_active_world_cup_snapshots(engine, *, edition_key: str) -> dict[str, dict[str, Any]]:
    sql = text(
        """
        SELECT DISTINCT ON (source_name)
          source_name,
          source_version,
          source_commit_or_release,
          edition_scope,
          checksum_sha256,
          local_path,
          license_code,
          attribution_note
        FROM control.wc_source_snapshots
        WHERE usage_decision = 'now'
          AND is_active = TRUE
          AND source_name IN (:statsbomb_source, :fjelstul_source)
          AND edition_scope IN (:edition_key, 'GLOBAL')
        ORDER BY
          source_name,
          CASE
            WHEN edition_scope = :edition_key THEN 0
            WHEN edition_scope = 'GLOBAL' THEN 1
            ELSE 2
          END,
          created_at DESC,
          source_commit_or_release DESC
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(
            sql,
            {
                "edition_key": edition_key,
                "statsbomb_source": STATSBOMB_SOURCE,
                "fjelstul_source": FJELSTUL_SOURCE,
            },
        ).mappings().all()

    snapshots = {row["source_name"]: dict(row) for row in rows}
    missing = [source for source in (STATSBOMB_SOURCE, FJELSTUL_SOURCE) if source not in snapshots]
    if missing:
        raise RuntimeError(
            f"Snapshots ativos ausentes para a edicao {edition_key}. Faltando: {missing}"
        )
    return snapshots


def fjelstul_stage_source_id(config: WorldCupEditionConfig, stage_name: str) -> str:
    return f"{config.fjelstul_tournament_id}::stage::{stage_name}"


def fjelstul_group_source_id(config: WorldCupEditionConfig, stage_name: str, group_name: str) -> str:
    return f"{config.fjelstul_tournament_id}::group::{stage_name}::{group_name}"


def statsbomb_stage_source_id(config: WorldCupEditionConfig, source_stage_id: str) -> str:
    return f"{config.edition_key}::stage::{source_stage_id}"
