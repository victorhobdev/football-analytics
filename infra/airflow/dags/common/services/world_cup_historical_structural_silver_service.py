from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any

from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.observability import StepMetrics, log_event
from common.services.world_cup_config import (
    DEFAULT_WORLD_CUP_EDITION_KEY,
    FJELSTUL_SOURCE,
)

WORLD_CUP_EDITION_PATTERN = "fifa_world_cup_mens__%"

INSERT_HISTORICAL_STAGES_SQL = """
INSERT INTO silver.wc_stages (
  edition_key, stage_internal_id, stage_key, stage_name, stage_type, stage_order,
  source_name, source_version, supporting_source_name, supporting_source_version, materialized_at
)
SELECT
  pm.edition_key,
  pm.canonical_id AS stage_internal_id,
  replace(pm.canonical_id, 'stage__' || pm.edition_key || '__', '') AS stage_key,
  CASE replace(pm.canonical_id, 'stage__' || pm.edition_key || '__', '')
    WHEN 'group_stage_1' THEN 'Group Stage'
    WHEN 'group_stage_2' THEN 'Second Group Stage'
    WHEN 'final_round' THEN 'Final Round'
    WHEN 'round_of_16' THEN 'Round of 16'
    WHEN 'quarter_final' THEN 'Quarter-finals'
    WHEN 'semi_final' THEN 'Semi-finals'
    WHEN 'third_place' THEN 'Third Place'
    WHEN 'final' THEN 'Final'
  END AS stage_name,
  CASE
    WHEN replace(pm.canonical_id, 'stage__' || pm.edition_key || '__', '') IN ('group_stage_1', 'group_stage_2', 'final_round')
      THEN 'group_stage'
    ELSE 'knockout_stage'
  END AS stage_type,
  CASE replace(pm.canonical_id, 'stage__' || pm.edition_key || '__', '')
    WHEN 'group_stage_1' THEN 1
    WHEN 'group_stage_2' THEN 2
    WHEN 'final_round' THEN 2
    WHEN 'round_of_16' THEN 3
    WHEN 'quarter_final' THEN 4
    WHEN 'semi_final' THEN 5
    WHEN 'third_place' THEN 6
    WHEN 'final' THEN 7
  END AS stage_order,
  :source_name,
  pm.source_version,
  NULL,
  NULL,
  :materialized_at
FROM raw.provider_entity_map pm
WHERE pm.provider = :source_name
  AND pm.entity_type = 'stage'
  AND pm.edition_key LIKE :edition_pattern
  AND pm.edition_key <> :skip_edition
ORDER BY pm.edition_key, stage_order, stage_name
"""

INSERT_HISTORICAL_GROUPS_SQL = """
INSERT INTO silver.wc_groups (
  edition_key, group_internal_id, stage_internal_id, stage_key, group_key, group_name,
  count_teams, source_name, source_version, source_group_id, materialized_at
)
SELECT
  g.edition_key,
  pm_group.canonical_id,
  pm_stage.canonical_id,
  replace(pm_stage.canonical_id, 'stage__' || g.edition_key || '__', '') AS stage_key,
  regexp_replace(g.group_name, '^Group\\s+', '') AS group_key,
  g.group_name,
  g.count_teams::integer,
  g.source_name,
  g.source_version,
  g.tournament_id || '::group::' || g.stage_name || '::' || g.group_name,
  :materialized_at
FROM bronze.fjelstul_wc_groups g
JOIN raw.provider_entity_map pm_stage
  ON pm_stage.provider = :source_name
 AND pm_stage.entity_type = 'stage'
 AND pm_stage.edition_key = g.edition_key
 AND replace(pm_stage.canonical_id, 'stage__' || g.edition_key || '__', '') = CASE
      WHEN g.stage_name IN ('first round', 'first group stage', 'group stage') THEN 'group_stage_1'
      WHEN g.stage_name = 'second group stage' THEN 'group_stage_2'
      WHEN g.stage_name = 'final round' THEN 'final_round'
    END
JOIN raw.provider_entity_map pm_group
  ON pm_group.provider = :source_name
 AND pm_group.entity_type = 'group'
 AND pm_group.source_id = g.tournament_id || '::group::' || g.stage_name || '::' || g.group_name
 AND pm_group.edition_key = g.edition_key
WHERE g.edition_key LIKE :edition_pattern
  AND g.edition_key <> :skip_edition
ORDER BY g.edition_key, group_key
"""

INSERT_HISTORICAL_GROUP_STANDINGS_SQL = """
INSERT INTO silver.wc_group_standings (
  edition_key, stage_internal_id, stage_key, group_internal_id, group_key, team_internal_id,
  source_name, source_version, source_row_id, final_position, team_name, team_code,
  played, wins, draws, losses, goals_for, goals_against, goal_difference, points, advanced, materialized_at
)
SELECT
  gs.edition_key,
  pm_stage.canonical_id,
  replace(pm_stage.canonical_id, 'stage__' || gs.edition_key || '__', '') AS stage_key,
  pm_group.canonical_id,
  regexp_replace(gs.group_name, '^Group\\s+', '') AS group_key,
  pm_team.canonical_id,
  gs.source_name,
  gs.source_version,
  gs.key_id,
  gs.position::integer,
  gs.team_name,
  gs.team_code,
  (gs.payload->>'played')::integer,
  (gs.payload->>'wins')::integer,
  (gs.payload->>'draws')::integer,
  (gs.payload->>'losses')::integer,
  (gs.payload->>'goals_for')::integer,
  (gs.payload->>'goals_against')::integer,
  (gs.payload->>'goal_difference')::integer,
  (gs.payload->>'points')::integer,
  CASE gs.advanced WHEN '1' THEN TRUE ELSE FALSE END,
  :materialized_at
FROM bronze.fjelstul_wc_group_standings gs
JOIN raw.provider_entity_map pm_stage
  ON pm_stage.provider = :source_name
 AND pm_stage.entity_type = 'stage'
 AND pm_stage.edition_key = gs.edition_key
 AND replace(pm_stage.canonical_id, 'stage__' || gs.edition_key || '__', '') = CASE
      WHEN gs.stage_name IN ('first round', 'first group stage', 'group stage') THEN 'group_stage_1'
      WHEN gs.stage_name = 'second group stage' THEN 'group_stage_2'
      WHEN gs.stage_name = 'final round' THEN 'final_round'
    END
JOIN raw.provider_entity_map pm_group
  ON pm_group.provider = :source_name
 AND pm_group.entity_type = 'group'
 AND pm_group.source_id = gs.tournament_id || '::group::' || gs.stage_name || '::' || gs.group_name
 AND pm_group.edition_key = gs.edition_key
JOIN raw.provider_entity_map pm_team
  ON pm_team.provider = :source_name
 AND pm_team.entity_type = 'team'
 AND pm_team.source_id = gs.team_id
WHERE gs.edition_key LIKE :edition_pattern
  AND gs.edition_key <> :skip_edition
ORDER BY
  gs.edition_key,
  replace(pm_stage.canonical_id, 'stage__' || gs.edition_key || '__', ''),
  regexp_replace(gs.group_name, '^Group\\s+', ''),
  gs.position::integer
"""

INSERT_HISTORICAL_FIXTURES_SQL = """
INSERT INTO silver.wc_fixtures (
  edition_key, internal_match_id, source_name, source_version, source_match_id,
  supporting_source_name, supporting_source_version, supporting_source_match_id,
  stage_internal_id, stage_key, group_internal_id, group_key, match_date,
  home_team_internal_id, away_team_internal_id, home_team_score, away_team_score,
  extra_time, penalty_shootout, home_penalty_score, away_penalty_score, materialized_at
)
SELECT
  m.edition_key,
  pm_match.canonical_id AS internal_match_id,
  m.source_name,
  m.source_version,
  m.match_id AS source_match_id,
  NULL,
  NULL,
  NULL,
  pm_stage.canonical_id AS stage_internal_id,
  replace(pm_stage.canonical_id, 'stage__' || m.edition_key || '__', '') AS stage_key,
  CASE WHEN m.group_name = 'not applicable' THEN NULL ELSE pm_group.canonical_id END AS group_internal_id,
  CASE WHEN m.group_name = 'not applicable' THEN NULL ELSE regexp_replace(m.group_name, '^Group\\s+', '') END AS group_key,
  m.match_date::date AS match_date,
  pm_home.canonical_id AS home_team_internal_id,
  pm_away.canonical_id AS away_team_internal_id,
  (m.payload->>'home_team_score')::integer AS home_team_score,
  (m.payload->>'away_team_score')::integer AS away_team_score,
  CASE m.payload->>'extra_time' WHEN '1' THEN TRUE ELSE FALSE END AS extra_time,
  CASE m.payload->>'penalty_shootout' WHEN '1' THEN TRUE ELSE FALSE END AS penalty_shootout,
  (m.payload->>'home_team_score_penalties')::integer AS home_penalty_score,
  (m.payload->>'away_team_score_penalties')::integer AS away_penalty_score,
  :materialized_at
FROM bronze.fjelstul_wc_matches m
JOIN raw.provider_entity_map pm_match
  ON pm_match.provider = :source_name
 AND pm_match.entity_type = 'match'
 AND pm_match.source_id = m.match_id
 AND pm_match.edition_key = m.edition_key
JOIN raw.provider_entity_map pm_stage
  ON pm_stage.provider = :source_name
 AND pm_stage.entity_type = 'stage'
 AND pm_stage.source_id = m.tournament_id || '::stage::' || m.stage_name
 AND pm_stage.edition_key = m.edition_key
LEFT JOIN raw.provider_entity_map pm_group
  ON pm_group.provider = :source_name
 AND pm_group.entity_type = 'group'
 AND pm_group.source_id = m.tournament_id || '::group::' || m.stage_name || '::' || m.group_name
 AND pm_group.edition_key = m.edition_key
JOIN raw.provider_entity_map pm_home
  ON pm_home.provider = :source_name
 AND pm_home.entity_type = 'team'
 AND pm_home.source_id = m.home_team_id
JOIN raw.provider_entity_map pm_away
  ON pm_away.provider = :source_name
 AND pm_away.entity_type = 'team'
 AND pm_away.source_id = m.away_team_id
WHERE m.edition_key LIKE :edition_pattern
  AND m.edition_key <> :skip_edition
ORDER BY m.edition_key, m.match_date, m.match_id
"""

INSERT_COVERAGE_MANIFEST_SQL = """
INSERT INTO silver.wc_coverage_manifest (
  edition_key, domain_name, source_name, coverage_status,
  expected_match_count, actual_match_count, expected_row_count, actual_row_count, notes, computed_at
) VALUES (
  :edition_key, :domain_name, :source_name, :coverage_status,
  :expected_match_count, :actual_match_count, :expected_row_count, :actual_row_count, :notes, :computed_at
)
"""


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_prerequisites(conn) -> None:
    checks = {
        "bronze_matches": (
            """
            SELECT count(DISTINCT edition_key) AS editions, count(*) AS rows
            FROM bronze.fjelstul_wc_matches
            WHERE edition_key LIKE :edition_pattern
            """,
            (22, 964),
        ),
        "bronze_stages": (
            """
            SELECT count(DISTINCT edition_key) AS editions, count(*) AS rows
            FROM bronze.fjelstul_wc_tournament_stages
            WHERE edition_key LIKE :edition_pattern
            """,
            (22, 113),
        ),
        "bronze_groups": (
            """
            SELECT count(DISTINCT edition_key) AS editions, count(*) AS rows
            FROM bronze.fjelstul_wc_groups
            WHERE edition_key LIKE :edition_pattern
            """,
            (20, 125),
        ),
        "bronze_group_standings": (
            """
            SELECT count(DISTINCT edition_key) AS editions, count(*) AS rows
            FROM bronze.fjelstul_wc_group_standings
            WHERE edition_key LIKE :edition_pattern
            """,
            (20, 490),
        ),
        "bronze_manager_appointments": (
            """
            SELECT count(DISTINCT edition_key) AS editions, count(*) AS rows
            FROM bronze.fjelstul_wc_manager_appointments
            WHERE edition_key LIKE :edition_pattern
            """,
            (22, 501),
        ),
        "provider_map_matches": (
            """
            SELECT count(DISTINCT edition_key) AS editions, count(*) AS rows
            FROM raw.provider_entity_map
            WHERE provider = :source_name
              AND entity_type = 'match'
              AND edition_key LIKE :edition_pattern
            """,
            (22, 964),
        ),
        "provider_map_stages": (
            """
            SELECT count(DISTINCT edition_key) AS editions, count(*) AS rows
            FROM raw.provider_entity_map
            WHERE provider = :source_name
              AND entity_type = 'stage'
              AND edition_key LIKE :edition_pattern
            """,
            (22, 113),
        ),
        "provider_map_groups": (
            """
            SELECT count(DISTINCT edition_key) AS editions, count(*) AS rows
            FROM raw.provider_entity_map
            WHERE provider = :source_name
              AND entity_type = 'group'
              AND edition_key LIKE :edition_pattern
            """,
            (20, 125),
        ),
        "provider_map_teams": (
            """
            SELECT count(*) AS editions, count(*) AS rows
            FROM raw.provider_entity_map
            WHERE provider = :source_name
              AND entity_type = 'team'
              AND edition_key IS NULL
            """,
            (85, 85),
        ),
    }
    for name, (sql, expected) in checks.items():
        row = conn.execute(
            text(sql),
            {
                "edition_pattern": WORLD_CUP_EDITION_PATTERN,
                "source_name": FJELSTUL_SOURCE,
            },
        ).mappings().one()
        actual = tuple(int(value) for value in row.values())
        if actual != expected:
            raise RuntimeError(f"Precondicao historica invalida para {name}: esperado={expected} atual={actual}")

    missing_checks = {
        "missing_match_map": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_matches b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = :source_name
             AND pm.entity_type = 'match'
             AND pm.source_id = b.match_id
             AND pm.edition_key = b.edition_key
            WHERE b.edition_key LIKE :edition_pattern
              AND pm.canonical_id IS NULL
        """,
        "missing_stage_map": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_tournament_stages b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = :source_name
             AND pm.entity_type = 'stage'
             AND pm.source_id = b.tournament_id || '::stage::' || b.stage_name
             AND pm.edition_key = b.edition_key
            WHERE b.edition_key LIKE :edition_pattern
              AND pm.canonical_id IS NULL
        """,
        "missing_group_map": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_groups b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = :source_name
             AND pm.entity_type = 'group'
             AND pm.source_id = b.tournament_id || '::group::' || b.stage_name || '::' || b.group_name
             AND pm.edition_key = b.edition_key
            WHERE b.edition_key LIKE :edition_pattern
              AND pm.canonical_id IS NULL
        """,
        "missing_team_map": """
            SELECT count(*)
            FROM (
              SELECT DISTINCT home_team_id AS team_id
              FROM bronze.fjelstul_wc_matches
              WHERE edition_key LIKE :edition_pattern
              UNION
              SELECT DISTINCT away_team_id AS team_id
              FROM bronze.fjelstul_wc_matches
              WHERE edition_key LIKE :edition_pattern
            ) b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = :source_name
             AND pm.entity_type = 'team'
             AND pm.source_id = b.team_id
            WHERE pm.canonical_id IS NULL
        """,
    }
    for name, sql in missing_checks.items():
        actual = conn.execute(
            text(sql),
            {
                "edition_pattern": WORLD_CUP_EDITION_PATTERN,
                "source_name": FJELSTUL_SOURCE,
            },
        ).scalar_one()
        if int(actual) != 0:
            raise RuntimeError(f"Precondicao historica invalida para {name}: atual={actual}")


def _delete_historical_rows(conn) -> None:
    for table_name in ("wc_group_standings", "wc_groups", "wc_stages", "wc_fixtures"):
        conn.execute(
            text(
                f"""
                DELETE FROM silver.{table_name}
                WHERE edition_key LIKE :edition_pattern
                  AND edition_key <> :skip_edition
                """
            ),
            {
                "edition_pattern": WORLD_CUP_EDITION_PATTERN,
                "skip_edition": DEFAULT_WORLD_CUP_EDITION_KEY,
            },
        )

    conn.execute(
        text(
            """
            DELETE FROM silver.wc_coverage_manifest
            WHERE edition_key LIKE :edition_pattern
              AND edition_key <> :skip_edition
              AND source_name = :source_name
              AND domain_name IN ('fixtures', 'stages', 'groups', 'group_standings', 'team_coaches')
            """
        ),
        {
            "edition_pattern": WORLD_CUP_EDITION_PATTERN,
            "skip_edition": DEFAULT_WORLD_CUP_EDITION_KEY,
            "source_name": FJELSTUL_SOURCE,
        },
    )


def _materialize_structural_silver(conn) -> None:
    params = {
        "edition_pattern": WORLD_CUP_EDITION_PATTERN,
        "skip_edition": DEFAULT_WORLD_CUP_EDITION_KEY,
        "source_name": FJELSTUL_SOURCE,
        "materialized_at": _utc_now(),
    }
    conn.execute(text(INSERT_HISTORICAL_STAGES_SQL), params)
    conn.execute(text(INSERT_HISTORICAL_GROUPS_SQL), params)
    conn.execute(text(INSERT_HISTORICAL_GROUP_STANDINGS_SQL), params)
    conn.execute(text(INSERT_HISTORICAL_FIXTURES_SQL), params)


def _upsert_coverage_manifest(conn) -> int:
    counts_by_edition = {
        row["edition_key"]: row
        for row in conn.execute(
            text(
                """
                WITH edition_base AS (
                  SELECT DISTINCT edition_key
                  FROM bronze.fjelstul_wc_matches
                  WHERE edition_key LIKE :edition_pattern
                    AND edition_key <> :skip_edition
                ),
                bronze_matches AS (
                  SELECT edition_key, count(*) AS count_rows
                  FROM bronze.fjelstul_wc_matches
                  WHERE edition_key LIKE :edition_pattern
                    AND edition_key <> :skip_edition
                  GROUP BY edition_key
                ),
                bronze_stages AS (
                  SELECT edition_key, count(*) AS count_rows
                  FROM bronze.fjelstul_wc_tournament_stages
                  WHERE edition_key LIKE :edition_pattern
                    AND edition_key <> :skip_edition
                  GROUP BY edition_key
                ),
                bronze_groups AS (
                  SELECT edition_key, count(*) AS count_rows
                  FROM bronze.fjelstul_wc_groups
                  WHERE edition_key LIKE :edition_pattern
                    AND edition_key <> :skip_edition
                  GROUP BY edition_key
                ),
                bronze_group_standings AS (
                  SELECT edition_key, count(*) AS count_rows
                  FROM bronze.fjelstul_wc_group_standings
                  WHERE edition_key LIKE :edition_pattern
                    AND edition_key <> :skip_edition
                  GROUP BY edition_key
                ),
                bronze_coaches AS (
                  SELECT edition_key, count(*) AS count_rows
                  FROM bronze.fjelstul_wc_manager_appointments
                  WHERE edition_key LIKE :edition_pattern
                    AND edition_key <> :skip_edition
                  GROUP BY edition_key
                ),
                silver_fixtures AS (
                  SELECT edition_key, count(*) AS count_rows
                  FROM silver.wc_fixtures
                  WHERE edition_key LIKE :edition_pattern
                    AND edition_key <> :skip_edition
                  GROUP BY edition_key
                ),
                silver_stages AS (
                  SELECT edition_key, count(*) AS count_rows
                  FROM silver.wc_stages
                  WHERE edition_key LIKE :edition_pattern
                    AND edition_key <> :skip_edition
                  GROUP BY edition_key
                ),
                silver_groups AS (
                  SELECT edition_key, count(*) AS count_rows
                  FROM silver.wc_groups
                  WHERE edition_key LIKE :edition_pattern
                    AND edition_key <> :skip_edition
                  GROUP BY edition_key
                ),
                silver_group_standings AS (
                  SELECT edition_key, count(*) AS count_rows
                  FROM silver.wc_group_standings
                  WHERE edition_key LIKE :edition_pattern
                    AND edition_key <> :skip_edition
                  GROUP BY edition_key
                )
                SELECT
                  e.edition_key,
                  COALESCE(bm.count_rows, 0) AS expected_fixtures,
                  COALESCE(sf.count_rows, 0) AS actual_fixtures,
                  COALESCE(bs.count_rows, 0) AS expected_stages,
                  COALESCE(ss.count_rows, 0) AS actual_stages,
                  COALESCE(bg.count_rows, 0) AS expected_groups,
                  COALESCE(sg.count_rows, 0) AS actual_groups,
                  COALESCE(bgs.count_rows, 0) AS expected_group_standings,
                  COALESCE(sgs.count_rows, 0) AS actual_group_standings,
                  COALESCE(bc.count_rows, 0) AS expected_team_coaches
                FROM edition_base e
                LEFT JOIN bronze_matches bm ON bm.edition_key = e.edition_key
                LEFT JOIN silver_fixtures sf ON sf.edition_key = e.edition_key
                LEFT JOIN bronze_stages bs ON bs.edition_key = e.edition_key
                LEFT JOIN silver_stages ss ON ss.edition_key = e.edition_key
                LEFT JOIN bronze_groups bg ON bg.edition_key = e.edition_key
                LEFT JOIN silver_groups sg ON sg.edition_key = e.edition_key
                LEFT JOIN bronze_group_standings bgs ON bgs.edition_key = e.edition_key
                LEFT JOIN silver_group_standings sgs ON sgs.edition_key = e.edition_key
                LEFT JOIN bronze_coaches bc ON bc.edition_key = e.edition_key
                ORDER BY e.edition_key
                """
            ),
            {
                "edition_pattern": WORLD_CUP_EDITION_PATTERN,
                "skip_edition": DEFAULT_WORLD_CUP_EDITION_KEY,
            },
        ).mappings().all()
    }

    rows: list[dict[str, Any]] = []
    computed_at = _utc_now()
    for edition_key, counts in counts_by_edition.items():
        rows.extend(
            [
                {
                    "edition_key": edition_key,
                    "domain_name": "fixtures",
                    "source_name": FJELSTUL_SOURCE,
                    "coverage_status": "FULL_TOURNAMENT",
                    "expected_match_count": counts["expected_fixtures"],
                    "actual_match_count": counts["actual_fixtures"],
                    "expected_row_count": counts["expected_fixtures"],
                    "actual_row_count": counts["actual_fixtures"],
                    "notes": "Backbone estrutural historico Fjelstul publicado em silver.wc_fixtures",
                    "computed_at": computed_at,
                },
                {
                    "edition_key": edition_key,
                    "domain_name": "stages",
                    "source_name": FJELSTUL_SOURCE,
                    "coverage_status": "FULL_TOURNAMENT",
                    "expected_match_count": None,
                    "actual_match_count": None,
                    "expected_row_count": counts["expected_stages"],
                    "actual_row_count": counts["actual_stages"],
                    "notes": "Stages canonicos historicos derivados do backbone Fjelstul",
                    "computed_at": computed_at,
                },
                {
                    "edition_key": edition_key,
                    "domain_name": "groups",
                    "source_name": FJELSTUL_SOURCE,
                    "coverage_status": "FULL_TOURNAMENT",
                    "expected_match_count": None,
                    "actual_match_count": None,
                    "expected_row_count": counts["expected_groups"],
                    "actual_row_count": counts["actual_groups"],
                    "notes": (
                        "Edicoes sem grupos permanecem com 0/0 por formato de torneio"
                        if counts["expected_groups"] == 0
                        else "Groups historicos derivados do backbone Fjelstul"
                    ),
                    "computed_at": computed_at,
                },
                {
                    "edition_key": edition_key,
                    "domain_name": "group_standings",
                    "source_name": FJELSTUL_SOURCE,
                    "coverage_status": "FULL_TOURNAMENT",
                    "expected_match_count": None,
                    "actual_match_count": None,
                    "expected_row_count": counts["expected_group_standings"],
                    "actual_row_count": counts["actual_group_standings"],
                    "notes": (
                        "Edicoes sem group standings permanecem com 0/0 por formato de torneio"
                        if counts["expected_group_standings"] == 0
                        else "Standings historicos por grupo no grao edition+stage+group+team"
                    ),
                    "computed_at": computed_at,
                },
                {
                    "edition_key": edition_key,
                    "domain_name": "team_coaches",
                    "source_name": FJELSTUL_SOURCE,
                    "coverage_status": "FULL_TOURNAMENT",
                    "expected_match_count": None,
                    "actual_match_count": None,
                    "expected_row_count": counts["expected_team_coaches"],
                    "actual_row_count": counts["expected_team_coaches"],
                    "notes": "Publish estrutural historico usa manager_appointments direto do bronze com team map canonico",
                    "computed_at": computed_at,
                },
            ]
        )
    conn.execute(text(INSERT_COVERAGE_MANIFEST_SQL), rows)
    return len(rows)


def _validate_outputs(conn) -> dict[str, Any]:
    results = {
        "fixtures_total": conn.execute(
            text("SELECT count(*) FROM silver.wc_fixtures WHERE edition_key LIKE :edition_pattern"),
            {"edition_pattern": WORLD_CUP_EDITION_PATTERN},
        ).scalar_one(),
        "fixture_editions": conn.execute(
            text("SELECT count(DISTINCT edition_key) FROM silver.wc_fixtures WHERE edition_key LIKE :edition_pattern"),
            {"edition_pattern": WORLD_CUP_EDITION_PATTERN},
        ).scalar_one(),
        "stages_total": conn.execute(
            text("SELECT count(*) FROM silver.wc_stages WHERE edition_key LIKE :edition_pattern"),
            {"edition_pattern": WORLD_CUP_EDITION_PATTERN},
        ).scalar_one(),
        "stage_editions": conn.execute(
            text("SELECT count(DISTINCT edition_key) FROM silver.wc_stages WHERE edition_key LIKE :edition_pattern"),
            {"edition_pattern": WORLD_CUP_EDITION_PATTERN},
        ).scalar_one(),
        "groups_total": conn.execute(
            text("SELECT count(*) FROM silver.wc_groups WHERE edition_key LIKE :edition_pattern"),
            {"edition_pattern": WORLD_CUP_EDITION_PATTERN},
        ).scalar_one(),
        "group_editions": conn.execute(
            text("SELECT count(DISTINCT edition_key) FROM silver.wc_groups WHERE edition_key LIKE :edition_pattern"),
            {"edition_pattern": WORLD_CUP_EDITION_PATTERN},
        ).scalar_one(),
        "group_standings_total": conn.execute(
            text("SELECT count(*) FROM silver.wc_group_standings WHERE edition_key LIKE :edition_pattern"),
            {"edition_pattern": WORLD_CUP_EDITION_PATTERN},
        ).scalar_one(),
        "group_standings_editions": conn.execute(
            text(
                "SELECT count(DISTINCT edition_key) FROM silver.wc_group_standings WHERE edition_key LIKE :edition_pattern"
            ),
            {"edition_pattern": WORLD_CUP_EDITION_PATTERN},
        ).scalar_one(),
    }
    expected = {
        "fixtures_total": 964,
        "fixture_editions": 22,
        "stages_total": 113,
        "stage_editions": 22,
        "groups_total": 125,
        "group_editions": 20,
        "group_standings_total": 490,
        "group_standings_editions": 20,
    }
    for key, expected_value in expected.items():
        if int(results[key]) != expected_value:
            raise RuntimeError(f"Silver historico invalido para {key}: esperado={expected_value} atual={results[key]}")

    duplicate_checks = {
        "fixture_duplicates": """
            SELECT count(*)
            FROM (
              SELECT edition_key, internal_match_id, count(*) AS row_count
              FROM silver.wc_fixtures
              WHERE edition_key LIKE :edition_pattern
              GROUP BY 1,2
              HAVING count(*) > 1
            ) dup
        """,
        "stage_duplicates": """
            SELECT count(*)
            FROM (
              SELECT edition_key, stage_key, count(*) AS row_count
              FROM silver.wc_stages
              WHERE edition_key LIKE :edition_pattern
              GROUP BY 1,2
              HAVING count(*) > 1
            ) dup
        """,
        "group_duplicates": """
            SELECT count(*)
            FROM (
              SELECT edition_key, stage_key, group_key, count(*) AS row_count
              FROM silver.wc_groups
              WHERE edition_key LIKE :edition_pattern
              GROUP BY 1,2,3
              HAVING count(*) > 1
            ) dup
        """,
        "group_standings_duplicates": """
            SELECT count(*)
            FROM (
              SELECT edition_key, stage_key, group_key, team_internal_id, count(*) AS row_count
              FROM silver.wc_group_standings
              WHERE edition_key LIKE :edition_pattern
              GROUP BY 1,2,3,4
              HAVING count(*) > 1
            ) dup
        """,
        "fixture_stage_key_nulls": """
            SELECT count(*)
            FROM silver.wc_fixtures
            WHERE edition_key LIKE :edition_pattern
              AND stage_key IS NULL
        """,
        "fixture_group_key_nulls": """
            SELECT count(*)
            FROM silver.wc_fixtures
            WHERE edition_key LIKE :edition_pattern
              AND stage_key = 'group_stage_1'
              AND group_key IS NULL
        """,
        "coverage_mismatches": """
            SELECT count(*)
            FROM silver.wc_coverage_manifest
            WHERE edition_key LIKE :edition_pattern
              AND source_name = :source_name
              AND domain_name IN ('fixtures', 'stages', 'groups', 'group_standings', 'team_coaches')
              AND coverage_status = 'FULL_TOURNAMENT'
              AND (
                (expected_match_count IS NOT NULL AND expected_match_count <> actual_match_count)
                OR (expected_row_count IS NOT NULL AND expected_row_count <> actual_row_count)
              )
        """,
    }
    for key, sql in duplicate_checks.items():
        actual = conn.execute(
            text(sql),
            {"edition_pattern": WORLD_CUP_EDITION_PATTERN, "source_name": FJELSTUL_SOURCE},
        ).scalar_one()
        results[key] = actual
        if int(actual) != 0:
            raise RuntimeError(f"Silver historico invalido para {key}: atual={actual}")

    results["coverage_rows_world_cup"] = conn.execute(
        text(
            """
            SELECT count(*)
            FROM silver.wc_coverage_manifest
            WHERE edition_key LIKE :edition_pattern
              AND source_name = :source_name
              AND domain_name IN ('fixtures', 'stages', 'groups', 'group_standings', 'team_coaches')
            """
        ),
        {"edition_pattern": WORLD_CUP_EDITION_PATTERN, "source_name": FJELSTUL_SOURCE},
    ).scalar_one()
    return results


def normalize_world_cup_historical_structural_to_silver() -> dict[str, Any]:
    context = get_current_context()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    with StepMetrics(
        service="airflow",
        module="world_cup_historical_structural_silver_service",
        step="normalize_world_cup_historical_structural_to_silver",
        context=context,
        dataset="silver.world_cup_historical_structural",
        table="silver.wc_*",
    ):
        with engine.begin() as conn:
            _validate_prerequisites(conn)
            _delete_historical_rows(conn)
            _materialize_structural_silver(conn)
            coverage_rows = _upsert_coverage_manifest(conn)
            summary = _validate_outputs(conn)
            summary["coverage_rows_inserted"] = coverage_rows

    log_event(
        service="airflow",
        module="world_cup_historical_structural_silver_service",
        step="summary",
        status="success",
        context=context,
        dataset="silver.world_cup_historical_structural",
        row_count=(
            summary["fixtures_total"]
            + summary["stages_total"]
            + summary["groups_total"]
            + summary["group_standings_total"]
            + summary["coverage_rows_world_cup"]
        ),
        message=(
            "Silver historico estrutural da Copa concluido | "
            f"fixtures={summary['fixtures_total']} | "
            f"stages={summary['stages_total']} | "
            f"groups={summary['groups_total']} | "
            f"group_standings={summary['group_standings_total']} | "
            f"coverage_rows={summary['coverage_rows_world_cup']}"
        ),
    )
    return summary
