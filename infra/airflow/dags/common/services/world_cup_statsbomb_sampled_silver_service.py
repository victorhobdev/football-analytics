from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from airflow.operators.python import get_current_context
from sqlalchemy import bindparam, create_engine, text

from common.observability import StepMetrics, log_event
from common.services.world_cup_config import (
    STATSBOMB_SOURCE,
    WORLD_CUP_COMPETITION_KEY,
    get_world_cup_statsbomb_sampled_edition_configs,
)
from common.services.world_cup_statsbomb_sampled_bronze_service import (
    EXPECTED_EVENT_ROWS,
    EXPECTED_LINEUP_ROWS,
)

FIXTURE_ID_BASE = 7_020_000_000_000_000_000
HASH_MOD = 1_000_000_000_000_000
TEAM_NAME_ALIASES = {
    "germany": "west germany",
    "german dr": "east germany",
}

DELETE_LINEUPS_SQL = text(
    """
    DELETE FROM silver.wc_lineups
    WHERE source_name = :source_name
      AND edition_key IN :edition_keys
    """
).bindparams(bindparam("edition_keys", expanding=True))

DELETE_EVENTS_SQL = text(
    """
    DELETE FROM silver.wc_match_events
    WHERE source_name = :source_name
      AND edition_key IN :edition_keys
    """
).bindparams(bindparam("edition_keys", expanding=True))

DELETE_COVERAGE_SQL = text(
    """
    DELETE FROM silver.wc_coverage_manifest
    WHERE source_name = :source_name
      AND coverage_status = 'PARTIAL_MATCH_SAMPLE'
      AND domain_name IN ('lineups', 'match_events')
      AND edition_key IN :edition_keys
    """
).bindparams(bindparam("edition_keys", expanding=True))

INSERT_LINEUP_SQL = text(
    """
    INSERT INTO silver.wc_lineups (
      edition_key, internal_match_id, team_internal_id, player_internal_id, source_name, source_version,
      source_match_id, source_team_id, source_player_id, team_name, player_name, player_nickname,
      jersey_number, is_starter, start_reason, first_position_name, first_position_id, payload, materialized_at
    ) VALUES (
      :edition_key, :internal_match_id, :team_internal_id, :player_internal_id, :source_name, :source_version,
      :source_match_id, :source_team_id, :source_player_id, :team_name, :player_name, :player_nickname,
      :jersey_number, :is_starter, :start_reason, :first_position_name, :first_position_id, CAST(:payload AS jsonb), :materialized_at
    )
    """
)

INSERT_EVENT_SQL = text(
    """
    INSERT INTO silver.wc_match_events (
      edition_key, internal_match_id, source_name, source_version, source_match_id, source_event_id, event_index,
      team_internal_id, player_internal_id, event_type_id, event_type, period, minute, second,
      timestamp_label, possession, play_pattern, location_x, location_y, has_three_sixty_frame, payload, materialized_at
    ) VALUES (
      :edition_key, :internal_match_id, :source_name, :source_version, :source_match_id, :source_event_id, :event_index,
      :team_internal_id, :player_internal_id, :event_type_id, :event_type, :period, :minute, :second,
      :timestamp_label, :possession, :play_pattern, :location_x, :location_y, :has_three_sixty_frame, CAST(:payload AS jsonb), :materialized_at
    )
    """
)

INSERT_COVERAGE_SQL = text(
    """
    INSERT INTO silver.wc_coverage_manifest (
      edition_key, domain_name, source_name, coverage_status,
      expected_match_count, actual_match_count, expected_row_count, actual_row_count, notes, computed_at
    ) VALUES (
      :edition_key, :domain_name, :source_name, 'PARTIAL_MATCH_SAMPLE',
      :expected_match_count, :actual_match_count, :expected_row_count, :actual_row_count, :notes, :computed_at
    )
    """
)

DELETE_FJELSTUL_OVERLAP_LINEUP_SQL = text(
    """
    DELETE FROM silver.wc_lineups
    WHERE source_name = 'fjelstul_worldcup'
      AND edition_key = :edition_key
      AND internal_match_id = :internal_match_id
    """
)

DELETE_FJELSTUL_OVERLAP_EVENT_SQL = text(
    """
    DELETE FROM silver.wc_match_events
    WHERE source_name = 'fjelstul_worldcup'
      AND edition_key = :edition_key
      AND internal_match_id = :internal_match_id
    """
)

UPDATE_FJELSTUL_COVERAGE_SQL = text(
    """
    UPDATE silver.wc_coverage_manifest
    SET actual_match_count = :actual_match_count,
        actual_row_count = :actual_row_count,
        computed_at = :computed_at,
        notes = CASE
          WHEN notes LIKE '%Sampled StatsBomb sampled enrichment overrides overlapping matches at silver grain.%' THEN notes
          ELSE notes || ' Sampled StatsBomb sampled enrichment overrides overlapping matches at silver grain.'
        END
    WHERE source_name = 'fjelstul_worldcup'
      AND domain_name = :domain_name
      AND edition_key = :edition_key
    """
)


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_bigint(seed: str, *, base: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return base + (int(digest[:15], 16) % HASH_MOD)


def _norm(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().strip()
    return TEAM_NAME_ALIASES.get(normalized, normalized)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _name_variants(given_name: str | None, family_name: str | None) -> set[str]:
    given = (given_name or "").strip()
    family = (family_name or "").strip()
    variants: set[str] = set()
    full = " ".join(part for part in (given, family) if part).strip()
    if full:
        variants.add(_norm(full))
    if given and given.lower() != "not applicable":
        variants.add(_norm(given))
        variants.add(_norm(given.split()[0]))
    if family and family.lower() != "not applicable":
        variants.add(_norm(family))
        variants.add(_norm(family.split()[-1]))
    if given.lower() == "not applicable" and family:
        variants.add(_norm(family))
    if given and family and given.lower() != "not applicable" and family.lower() != "not applicable":
        variants.add(_norm(f"{given.split()[0]} {family.split()[-1]}"))
    return {item for item in variants if item}


def _load_statsbomb_bronze(conn, edition_keys: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    def _read(table_name: str):
        return conn.execute(
            text(
                f"""
                SELECT edition_key, source_version, match_id, payload
                FROM bronze.{table_name}
                WHERE edition_key IN :edition_keys
                ORDER BY edition_key, match_id
                """
            ).bindparams(bindparam("edition_keys", expanding=True)),
            {"edition_keys": edition_keys},
        ).mappings().all()

    matches = _read("statsbomb_wc_matches")
    lineups = _read("statsbomb_wc_lineups")
    events = _read("statsbomb_wc_events")
    return [dict(row) for row in matches], [dict(row) for row in lineups], [dict(row) for row in events]


def _load_fixture_backbone(conn, edition_keys: list[str]) -> dict[str, list[dict[str, Any]]]:
    silver_rows = conn.execute(
        text(
            """
            SELECT edition_key, internal_match_id, home_team_internal_id, away_team_internal_id,
                   match_date, home_team_score, away_team_score
            FROM silver.wc_fixtures
            WHERE edition_key IN :edition_keys
            ORDER BY edition_key, match_date, internal_match_id
            """
        ).bindparams(bindparam("edition_keys", expanding=True)),
        {"edition_keys": edition_keys},
    ).mappings().all()
    raw_rows = conn.execute(
        text(
            """
            SELECT fixture_id, season_label, date, home_team_name, away_team_name
            FROM raw.fixtures
            WHERE competition_key = :competition_key
              AND season_label IN :season_labels
            ORDER BY season_label, date, fixture_id
            """
        ).bindparams(bindparam("season_labels", expanding=True)),
        {
            "competition_key": WORLD_CUP_COMPETITION_KEY,
            "season_labels": [edition.rsplit("__", 1)[1] for edition in edition_keys],
        },
    ).mappings().all()
    raw_by_fixture_id = {int(row["fixture_id"]): dict(row) for row in raw_rows}
    by_edition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in silver_rows:
        fixture_id = _stable_bigint(str(row["internal_match_id"]), base=FIXTURE_ID_BASE)
        raw_row = raw_by_fixture_id.get(fixture_id)
        if raw_row is None:
            raise RuntimeError(
                f"Fixture backbone sem raw.fixtures correspondente para internal_match_id={row['internal_match_id']}"
            )
        by_edition[str(row["edition_key"])].append(
            {
                "internal_match_id": str(row["internal_match_id"]),
                "fixture_id": fixture_id,
                "home_team_internal_id": str(row["home_team_internal_id"]),
                "away_team_internal_id": str(row["away_team_internal_id"]),
                "match_date": row["match_date"],
                "home_team_score": int(row["home_team_score"]),
                "away_team_score": int(row["away_team_score"]),
                "home_team_name": str(raw_row["home_team_name"]),
                "away_team_name": str(raw_row["away_team_name"]),
            }
        )
    return by_edition


def _load_player_refs(conn, edition_keys: list[str]) -> tuple[dict[tuple[str, str, int], set[str]], dict[tuple[str, str, str], set[str]]]:
    rows = conn.execute(
        text(
            """
            WITH refs AS (
              SELECT s.edition_key,
                     tm.canonical_id AS team_internal_id,
                     pm.canonical_id AS player_internal_id,
                     s.shirt_number,
                     s.given_name,
                     s.family_name
              FROM bronze.fjelstul_wc_squads s
              JOIN raw.provider_entity_map tm
                ON tm.provider = 'fjelstul_worldcup'
               AND tm.entity_type = 'team'
               AND tm.source_id = s.team_id
              JOIN raw.provider_entity_map pm
                ON pm.provider = 'fjelstul_worldcup'
               AND pm.entity_type = 'player'
               AND pm.source_id = s.player_id
              WHERE s.edition_key IN :edition_keys
              UNION ALL
              SELECT a.edition_key,
                     tm.canonical_id AS team_internal_id,
                     pm.canonical_id AS player_internal_id,
                     a.shirt_number,
                     a.given_name,
                     a.family_name
              FROM bronze.fjelstul_wc_player_appearances a
              JOIN raw.provider_entity_map tm
                ON tm.provider = 'fjelstul_worldcup'
               AND tm.entity_type = 'team'
               AND tm.source_id = a.team_id
              JOIN raw.provider_entity_map pm
                ON pm.provider = 'fjelstul_worldcup'
               AND pm.entity_type = 'player'
               AND pm.source_id = a.player_id
              WHERE a.edition_key IN :edition_keys
            )
            SELECT edition_key, team_internal_id, player_internal_id, shirt_number, given_name, family_name
            FROM refs
            """
        ).bindparams(bindparam("edition_keys", expanding=True)),
        {"edition_keys": edition_keys},
    ).mappings().all()
    by_jersey: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    by_name: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in rows:
        edition_key = str(row["edition_key"])
        team_internal_id = str(row["team_internal_id"])
        player_internal_id = str(row["player_internal_id"])
        shirt_number = str(row["shirt_number"] or "").strip()
        if shirt_number and shirt_number != "0":
            try:
                by_jersey[(edition_key, team_internal_id, int(shirt_number))].add(player_internal_id)
            except ValueError:
                pass
        for variant in _name_variants(row["given_name"], row["family_name"]):
            by_name[(edition_key, team_internal_id, variant)].add(player_internal_id)
    return by_jersey, by_name


def _resolve_fixture_map(match_rows: list[dict[str, Any]], fixture_backbone: dict[str, list[dict[str, Any]]]) -> dict[tuple[str, str], dict[str, Any]]:
    resolved: dict[tuple[str, str], dict[str, Any]] = {}
    for row in match_rows:
        payload = row["payload"]
        edition_key = str(row["edition_key"])
        candidates: list[tuple[int, dict[str, Any]]] = []
        for fixture in fixture_backbone[edition_key]:
            if _norm(fixture["home_team_name"]) != _norm(payload["home_team"]["home_team_name"]):
                continue
            if _norm(fixture["away_team_name"]) != _norm(payload["away_team"]["away_team_name"]):
                continue
            if fixture["home_team_score"] != int(payload["home_score"]):
                continue
            if fixture["away_team_score"] != int(payload["away_score"]):
                continue
            delta_days = abs((fixture["match_date"] - datetime.fromisoformat(payload["match_date"]).date()).days)
            if delta_days <= 1:
                candidates.append((delta_days, fixture))
        candidates.sort(key=lambda item: (item[0], item[1]["fixture_id"]))
        if len(candidates) != 1:
            raise RuntimeError(
                f"Sample StatsBomb sem match deterministico no backbone para edition={edition_key} "
                f"match_id={row['match_id']} candidates={len(candidates)}"
            )
        fixture = candidates[0][1]
        resolved[(edition_key, str(row["match_id"]))] = {
            "internal_match_id": fixture["internal_match_id"],
            "fixture_id": fixture["fixture_id"],
            "source_version": str(row["source_version"]),
            "home_team_internal_id": fixture["home_team_internal_id"],
            "away_team_internal_id": fixture["away_team_internal_id"],
            "source_team_map": {
                str(payload["home_team"]["home_team_id"]): fixture["home_team_internal_id"],
                str(payload["away_team"]["away_team_id"]): fixture["away_team_internal_id"],
            },
        }
    return resolved


def _resolve_player_internal_id(
    *,
    edition_key: str,
    team_internal_id: str,
    player_payload: dict[str, Any],
    player_by_jersey: dict[tuple[str, str, int], set[str]],
    player_by_name: dict[tuple[str, str, str], set[str]],
) -> str:
    jersey_number = player_payload.get("jersey_number")
    if jersey_number is not None:
        jersey_candidates = sorted(player_by_jersey.get((edition_key, team_internal_id, int(jersey_number)), set()))
        if len(jersey_candidates) == 1:
            return jersey_candidates[0]
        if len(jersey_candidates) > 1:
            raise RuntimeError(
                f"Player sampled StatsBomb ambiguo por jersey | edition={edition_key} "
                f"team={team_internal_id} jersey={jersey_number} candidates={jersey_candidates}"
            )
    name_candidates: set[str] = set()
    for raw_value in (player_payload.get("player_nickname"), player_payload.get("player_name")):
        if raw_value:
            name_candidates.update(player_by_name.get((edition_key, team_internal_id, _norm(raw_value)), set()))
    if len(name_candidates) == 1:
        return next(iter(name_candidates))
    if len(name_candidates) > 1:
        raise RuntimeError(
            f"Player sampled StatsBomb ambiguo por nome | edition={edition_key} "
            f"team={team_internal_id} player={player_payload.get('player_name')} candidates={sorted(name_candidates)}"
        )
    raise RuntimeError(
        f"Player sampled StatsBomb sem mapeamento | edition={edition_key} "
        f"team={team_internal_id} player={player_payload.get('player_name')} jersey={player_payload.get('jersey_number')}"
    )


def _build_lineup_rows(
    lineup_rows: list[dict[str, Any]],
    fixture_map: dict[tuple[str, str], dict[str, Any]],
    player_by_jersey: dict[tuple[str, str, int], set[str]],
    player_by_name: dict[tuple[str, str, str], set[str]],
    materialized_at: datetime,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], str]]:
    silver_rows: list[dict[str, Any]] = []
    player_lookup: dict[tuple[str, str, str], str] = {}
    for row in lineup_rows:
        edition_key = str(row["edition_key"])
        source_match_id = str(row["match_id"])
        match_meta = fixture_map[(edition_key, source_match_id)]
        for team in row["payload"]:
            source_team_id = str(team["team_id"])
            team_internal_id = match_meta["source_team_map"].get(source_team_id)
            if team_internal_id is None:
                raise RuntimeError(
                    f"Team sampled StatsBomb sem resolucao local | edition={edition_key} "
                    f"match={source_match_id} team_id={source_team_id}"
                )
            for player in team.get("lineup", []):
                player_internal_id = _resolve_player_internal_id(
                    edition_key=edition_key,
                    team_internal_id=team_internal_id,
                    player_payload=player,
                    player_by_jersey=player_by_jersey,
                    player_by_name=player_by_name,
                )
                player_lookup[(edition_key, source_match_id, str(player["player_id"]))] = player_internal_id
                positions = player.get("positions") or []
                first_position = positions[0] if positions else {}
                silver_rows.append(
                    {
                        "edition_key": edition_key,
                        "internal_match_id": match_meta["internal_match_id"],
                        "team_internal_id": team_internal_id,
                        "player_internal_id": player_internal_id,
                        "source_name": STATSBOMB_SOURCE,
                        "source_version": str(row["source_version"]),
                        "source_match_id": source_match_id,
                        "source_team_id": source_team_id,
                        "source_player_id": str(player["player_id"]),
                        "team_name": team.get("team_name"),
                        "player_name": player.get("player_name"),
                        "player_nickname": player.get("player_nickname"),
                        "jersey_number": player.get("jersey_number"),
                        "is_starter": any(pos.get("start_reason") == "Starting XI" for pos in positions),
                        "start_reason": first_position.get("start_reason"),
                        "first_position_name": first_position.get("position"),
                        "first_position_id": first_position.get("position_id"),
                        "payload": _json_text(player),
                        "materialized_at": materialized_at,
                    }
                )
    return silver_rows, player_lookup


def _build_event_rows(
    event_rows: list[dict[str, Any]],
    fixture_map: dict[tuple[str, str], dict[str, Any]],
    player_lookup: dict[tuple[str, str, str], str],
    materialized_at: datetime,
) -> list[dict[str, Any]]:
    silver_rows: list[dict[str, Any]] = []
    for row in event_rows:
        edition_key = str(row["edition_key"])
        source_match_id = str(row["match_id"])
        match_meta = fixture_map[(edition_key, source_match_id)]
        for event in row["payload"]:
            team_internal_id = None
            if isinstance(event.get("team"), dict) and event["team"].get("id") is not None:
                team_internal_id = match_meta["source_team_map"].get(str(event["team"]["id"]))
            player_internal_id = None
            if isinstance(event.get("player"), dict) and event["player"].get("id") is not None:
                player_internal_id = player_lookup.get((edition_key, source_match_id, str(event["player"]["id"])))
            location = event.get("location") or []
            silver_rows.append(
                {
                    "edition_key": edition_key,
                    "internal_match_id": match_meta["internal_match_id"],
                    "source_name": STATSBOMB_SOURCE,
                    "source_version": str(row["source_version"]),
                    "source_match_id": source_match_id,
                    "source_event_id": event.get("id"),
                    "event_index": event.get("index"),
                    "team_internal_id": team_internal_id,
                    "player_internal_id": player_internal_id,
                    "event_type_id": (event.get("type") or {}).get("id"),
                    "event_type": (event.get("type") or {}).get("name"),
                    "period": event.get("period"),
                    "minute": event.get("minute"),
                    "second": event.get("second"),
                    "timestamp_label": event.get("timestamp"),
                    "possession": event.get("possession"),
                    "play_pattern": (event.get("play_pattern") or {}).get("name"),
                    "location_x": location[0] if len(location) > 0 else None,
                    "location_y": location[1] if len(location) > 1 else None,
                    "has_three_sixty_frame": False,
                    "payload": _json_text(event),
                    "materialized_at": materialized_at,
                }
            )
    return silver_rows


def _insert_in_chunks(conn, sql, rows: list[dict[str, Any]], *, chunk_size: int = 5000) -> None:
    for start in range(0, len(rows), chunk_size):
        conn.execute(sql, rows[start : start + chunk_size])


def _delete_fjelstul_lineup_overlaps(conn, silver_lineups: list[dict[str, Any]]) -> None:
    overlap_keys = sorted(
        {
            (row["edition_key"], row["internal_match_id"])
            for row in silver_lineups
        }
    )
    for edition_key, internal_match_id in overlap_keys:
        conn.execute(
            DELETE_FJELSTUL_OVERLAP_LINEUP_SQL,
            {
                "edition_key": edition_key,
                "internal_match_id": internal_match_id,
            },
        )


def _delete_fjelstul_event_overlaps(conn, silver_events: list[dict[str, Any]]) -> None:
    overlap_keys = sorted(
        {
            (row["edition_key"], row["internal_match_id"])
            for row in silver_events
        }
    )
    for edition_key, internal_match_id in overlap_keys:
        conn.execute(
            DELETE_FJELSTUL_OVERLAP_EVENT_SQL,
            {
                "edition_key": edition_key,
                "internal_match_id": internal_match_id,
            },
        )


def _refresh_fjelstul_coverage_manifest(conn, edition_keys: list[str], computed_at: datetime, *, domain_name: str) -> None:
    source_table = "silver.wc_lineups" if domain_name == "lineups" else "silver.wc_match_events"
    for edition_key in edition_keys:
        counts = conn.execute(
            text(
                f"""
                SELECT
                  count(DISTINCT internal_match_id) AS actual_match_count,
                  count(*) AS actual_row_count
                FROM {source_table}
                WHERE source_name = 'fjelstul_worldcup'
                  AND edition_key = :edition_key
                """
            ),
            {"edition_key": edition_key},
        ).mappings().one()
        conn.execute(
            UPDATE_FJELSTUL_COVERAGE_SQL,
            {
                "edition_key": edition_key,
                "domain_name": domain_name,
                "actual_match_count": int(counts["actual_match_count"] or 0),
                "actual_row_count": int(counts["actual_row_count"] or 0),
                "computed_at": computed_at,
            },
        )


def _validate_prerequisites(conn, edition_keys: list[str]) -> None:
    bronze_summary = conn.execute(
        text(
            """
            SELECT count(DISTINCT edition_key)
            FROM bronze.statsbomb_wc_matches
            WHERE edition_key IN :edition_keys
            """
        ).bindparams(bindparam("edition_keys", expanding=True)),
        {"edition_keys": edition_keys},
    ).scalar_one()
    if int(bronze_summary) != len(edition_keys):
        raise RuntimeError("Bronze sampled StatsBomb ainda nao cobre todas as edicoes esperadas.")
    fixture_summary = conn.execute(
        text(
            """
            SELECT count(DISTINCT edition_key)
            FROM silver.wc_fixtures
            WHERE edition_key IN :edition_keys
            """
        ).bindparams(bindparam("edition_keys", expanding=True)),
        {"edition_keys": edition_keys},
    ).scalar_one()
    if int(fixture_summary) != len(edition_keys):
        raise RuntimeError("Backbone silver historico ausente para alguma edicao sampled do StatsBomb.")


def _validate_outputs(conn, edition_keys: list[str]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for config in get_world_cup_statsbomb_sampled_edition_configs():
        params = {"edition_key": config.edition_key, "source_name": STATSBOMB_SOURCE}
        lineup_rows = int(
            conn.execute(
                text("SELECT count(*) FROM silver.wc_lineups WHERE source_name = :source_name AND edition_key = :edition_key"),
                params,
            ).scalar_one()
        )
        event_rows = int(
            conn.execute(
                text("SELECT count(*) FROM silver.wc_match_events WHERE source_name = :source_name AND edition_key = :edition_key"),
                params,
            ).scalar_one()
        )
        lineup_matches = int(
            conn.execute(
                text(
                    """
                    SELECT count(DISTINCT internal_match_id)
                    FROM silver.wc_lineups
                    WHERE source_name = :source_name
                      AND edition_key = :edition_key
                    """
                ),
                params,
            ).scalar_one()
        )
        event_matches = int(
            conn.execute(
                text(
                    """
                    SELECT count(DISTINCT internal_match_id)
                    FROM silver.wc_match_events
                    WHERE source_name = :source_name
                      AND edition_key = :edition_key
                    """
                ),
                params,
            ).scalar_one()
        )
        if lineup_rows != EXPECTED_LINEUP_ROWS[config.edition_key]:
            raise RuntimeError(
                f"Silver sampled invalido para {config.edition_key}: lineup_rows esperado={EXPECTED_LINEUP_ROWS[config.edition_key]} atual={lineup_rows}"
            )
        if event_rows != EXPECTED_EVENT_ROWS[config.edition_key]:
            raise RuntimeError(
                f"Silver sampled invalido para {config.edition_key}: event_rows esperado={EXPECTED_EVENT_ROWS[config.edition_key]} atual={event_rows}"
            )
        if lineup_matches != config.expected_statsbomb_lineup_match_files:
            raise RuntimeError(
                f"Silver sampled invalido para {config.edition_key}: lineup_matches esperado={config.expected_statsbomb_lineup_match_files} atual={lineup_matches}"
            )
        if event_matches != config.expected_statsbomb_event_match_files:
            raise RuntimeError(
                f"Silver sampled invalido para {config.edition_key}: event_matches esperado={config.expected_statsbomb_event_match_files} atual={event_matches}"
            )
        results[config.edition_key] = {
            "lineup_rows": lineup_rows,
            "event_rows": event_rows,
            "lineup_matches": lineup_matches,
            "event_matches": event_matches,
        }

    shared_params = {"source_name": STATSBOMB_SOURCE, "edition_keys": edition_keys}
    lineup_duplicates = int(
        conn.execute(
            text(
                """
                SELECT count(*)
                FROM (
                  SELECT edition_key, internal_match_id, team_internal_id, player_internal_id, source_name, count(*) AS row_count
                  FROM silver.wc_lineups
                  WHERE source_name = :source_name
                    AND edition_key IN :edition_keys
                  GROUP BY 1,2,3,4,5
                  HAVING count(*) > 1
                ) dup
                """
            ).bindparams(bindparam("edition_keys", expanding=True)),
            shared_params,
        ).scalar_one()
    )
    event_duplicates = int(
        conn.execute(
            text(
                """
                SELECT count(*)
                FROM (
                  SELECT source_name, source_match_id, source_event_id, count(*) AS row_count
                  FROM silver.wc_match_events
                  WHERE source_name = :source_name
                    AND edition_key IN :edition_keys
                  GROUP BY 1,2,3
                  HAVING count(*) > 1
                ) dup
                """
            ).bindparams(bindparam("edition_keys", expanding=True)),
            shared_params,
        ).scalar_one()
    )
    coverage_rows = int(
        conn.execute(
            text(
                """
                SELECT count(*)
                FROM silver.wc_coverage_manifest
                WHERE source_name = :source_name
                  AND coverage_status = 'PARTIAL_MATCH_SAMPLE'
                  AND domain_name IN ('lineups', 'match_events')
                  AND edition_key IN :edition_keys
                """
            ).bindparams(bindparam("edition_keys", expanding=True)),
            shared_params,
        ).scalar_one()
    )
    if lineup_duplicates != 0 or event_duplicates != 0:
        raise RuntimeError(f"Silver sampled com duplicidade: lineups={lineup_duplicates} events={event_duplicates}")
    if coverage_rows != len(edition_keys) * 2:
        raise RuntimeError(
            f"Silver sampled com coverage incompleto: esperado={len(edition_keys) * 2} atual={coverage_rows}"
        )
    results["lineup_duplicates"] = lineup_duplicates
    results["event_duplicates"] = event_duplicates
    results["coverage_rows"] = coverage_rows
    return results


def normalize_world_cup_statsbomb_sampled_silver() -> dict[str, Any]:
    context = get_current_context()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    now = _utc_now()
    sampled_configs = get_world_cup_statsbomb_sampled_edition_configs()
    edition_keys = [config.edition_key for config in sampled_configs]

    with StepMetrics(
        service="airflow",
        module="world_cup_statsbomb_sampled_silver_service",
        step="normalize_world_cup_statsbomb_sampled_silver",
        context=context,
        dataset="silver.world_cup_statsbomb_sampled",
        table="silver.wc_lineups/silver.wc_match_events",
    ):
        with engine.begin() as conn:
            _validate_prerequisites(conn, edition_keys)
            match_rows, lineup_rows, event_rows = _load_statsbomb_bronze(conn, edition_keys)
            fixture_backbone = _load_fixture_backbone(conn, edition_keys)
            player_by_jersey, player_by_name = _load_player_refs(conn, edition_keys)
            fixture_map = _resolve_fixture_map(match_rows, fixture_backbone)
            silver_lineups, player_lookup = _build_lineup_rows(
                lineup_rows,
                fixture_map,
                player_by_jersey,
                player_by_name,
                now,
            )
            silver_events = _build_event_rows(event_rows, fixture_map, player_lookup, now)

            conn.execute(DELETE_LINEUPS_SQL, {"source_name": STATSBOMB_SOURCE, "edition_keys": edition_keys})
            conn.execute(DELETE_EVENTS_SQL, {"source_name": STATSBOMB_SOURCE, "edition_keys": edition_keys})
            conn.execute(DELETE_COVERAGE_SQL, {"source_name": STATSBOMB_SOURCE, "edition_keys": edition_keys})
            _delete_fjelstul_lineup_overlaps(conn, silver_lineups)
            _delete_fjelstul_event_overlaps(conn, silver_events)

            _insert_in_chunks(conn, INSERT_LINEUP_SQL, silver_lineups)
            _insert_in_chunks(conn, INSERT_EVENT_SQL, silver_events)
            _refresh_fjelstul_coverage_manifest(conn, edition_keys, now, domain_name="lineups")
            _refresh_fjelstul_coverage_manifest(conn, edition_keys, now, domain_name="match_events")

            coverage_rows = []
            for config in sampled_configs:
                coverage_rows.append(
                    {
                        "edition_key": config.edition_key,
                        "domain_name": "lineups",
                        "source_name": STATSBOMB_SOURCE,
                        "expected_match_count": config.expected_statsbomb_lineup_match_files,
                        "actual_match_count": config.expected_statsbomb_lineup_match_files,
                        "expected_row_count": EXPECTED_LINEUP_ROWS[config.edition_key],
                        "actual_row_count": EXPECTED_LINEUP_ROWS[config.edition_key],
                        "notes": "StatsBomb historico sampled enrichment; nao representa cobertura completa da edicao.",
                        "computed_at": now,
                    }
                )
                coverage_rows.append(
                    {
                        "edition_key": config.edition_key,
                        "domain_name": "match_events",
                        "source_name": STATSBOMB_SOURCE,
                        "expected_match_count": config.expected_statsbomb_event_match_files,
                        "actual_match_count": config.expected_statsbomb_event_match_files,
                        "expected_row_count": EXPECTED_EVENT_ROWS[config.edition_key],
                        "actual_row_count": EXPECTED_EVENT_ROWS[config.edition_key],
                        "notes": "StatsBomb historico sampled enrichment; nao representa cobertura completa da edicao.",
                        "computed_at": now,
                    }
                )
            conn.execute(INSERT_COVERAGE_SQL, coverage_rows)
            summary = _validate_outputs(conn, edition_keys)

    log_event(
        service="airflow",
        module="world_cup_statsbomb_sampled_silver_service",
        step="summary",
        status="success",
        context=context,
        dataset="silver.world_cup_statsbomb_sampled",
        row_count=len(silver_lineups) + len(silver_events) + (len(edition_keys) * 2),
        message=(
            "Silver sampled StatsBomb da Copa materializado | "
            + " | ".join(
                f"{edition} lineups={summary[edition]['lineup_rows']} events={summary[edition]['event_rows']}"
                for edition in edition_keys
            )
        ),
    )
    return {
        "lineups_rows": len(silver_lineups),
        "event_rows": len(silver_events),
        "coverage_rows": len(edition_keys) * 2,
        "validations": summary,
    }
