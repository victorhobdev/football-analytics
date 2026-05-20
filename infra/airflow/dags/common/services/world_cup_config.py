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
    kickoff_timezone_by_venue_id: dict[str, str] | None = None
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
        kickoff_timezone_by_venue_id={
            "249": "Europe/Moscow",
            "255": "Europe/Moscow",
            "256": "Europe/Moscow",
            "4130": "Europe/Moscow",
            "4257": "Europe/Volgograd",
            "4258": "Europe/Moscow",
            "4259": "Europe/Moscow",
            "4260": "Europe/Kaliningrad",
            "4261": "Asia/Yekaterinburg",
            "4263": "Europe/Moscow",
            "4726": "Europe/Moscow",
            "118023": "Europe/Samara",
        },
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

WORLD_CUP_STATSBOMB_SAMPLED_EDITIONS: dict[str, WorldCupEditionConfig] = {
    "fifa_world_cup_mens__1958": WorldCupEditionConfig(
        edition_key="fifa_world_cup_mens__1958",
        season_label="1958",
        season_year=1958,
        fjelstul_tournament_id="WC-1958",
        statsbomb_season_name="1958",
        provider="world_cup_1958",
        season_name="1958 FIFA Men's World Cup",
        expected_matches=2,
        expected_groups=0,
        expected_group_standings=0,
        expected_stages=0,
        expected_statsbomb_event_match_files=2,
        expected_statsbomb_lineup_match_files=2,
        expected_statsbomb_three_sixty_match_files=0,
    ),
    "fifa_world_cup_mens__1962": WorldCupEditionConfig(
        edition_key="fifa_world_cup_mens__1962",
        season_label="1962",
        season_year=1962,
        fjelstul_tournament_id="WC-1962",
        statsbomb_season_name="1962",
        provider="world_cup_1962",
        season_name="1962 FIFA Men's World Cup",
        expected_matches=1,
        expected_groups=0,
        expected_group_standings=0,
        expected_stages=0,
        expected_statsbomb_event_match_files=1,
        expected_statsbomb_lineup_match_files=1,
        expected_statsbomb_three_sixty_match_files=0,
    ),
    "fifa_world_cup_mens__1970": WorldCupEditionConfig(
        edition_key="fifa_world_cup_mens__1970",
        season_label="1970",
        season_year=1970,
        fjelstul_tournament_id="WC-1970",
        statsbomb_season_name="1970",
        provider="world_cup_1970",
        season_name="1970 FIFA Men's World Cup",
        expected_matches=6,
        expected_groups=0,
        expected_group_standings=0,
        expected_stages=0,
        expected_statsbomb_event_match_files=6,
        expected_statsbomb_lineup_match_files=6,
        expected_statsbomb_three_sixty_match_files=0,
    ),
    "fifa_world_cup_mens__1974": WorldCupEditionConfig(
        edition_key="fifa_world_cup_mens__1974",
        season_label="1974",
        season_year=1974,
        fjelstul_tournament_id="WC-1974",
        statsbomb_season_name="1974",
        provider="world_cup_1974",
        season_name="1974 FIFA Men's World Cup",
        expected_matches=6,
        expected_groups=0,
        expected_group_standings=0,
        expected_stages=0,
        expected_statsbomb_event_match_files=6,
        expected_statsbomb_lineup_match_files=6,
        expected_statsbomb_three_sixty_match_files=0,
    ),
    "fifa_world_cup_mens__1986": WorldCupEditionConfig(
        edition_key="fifa_world_cup_mens__1986",
        season_label="1986",
        season_year=1986,
        fjelstul_tournament_id="WC-1986",
        statsbomb_season_name="1986",
        provider="world_cup_1986",
        season_name="1986 FIFA Men's World Cup",
        expected_matches=3,
        expected_groups=0,
        expected_group_standings=0,
        expected_stages=0,
        expected_statsbomb_event_match_files=3,
        expected_statsbomb_lineup_match_files=3,
        expected_statsbomb_three_sixty_match_files=0,
    ),
    "fifa_world_cup_mens__1990": WorldCupEditionConfig(
        edition_key="fifa_world_cup_mens__1990",
        season_label="1990",
        season_year=1990,
        fjelstul_tournament_id="WC-1990",
        statsbomb_season_name="1990",
        provider="world_cup_1990",
        season_name="1990 FIFA Men's World Cup",
        expected_matches=1,
        expected_groups=0,
        expected_group_standings=0,
        expected_stages=0,
        expected_statsbomb_event_match_files=1,
        expected_statsbomb_lineup_match_files=1,
        expected_statsbomb_three_sixty_match_files=0,
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
    "first round": "group_stage_1",
    "first group stage": "group_stage_1",
    "group stage": "group_stage_1",
    "second group stage": "group_stage_2",
    "final round": "final_round",
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


def get_world_cup_statsbomb_sampled_edition_config(edition_key: str) -> WorldCupEditionConfig:
    try:
        return WORLD_CUP_STATSBOMB_SAMPLED_EDITIONS[edition_key]
    except KeyError as exc:
        supported = ", ".join(sorted(WORLD_CUP_STATSBOMB_SAMPLED_EDITIONS))
        raise RuntimeError(
            f"Edicao sampled do StatsBomb ainda nao suportada: {edition_key}. "
            f"Suportadas agora: {supported}"
        ) from exc


def get_world_cup_statsbomb_sampled_edition_configs() -> tuple[WorldCupEditionConfig, ...]:
    return tuple(WORLD_CUP_STATSBOMB_SAMPLED_EDITIONS[key] for key in sorted(WORLD_CUP_STATSBOMB_SAMPLED_EDITIONS))


def fetch_active_world_cup_snapshot(engine, *, source_name: str, edition_key: str) -> dict[str, Any]:
    sql = text(
        """
        SELECT
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
          AND source_name = :source_name
          AND edition_scope IN (:edition_key, 'GLOBAL')
        ORDER BY
          CASE
            WHEN edition_scope = :edition_key THEN 0
            WHEN edition_scope = 'GLOBAL' THEN 1
            ELSE 2
          END,
          created_at DESC,
          source_commit_or_release DESC
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(
            sql,
            {
                "edition_key": edition_key,
                "source_name": source_name,
            },
        ).mappings().first()

    if row is None:
        raise RuntimeError(
            f"Snapshot ativo ausente para source={source_name} na edicao {edition_key}."
        )
    return dict(row)


def fetch_active_world_cup_snapshots(engine, *, edition_key: str) -> dict[str, dict[str, Any]]:
    return {
        STATSBOMB_SOURCE: fetch_active_world_cup_snapshot(
            engine,
            source_name=STATSBOMB_SOURCE,
            edition_key=edition_key,
        ),
        FJELSTUL_SOURCE: fetch_active_world_cup_snapshot(
            engine,
            source_name=FJELSTUL_SOURCE,
            edition_key=edition_key,
        ),
    }


def fjelstul_stage_source_id(config: WorldCupEditionConfig, stage_name: str) -> str:
    return f"{config.fjelstul_tournament_id}::stage::{stage_name}"


def fjelstul_group_source_id(config: WorldCupEditionConfig, stage_name: str, group_name: str) -> str:
    return f"{config.fjelstul_tournament_id}::group::{stage_name}::{group_name}"


def statsbomb_stage_source_id(config: WorldCupEditionConfig, source_stage_id: str) -> str:
    return f"{config.edition_key}::stage::{source_stage_id}"
