from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import secrets
import time
import uuid
from typing import Any

from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.observability import StepMetrics, log_event
from common.services.world_cup_config import (
    DEFAULT_WORLD_CUP_EDITION_KEY,
    FJELSTUL_SOURCE,
    FJELSTUL_STAGE_KEY_MAP,
    STATSBOMB_SOURCE,
    STATSBOMB_STAGE_KEY_MAP,
    WORLD_CUP_TEAM_TYPE,
    WorldCupEditionConfig,
    fetch_active_world_cup_snapshots,
    fjelstul_group_source_id,
    fjelstul_stage_source_id,
    get_world_cup_edition_config,
    get_world_cup_edition_config_from_context,
    statsbomb_stage_source_id,
)

GROUP_PATTERN = re.compile(r"Group\s+([A-Z0-9]+)$", re.IGNORECASE)
HISTORICAL_GROUP_ROW_EDITION_COUNT = 20
HISTORICAL_MATCH_ROW_COUNT = 964
HISTORICAL_STAGE_ROW_COUNT = 113
HISTORICAL_TEAM_COUNT = 85
HISTORICAL_WORLD_CUP_EDITION_PATTERN = "fifa_world_cup_mens__%"
HISTORICAL_TEAM_INTERNAL_ID_OVERRIDES = {
    "T-86": "team__national_team__WEST_GERMANY",
}
ALLOWED_HISTORICAL_TEAM_CODE_COLLISIONS = {
    "DEU": {"T-31", "T-86"},
}


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid7() -> str:
    timestamp_ms = int(time.time_ns() // 1_000_000)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    uuid_int = (
        ((timestamp_ms & ((1 << 48) - 1)) << 80)
        | (0x7 << 76)
        | (rand_a << 64)
        | (0b10 << 62)
        | rand_b
    )
    return str(uuid.UUID(int=uuid_int))


def _team_internal_id(team_code: str) -> str:
    return f"team__{WORLD_CUP_TEAM_TYPE}__{team_code}"


def _historical_team_internal_id(team_id: str, team_code: str) -> str:
    override = HISTORICAL_TEAM_INTERNAL_ID_OVERRIDES.get(team_id)
    if override is not None:
        return override
    return _team_internal_id(team_code)


def _stage_internal_id(stage_key: str, edition_key: str) -> str:
    return f"stage__{edition_key}__{stage_key}"


def _group_internal_id(stage_key: str, group_code: str, edition_key: str) -> str:
    return f"group__{edition_key}__{stage_key}__{group_code}"


def _match_internal_id() -> str:
    return f"match__wc__{_uuid7()}"


def _player_internal_id() -> str:
    return f"player__{_uuid7()}"


def _require_group_code(group_name: str) -> str:
    match = GROUP_PATTERN.match(group_name.strip())
    if not match:
        raise RuntimeError(f"Nome de grupo invalido para canonicalizacao: {group_name}")
    return match.group(1).upper()


def _validate_bronze_counts(conn, config: WorldCupEditionConfig) -> None:
    checks = {
        "statsbomb_matches": (
            "SELECT count(*) FROM bronze.statsbomb_wc_matches WHERE edition_key = :edition_key",
            config.expected_matches,
        ),
        "statsbomb_events_matches": (
            "SELECT count(DISTINCT match_id) FROM bronze.statsbomb_wc_events WHERE edition_key = :edition_key",
            config.expected_statsbomb_event_match_files,
        ),
        "statsbomb_lineups_matches": (
            "SELECT count(DISTINCT match_id) FROM bronze.statsbomb_wc_lineups WHERE edition_key = :edition_key",
            config.expected_statsbomb_lineup_match_files,
        ),
        "statsbomb_three_sixty_matches": (
            "SELECT count(DISTINCT match_id) FROM bronze.statsbomb_wc_three_sixty WHERE edition_key = :edition_key",
            config.expected_statsbomb_three_sixty_match_files,
        ),
        "fjelstul_matches": (
            "SELECT count(*) FROM bronze.fjelstul_wc_matches WHERE edition_key = :edition_key",
            config.expected_matches,
        ),
        "fjelstul_groups": (
            "SELECT count(*) FROM bronze.fjelstul_wc_groups WHERE edition_key = :edition_key",
            config.expected_groups,
        ),
        "fjelstul_group_standings": (
            "SELECT count(*) FROM bronze.fjelstul_wc_group_standings WHERE edition_key = :edition_key",
            config.expected_group_standings,
        ),
    }
    for name, (sql, expected) in checks.items():
        actual = conn.execute(text(sql), {"edition_key": config.edition_key}).scalar_one()
        if actual != expected:
            raise RuntimeError(f"Precondicao do bronze invalida para {name}: esperado={expected} atual={actual}")


def _validate_bronze_snapshot_versions(conn, snapshots: dict[str, dict[str, Any]], config: WorldCupEditionConfig) -> None:
    version_checks = [
        ("bronze.statsbomb_wc_matches", STATSBOMB_SOURCE),
        ("bronze.statsbomb_wc_events", STATSBOMB_SOURCE),
        ("bronze.statsbomb_wc_lineups", STATSBOMB_SOURCE),
        ("bronze.statsbomb_wc_three_sixty", STATSBOMB_SOURCE),
        ("bronze.fjelstul_wc_matches", FJELSTUL_SOURCE),
        ("bronze.fjelstul_wc_groups", FJELSTUL_SOURCE),
        ("bronze.fjelstul_wc_group_standings", FJELSTUL_SOURCE),
        ("bronze.fjelstul_wc_manager_appointments", FJELSTUL_SOURCE),
    ]
    for table_name, source_name in version_checks:
        rows = conn.execute(
            text(f"SELECT DISTINCT source_version FROM {table_name} WHERE edition_key = :edition_key ORDER BY source_version"),
            {"edition_key": config.edition_key},
        ).scalars().all()
        if table_name == "bronze.statsbomb_wc_three_sixty" and config.expected_statsbomb_three_sixty_match_files == 0:
            expected = [snapshots[source_name]["source_version"]] if rows else []
        else:
            expected = [snapshots[source_name]["source_version"]]
        if rows != expected:
            raise RuntimeError(
                f"Versao do bronze divergente do snapshot ativo em {table_name}: bronze={rows} ativo={expected}"
            )


def _fetch_existing_map(conn, config: WorldCupEditionConfig) -> dict[tuple[str, str, str], str]:
    rows = conn.execute(
        text(
            """
            SELECT provider, entity_type, source_id, canonical_id
            FROM raw.provider_entity_map
            WHERE provider IN (:statsbomb_source, :fjelstul_source)
              AND entity_type IN ('team', 'match', 'stage', 'group', 'player')
              AND (
                entity_type = 'team'
                OR edition_key = :edition_key
              )
            """
        ),
        {
            "statsbomb_source": STATSBOMB_SOURCE,
            "fjelstul_source": FJELSTUL_SOURCE,
            "edition_key": config.edition_key,
        },
    ).mappings().all()
    return {(row["provider"], row["entity_type"], row["source_id"]): row["canonical_id"] for row in rows}


def _fetch_team_rows(conn, config: WorldCupEditionConfig) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            WITH sb AS (
              SELECT DISTINCT (payload->'home_team'->>'home_team_id')::text AS statsbomb_team_id, payload->'home_team'->>'home_team_name' AS team_name
              FROM bronze.statsbomb_wc_matches
              WHERE edition_key = :edition_key
              UNION
              SELECT DISTINCT (payload->'away_team'->>'away_team_id')::text AS statsbomb_team_id, payload->'away_team'->>'away_team_name' AS team_name
              FROM bronze.statsbomb_wc_matches
              WHERE edition_key = :edition_key
            ),
            fj AS (
              SELECT DISTINCT team_id AS fjelstul_team_id, team_name, team_code
              FROM bronze.fjelstul_wc_group_standings
              WHERE edition_key = :edition_key
            )
            SELECT sb.statsbomb_team_id, fj.fjelstul_team_id, sb.team_name AS statsbomb_team_name, fj.team_name AS fjelstul_team_name, fj.team_code
            FROM sb
            JOIN fj ON lower(sb.team_name) = lower(fj.team_name)
            ORDER BY fj.team_code
            """
        ),
        {"edition_key": config.edition_key},
    ).mappings().all()
    expected = conn.execute(
        text(
            """
            SELECT count(DISTINCT team_id)
            FROM bronze.fjelstul_wc_group_standings
            WHERE edition_key = :edition_key
            """
        ),
        {"edition_key": config.edition_key},
    ).scalar_one()
    if len(rows) != expected:
        raise RuntimeError(
            f"Team bootstrap exige {expected} joins StatsBomb<->Fjelstul para {config.edition_key}. "
            f"Encontrei {len(rows)}."
        )
    return [dict(row) for row in rows]


def _fetch_stage_rows(conn, config: WorldCupEditionConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    statsbomb_rows = conn.execute(
        text(
            """
            SELECT DISTINCT (payload->'competition_stage'->>'id')::text AS source_id, payload->'competition_stage'->>'name' AS stage_name
            FROM bronze.statsbomb_wc_matches
            WHERE edition_key = :edition_key
            ORDER BY source_id
            """
        ),
        {"edition_key": config.edition_key},
    ).mappings().all()
    fjelstul_rows = conn.execute(
        text(
            """
            SELECT DISTINCT stage_name
            FROM bronze.fjelstul_wc_matches
            WHERE edition_key = :edition_key
            ORDER BY stage_name
            """
        ),
        {"edition_key": config.edition_key},
    ).mappings().all()
    if len(statsbomb_rows) != config.expected_stages or len(fjelstul_rows) != config.expected_stages:
        raise RuntimeError(
            "Stage bootstrap invalido: "
            f"statsbomb={len(statsbomb_rows)} fjelstul={len(fjelstul_rows)} "
            f"esperado={config.expected_stages}"
        )
    return [dict(row) for row in statsbomb_rows], [dict(row) for row in fjelstul_rows]


def _fetch_group_rows(conn, config: WorldCupEditionConfig) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT stage_name, group_name
            FROM bronze.fjelstul_wc_groups
            WHERE edition_key = :edition_key
            ORDER BY group_name
            """
        ),
        {"edition_key": config.edition_key},
    ).mappings().all()
    if len(rows) != config.expected_groups:
        raise RuntimeError(
            f"Group bootstrap exige {config.expected_groups} grupos para {config.edition_key}. Encontrei {len(rows)}."
        )
    return [dict(row) for row in rows]


def _fetch_match_rows(conn, config: WorldCupEditionConfig) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            WITH fj_team_map AS (
              SELECT DISTINCT team_id, team_name, team_code
              FROM bronze.fjelstul_wc_group_standings
              WHERE edition_key = :edition_key
            ),
            fj AS (
              SELECT
                m.match_id AS fjelstul_match_id,
                m.match_date,
                m.stage_name AS fjelstul_stage_name,
                m.group_name,
                m.home_team_id AS fjelstul_home_team_id,
                m.away_team_id AS fjelstul_away_team_id,
                h.team_name AS home_team_name,
                h.team_code AS home_team_code,
                a.team_name AS away_team_name,
                a.team_code AS away_team_code
              FROM bronze.fjelstul_wc_matches m
              JOIN fj_team_map h ON m.home_team_id = h.team_id
              JOIN fj_team_map a ON m.away_team_id = a.team_id
              WHERE m.edition_key = :edition_key
            ),
            sb AS (
              SELECT
                match_id::text AS statsbomb_match_id,
                payload->>'match_date' AS match_date,
                (payload->'home_team'->>'home_team_id')::text AS statsbomb_home_team_id,
                (payload->'away_team'->>'away_team_id')::text AS statsbomb_away_team_id,
                payload->'competition_stage'->>'name' AS statsbomb_stage_name,
                payload->'home_team'->>'home_team_name' AS home_team_name,
                payload->'away_team'->>'away_team_name' AS away_team_name
              FROM bronze.statsbomb_wc_matches
              WHERE edition_key = :edition_key
            )
            SELECT
              sb.statsbomb_match_id,
              sb.statsbomb_home_team_id,
              sb.statsbomb_away_team_id,
              sb.statsbomb_stage_name,
              fj.fjelstul_match_id,
              fj.fjelstul_home_team_id,
              fj.fjelstul_away_team_id,
              fj.fjelstul_stage_name,
              fj.group_name,
              fj.home_team_code,
              fj.away_team_code,
              sb.match_date
            FROM sb
            JOIN fj
              ON sb.match_date = fj.match_date
             AND lower(sb.home_team_name) = lower(fj.home_team_name)
             AND lower(sb.away_team_name) = lower(fj.away_team_name)
            ORDER BY sb.match_date, sb.statsbomb_match_id
            """
        ),
        {"edition_key": config.edition_key},
    ).mappings().all()
    if len(rows) != config.expected_matches:
        raise RuntimeError(
            f"Match bootstrap exige {config.expected_matches} joins StatsBomb<->Fjelstul para {config.edition_key}. "
            f"Encontrei {len(rows)}."
        )
    return [dict(row) for row in rows]


def _fetch_player_rows(conn, config: WorldCupEditionConfig) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT
              (team->>'team_id')::text AS statsbomb_team_id,
              team->>'team_name' AS team_name,
              (player->>'player_id')::text AS player_id,
              player->>'player_name' AS player_name,
              player->>'player_nickname' AS player_nickname,
              player->>'jersey_number' AS jersey_number
            FROM bronze.statsbomb_wc_lineups l
            CROSS JOIN LATERAL jsonb_array_elements(l.payload) team
            CROSS JOIN LATERAL jsonb_array_elements(team->'lineup') player
            WHERE l.edition_key = :edition_key
            ORDER BY team_name, player_name, player_id
            """
        ),
        {"edition_key": config.edition_key},
    ).mappings().all()
    if not rows:
        raise RuntimeError("Nenhum player encontrado em bronze.statsbomb_wc_lineups.")
    return [dict(row) for row in rows]


def _delete_obsolete_stage_rows(conn, config: WorldCupEditionConfig) -> None:
    conn.execute(
        text(
            """
            DELETE FROM raw.provider_entity_map
            WHERE provider = :provider
              AND entity_type = 'stage'
              AND edition_key = :edition_key
              AND source_id ~ '^[0-9]+$'
            """
        ),
        {"provider": STATSBOMB_SOURCE, "edition_key": config.edition_key},
    )


def _fetch_existing_historical_fjelstul_map(conn) -> dict[tuple[str, str, str], str]:
    rows = conn.execute(
        text(
            """
            SELECT provider, entity_type, source_id, canonical_id
            FROM raw.provider_entity_map
            WHERE provider = :provider
              AND entity_type IN ('team', 'match', 'stage', 'group', 'player')
              AND (
                edition_key IS NULL
                OR edition_key LIKE :edition_pattern
              )
            """
        ),
        {
            "provider": FJELSTUL_SOURCE,
            "edition_pattern": HISTORICAL_WORLD_CUP_EDITION_PATTERN,
        },
    ).mappings().all()
    return {(row["provider"], row["entity_type"], row["source_id"]): row["canonical_id"] for row in rows}


def _validate_historical_fjelstul_backbone_bronze(conn) -> None:
    checks = {
        "fjelstul_matches": (
            """
            SELECT count(DISTINCT edition_key) AS edition_count, count(*) AS row_count
            FROM bronze.fjelstul_wc_matches
            WHERE edition_key LIKE :edition_pattern
            """,
            (22, HISTORICAL_MATCH_ROW_COUNT),
        ),
        "fjelstul_stages": (
            """
            SELECT count(DISTINCT edition_key) AS edition_count, count(*) AS row_count
            FROM bronze.fjelstul_wc_tournament_stages
            WHERE edition_key LIKE :edition_pattern
            """,
            (22, HISTORICAL_STAGE_ROW_COUNT),
        ),
        "fjelstul_groups": (
            """
            SELECT count(DISTINCT edition_key) AS edition_count, count(*) AS row_count
            FROM bronze.fjelstul_wc_groups
            WHERE edition_key LIKE :edition_pattern
            """,
            (HISTORICAL_GROUP_ROW_EDITION_COUNT, 125),
        ),
        "fjelstul_managers": (
            """
            SELECT count(DISTINCT edition_key) AS edition_count, count(*) AS row_count
            FROM bronze.fjelstul_wc_manager_appointments
            WHERE edition_key LIKE :edition_pattern
            """,
            (22, 501),
        ),
        "fjelstul_squads": (
            """
            SELECT count(DISTINCT edition_key) AS edition_count, count(*) AS row_count
            FROM bronze.fjelstul_wc_squads
            WHERE edition_key LIKE :edition_pattern
            """,
            (22, 10973),
        ),
    }
    for name, (sql, expected) in checks.items():
        row = conn.execute(
            text(sql),
            {"edition_pattern": HISTORICAL_WORLD_CUP_EDITION_PATTERN},
        ).mappings().one()
        actual = (row["edition_count"], row["row_count"])
        if actual != expected:
            raise RuntimeError(
                f"Precondicao do bronze historico invalida para {name}: esperado={expected} atual={actual}"
            )


def _fetch_historical_team_rows(conn) -> list[dict[str, Any]]:
    collision_rows = conn.execute(
        text(
            """
            WITH refs AS (
              SELECT team_id, team_code
              FROM bronze.fjelstul_wc_group_standings
              WHERE edition_key LIKE :edition_pattern
              UNION ALL
              SELECT team_id, team_code
              FROM bronze.fjelstul_wc_manager_appointments
              WHERE edition_key LIKE :edition_pattern
              UNION ALL
              SELECT team_id, team_code
              FROM bronze.fjelstul_wc_squads
              WHERE edition_key LIKE :edition_pattern
            )
            SELECT
              team_code,
              string_agg(DISTINCT team_id, '|' ORDER BY team_id) AS team_ids
            FROM refs
            WHERE team_code IS NOT NULL
            GROUP BY team_code
            HAVING count(DISTINCT team_id) > 1
            ORDER BY team_code
            """
        ),
        {"edition_pattern": HISTORICAL_WORLD_CUP_EDITION_PATTERN},
    ).mappings().all()
    actual_collisions = {
        row["team_code"]: set(str(row["team_ids"]).split("|"))
        for row in collision_rows
    }
    if actual_collisions != ALLOWED_HISTORICAL_TEAM_CODE_COLLISIONS:
        raise RuntimeError(
            f"Colisoes de team_code historico fora do dicionario esperado: {actual_collisions}"
        )

    rows = conn.execute(
        text(
            """
            WITH refs AS (
              SELECT team_id, team_code, team_name, source_version
              FROM bronze.fjelstul_wc_group_standings
              WHERE edition_key LIKE :edition_pattern
              UNION ALL
              SELECT team_id, team_code, team_name, source_version
              FROM bronze.fjelstul_wc_manager_appointments
              WHERE edition_key LIKE :edition_pattern
              UNION ALL
              SELECT team_id, team_code, team_name, source_version
              FROM bronze.fjelstul_wc_squads
              WHERE edition_key LIKE :edition_pattern
            )
            SELECT
              team_id,
              min(team_code) AS team_code,
              min(team_name) AS team_name,
              min(source_version) AS source_version,
              count(DISTINCT team_code) AS team_code_count
            FROM refs
            GROUP BY team_id
            ORDER BY min(team_code), team_id
            """
        ),
        {"edition_pattern": HISTORICAL_WORLD_CUP_EDITION_PATTERN},
    ).mappings().all()
    if len(rows) != HISTORICAL_TEAM_COUNT:
        raise RuntimeError(
            f"Team backbone historico exige {HISTORICAL_TEAM_COUNT} selecoes. Encontrei {len(rows)}."
        )
    for row in rows:
        if row["team_code_count"] != 1 or not row["team_code"]:
            raise RuntimeError(
                f"Selecao historica sem team_code estavel: team_id={row['team_id']} row={dict(row)}"
            )
    return [dict(row) for row in rows]


def _fetch_historical_stage_rows(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT edition_key, source_version, tournament_id, stage_name
            FROM bronze.fjelstul_wc_tournament_stages
            WHERE edition_key LIKE :edition_pattern
            ORDER BY edition_key, stage_name
            """
        ),
        {"edition_pattern": HISTORICAL_WORLD_CUP_EDITION_PATTERN},
    ).mappings().all()
    if len(rows) != HISTORICAL_STAGE_ROW_COUNT:
        raise RuntimeError(
            f"Stage backbone historico exige {HISTORICAL_STAGE_ROW_COUNT} rows. Encontrei {len(rows)}."
        )
    return [dict(row) for row in rows]


def _fetch_historical_group_rows(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT edition_key, source_version, tournament_id, stage_name, group_name
            FROM bronze.fjelstul_wc_groups
            WHERE edition_key LIKE :edition_pattern
            ORDER BY edition_key, stage_name, group_name
            """
        ),
        {"edition_pattern": HISTORICAL_WORLD_CUP_EDITION_PATTERN},
    ).mappings().all()
    if len(rows) != 125:
        raise RuntimeError(f"Group backbone historico exige 125 rows. Encontrei {len(rows)}.")
    return [dict(row) for row in rows]


def _fetch_historical_match_rows(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT edition_key, source_version, tournament_id, match_id, match_date, stage_name, group_name
            FROM bronze.fjelstul_wc_matches
            WHERE edition_key LIKE :edition_pattern
            ORDER BY edition_key, match_date, match_id
            """
        ),
        {"edition_pattern": HISTORICAL_WORLD_CUP_EDITION_PATTERN},
    ).mappings().all()
    if len(rows) != HISTORICAL_MATCH_ROW_COUNT:
        raise RuntimeError(
            f"Match backbone historico exige {HISTORICAL_MATCH_ROW_COUNT} rows. Encontrei {len(rows)}."
        )
    return [dict(row) for row in rows]


def _fetch_historical_player_rows(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            WITH refs AS (
              SELECT player_id, given_name, family_name, source_version
              FROM bronze.fjelstul_wc_squads
              WHERE edition_key LIKE :edition_pattern
              UNION ALL
              SELECT player_id, given_name, family_name, source_version
              FROM bronze.fjelstul_wc_player_appearances
              WHERE edition_key LIKE :edition_pattern
              UNION ALL
              SELECT
                player_id,
                payload->>'given_name' AS given_name,
                payload->>'family_name' AS family_name,
                source_version
              FROM bronze.fjelstul_wc_goals
              WHERE edition_key LIKE :edition_pattern
              UNION ALL
              SELECT
                player_id,
                payload->>'given_name' AS given_name,
                payload->>'family_name' AS family_name,
                source_version
              FROM bronze.fjelstul_wc_bookings
              WHERE edition_key LIKE :edition_pattern
              UNION ALL
              SELECT
                player_id,
                payload->>'given_name' AS given_name,
                payload->>'family_name' AS family_name,
                source_version
              FROM bronze.fjelstul_wc_substitutions
              WHERE edition_key LIKE :edition_pattern
            )
            SELECT
              player_id,
              min(source_version) AS source_version,
              min(NULLIF(given_name, '')) AS given_name,
              min(NULLIF(family_name, '')) AS family_name
            FROM refs
            WHERE player_id IS NOT NULL
            GROUP BY player_id
            ORDER BY player_id
            """
        ),
        {"edition_pattern": HISTORICAL_WORLD_CUP_EDITION_PATTERN},
    ).mappings().all()
    if not rows:
        raise RuntimeError("Nenhum player historico Fjelstul encontrado para bootstrap source-scoped.")
    return [dict(row) for row in rows]


def _upsert_provider_entity_map(conn, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    conn.execute(
        text(
            """
            INSERT INTO raw.provider_entity_map (
              provider, entity_type, source_id, canonical_id, edition_key, source_version,
              mapping_confidence, resolution_method, needs_manual_review, review_reason,
              is_active, team_type, updated_at
            ) VALUES (
              :provider, :entity_type, :source_id, :canonical_id, :edition_key, :source_version,
              :mapping_confidence, :resolution_method, :needs_manual_review, :review_reason,
              :is_active, :team_type, :updated_at
            )
            ON CONFLICT (provider, entity_type, source_id)
            DO UPDATE SET
              canonical_id = EXCLUDED.canonical_id,
              edition_key = EXCLUDED.edition_key,
              source_version = EXCLUDED.source_version,
              mapping_confidence = EXCLUDED.mapping_confidence,
              resolution_method = EXCLUDED.resolution_method,
              needs_manual_review = EXCLUDED.needs_manual_review,
              review_reason = EXCLUDED.review_reason,
              is_active = EXCLUDED.is_active,
              team_type = EXCLUDED.team_type,
              updated_at = EXCLUDED.updated_at
            """
        ),
        rows,
    )


def bootstrap_world_cup_historical_backbone_identity_map() -> dict[str, Any]:
    context = get_current_context()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    now = _utc_now()

    with StepMetrics(
        service="airflow",
        module="world_cup_identity_bootstrap_service",
        step="bootstrap_world_cup_historical_backbone_identity_map",
        context=context,
        dataset="raw.provider_entity_map",
        table="raw.provider_entity_map",
    ):
        with engine.begin() as conn:
            _validate_historical_fjelstul_backbone_bronze(conn)
            existing_map = _fetch_existing_historical_fjelstul_map(conn)
            team_rows = _fetch_historical_team_rows(conn)
            stage_rows = _fetch_historical_stage_rows(conn)
            group_rows = _fetch_historical_group_rows(conn)
            match_rows = _fetch_historical_match_rows(conn)

            provider_rows: list[dict[str, Any]] = []

            for row in team_rows:
                canonical_id = (
                    existing_map.get((FJELSTUL_SOURCE, "team", row["team_id"]))
                    or _historical_team_internal_id(row["team_id"], row["team_code"])
                )
                provider_rows.append(
                    {
                        "provider": FJELSTUL_SOURCE,
                        "entity_type": "team",
                        "source_id": row["team_id"],
                        "canonical_id": canonical_id,
                        "edition_key": None,
                        "source_version": row["source_version"],
                        "mapping_confidence": "high",
                        "resolution_method": "historical_team_code_backbone",
                        "needs_manual_review": False,
                        "review_reason": None,
                        "is_active": True,
                        "team_type": WORLD_CUP_TEAM_TYPE,
                        "updated_at": now,
                    }
                )

            for row in stage_rows:
                stage_key = FJELSTUL_STAGE_KEY_MAP.get(row["stage_name"])
                if stage_key is None:
                    raise RuntimeError(f"Stage historico Fjelstul sem mapeamento canonico: {row['stage_name']}")
                source_id = f"{row['tournament_id']}::stage::{row['stage_name']}"
                canonical_id = existing_map.get((FJELSTUL_SOURCE, "stage", source_id)) or _stage_internal_id(
                    stage_key,
                    row["edition_key"],
                )
                provider_rows.append(
                    {
                        "provider": FJELSTUL_SOURCE,
                        "entity_type": "stage",
                        "source_id": source_id,
                        "canonical_id": canonical_id,
                        "edition_key": row["edition_key"],
                        "source_version": row["source_version"],
                        "mapping_confidence": "high",
                        "resolution_method": "historical_stage_mapping",
                        "needs_manual_review": False,
                        "review_reason": None,
                        "is_active": True,
                        "team_type": None,
                        "updated_at": now,
                    }
                )

            for row in group_rows:
                stage_key = FJELSTUL_STAGE_KEY_MAP.get(row["stage_name"])
                if stage_key is None:
                    raise RuntimeError(f"Group historico com stage sem mapeamento canonico: {row['stage_name']}")
                source_id = f"{row['tournament_id']}::group::{row['stage_name']}::{row['group_name']}"
                canonical_id = existing_map.get((FJELSTUL_SOURCE, "group", source_id)) or _group_internal_id(
                    stage_key,
                    _require_group_code(row["group_name"]),
                    row["edition_key"],
                )
                provider_rows.append(
                    {
                        "provider": FJELSTUL_SOURCE,
                        "entity_type": "group",
                        "source_id": source_id,
                        "canonical_id": canonical_id,
                        "edition_key": row["edition_key"],
                        "source_version": row["source_version"],
                        "mapping_confidence": "high",
                        "resolution_method": "historical_group_mapping",
                        "needs_manual_review": False,
                        "review_reason": None,
                        "is_active": True,
                        "team_type": None,
                        "updated_at": now,
                    }
                )

            for row in match_rows:
                canonical_id = existing_map.get((FJELSTUL_SOURCE, "match", row["match_id"])) or _match_internal_id()
                provider_rows.append(
                    {
                        "provider": FJELSTUL_SOURCE,
                        "entity_type": "match",
                        "source_id": row["match_id"],
                        "canonical_id": canonical_id,
                        "edition_key": row["edition_key"],
                        "source_version": row["source_version"],
                        "mapping_confidence": "high",
                        "resolution_method": "historical_fjelstul_match_id_backbone",
                        "needs_manual_review": False,
                        "review_reason": None,
                        "is_active": True,
                        "team_type": None,
                        "updated_at": now,
                    }
                )

            _upsert_provider_entity_map(conn, provider_rows)

            summary = {
                "team_rows_upserted": sum(1 for row in provider_rows if row["entity_type"] == "team"),
                "match_rows_upserted": sum(1 for row in provider_rows if row["entity_type"] == "match"),
                "stage_rows_upserted": sum(1 for row in provider_rows if row["entity_type"] == "stage"),
                "group_rows_upserted": sum(1 for row in provider_rows if row["entity_type"] == "group"),
                "distinct_team_ids": len({row["canonical_id"] for row in provider_rows if row["entity_type"] == "team"}),
                "editions_with_matches": len({row["edition_key"] for row in provider_rows if row["entity_type"] == "match"}),
                "editions_with_stages": len({row["edition_key"] for row in provider_rows if row["entity_type"] == "stage"}),
                "editions_with_groups": len({row["edition_key"] for row in provider_rows if row["entity_type"] == "group"}),
            }

    log_event(
        service="airflow",
        module="world_cup_identity_bootstrap_service",
        step="summary",
        status="success",
        context=context,
        dataset="raw.provider_entity_map",
        row_count=(
            summary["team_rows_upserted"]
            + summary["match_rows_upserted"]
            + summary["stage_rows_upserted"]
            + summary["group_rows_upserted"]
        ),
        message=(
            "Bootstrap historico World Cup concluido | "
            f"team_rows={summary['team_rows_upserted']} | "
            f"match_rows={summary['match_rows_upserted']} | "
            f"stage_rows={summary['stage_rows_upserted']} | "
            f"group_rows={summary['group_rows_upserted']} | "
            f"distinct_team_ids={summary['distinct_team_ids']} | "
            f"match_editions={summary['editions_with_matches']} | "
            f"stage_editions={summary['editions_with_stages']} | "
            f"group_editions={summary['editions_with_groups']}"
        ),
    )
    return summary


def bootstrap_world_cup_historical_player_identity_map() -> dict[str, Any]:
    context = get_current_context()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    now = _utc_now()

    with StepMetrics(
        service="airflow",
        module="world_cup_identity_bootstrap_service",
        step="bootstrap_world_cup_historical_player_identity_map",
        context=context,
        dataset="raw.provider_entity_map",
        table="raw.provider_entity_map",
    ):
        with engine.begin() as conn:
            _validate_historical_fjelstul_backbone_bronze(conn)
            existing_map = _fetch_existing_historical_fjelstul_map(conn)
            player_rows = _fetch_historical_player_rows(conn)

            provider_rows: list[dict[str, Any]] = []
            for row in player_rows:
                canonical_id = existing_map.get((FJELSTUL_SOURCE, "player", row["player_id"])) or _player_internal_id()
                provider_rows.append(
                    {
                        "provider": FJELSTUL_SOURCE,
                        "entity_type": "player",
                        "source_id": row["player_id"],
                        "canonical_id": canonical_id,
                        "edition_key": None,
                        "source_version": row["source_version"],
                        "mapping_confidence": "high",
                        "resolution_method": "historical_fjelstul_player_id_source_scoped",
                        "needs_manual_review": False,
                        "review_reason": None,
                        "is_active": True,
                        "team_type": None,
                        "updated_at": now,
                    }
                )

            _upsert_provider_entity_map(conn, provider_rows)

            summary = {
                "player_rows_upserted": len(provider_rows),
                "distinct_player_ids": len({row["canonical_id"] for row in provider_rows}),
            }

    log_event(
        service="airflow",
        module="world_cup_identity_bootstrap_service",
        step="summary",
        status="success",
        context=context,
        dataset="raw.provider_entity_map",
        row_count=summary["player_rows_upserted"],
        message=(
            "Bootstrap historico World Cup players concluido | "
            f"player_rows={summary['player_rows_upserted']} | "
            f"distinct_player_ids={summary['distinct_player_ids']}"
        ),
    )
    return summary


def _upsert_review_queue(conn, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    conn.execute(
        text(
            """
            INSERT INTO control.wc_entity_match_review_queue (
              entity_type, edition_key, source_name, source_external_id, candidate_internal_id,
              confidence_level, review_reason, candidate_payload, review_status
            ) VALUES (
              :entity_type, :edition_key, :source_name, :source_external_id, :candidate_internal_id,
              :confidence_level, :review_reason, CAST(:candidate_payload AS jsonb), :review_status
            )
            ON CONFLICT (
              entity_type, source_name, source_external_id, COALESCE(edition_key, 'GLOBAL')
            )
            DO UPDATE SET
              candidate_internal_id = EXCLUDED.candidate_internal_id,
              confidence_level = EXCLUDED.confidence_level,
              review_reason = EXCLUDED.review_reason,
              candidate_payload = EXCLUDED.candidate_payload,
              review_status = EXCLUDED.review_status
            """
        ),
        rows,
    )


def bootstrap_world_cup_identity_map(edition_key: str | None = None) -> dict[str, Any]:
    context = get_current_context()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    now = _utc_now()
    config = (
        get_world_cup_edition_config(edition_key)
        if edition_key
        else get_world_cup_edition_config_from_context(default=DEFAULT_WORLD_CUP_EDITION_KEY)
    )

    with StepMetrics(
        service="airflow",
        module="world_cup_identity_bootstrap_service",
        step="bootstrap_world_cup_identity_map",
        context=context,
        dataset="raw.provider_entity_map",
        table="raw.provider_entity_map",
    ):
        snapshots = fetch_active_world_cup_snapshots(engine, edition_key=config.edition_key)
        with engine.begin() as conn:
            _validate_bronze_counts(conn, config)
            _validate_bronze_snapshot_versions(conn, snapshots, config)
            _delete_obsolete_stage_rows(conn, config)
            existing_map = _fetch_existing_map(conn, config)
            team_rows = _fetch_team_rows(conn, config)
            statsbomb_stage_rows, fjelstul_stage_rows = _fetch_stage_rows(conn, config)
            group_rows = _fetch_group_rows(conn, config)
            match_rows = _fetch_match_rows(conn, config)
            player_rows = _fetch_player_rows(conn, config)

            provider_rows: list[dict[str, Any]] = []
            review_rows: list[dict[str, Any]] = []
            team_internal_by_statsbomb_id: dict[str, str] = {}
            player_confidence_counts = {"exact": 0, "high": 0, "medium": 0, "low": 0}

            for row in team_rows:
                canonical_id = _team_internal_id(row["team_code"])
                team_internal_by_statsbomb_id[row["statsbomb_team_id"]] = canonical_id
                provider_rows.extend(
                    [
                        {
                            "provider": STATSBOMB_SOURCE,
                            "entity_type": "team",
                            "source_id": row["statsbomb_team_id"],
                            "canonical_id": canonical_id,
                            "edition_key": None,
                            "source_version": snapshots[STATSBOMB_SOURCE]["source_version"],
                            "mapping_confidence": "high",
                            "resolution_method": "team_name_to_team_code_match",
                            "needs_manual_review": False,
                            "review_reason": None,
                            "is_active": True,
                            "team_type": WORLD_CUP_TEAM_TYPE,
                            "updated_at": now,
                        },
                        {
                            "provider": FJELSTUL_SOURCE,
                            "entity_type": "team",
                            "source_id": row["fjelstul_team_id"],
                            "canonical_id": canonical_id,
                            "edition_key": None,
                            "source_version": snapshots[FJELSTUL_SOURCE]["source_version"],
                            "mapping_confidence": "high",
                            "resolution_method": "team_name_to_team_code_match",
                            "needs_manual_review": False,
                            "review_reason": None,
                            "is_active": True,
                            "team_type": WORLD_CUP_TEAM_TYPE,
                            "updated_at": now,
                        },
                    ]
                )

            for row in statsbomb_stage_rows:
                stage_key = STATSBOMB_STAGE_KEY_MAP.get(row["stage_name"])
                if stage_key is None:
                    raise RuntimeError(f"Stage StatsBomb sem mapeamento canonico: {row['stage_name']}")
                provider_rows.append(
                    {
                        "provider": STATSBOMB_SOURCE,
                        "entity_type": "stage",
                        "source_id": statsbomb_stage_source_id(config, row["source_id"]),
                        "canonical_id": _stage_internal_id(stage_key, config.edition_key),
                        "edition_key": config.edition_key,
                        "source_version": snapshots[STATSBOMB_SOURCE]["source_version"],
                        "mapping_confidence": "high",
                        "resolution_method": "canonical_stage_mapping",
                        "needs_manual_review": False,
                        "review_reason": None,
                        "is_active": True,
                        "team_type": None,
                        "updated_at": now,
                    }
                )

            for row in fjelstul_stage_rows:
                stage_key = FJELSTUL_STAGE_KEY_MAP.get(row["stage_name"])
                if stage_key is None:
                    raise RuntimeError(f"Stage Fjelstul sem mapeamento canonico: {row['stage_name']}")
                provider_rows.append(
                    {
                        "provider": FJELSTUL_SOURCE,
                        "entity_type": "stage",
                        "source_id": fjelstul_stage_source_id(config, row["stage_name"]),
                        "canonical_id": _stage_internal_id(stage_key, config.edition_key),
                        "edition_key": config.edition_key,
                        "source_version": snapshots[FJELSTUL_SOURCE]["source_version"],
                        "mapping_confidence": "high",
                        "resolution_method": "canonical_stage_mapping",
                        "needs_manual_review": False,
                        "review_reason": None,
                        "is_active": True,
                        "team_type": None,
                        "updated_at": now,
                    }
                )

            for row in group_rows:
                stage_key = FJELSTUL_STAGE_KEY_MAP.get(row["stage_name"])
                if stage_key is None:
                    raise RuntimeError(f"Group com stage sem mapeamento canonico: {row['stage_name']}")
                provider_rows.append(
                    {
                        "provider": FJELSTUL_SOURCE,
                        "entity_type": "group",
                        "source_id": fjelstul_group_source_id(config, row["stage_name"], row["group_name"]),
                        "canonical_id": _group_internal_id(
                            stage_key,
                            _require_group_code(row["group_name"]),
                            config.edition_key,
                        ),
                        "edition_key": config.edition_key,
                        "source_version": snapshots[FJELSTUL_SOURCE]["source_version"],
                        "mapping_confidence": "high",
                        "resolution_method": "canonical_group_mapping",
                        "needs_manual_review": False,
                        "review_reason": None,
                        "is_active": True,
                        "team_type": None,
                        "updated_at": now,
                    }
                )

            match_cluster_ids: dict[tuple[str, str, str], str] = {}
            for row in match_rows:
                match_key = (row["match_date"], row["home_team_code"], row["away_team_code"])
                canonical_id = (
                    match_cluster_ids.get(match_key)
                    or existing_map.get((STATSBOMB_SOURCE, "match", row["statsbomb_match_id"]))
                    or existing_map.get((FJELSTUL_SOURCE, "match", row["fjelstul_match_id"]))
                    or _match_internal_id()
                )
                match_cluster_ids[match_key] = canonical_id
                provider_rows.extend(
                    [
                        {
                            "provider": STATSBOMB_SOURCE,
                            "entity_type": "match",
                            "source_id": row["statsbomb_match_id"],
                            "canonical_id": canonical_id,
                            "edition_key": config.edition_key,
                            "source_version": snapshots[STATSBOMB_SOURCE]["source_version"],
                            "mapping_confidence": "high",
                            "resolution_method": "date_teams_match",
                            "needs_manual_review": False,
                            "review_reason": None,
                            "is_active": True,
                            "team_type": None,
                            "updated_at": now,
                        },
                        {
                            "provider": FJELSTUL_SOURCE,
                            "entity_type": "match",
                            "source_id": row["fjelstul_match_id"],
                            "canonical_id": canonical_id,
                            "edition_key": config.edition_key,
                            "source_version": snapshots[FJELSTUL_SOURCE]["source_version"],
                            "mapping_confidence": "high",
                            "resolution_method": "date_teams_match",
                            "needs_manual_review": False,
                            "review_reason": None,
                            "is_active": True,
                            "team_type": None,
                            "updated_at": now,
                        },
                    ]
                )

            for row in player_rows:
                if not row["player_id"]:
                    confidence = "low"
                    review_reason = "statsbomb_player_id_missing"
                elif row["statsbomb_team_id"] not in team_internal_by_statsbomb_id:
                    confidence = "medium"
                    review_reason = "statsbomb_team_not_mapped"
                else:
                    confidence = "exact"
                    review_reason = None
                player_confidence_counts[confidence] += 1

                if confidence in {"exact", "high"}:
                    canonical_id = existing_map.get((STATSBOMB_SOURCE, "player", row["player_id"])) or _player_internal_id()
                    provider_rows.append(
                        {
                            "provider": STATSBOMB_SOURCE,
                            "entity_type": "player",
                            "source_id": row["player_id"],
                            "canonical_id": canonical_id,
                            "edition_key": config.edition_key,
                            "source_version": snapshots[STATSBOMB_SOURCE]["source_version"],
                            "mapping_confidence": confidence,
                            "resolution_method": "source_id_exact",
                            "needs_manual_review": False,
                            "review_reason": None,
                            "is_active": True,
                            "team_type": None,
                            "updated_at": now,
                        }
                    )
                else:
                    review_rows.append(
                        {
                            "entity_type": "player",
                            "edition_key": config.edition_key,
                            "source_name": STATSBOMB_SOURCE,
                            "source_external_id": row["player_id"] or f"missing::{row['team_name']}::{row['player_name']}",
                            "candidate_internal_id": None,
                            "confidence_level": confidence,
                            "review_reason": review_reason,
                            "candidate_payload": json.dumps(
                                {
                                    "team_name": row["team_name"],
                                    "statsbomb_team_id": row["statsbomb_team_id"],
                                    "player_name": row["player_name"],
                                    "player_nickname": row["player_nickname"],
                                    "jersey_number": row["jersey_number"],
                                },
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                            "review_status": "pending",
                        }
                    )

            if any(row["entity_type"] == "player" and row["mapping_confidence"] == "low" for row in provider_rows):
                raise RuntimeError("Existem players low auto-homologados, o que viola o contrato do Bloco 4.")

            _upsert_provider_entity_map(conn, provider_rows)
            _upsert_review_queue(conn, review_rows)

            summary = {
                "team_rows_upserted": sum(1 for row in provider_rows if row["entity_type"] == "team"),
                "match_rows_upserted": sum(1 for row in provider_rows if row["entity_type"] == "match"),
                "stage_rows_upserted": sum(1 for row in provider_rows if row["entity_type"] == "stage"),
                "group_rows_upserted": sum(1 for row in provider_rows if row["entity_type"] == "group"),
                "player_rows_homologated": sum(1 for row in provider_rows if row["entity_type"] == "player"),
                "player_review_rows_upserted": len(review_rows),
                "player_exact": player_confidence_counts["exact"],
                "player_high": player_confidence_counts["high"],
                "player_medium": player_confidence_counts["medium"],
                "player_low": player_confidence_counts["low"],
                "distinct_matches": len(match_cluster_ids),
            }

    log_event(
        service="airflow",
        module="world_cup_identity_bootstrap_service",
        step="summary",
        status="success",
        context=context,
        dataset="raw.provider_entity_map",
        row_count=(
            summary["team_rows_upserted"]
            + summary["match_rows_upserted"]
            + summary["stage_rows_upserted"]
            + summary["group_rows_upserted"]
            + summary["player_rows_homologated"]
            + summary["player_review_rows_upserted"]
        ),
        message=(
            "Bootstrap World Cup concluido | "
            f"edition={config.edition_key} | "
            f"team_rows={summary['team_rows_upserted']} | "
            f"match_rows={summary['match_rows_upserted']} | "
            f"stage_rows={summary['stage_rows_upserted']} | "
            f"group_rows={summary['group_rows_upserted']} | "
            f"player_homologated={summary['player_rows_homologated']} | "
            f"player_review_rows={summary['player_review_rows_upserted']} | "
            f"player_exact={summary['player_exact']} | "
            f"player_medium={summary['player_medium']} | "
            f"player_low={summary['player_low']}"
        ),
    )
    return summary


def bootstrap_world_cup_2022_identity_map() -> dict[str, Any]:
    return bootstrap_world_cup_identity_map(DEFAULT_WORLD_CUP_EDITION_KEY)
