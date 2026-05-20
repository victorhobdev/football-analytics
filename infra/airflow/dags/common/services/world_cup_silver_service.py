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
    STATSBOMB_SOURCE,
    WorldCupEditionConfig,
    fetch_active_world_cup_snapshots,
    get_world_cup_edition_config,
    get_world_cup_edition_config_from_context,
)


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_prerequisites(conn, snapshots: dict[str, dict[str, Any]], config: WorldCupEditionConfig) -> None:
    bronze_checks = {
        "statsbomb_matches": ("SELECT count(*) FROM bronze.statsbomb_wc_matches WHERE edition_key = :edition_key", config.expected_matches),
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
        "fjelstul_matches": ("SELECT count(*) FROM bronze.fjelstul_wc_matches WHERE edition_key = :edition_key", config.expected_matches),
        "fjelstul_groups": ("SELECT count(*) FROM bronze.fjelstul_wc_groups WHERE edition_key = :edition_key", config.expected_groups),
        "fjelstul_group_standings": (
            "SELECT count(*) FROM bronze.fjelstul_wc_group_standings WHERE edition_key = :edition_key",
            config.expected_group_standings,
        ),
    }
    for name, (sql, expected) in bronze_checks.items():
        actual = conn.execute(text(sql), {"edition_key": config.edition_key}).scalar_one()
        if actual != expected:
            raise RuntimeError(f"Precondicao do bronze invalida para {name}: esperado={expected} atual={actual}")

    version_checks = [
        ("bronze.statsbomb_wc_matches", STATSBOMB_SOURCE),
        ("bronze.statsbomb_wc_events", STATSBOMB_SOURCE),
        ("bronze.statsbomb_wc_lineups", STATSBOMB_SOURCE),
        ("bronze.statsbomb_wc_three_sixty", STATSBOMB_SOURCE),
        ("bronze.fjelstul_wc_matches", FJELSTUL_SOURCE),
        ("bronze.fjelstul_wc_groups", FJELSTUL_SOURCE),
        ("bronze.fjelstul_wc_group_standings", FJELSTUL_SOURCE),
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

    mapping_checks = {
        "statsbomb_match_map_missing": """
            SELECT count(*)
            FROM bronze.statsbomb_wc_matches b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = 'statsbomb_open_data'
             AND pm.entity_type = 'match'
             AND pm.source_id = b.match_id::text
             AND pm.edition_key = :edition_key
            WHERE b.edition_key = :edition_key
              AND pm.canonical_id IS NULL
        """,
        "statsbomb_stage_map_missing": """
            SELECT count(*)
            FROM (
              SELECT DISTINCT (payload->'competition_stage'->>'id')::text AS source_stage_id
              FROM bronze.statsbomb_wc_matches
              WHERE edition_key = :edition_key
            ) b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = 'statsbomb_open_data'
             AND pm.entity_type = 'stage'
             AND pm.source_id = :edition_key || '::stage::' || b.source_stage_id
             AND pm.edition_key = :edition_key
            WHERE pm.canonical_id IS NULL
        """,
        "statsbomb_team_map_missing": """
            SELECT count(*)
            FROM (
              SELECT DISTINCT (payload->'home_team'->>'home_team_id')::text AS source_team_id
              FROM bronze.statsbomb_wc_matches
              WHERE edition_key = :edition_key
              UNION
              SELECT DISTINCT (payload->'away_team'->>'away_team_id')::text AS source_team_id
              FROM bronze.statsbomb_wc_matches
              WHERE edition_key = :edition_key
            ) b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = 'statsbomb_open_data'
             AND pm.entity_type = 'team'
             AND pm.source_id = b.source_team_id
            WHERE pm.canonical_id IS NULL
        """,
        "statsbomb_player_map_missing": """
            SELECT count(*)
            FROM (
              SELECT DISTINCT player->>'player_id' AS source_player_id
              FROM bronze.statsbomb_wc_lineups l
              CROSS JOIN LATERAL jsonb_array_elements(l.payload) team
              CROSS JOIN LATERAL jsonb_array_elements(team->'lineup') player
              WHERE l.edition_key = :edition_key
            ) b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = 'statsbomb_open_data'
             AND pm.entity_type = 'player'
             AND pm.source_id = b.source_player_id
             AND pm.edition_key = :edition_key
            WHERE pm.canonical_id IS NULL
        """,
        "fjelstul_match_map_missing": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_matches b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = 'fjelstul_worldcup'
             AND pm.entity_type = 'match'
             AND pm.source_id = b.match_id
             AND pm.edition_key = :edition_key
            WHERE b.edition_key = :edition_key
              AND pm.canonical_id IS NULL
        """,
        "fjelstul_stage_map_missing": """
            SELECT count(*)
            FROM (
              SELECT DISTINCT stage_name
              FROM bronze.fjelstul_wc_matches
              WHERE edition_key = :edition_key
            ) b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = 'fjelstul_worldcup'
             AND pm.entity_type = 'stage'
             AND pm.source_id = :fjelstul_tournament_id || '::stage::' || b.stage_name
             AND pm.edition_key = :edition_key
            WHERE pm.canonical_id IS NULL
        """,
        "fjelstul_group_map_missing": """
            SELECT count(*)
            FROM bronze.fjelstul_wc_groups b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = 'fjelstul_worldcup'
             AND pm.entity_type = 'group'
             AND pm.source_id = :fjelstul_tournament_id || '::group::' || b.stage_name || '::' || b.group_name
             AND pm.edition_key = :edition_key
            WHERE b.edition_key = :edition_key
              AND pm.canonical_id IS NULL
        """,
        "fjelstul_team_map_missing": """
            SELECT count(*)
            FROM (
              SELECT DISTINCT home_team_id AS source_team_id
              FROM bronze.fjelstul_wc_matches
              WHERE edition_key = :edition_key
              UNION
              SELECT DISTINCT away_team_id AS source_team_id
              FROM bronze.fjelstul_wc_matches
              WHERE edition_key = :edition_key
            ) b
            LEFT JOIN raw.provider_entity_map pm
              ON pm.provider = 'fjelstul_worldcup'
             AND pm.entity_type = 'team'
             AND pm.source_id = b.source_team_id
            WHERE pm.canonical_id IS NULL
        """,
    }
    mapping_params = {
        "edition_key": config.edition_key,
        "fjelstul_tournament_id": config.fjelstul_tournament_id,
    }
    for name, sql in mapping_checks.items():
        actual = conn.execute(text(sql), mapping_params).scalar_one()
        if actual != 0:
            raise RuntimeError(f"Precondicao do mapa canonico invalida para {name}: atual={actual}")


def _delete_edition_rows(conn, config: WorldCupEditionConfig) -> None:
    for table_name in (
        "wc_match_events",
        "wc_lineups",
        "wc_group_standings",
        "wc_groups",
        "wc_stages",
        "wc_fixtures",
    ):
        conn.execute(
            text(f"DELETE FROM silver.{table_name} WHERE edition_key = :edition_key"),
            {"edition_key": config.edition_key},
        )

    conn.execute(
        text("DELETE FROM silver.wc_coverage_manifest WHERE edition_key = :edition_key"),
        {"edition_key": config.edition_key},
    )
    conn.execute(
        text("DELETE FROM silver.wc_source_divergences WHERE edition_key = :edition_key"),
        {"edition_key": config.edition_key},
    )


INSERT_STAGES_SQL = """
INSERT INTO silver.wc_stages (
  edition_key, stage_internal_id, stage_key, stage_name, stage_type, stage_order,
  source_name, source_version, supporting_source_name, supporting_source_version, materialized_at
)
WITH fj AS (
  SELECT canonical_id, source_version
  FROM raw.provider_entity_map
  WHERE provider = 'fjelstul_worldcup'
    AND entity_type = 'stage'
    AND edition_key = :edition_key
),
sb AS (
  SELECT canonical_id, source_version
  FROM raw.provider_entity_map
  WHERE provider = 'statsbomb_open_data'
    AND entity_type = 'stage'
    AND edition_key = :edition_key
)
SELECT
  :edition_key,
  fj.canonical_id,
  replace(fj.canonical_id, 'stage__' || :edition_key || '__', '') AS stage_key,
  CASE replace(fj.canonical_id, 'stage__' || :edition_key || '__', '')
    WHEN 'group_stage_1' THEN 'Group Stage'
    WHEN 'round_of_16' THEN 'Round of 16'
    WHEN 'quarter_final' THEN 'Quarter-finals'
    WHEN 'semi_final' THEN 'Semi-finals'
    WHEN 'third_place' THEN 'Third Place'
    WHEN 'final' THEN 'Final'
  END AS stage_name,
  CASE
    WHEN replace(fj.canonical_id, 'stage__' || :edition_key || '__', '') = 'group_stage_1' THEN 'group_stage'
    ELSE 'knockout_stage'
  END AS stage_type,
  CASE replace(fj.canonical_id, 'stage__' || :edition_key || '__', '')
    WHEN 'group_stage_1' THEN 1
    WHEN 'round_of_16' THEN 2
    WHEN 'quarter_final' THEN 3
    WHEN 'semi_final' THEN 4
    WHEN 'third_place' THEN 5
    WHEN 'final' THEN 6
  END AS stage_order,
  'fjelstul_worldcup',
  fj.source_version,
  'statsbomb_open_data',
  sb.source_version,
  :materialized_at
FROM fj
JOIN sb
  ON sb.canonical_id = fj.canonical_id
"""


INSERT_GROUPS_SQL = """
INSERT INTO silver.wc_groups (
  edition_key, group_internal_id, stage_internal_id, stage_key, group_key, group_name,
  count_teams, source_name, source_version, source_group_id, materialized_at
)
SELECT
  g.edition_key,
  pm_group.canonical_id,
  pm_stage.canonical_id,
  replace(pm_stage.canonical_id, 'stage__' || :edition_key || '__', '') AS stage_key,
  regexp_replace(g.group_name, '^Group\\s+', '') AS group_key,
  g.group_name,
  g.count_teams::integer,
  g.source_name,
  g.source_version,
  :fjelstul_tournament_id || '::group::' || g.stage_name || '::' || g.group_name,
  :materialized_at
FROM bronze.fjelstul_wc_groups g
JOIN raw.provider_entity_map pm_stage
  ON pm_stage.provider = 'fjelstul_worldcup'
 AND pm_stage.entity_type = 'stage'
 AND pm_stage.source_id = :fjelstul_tournament_id || '::stage::' || g.stage_name
 AND pm_stage.edition_key = :edition_key
JOIN raw.provider_entity_map pm_group
  ON pm_group.provider = 'fjelstul_worldcup'
 AND pm_group.entity_type = 'group'
 AND pm_group.source_id = :fjelstul_tournament_id || '::group::' || g.stage_name || '::' || g.group_name
 AND pm_group.edition_key = :edition_key
WHERE g.edition_key = :edition_key
"""


INSERT_GROUP_STANDINGS_SQL = """
INSERT INTO silver.wc_group_standings (
  edition_key, stage_internal_id, stage_key, group_internal_id, group_key, team_internal_id,
  source_name, source_version, source_row_id, final_position, team_name, team_code,
  played, wins, draws, losses, goals_for, goals_against, goal_difference, points, advanced, materialized_at
)
SELECT
  gs.edition_key,
  pm_stage.canonical_id,
  replace(pm_stage.canonical_id, 'stage__' || :edition_key || '__', '') AS stage_key,
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
  ON pm_stage.provider = 'fjelstul_worldcup'
 AND pm_stage.entity_type = 'stage'
 AND pm_stage.source_id = :fjelstul_tournament_id || '::stage::' || gs.stage_name
 AND pm_stage.edition_key = :edition_key
JOIN raw.provider_entity_map pm_group
  ON pm_group.provider = 'fjelstul_worldcup'
 AND pm_group.entity_type = 'group'
 AND pm_group.source_id = :fjelstul_tournament_id || '::group::' || gs.stage_name || '::' || gs.group_name
 AND pm_group.edition_key = :edition_key
JOIN raw.provider_entity_map pm_team
  ON pm_team.provider = 'fjelstul_worldcup'
 AND pm_team.entity_type = 'team'
 AND pm_team.source_id = gs.team_id
WHERE gs.edition_key = :edition_key;
"""


INSERT_FIXTURES_SQL = """
INSERT INTO silver.wc_fixtures (
  edition_key, internal_match_id, source_name, source_version, source_match_id,
  supporting_source_name, supporting_source_version, supporting_source_match_id,
  stage_internal_id, stage_key, group_internal_id, group_key, match_date,
  home_team_internal_id, away_team_internal_id, home_team_score, away_team_score,
  extra_time, penalty_shootout, home_penalty_score, away_penalty_score, materialized_at
)
WITH fj AS (
  SELECT
    m.edition_key,
    pm_match.canonical_id AS internal_match_id,
    m.source_name,
    m.source_version,
    m.match_id AS source_match_id,
    pm_stage.canonical_id AS stage_internal_id,
    replace(pm_stage.canonical_id, 'stage__' || :edition_key || '__', '') AS stage_key,
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
    (m.payload->>'away_team_score_penalties')::integer AS away_penalty_score
  FROM bronze.fjelstul_wc_matches m
  JOIN raw.provider_entity_map pm_match
    ON pm_match.provider = 'fjelstul_worldcup'
   AND pm_match.entity_type = 'match'
   AND pm_match.source_id = m.match_id
   AND pm_match.edition_key = :edition_key
  JOIN raw.provider_entity_map pm_stage
    ON pm_stage.provider = 'fjelstul_worldcup'
   AND pm_stage.entity_type = 'stage'
   AND pm_stage.source_id = :fjelstul_tournament_id || '::stage::' || m.stage_name
   AND pm_stage.edition_key = :edition_key
  LEFT JOIN raw.provider_entity_map pm_group
    ON pm_group.provider = 'fjelstul_worldcup'
   AND pm_group.entity_type = 'group'
   AND pm_group.source_id = :fjelstul_tournament_id || '::group::' || m.stage_name || '::' || m.group_name
   AND pm_group.edition_key = :edition_key
  JOIN raw.provider_entity_map pm_home
    ON pm_home.provider = 'fjelstul_worldcup'
   AND pm_home.entity_type = 'team'
   AND pm_home.source_id = m.home_team_id
  JOIN raw.provider_entity_map pm_away
    ON pm_away.provider = 'fjelstul_worldcup'
   AND pm_away.entity_type = 'team'
   AND pm_away.source_id = m.away_team_id
  WHERE m.edition_key = :edition_key
),
sb AS (
  SELECT
    pm_match.canonical_id AS internal_match_id,
    m.source_version AS supporting_source_version,
    m.match_id::text AS supporting_source_match_id
  FROM bronze.statsbomb_wc_matches m
  JOIN raw.provider_entity_map pm_match
    ON pm_match.provider = 'statsbomb_open_data'
   AND pm_match.entity_type = 'match'
   AND pm_match.source_id = m.match_id::text
   AND pm_match.edition_key = :edition_key
  WHERE m.edition_key = :edition_key
)
SELECT
  fj.edition_key,
  fj.internal_match_id,
  fj.source_name,
  fj.source_version,
  fj.source_match_id,
  'statsbomb_open_data',
  sb.supporting_source_version,
  sb.supporting_source_match_id,
  fj.stage_internal_id,
  fj.stage_key,
  fj.group_internal_id,
  fj.group_key,
  fj.match_date,
  fj.home_team_internal_id,
  fj.away_team_internal_id,
  fj.home_team_score,
  fj.away_team_score,
  fj.extra_time,
  fj.penalty_shootout,
  fj.home_penalty_score,
  fj.away_penalty_score,
  :materialized_at
FROM fj
JOIN sb
  ON sb.internal_match_id = fj.internal_match_id
"""


INSERT_LINEUPS_SQL = """
INSERT INTO silver.wc_lineups (
  edition_key, internal_match_id, team_internal_id, player_internal_id, source_name, source_version,
  source_match_id, source_team_id, source_player_id, team_name, player_name, player_nickname,
  jersey_number, is_starter, start_reason, first_position_name, first_position_id, payload, materialized_at
)
SELECT
  l.edition_key,
  pm_match.canonical_id AS internal_match_id,
  pm_team.canonical_id AS team_internal_id,
  pm_player.canonical_id AS player_internal_id,
  l.source_name,
  l.source_version,
  l.match_id::text AS source_match_id,
  team->>'team_id' AS source_team_id,
  player->>'player_id' AS source_player_id,
  team->>'team_name' AS team_name,
  player->>'player_name' AS player_name,
  player->>'player_nickname' AS player_nickname,
  NULLIF(player->>'jersey_number', '')::integer AS jersey_number,
  EXISTS (
    SELECT 1
    FROM jsonb_array_elements(COALESCE(player->'positions', '[]'::jsonb)) pos
    WHERE pos->>'start_reason' = 'Starting XI'
  ) AS is_starter,
  (
    SELECT pos->>'start_reason'
    FROM jsonb_array_elements(COALESCE(player->'positions', '[]'::jsonb)) pos
    LIMIT 1
  ) AS start_reason,
  (
    SELECT pos->>'position'
    FROM jsonb_array_elements(COALESCE(player->'positions', '[]'::jsonb)) pos
    LIMIT 1
  ) AS first_position_name,
  (
    SELECT NULLIF(pos->>'position_id', '')::integer
    FROM jsonb_array_elements(COALESCE(player->'positions', '[]'::jsonb)) pos
    LIMIT 1
  ) AS first_position_id,
  player AS payload,
  :materialized_at
FROM bronze.statsbomb_wc_lineups l
CROSS JOIN LATERAL jsonb_array_elements(l.payload) team
CROSS JOIN LATERAL jsonb_array_elements(team->'lineup') player
JOIN raw.provider_entity_map pm_match
  ON pm_match.provider = 'statsbomb_open_data'
 AND pm_match.entity_type = 'match'
 AND pm_match.source_id = l.match_id::text
 AND pm_match.edition_key = :edition_key
JOIN raw.provider_entity_map pm_team
  ON pm_team.provider = 'statsbomb_open_data'
 AND pm_team.entity_type = 'team'
 AND pm_team.source_id = team->>'team_id'
JOIN raw.provider_entity_map pm_player
  ON pm_player.provider = 'statsbomb_open_data'
 AND pm_player.entity_type = 'player'
 AND pm_player.source_id = player->>'player_id'
 AND pm_player.edition_key = :edition_key
WHERE l.edition_key = :edition_key;
"""


INSERT_MATCH_EVENTS_SQL = """
INSERT INTO silver.wc_match_events (
  edition_key, internal_match_id, source_name, source_version, source_match_id, source_event_id, event_index,
  team_internal_id, player_internal_id, event_type_id, event_type, period, minute, second,
  timestamp_label, possession, play_pattern, location_x, location_y, has_three_sixty_frame, payload, materialized_at
)
WITH frames AS (
  SELECT
    t.match_id::text AS source_match_id,
    frame->>'event_uuid' AS source_event_id
  FROM bronze.statsbomb_wc_three_sixty t
  CROSS JOIN LATERAL jsonb_array_elements(t.payload) frame
  WHERE t.edition_key = :edition_key
)
SELECT
  e.edition_key,
  pm_match.canonical_id AS internal_match_id,
  e.source_name,
  e.source_version,
  e.match_id::text AS source_match_id,
  event->>'id' AS source_event_id,
  NULLIF(event->>'index', '')::integer AS event_index,
  pm_team.canonical_id AS team_internal_id,
  pm_player.canonical_id AS player_internal_id,
  NULLIF(event->'type'->>'id', '')::integer AS event_type_id,
  event->'type'->>'name' AS event_type,
  NULLIF(event->>'period', '')::integer AS period,
  NULLIF(event->>'minute', '')::integer AS minute,
  NULLIF(event->>'second', '')::numeric(8,3) AS second,
  event->>'timestamp' AS timestamp_label,
  NULLIF(event->>'possession', '')::integer AS possession,
  event->'play_pattern'->>'name' AS play_pattern,
  CASE WHEN event ? 'location' THEN NULLIF(event->'location'->>0, '')::numeric(10,4) END AS location_x,
  CASE WHEN event ? 'location' THEN NULLIF(event->'location'->>1, '')::numeric(10,4) END AS location_y,
  CASE WHEN frames.source_event_id IS NOT NULL THEN TRUE ELSE FALSE END AS has_three_sixty_frame,
  event AS payload,
  :materialized_at
FROM bronze.statsbomb_wc_events e
CROSS JOIN LATERAL jsonb_array_elements(e.payload) event
JOIN raw.provider_entity_map pm_match
  ON pm_match.provider = 'statsbomb_open_data'
 AND pm_match.entity_type = 'match'
 AND pm_match.source_id = e.match_id::text
 AND pm_match.edition_key = :edition_key
LEFT JOIN raw.provider_entity_map pm_team
  ON pm_team.provider = 'statsbomb_open_data'
 AND pm_team.entity_type = 'team'
 AND pm_team.source_id = event->'team'->>'id'
LEFT JOIN raw.provider_entity_map pm_player
  ON pm_player.provider = 'statsbomb_open_data'
 AND pm_player.entity_type = 'player'
 AND pm_player.source_id = event->'player'->>'id'
 AND pm_player.edition_key = :edition_key
LEFT JOIN frames
  ON frames.source_match_id = e.match_id::text
 AND frames.source_event_id = event->>'id'
WHERE e.edition_key = :edition_key;
"""


INSERT_COVERAGE_MANIFEST_SQL = """
INSERT INTO silver.wc_coverage_manifest (
  edition_key, domain_name, source_name, coverage_status,
  expected_match_count, actual_match_count, expected_row_count, actual_row_count, notes, computed_at
)
VALUES
  (:edition_key, 'fixtures', 'fjelstul_worldcup', 'FULL_TOURNAMENT', 64,
    (SELECT count(*) FROM silver.wc_fixtures WHERE edition_key = :edition_key), 64,
    (SELECT count(*) FROM silver.wc_fixtures WHERE edition_key = :edition_key),
    'Fjelstul como backbone estrutural do silver inicial', :materialized_at),
  (:edition_key, 'stages', 'fjelstul_worldcup', 'FULL_TOURNAMENT', NULL, NULL, 6,
    (SELECT count(*) FROM silver.wc_stages WHERE edition_key = :edition_key),
    'Stages canonicos reconciliados com suporte StatsBomb', :materialized_at),
  (:edition_key, 'groups', 'fjelstul_worldcup', 'FULL_TOURNAMENT', NULL, NULL, 8,
    (SELECT count(*) FROM silver.wc_groups WHERE edition_key = :edition_key),
    'Groups canonicos derivados do backbone Fjelstul', :materialized_at),
  (:edition_key, 'group_standings', 'fjelstul_worldcup', 'FULL_TOURNAMENT', NULL, NULL, 32,
    (SELECT count(*) FROM silver.wc_group_standings WHERE edition_key = :edition_key),
    'Standings finais por grupo no grão team-per-group', :materialized_at),
  (:edition_key, 'lineups', 'statsbomb_open_data', 'FULL_TOURNAMENT', 64,
    (SELECT count(DISTINCT internal_match_id) FROM silver.wc_lineups WHERE edition_key = :edition_key), NULL,
    (SELECT count(*) FROM silver.wc_lineups WHERE edition_key = :edition_key),
    'Lineups source-scoped via StatsBomb bootstrap inicial', :materialized_at),
  (:edition_key, 'match_events', 'statsbomb_open_data', 'FULL_TOURNAMENT', 64,
    (SELECT count(DISTINCT internal_match_id) FROM silver.wc_match_events WHERE edition_key = :edition_key), NULL,
    (SELECT count(*) FROM silver.wc_match_events WHERE edition_key = :edition_key),
    'Eventos ricos preservados em silver sem derivacao estatistica', :materialized_at);
"""


INSERT_SOURCE_DIVERGENCES_SQL = """
INSERT INTO silver.wc_source_divergences (
  edition_key, entity_type, internal_id, source_left, source_right, divergence_type, field_name,
  left_value, right_value, severity, resolution_status, detected_at
)
WITH fj AS (
  SELECT
    f.internal_match_id,
    f.match_date::text AS match_date,
    f.home_team_internal_id,
    f.away_team_internal_id,
    f.stage_key,
    f.home_team_score,
    f.away_team_score
  FROM silver.wc_fixtures f
  WHERE f.edition_key = :edition_key
),
sb AS (
  SELECT
    pm_match.canonical_id AS internal_match_id,
    (m.payload->>'match_date')::text AS match_date,
    pm_home.canonical_id AS home_team_internal_id,
    pm_away.canonical_id AS away_team_internal_id,
    replace(pm_stage.canonical_id, 'stage__' || :edition_key || '__', '') AS stage_key,
    (m.payload->>'home_score')::integer AS home_team_score,
    (m.payload->>'away_score')::integer AS away_team_score
  FROM bronze.statsbomb_wc_matches m
  JOIN raw.provider_entity_map pm_match
    ON pm_match.provider = 'statsbomb_open_data'
   AND pm_match.entity_type = 'match'
   AND pm_match.source_id = m.match_id::text
   AND pm_match.edition_key = :edition_key
  JOIN raw.provider_entity_map pm_home
    ON pm_home.provider = 'statsbomb_open_data'
   AND pm_home.entity_type = 'team'
   AND pm_home.source_id = m.payload->'home_team'->>'home_team_id'
  JOIN raw.provider_entity_map pm_away
    ON pm_away.provider = 'statsbomb_open_data'
   AND pm_away.entity_type = 'team'
   AND pm_away.source_id = m.payload->'away_team'->>'away_team_id'
  JOIN raw.provider_entity_map pm_stage
    ON pm_stage.provider = 'statsbomb_open_data'
   AND pm_stage.entity_type = 'stage'
   AND pm_stage.source_id = :edition_key || '::stage::' || (m.payload->'competition_stage'->>'id')
   AND pm_stage.edition_key = :edition_key
  WHERE m.edition_key = :edition_key
),
cmp AS (
  SELECT
    fj.internal_match_id,
    sb.match_date AS sb_match_date,
    fj.match_date AS fj_match_date,
    sb.home_team_internal_id AS sb_home_team_internal_id,
    fj.home_team_internal_id AS fj_home_team_internal_id,
    sb.away_team_internal_id AS sb_away_team_internal_id,
    fj.away_team_internal_id AS fj_away_team_internal_id,
    sb.stage_key AS sb_stage_key,
    fj.stage_key AS fj_stage_key,
    sb.home_team_score AS sb_home_team_score,
    fj.home_team_score AS fj_home_team_score,
    sb.away_team_score AS sb_away_team_score,
    fj.away_team_score AS fj_away_team_score
  FROM fj
  JOIN sb ON sb.internal_match_id = fj.internal_match_id
)
SELECT :edition_key, 'match', internal_match_id, 'statsbomb_open_data', 'fjelstul_worldcup',
       'field_mismatch', 'match_date', to_jsonb(sb_match_date), to_jsonb(fj_match_date), 'blocking', 'open', :materialized_at
FROM cmp
WHERE sb_match_date IS DISTINCT FROM fj_match_date
UNION ALL
SELECT :edition_key, 'match', internal_match_id, 'statsbomb_open_data', 'fjelstul_worldcup',
       'field_mismatch', 'home_team_internal_id', to_jsonb(sb_home_team_internal_id), to_jsonb(fj_home_team_internal_id), 'blocking', 'open', :materialized_at
FROM cmp
WHERE sb_home_team_internal_id IS DISTINCT FROM fj_home_team_internal_id
UNION ALL
SELECT :edition_key, 'match', internal_match_id, 'statsbomb_open_data', 'fjelstul_worldcup',
       'field_mismatch', 'away_team_internal_id', to_jsonb(sb_away_team_internal_id), to_jsonb(fj_away_team_internal_id), 'blocking', 'open', :materialized_at
FROM cmp
WHERE sb_away_team_internal_id IS DISTINCT FROM fj_away_team_internal_id
UNION ALL
SELECT :edition_key, 'match', internal_match_id, 'statsbomb_open_data', 'fjelstul_worldcup',
       'field_mismatch', 'stage_key', to_jsonb(sb_stage_key), to_jsonb(fj_stage_key), 'blocking', 'open', :materialized_at
FROM cmp
WHERE sb_stage_key IS DISTINCT FROM fj_stage_key
UNION ALL
SELECT :edition_key, 'match', internal_match_id, 'statsbomb_open_data', 'fjelstul_worldcup',
       'field_mismatch', 'home_team_score', to_jsonb(sb_home_team_score), to_jsonb(fj_home_team_score), 'blocking', 'open', :materialized_at
FROM cmp
WHERE sb_home_team_score IS DISTINCT FROM fj_home_team_score
UNION ALL
SELECT :edition_key, 'match', internal_match_id, 'statsbomb_open_data', 'fjelstul_worldcup',
       'field_mismatch', 'away_team_score', to_jsonb(sb_away_team_score), to_jsonb(fj_away_team_score), 'blocking', 'open', :materialized_at
FROM cmp
WHERE sb_away_team_score IS DISTINCT FROM fj_away_team_score;
"""


def _materialize_silver(conn, config: WorldCupEditionConfig) -> None:
    params = {
        "edition_key": config.edition_key,
        "fjelstul_tournament_id": config.fjelstul_tournament_id,
        "materialized_at": _utc_now(),
    }
    conn.execute(text(INSERT_STAGES_SQL), params)
    conn.execute(text(INSERT_GROUPS_SQL), params)
    conn.execute(text(INSERT_GROUP_STANDINGS_SQL), params)
    conn.execute(text(INSERT_FIXTURES_SQL), params)
    conn.execute(text(INSERT_LINEUPS_SQL), params)
    conn.execute(text(INSERT_MATCH_EVENTS_SQL), params)
    conn.execute(text(INSERT_COVERAGE_MANIFEST_SQL), params)
    conn.execute(text(INSERT_SOURCE_DIVERGENCES_SQL), params)


def _validate_silver_outputs(conn, config: WorldCupEditionConfig) -> dict[str, Any]:
    results: dict[str, Any] = {}

    results["fixtures"] = conn.execute(
        text("SELECT count(*) FROM silver.wc_fixtures WHERE edition_key = :edition_key"),
        {"edition_key": config.edition_key},
    ).scalar_one()
    if results["fixtures"] != config.expected_matches:
        raise RuntimeError(
            f"silver.wc_fixtures invalido: esperado={config.expected_matches} atual={results['fixtures']}"
        )

    stage_nulls = conn.execute(
        text(
            """
            SELECT count(*)
            FROM silver.wc_fixtures
            WHERE edition_key = :edition_key
              AND stage_key IS NULL
            """
        ),
        {"edition_key": config.edition_key},
    ).scalar_one()
    if stage_nulls != 0:
        raise RuntimeError(f"silver.wc_fixtures tem stage_key nulo: {stage_nulls}")
    results["fixtures_stage_key_nulls"] = stage_nulls

    group_nulls = conn.execute(
        text(
            """
            SELECT count(*)
            FROM silver.wc_fixtures
            WHERE edition_key = :edition_key
              AND stage_key = 'group_stage_1'
              AND group_key IS NULL
            """
        ),
        {"edition_key": config.edition_key},
    ).scalar_one()
    if group_nulls != 0:
        raise RuntimeError(f"silver.wc_fixtures tem group_key nulo na fase de grupos: {group_nulls}")
    results["fixtures_group_key_nulls"] = group_nulls

    standings_duplicates = conn.execute(
        text(
            """
            SELECT count(*)
            FROM (
              SELECT edition_key, stage_key, group_key, team_internal_id, count(*) AS row_count
              FROM silver.wc_group_standings
              WHERE edition_key = :edition_key
              GROUP BY 1,2,3,4
              HAVING count(*) > 1
            ) dup
            """
        ),
        {"edition_key": config.edition_key},
    ).scalar_one()
    if standings_duplicates != 0:
        raise RuntimeError(f"silver.wc_group_standings com grão duplicado: {standings_duplicates}")
    results["group_standings_duplicates"] = standings_duplicates

    lineup_bad_matches = conn.execute(
        text(
            """
            SELECT count(*)
            FROM (
              SELECT internal_match_id
              FROM silver.wc_lineups
              WHERE edition_key = :edition_key
              GROUP BY internal_match_id
              HAVING count(DISTINCT team_internal_id) <> 2
            ) bad
            """
        ),
        {"edition_key": config.edition_key},
    ).scalar_one()
    if lineup_bad_matches != 0:
        raise RuntimeError(f"silver.wc_lineups com match sem 2 times: {lineup_bad_matches}")
    results["lineup_bad_matches"] = lineup_bad_matches

    lineup_bad_starters = conn.execute(
        text(
            """
            SELECT count(*)
            FROM (
              SELECT internal_match_id, team_internal_id
              FROM silver.wc_lineups
              WHERE edition_key = :edition_key
              GROUP BY internal_match_id, team_internal_id
              HAVING count(*) FILTER (WHERE is_starter = TRUE) <> 11
            ) bad
            """
        ),
        {"edition_key": config.edition_key},
    ).scalar_one()
    if lineup_bad_starters != 0:
        raise RuntimeError(f"silver.wc_lineups com contagem de titulares invalida: {lineup_bad_starters}")
    results["lineup_bad_starters"] = lineup_bad_starters

    event_matches = conn.execute(
        text(
            """
            SELECT count(DISTINCT internal_match_id)
            FROM silver.wc_match_events
            WHERE edition_key = :edition_key
            """
        ),
        {"edition_key": config.edition_key},
    ).scalar_one()
    if event_matches != config.expected_statsbomb_event_match_files:
        raise RuntimeError(
            "silver.wc_match_events cobre matches invalidos: "
            f"esperado={config.expected_statsbomb_event_match_files} atual={event_matches}"
        )
    results["event_matches"] = event_matches

    blocking_divergences = conn.execute(
        text(
            """
            SELECT count(*)
            FROM silver.wc_source_divergences
            WHERE edition_key = :edition_key
              AND severity = 'blocking'
            """
        ),
        {"edition_key": config.edition_key},
    ).scalar_one()
    if blocking_divergences != 0:
        raise RuntimeError(f"silver.wc_source_divergences tem blockers: {blocking_divergences}")
    results["blocking_divergences"] = blocking_divergences

    manifest_full_tournament_mismatches = conn.execute(
        text(
            """
            SELECT count(*)
            FROM silver.wc_coverage_manifest
            WHERE edition_key = :edition_key
              AND coverage_status = 'FULL_TOURNAMENT'
              AND (
                (expected_match_count IS NOT NULL AND expected_match_count <> actual_match_count)
                OR (expected_row_count IS NOT NULL AND expected_row_count <> actual_row_count)
              )
            """
        ),
        {"edition_key": config.edition_key},
    ).scalar_one()
    if manifest_full_tournament_mismatches != 0:
        raise RuntimeError(
            f"silver.wc_coverage_manifest tem linhas FULL_TOURNAMENT inconsistentes: {manifest_full_tournament_mismatches}"
        )
    results["coverage_mismatches"] = manifest_full_tournament_mismatches

    results["stages"] = conn.execute(
        text("SELECT count(*) FROM silver.wc_stages WHERE edition_key = :edition_key"),
        {"edition_key": config.edition_key},
    ).scalar_one()
    results["groups"] = conn.execute(
        text("SELECT count(*) FROM silver.wc_groups WHERE edition_key = :edition_key"),
        {"edition_key": config.edition_key},
    ).scalar_one()
    results["group_standings"] = conn.execute(
        text("SELECT count(*) FROM silver.wc_group_standings WHERE edition_key = :edition_key"),
        {"edition_key": config.edition_key},
    ).scalar_one()
    results["lineups"] = conn.execute(
        text("SELECT count(*) FROM silver.wc_lineups WHERE edition_key = :edition_key"),
        {"edition_key": config.edition_key},
    ).scalar_one()
    results["match_events"] = conn.execute(
        text("SELECT count(*) FROM silver.wc_match_events WHERE edition_key = :edition_key"),
        {"edition_key": config.edition_key},
    ).scalar_one()
    results["coverage_rows"] = conn.execute(
        text("SELECT count(*) FROM silver.wc_coverage_manifest WHERE edition_key = :edition_key"),
        {"edition_key": config.edition_key},
    ).scalar_one()
    results["divergence_rows"] = conn.execute(
        text("SELECT count(*) FROM silver.wc_source_divergences WHERE edition_key = :edition_key"),
        {"edition_key": config.edition_key},
    ).scalar_one()

    return results


def normalize_world_cup_to_silver(edition_key: str | None = None) -> dict[str, Any]:
    context = get_current_context()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    config = (
        get_world_cup_edition_config(edition_key)
        if edition_key
        else get_world_cup_edition_config_from_context(default=DEFAULT_WORLD_CUP_EDITION_KEY)
    )

    with StepMetrics(
        service="airflow",
        module="world_cup_silver_service",
        step="normalize_world_cup_to_silver",
        context=context,
        dataset=f"silver.world_cup_{config.season_label}",
        table="silver.*",
    ):
        snapshots = fetch_active_world_cup_snapshots(engine, edition_key=config.edition_key)
        with engine.begin() as conn:
            _validate_prerequisites(conn, snapshots, config)
            _delete_edition_rows(conn, config)
            _materialize_silver(conn, config)
            summary = _validate_silver_outputs(conn, config)

    log_event(
        service="airflow",
        module="world_cup_silver_service",
        step="summary",
        status="success",
        context=context,
        dataset=f"silver.world_cup_{config.season_label}",
        row_count=sum(
            summary[key]
            for key in ("fixtures", "stages", "groups", "group_standings", "lineups", "match_events", "coverage_rows", "divergence_rows")
        ),
        message=(
            "Silver World Cup concluido | "
            f"edition={config.edition_key} | "
            f"fixtures={summary['fixtures']} | "
            f"stages={summary['stages']} | "
            f"groups={summary['groups']} | "
            f"group_standings={summary['group_standings']} | "
            f"lineups={summary['lineups']} | "
            f"match_events={summary['match_events']} | "
            f"coverage_rows={summary['coverage_rows']} | "
            f"divergence_rows={summary['divergence_rows']}"
        ),
    )
    return summary


def normalize_world_cup_2022_to_silver() -> dict[str, Any]:
    return normalize_world_cup_to_silver(DEFAULT_WORLD_CUP_EDITION_KEY)
