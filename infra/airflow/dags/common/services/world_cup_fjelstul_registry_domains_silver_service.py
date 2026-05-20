from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.observability import StepMetrics, log_event
from common.services.world_cup_config import FJELSTUL_SOURCE

WORLD_CUP_EDITION_PATTERN = "fifa_world_cup_mens__%"
COVERAGE_DOMAINS = ("squads", "goals", "bookings", "substitutions")


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _params(materialized_at: datetime) -> dict[str, Any]:
    return {
        "edition_pattern": WORLD_CUP_EDITION_PATTERN,
        "source_name": FJELSTUL_SOURCE,
        "materialized_at": materialized_at,
    }


def _validate_prerequisites(conn) -> dict[str, int]:
    params = _params(_utc_now())
    checks = {
        "fixture_editions": """
            SELECT count(DISTINCT edition_key)
            FROM silver.wc_fixtures
            WHERE edition_key LIKE :edition_pattern
        """,
        "source_squads_rows": "SELECT count(*) FROM bronze.fjelstul_wc_squads",
        "source_goals_rows": "SELECT count(*) FROM bronze.fjelstul_wc_goals",
        "source_bookings_rows": "SELECT count(*) FROM bronze.fjelstul_wc_bookings",
        "source_substitutions_rows": "SELECT count(*) FROM bronze.fjelstul_wc_substitutions",
        "unmapped_squad_players": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_squads s
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = :source_name
             AND pm.entity_type = 'player'
             AND pm.source_id = s.player_id
            WHERE pm.canonical_id IS NULL
        """,
        "unmapped_squad_teams": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_squads s
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = :source_name
             AND pm.entity_type = 'team'
             AND pm.source_id = s.team_id
            WHERE pm.canonical_id IS NULL
        """,
        "unmapped_goal_matches": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_goals g
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = :source_name
             AND pm.entity_type = 'match'
             AND pm.source_id = g.match_id
             AND pm.edition_key = g.edition_key
            WHERE pm.canonical_id IS NULL
        """,
        "unmapped_goal_players": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_goals g
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = :source_name
             AND pm.entity_type = 'player'
             AND pm.source_id = g.player_id
            WHERE pm.canonical_id IS NULL
        """,
        "unmapped_goal_player_teams": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_goals g
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = :source_name
             AND pm.entity_type = 'team'
             AND pm.source_id = g.player_team_id
            WHERE pm.canonical_id IS NULL
        """,
        "unmapped_booking_players": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_bookings b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = :source_name
             AND pm.entity_type = 'player'
             AND pm.source_id = b.player_id
            WHERE pm.canonical_id IS NULL
        """,
        "unmapped_substitution_players": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_substitutions s
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = :source_name
             AND pm.entity_type = 'player'
             AND pm.source_id = s.player_id
            WHERE pm.canonical_id IS NULL
        """,
        "invalid_substitution_flags": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_substitutions
            WHERE (CASE WHEN going_off = '1' THEN 1 ELSE 0 END)
                + (CASE WHEN coming_on = '1' THEN 1 ELSE 0 END) <> 1
        """,
    }
    results = {name: int(conn.execute(text(sql), params).scalar_one()) for name, sql in checks.items()}
    if results["fixture_editions"] != 22:
        raise RuntimeError(f"Precondicao invalida: silver.wc_fixtures deveria cobrir 22 edicoes, atual={results['fixture_editions']}")
    for key in ("source_squads_rows", "source_goals_rows", "source_bookings_rows", "source_substitutions_rows"):
        if results[key] <= 0:
            raise RuntimeError(f"Precondicao invalida: {key} sem dados.")
    for key in (
        "unmapped_squad_players",
        "unmapped_squad_teams",
        "unmapped_goal_matches",
        "unmapped_goal_players",
        "unmapped_goal_player_teams",
        "unmapped_booking_players",
        "unmapped_substitution_players",
        "invalid_substitution_flags",
    ):
        if results[key] != 0:
            raise RuntimeError(f"Precondicao invalida para {key}: atual={results[key]}")
    return results


def _delete_previous_rows(conn) -> None:
    params = _params(_utc_now())
    for table_name in ("wc_squads", "wc_goals", "wc_bookings", "wc_substitutions"):
        conn.execute(
            text(
                f"""
                DELETE FROM silver.{table_name}
                WHERE source_name = :source_name
                """
            ),
            params,
        )
    conn.execute(
        text(
            """
            DELETE FROM silver.wc_coverage_manifest
            WHERE source_name = :source_name
              AND domain_name IN ('squads', 'goals', 'bookings', 'substitutions')
            """
        ),
        params,
    )


INSERT_SQUADS_SQL = """
INSERT INTO silver.wc_squads (
  edition_key, team_internal_id, player_internal_id, source_name, source_version, source_row_id,
  source_team_id, source_player_id, team_name, team_code, player_name, jersey_number, position_name,
  position_code, payload, materialized_at
)
SELECT
  s.edition_key,
  pm_team.canonical_id AS team_internal_id,
  pm_player.canonical_id AS player_internal_id,
  s.source_name,
  s.source_version,
  s.key_id AS source_row_id,
  s.team_id AS source_team_id,
  s.player_id AS source_player_id,
  s.team_name,
  s.team_code,
  NULLIF(trim(concat_ws(' ', NULLIF(s.given_name, ''), NULLIF(s.family_name, ''))), '') AS player_name,
  NULLIF(NULLIF(s.shirt_number, ''), '0')::integer AS jersey_number,
  NULLIF(s.position_name, '') AS position_name,
  NULLIF(s.position_code, '') AS position_code,
  jsonb_build_object(
    'dataset', 'squads',
    'coverage_tier', 'full_tournament',
    'source_payload', s.payload
  ) AS payload,
  :materialized_at
FROM bronze.fjelstul_wc_squads s
JOIN raw.provider_entity_map pm_team
  ON pm_team.provider = 'fjelstul_worldcup'
 AND pm_team.entity_type = 'team'
 AND pm_team.source_id = s.team_id
JOIN raw.provider_entity_map pm_player
  ON pm_player.provider = 'fjelstul_worldcup'
 AND pm_player.entity_type = 'player'
 AND pm_player.source_id = s.player_id
"""


INSERT_GOALS_SQL = """
INSERT INTO silver.wc_goals (
  edition_key, internal_match_id, team_internal_id, player_internal_id, player_team_internal_id,
  source_name, source_version, source_match_id, source_goal_id, source_team_id, source_player_id,
  source_player_team_id, team_name, team_code, player_name, player_team_name, player_team_code,
  minute_regulation, minute_stoppage, match_period, minute_label, is_penalty, is_own_goal, payload, materialized_at
)
SELECT
  g.edition_key,
  pm_match.canonical_id AS internal_match_id,
  pm_team.canonical_id AS team_internal_id,
  pm_player.canonical_id AS player_internal_id,
  pm_player_team.canonical_id AS player_team_internal_id,
  g.source_name,
  g.source_version,
  g.match_id AS source_match_id,
  g.goal_id AS source_goal_id,
  g.team_id AS source_team_id,
  g.player_id AS source_player_id,
  g.player_team_id AS source_player_team_id,
  g.team_name,
  g.team_code,
  NULLIF(trim(concat_ws(' ', NULLIF(g.payload->>'given_name', ''), NULLIF(g.payload->>'family_name', ''))), '') AS player_name,
  g.payload->>'player_team_name' AS player_team_name,
  g.payload->>'player_team_code' AS player_team_code,
  NULLIF(g.minute_regulation, '')::integer AS minute_regulation,
  COALESCE(NULLIF(g.minute_stoppage, '')::integer, 0) AS minute_stoppage,
  g.payload->>'match_period' AS match_period,
  g.payload->>'minute_label' AS minute_label,
  COALESCE(g.penalty, '0') = '1' AS is_penalty,
  COALESCE(g.own_goal, '0') = '1' AS is_own_goal,
  jsonb_build_object(
    'dataset', 'goals',
    'coverage_tier', 'historical_partial_domain',
    'source_payload', g.payload
  ) AS payload,
  :materialized_at
FROM bronze.fjelstul_wc_goals g
JOIN raw.provider_entity_map pm_match
  ON pm_match.provider = 'fjelstul_worldcup'
 AND pm_match.entity_type = 'match'
 AND pm_match.source_id = g.match_id
 AND pm_match.edition_key = g.edition_key
JOIN raw.provider_entity_map pm_team
  ON pm_team.provider = 'fjelstul_worldcup'
 AND pm_team.entity_type = 'team'
 AND pm_team.source_id = g.team_id
JOIN raw.provider_entity_map pm_player
  ON pm_player.provider = 'fjelstul_worldcup'
 AND pm_player.entity_type = 'player'
 AND pm_player.source_id = g.player_id
JOIN raw.provider_entity_map pm_player_team
  ON pm_player_team.provider = 'fjelstul_worldcup'
 AND pm_player_team.entity_type = 'team'
 AND pm_player_team.source_id = g.player_team_id
"""


INSERT_BOOKINGS_SQL = """
INSERT INTO silver.wc_bookings (
  edition_key, internal_match_id, team_internal_id, player_internal_id, source_name, source_version,
  source_match_id, source_booking_id, source_team_id, source_player_id, team_name, team_code, player_name,
  minute_regulation, minute_stoppage, match_period, minute_label, is_yellow_card, is_red_card,
  is_second_yellow_card, is_sending_off, payload, materialized_at
)
SELECT
  b.edition_key,
  pm_match.canonical_id AS internal_match_id,
  pm_team.canonical_id AS team_internal_id,
  pm_player.canonical_id AS player_internal_id,
  b.source_name,
  b.source_version,
  b.match_id AS source_match_id,
  b.booking_id AS source_booking_id,
  b.team_id AS source_team_id,
  b.player_id AS source_player_id,
  b.team_name,
  b.team_code,
  NULLIF(trim(concat_ws(' ', NULLIF(b.payload->>'given_name', ''), NULLIF(b.payload->>'family_name', ''))), '') AS player_name,
  NULLIF(b.minute_regulation, '')::integer AS minute_regulation,
  COALESCE(NULLIF(b.minute_stoppage, '')::integer, 0) AS minute_stoppage,
  b.payload->>'match_period' AS match_period,
  b.payload->>'minute_label' AS minute_label,
  COALESCE(b.yellow_card, '0') = '1' AS is_yellow_card,
  COALESCE(b.red_card, '0') = '1' AS is_red_card,
  COALESCE(b.second_yellow_card, '0') = '1' AS is_second_yellow_card,
  COALESCE(b.sending_off, '0') = '1' AS is_sending_off,
  jsonb_build_object(
    'dataset', 'bookings',
    'coverage_tier', 'historical_partial_domain',
    'source_payload', b.payload
  ) AS payload,
  :materialized_at
FROM bronze.fjelstul_wc_bookings b
JOIN raw.provider_entity_map pm_match
  ON pm_match.provider = 'fjelstul_worldcup'
 AND pm_match.entity_type = 'match'
 AND pm_match.source_id = b.match_id
 AND pm_match.edition_key = b.edition_key
JOIN raw.provider_entity_map pm_team
  ON pm_team.provider = 'fjelstul_worldcup'
 AND pm_team.entity_type = 'team'
 AND pm_team.source_id = b.team_id
JOIN raw.provider_entity_map pm_player
  ON pm_player.provider = 'fjelstul_worldcup'
 AND pm_player.entity_type = 'player'
 AND pm_player.source_id = b.player_id
"""


INSERT_SUBSTITUTIONS_SQL = """
INSERT INTO silver.wc_substitutions (
  edition_key, internal_match_id, team_internal_id, player_internal_id, source_name, source_version,
  source_match_id, source_substitution_id, source_team_id, source_player_id, team_name, team_code, player_name,
  minute_regulation, minute_stoppage, match_period, minute_label, is_going_off, is_coming_on,
  substitution_role, payload, materialized_at
)
SELECT
  s.edition_key,
  pm_match.canonical_id AS internal_match_id,
  pm_team.canonical_id AS team_internal_id,
  pm_player.canonical_id AS player_internal_id,
  s.source_name,
  s.source_version,
  s.match_id AS source_match_id,
  s.substitution_id AS source_substitution_id,
  s.team_id AS source_team_id,
  s.player_id AS source_player_id,
  s.team_name,
  s.team_code,
  NULLIF(trim(concat_ws(' ', NULLIF(s.payload->>'given_name', ''), NULLIF(s.payload->>'family_name', ''))), '') AS player_name,
  NULLIF(s.minute_regulation, '')::integer AS minute_regulation,
  COALESCE(NULLIF(s.minute_stoppage, '')::integer, 0) AS minute_stoppage,
  s.payload->>'match_period' AS match_period,
  s.payload->>'minute_label' AS minute_label,
  COALESCE(s.going_off, '0') = '1' AS is_going_off,
  COALESCE(s.coming_on, '0') = '1' AS is_coming_on,
  CASE
    WHEN COALESCE(s.going_off, '0') = '1' THEN 'going_off'
    ELSE 'coming_on'
  END AS substitution_role,
  jsonb_build_object(
    'dataset', 'substitutions',
    'coverage_tier', 'historical_partial_domain',
    'source_payload', s.payload
  ) AS payload,
  :materialized_at
FROM bronze.fjelstul_wc_substitutions s
JOIN raw.provider_entity_map pm_match
  ON pm_match.provider = 'fjelstul_worldcup'
 AND pm_match.entity_type = 'match'
 AND pm_match.source_id = s.match_id
 AND pm_match.edition_key = s.edition_key
JOIN raw.provider_entity_map pm_team
  ON pm_team.provider = 'fjelstul_worldcup'
 AND pm_team.entity_type = 'team'
 AND pm_team.source_id = s.team_id
JOIN raw.provider_entity_map pm_player
  ON pm_player.provider = 'fjelstul_worldcup'
 AND pm_player.entity_type = 'player'
 AND pm_player.source_id = s.player_id
"""


INSERT_COVERAGE_SQL = """
WITH editions AS (
  SELECT
    edition_key,
    substring(edition_key from '([0-9]{4})$')::integer AS edition_year
  FROM silver.wc_fixtures
  WHERE edition_key LIKE :edition_pattern
  GROUP BY edition_key
),
squads_actual AS (
  SELECT edition_key, count(*) AS actual_row_count
  FROM silver.wc_squads
  WHERE source_name = :source_name
  GROUP BY edition_key
),
goals_actual AS (
  SELECT edition_key, count(*) AS actual_row_count
  FROM silver.wc_goals
  WHERE source_name = :source_name
  GROUP BY edition_key
),
bookings_actual AS (
  SELECT edition_key, count(*) AS actual_row_count
  FROM silver.wc_bookings
  WHERE source_name = :source_name
  GROUP BY edition_key
),
substitutions_actual AS (
  SELECT edition_key, count(*) AS actual_row_count
  FROM silver.wc_substitutions
  WHERE source_name = :source_name
  GROUP BY edition_key
)
INSERT INTO silver.wc_coverage_manifest (
  edition_key, domain_name, source_name, coverage_status, expected_match_count,
  actual_match_count, expected_row_count, actual_row_count, notes, computed_at
)
SELECT
  e.edition_key,
  'squads' AS domain_name,
  :source_name,
  'FULL_TOURNAMENT' AS coverage_status,
  NULL::integer,
  NULL::integer,
  NULL::integer,
  COALESCE(sa.actual_row_count, 0)::integer,
  'one row por edition/team/player do squad Fjelstul' AS notes,
  :materialized_at
FROM editions e
LEFT JOIN squads_actual sa
  ON sa.edition_key = e.edition_key
UNION ALL
SELECT
  e.edition_key,
  'goals',
  :source_name,
  'PARTIAL_DOMAIN',
  NULL::integer,
  NULL::integer,
  NULL::integer,
  COALESCE(ga.actual_row_count, 0)::integer,
  'registry discreto de goals; nao representa event stream completo da partida' AS notes,
  :materialized_at
FROM editions e
LEFT JOIN goals_actual ga
  ON ga.edition_key = e.edition_key
UNION ALL
SELECT
  e.edition_key,
  'bookings',
  :source_name,
  CASE WHEN e.edition_year >= 1970 THEN 'PARTIAL_DOMAIN' ELSE 'PROVIDER_COVERAGE_GAP' END,
  NULL::integer,
  NULL::integer,
  NULL::integer,
  COALESCE(ba.actual_row_count, 0)::integer,
  CASE
    WHEN e.edition_year >= 1970 THEN 'registry discreto de bookings; coverage parcial do dominio de eventos'
    ELSE 'Fjelstul nao cobre bookings antes de 1970'
  END AS notes,
  :materialized_at
FROM editions e
LEFT JOIN bookings_actual ba
  ON ba.edition_key = e.edition_key
UNION ALL
SELECT
  e.edition_key,
  'substitutions',
  :source_name,
  CASE WHEN e.edition_year >= 1970 THEN 'PARTIAL_DOMAIN' ELSE 'PROVIDER_COVERAGE_GAP' END,
  NULL::integer,
  NULL::integer,
  NULL::integer,
  COALESCE(sa.actual_row_count, 0)::integer,
  CASE
    WHEN e.edition_year >= 1970 THEN 'registry discreto de substitutions no grao atomico da fonte'
    ELSE 'Fjelstul nao cobre substitutions antes de 1970'
  END AS notes,
  :materialized_at
FROM editions e
LEFT JOIN substitutions_actual sa
  ON sa.edition_key = e.edition_key
"""


def _validate_outputs(conn, prereq: dict[str, int]) -> dict[str, int]:
    queries = {
        "silver_squads_rows": "SELECT count(*) FROM silver.wc_squads WHERE source_name = :source_name",
        "silver_goals_rows": "SELECT count(*) FROM silver.wc_goals WHERE source_name = :source_name",
        "silver_bookings_rows": "SELECT count(*) FROM silver.wc_bookings WHERE source_name = :source_name",
        "silver_substitutions_rows": "SELECT count(*) FROM silver.wc_substitutions WHERE source_name = :source_name",
        "silver_squads_editions": "SELECT count(DISTINCT edition_key) FROM silver.wc_squads WHERE source_name = :source_name",
        "silver_goals_editions": "SELECT count(DISTINCT edition_key) FROM silver.wc_goals WHERE source_name = :source_name",
        "silver_bookings_editions": "SELECT count(DISTINCT edition_key) FROM silver.wc_bookings WHERE source_name = :source_name",
        "silver_substitutions_editions": "SELECT count(DISTINCT edition_key) FROM silver.wc_substitutions WHERE source_name = :source_name",
        "coverage_rows": """
            SELECT count(*)
            FROM silver.wc_coverage_manifest
            WHERE source_name = :source_name
              AND domain_name IN ('squads', 'goals', 'bookings', 'substitutions')
        """,
    }
    params = _params(_utc_now())
    results = {name: int(conn.execute(text(sql), params).scalar_one()) for name, sql in queries.items()}
    expected = {
        "silver_squads_rows": prereq["source_squads_rows"],
        "silver_goals_rows": prereq["source_goals_rows"],
        "silver_bookings_rows": prereq["source_bookings_rows"],
        "silver_substitutions_rows": prereq["source_substitutions_rows"],
        "silver_squads_editions": 22,
        "silver_goals_editions": 22,
        "silver_bookings_editions": int(
            conn.execute(text("SELECT count(DISTINCT edition_key) FROM bronze.fjelstul_wc_bookings")).scalar_one()
        ),
        "silver_substitutions_editions": int(
            conn.execute(text("SELECT count(DISTINCT edition_key) FROM bronze.fjelstul_wc_substitutions")).scalar_one()
        ),
        "coverage_rows": 22 * len(COVERAGE_DOMAINS),
    }
    for key, expected_value in expected.items():
        if results[key] != expected_value:
            raise RuntimeError(f"Validacao silver invalida para {key}: esperado={expected_value} atual={results[key]}")
    return results


def normalize_world_cup_fjelstul_registry_domains_silver() -> dict[str, Any]:
    context = get_current_context()
    materialized_at = _utc_now()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    with StepMetrics(
        service="airflow",
        module="world_cup_fjelstul_registry_domains_silver_service",
        step="normalize_world_cup_fjelstul_registry_domains_silver",
        context=context,
        dataset="silver.world_cup_fjelstul_registry_domains",
        table="silver.wc_squads/silver.wc_goals/silver.wc_bookings/silver.wc_substitutions",
    ):
        with engine.begin() as conn:
            prereq = _validate_prerequisites(conn)
            params = _params(materialized_at)
            _delete_previous_rows(conn)
            conn.execute(text(INSERT_SQUADS_SQL), params)
            conn.execute(text(INSERT_GOALS_SQL), params)
            conn.execute(text(INSERT_BOOKINGS_SQL), params)
            conn.execute(text(INSERT_SUBSTITUTIONS_SQL), params)
            conn.execute(text(INSERT_COVERAGE_SQL), params)
            validations = _validate_outputs(conn, prereq)

    summary = {
        "prerequisites": prereq,
        "validations": validations,
        "run_id": f"world_cup_fjelstul_registry_domains_silver__{materialized_at.strftime('%Y%m%dT%H%M%SZ')}",
    }
    log_event(
        service="airflow",
        module="world_cup_fjelstul_registry_domains_silver_service",
        step="summary",
        status="success",
        context=context,
        dataset="silver.world_cup_fjelstul_registry_domains",
        row_count=(
            validations["silver_squads_rows"]
            + validations["silver_goals_rows"]
            + validations["silver_bookings_rows"]
            + validations["silver_substitutions_rows"]
        ),
        message=(
            "Silver World Cup Fjelstul registry domains normalizado | "
            f"squads={validations['silver_squads_rows']} | "
            f"goals={validations['silver_goals_rows']} | "
            f"bookings={validations['silver_bookings_rows']} | "
            f"substitutions={validations['silver_substitutions_rows']}"
        ),
    )
    return summary
