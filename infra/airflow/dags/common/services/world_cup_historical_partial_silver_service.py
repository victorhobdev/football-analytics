from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.observability import StepMetrics, log_event
from common.services.world_cup_config import DEFAULT_WORLD_CUP_EDITION_KEY, FJELSTUL_SOURCE

WORLD_CUP_EDITION_PATTERN = "fifa_world_cup_mens__%"
WORLD_CUP_2018_EDITION_KEY = "fifa_world_cup_mens__2018"


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
        "edition_2018": WORLD_CUP_2018_EDITION_KEY,
        "edition_2022": DEFAULT_WORLD_CUP_EDITION_KEY,
        "source_name": FJELSTUL_SOURCE,
        "materialized_at": materialized_at,
    }


def _validate_prerequisites(conn) -> None:
    checks = {
        "historical_fixtures_editions": (
            """
            SELECT count(DISTINCT edition_key)
            FROM silver.wc_fixtures
            WHERE edition_key LIKE :edition_pattern
              AND edition_key <> :edition_2018
              AND edition_key <> :edition_2022
            """,
            20,
        ),
        "historical_player_map": (
            """
            SELECT count(*)
            FROM raw.provider_entity_map
            WHERE provider = :source_name
              AND entity_type = 'player'
            """,
            None,
        ),
        "historical_player_appearance_editions": (
            """
            SELECT count(DISTINCT edition_key)
            FROM bronze.fjelstul_wc_player_appearances
            WHERE edition_key LIKE :edition_pattern
              AND edition_key <> :edition_2018
              AND edition_key <> :edition_2022
            """,
            12,
        ),
        "historical_goal_editions": (
            """
            SELECT count(DISTINCT edition_key)
            FROM bronze.fjelstul_wc_goals
            WHERE edition_key LIKE :edition_pattern
              AND edition_key <> :edition_2018
              AND edition_key <> :edition_2022
            """,
            20,
        ),
    }
    for name, (sql, expected) in checks.items():
        actual = conn.execute(text(sql), _params(_utc_now())).scalar_one()
        if expected is None:
            if int(actual) <= 0:
                raise RuntimeError(f"Precondicao historica invalida para {name}: atual={actual}")
        elif int(actual) != expected:
            raise RuntimeError(f"Precondicao historica invalida para {name}: esperado={expected} atual={actual}")


def _delete_previous_rows(conn) -> None:
    params = _params(_utc_now())
    conn.execute(
        text(
            """
            DELETE FROM silver.wc_lineups
            WHERE source_name = :source_name
              AND edition_key LIKE :edition_pattern
              AND edition_key <> :edition_2018
              AND edition_key <> :edition_2022
            """
        ),
        params,
    )
    conn.execute(
        text(
            """
            DELETE FROM silver.wc_match_events
            WHERE source_name = :source_name
              AND edition_key LIKE :edition_pattern
              AND edition_key <> :edition_2018
              AND edition_key <> :edition_2022
            """
        ),
        params,
    )
    conn.execute(
        text(
            """
            DELETE FROM silver.wc_coverage_manifest
            WHERE source_name = :source_name
              AND domain_name IN ('lineups', 'match_events')
              AND edition_key LIKE :edition_pattern
              AND edition_key <> :edition_2018
              AND edition_key <> :edition_2022
            """
        ),
        params,
    )


INSERT_HISTORICAL_LINEUPS_SQL = """
INSERT INTO silver.wc_lineups (
  edition_key, internal_match_id, team_internal_id, player_internal_id, source_name, source_version,
  source_match_id, source_team_id, source_player_id, team_name, player_name, player_nickname,
  jersey_number, is_starter, start_reason, first_position_name, first_position_id, payload, materialized_at
)
SELECT
  a.edition_key,
  pm_match.canonical_id AS internal_match_id,
  pm_team.canonical_id AS team_internal_id,
  pm_player.canonical_id AS player_internal_id,
  a.source_name,
  a.source_version,
  a.match_id AS source_match_id,
  a.team_id AS source_team_id,
  a.player_id AS source_player_id,
  a.team_name,
  NULLIF(trim(concat_ws(' ', NULLIF(a.given_name, ''), NULLIF(a.family_name, ''))), '') AS player_name,
  NULL::text AS player_nickname,
  NULLIF(NULLIF(a.shirt_number, ''), '0')::integer AS jersey_number,
  CASE a.starter WHEN '1' THEN TRUE ELSE FALSE END AS is_starter,
  CASE
    WHEN a.starter = '1' THEN 'Starting XI'
    WHEN a.substitute = '1' THEN 'Substitute'
    ELSE NULL
  END AS start_reason,
  NULLIF(a.position_name, '') AS first_position_name,
  NULL::integer AS first_position_id,
  jsonb_build_object(
    'dataset', 'player_appearances',
    'coverage_tier', 'historical_partial_domain',
    'source_payload', a.payload
  ) AS payload,
  :materialized_at
FROM bronze.fjelstul_wc_player_appearances a
JOIN raw.provider_entity_map pm_match
  ON pm_match.provider = 'fjelstul_worldcup'
 AND pm_match.entity_type = 'match'
 AND pm_match.source_id = a.match_id
 AND pm_match.edition_key = a.edition_key
JOIN raw.provider_entity_map pm_team
  ON pm_team.provider = 'fjelstul_worldcup'
 AND pm_team.entity_type = 'team'
 AND pm_team.source_id = a.team_id
JOIN raw.provider_entity_map pm_player
  ON pm_player.provider = 'fjelstul_worldcup'
 AND pm_player.entity_type = 'player'
 AND pm_player.source_id = a.player_id
WHERE a.edition_key LIKE :edition_pattern
  AND a.edition_key <> :edition_2018
  AND a.edition_key <> :edition_2022
"""


INSERT_HISTORICAL_MATCH_EVENTS_SQL = """
WITH goal_rows AS (
  SELECT
    g.edition_key,
    pm_match.canonical_id AS internal_match_id,
    g.source_name,
    g.source_version,
    g.match_id AS source_match_id,
    'goal::' || COALESCE(g.goal_id, g.key_id) AS source_event_id,
    pm_team.canonical_id AS team_internal_id,
    pm_player.canonical_id AS player_internal_id,
    NULL::integer AS event_type_id,
    'goal'::text AS event_type,
    CASE lower(g.payload->>'match_period')
      WHEN 'first half' THEN 1
      WHEN 'second half' THEN 2
      WHEN 'first period of extra time' THEN 3
      WHEN 'second period of extra time' THEN 4
      ELSE NULL
    END AS period,
    NULLIF(g.payload->>'minute_regulation', '')::integer AS minute,
    NULL::numeric AS second,
    g.payload->>'minute_label' AS timestamp_label,
    NULL::integer AS possession,
    NULL::text AS play_pattern,
    NULL::numeric AS location_x,
    NULL::numeric AS location_y,
    FALSE AS has_three_sixty_frame,
    jsonb_build_object(
      'dataset', 'goals',
      'goal_id', g.goal_id,
      'penalty', COALESCE(g.payload->>'penalty', '0') = '1',
      'own_goal', COALESCE(g.payload->>'own_goal', '0') = '1',
      'coverage_tier', 'historical_partial_domain',
      'source_payload', g.payload
    ) AS payload,
    COALESCE(NULLIF(g.payload->>'minute_stoppage', '')::integer, 0) AS minute_stoppage,
    1 AS event_priority
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
  LEFT JOIN raw.provider_entity_map pm_player
    ON pm_player.provider = 'fjelstul_worldcup'
   AND pm_player.entity_type = 'player'
   AND pm_player.source_id = g.player_id
  WHERE g.edition_key LIKE :edition_pattern
    AND g.edition_key <> :edition_2018
    AND g.edition_key <> :edition_2022
),
booking_rows AS (
  SELECT
    b.edition_key,
    pm_match.canonical_id AS internal_match_id,
    b.source_name,
    b.source_version,
    b.match_id AS source_match_id,
    'booking::' || COALESCE(b.booking_id, b.key_id) AS source_event_id,
    pm_team.canonical_id AS team_internal_id,
    pm_player.canonical_id AS player_internal_id,
    NULL::integer AS event_type_id,
    CASE
      WHEN COALESCE(b.payload->>'second_yellow_card', '0') = '1' THEN 'second_yellow_red'
      WHEN COALESCE(b.payload->>'red_card', '0') = '1' OR COALESCE(b.payload->>'sending_off', '0') = '1' THEN 'red_card'
      ELSE 'yellow_card'
    END AS event_type,
    CASE lower(b.payload->>'match_period')
      WHEN 'first half' THEN 1
      WHEN 'second half' THEN 2
      WHEN 'first period of extra time' THEN 3
      WHEN 'second period of extra time' THEN 4
      ELSE NULL
    END AS period,
    NULLIF(b.payload->>'minute_regulation', '')::integer AS minute,
    NULL::numeric AS second,
    b.payload->>'minute_label' AS timestamp_label,
    NULL::integer AS possession,
    NULL::text AS play_pattern,
    NULL::numeric AS location_x,
    NULL::numeric AS location_y,
    FALSE AS has_three_sixty_frame,
    jsonb_build_object(
      'dataset', 'bookings',
      'booking_id', b.booking_id,
      'yellow_card', COALESCE(b.payload->>'yellow_card', '0') = '1',
      'red_card', COALESCE(b.payload->>'red_card', '0') = '1',
      'second_yellow_card', COALESCE(b.payload->>'second_yellow_card', '0') = '1',
      'sending_off', COALESCE(b.payload->>'sending_off', '0') = '1',
      'coverage_tier', 'historical_partial_domain',
      'source_payload', b.payload
    ) AS payload,
    COALESCE(NULLIF(b.payload->>'minute_stoppage', '')::integer, 0) AS minute_stoppage,
    2 AS event_priority
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
  LEFT JOIN raw.provider_entity_map pm_player
    ON pm_player.provider = 'fjelstul_worldcup'
   AND pm_player.entity_type = 'player'
   AND pm_player.source_id = b.player_id
  WHERE b.edition_key LIKE :edition_pattern
    AND b.edition_key <> :edition_2018
    AND b.edition_key <> :edition_2022
),
substitution_rows AS (
  SELECT
    s.edition_key,
    pm_match.canonical_id AS internal_match_id,
    s.source_name,
    s.source_version,
    s.match_id AS source_match_id,
    'substitution::' || COALESCE(s.substitution_id, s.key_id) AS source_event_id,
    pm_team.canonical_id AS team_internal_id,
    pm_player.canonical_id AS player_internal_id,
    NULL::integer AS event_type_id,
    'substitution'::text AS event_type,
    CASE lower(s.payload->>'match_period')
      WHEN 'first half' THEN 1
      WHEN 'second half' THEN 2
      WHEN 'first period of extra time' THEN 3
      WHEN 'second period of extra time' THEN 4
      ELSE NULL
    END AS period,
    NULLIF(s.payload->>'minute_regulation', '')::integer AS minute,
    NULL::numeric AS second,
    s.payload->>'minute_label' AS timestamp_label,
    NULL::integer AS possession,
    NULL::text AS play_pattern,
    NULL::numeric AS location_x,
    NULL::numeric AS location_y,
    FALSE AS has_three_sixty_frame,
    jsonb_build_object(
      'dataset', 'substitutions',
      'substitution_id', s.substitution_id,
      'going_off', COALESCE(s.payload->>'going_off', '0') = '1',
      'coming_on', COALESCE(s.payload->>'coming_on', '0') = '1',
      'coverage_tier', 'historical_partial_domain',
      'source_payload', s.payload
    ) AS payload,
    COALESCE(NULLIF(s.payload->>'minute_stoppage', '')::integer, 0) AS minute_stoppage,
    3 AS event_priority
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
  LEFT JOIN raw.provider_entity_map pm_player
    ON pm_player.provider = 'fjelstul_worldcup'
   AND pm_player.entity_type = 'player'
   AND pm_player.source_id = s.player_id
  WHERE s.edition_key LIKE :edition_pattern
    AND s.edition_key <> :edition_2018
    AND s.edition_key <> :edition_2022
),
unified AS (
  SELECT * FROM goal_rows
  UNION ALL
  SELECT * FROM booking_rows
  UNION ALL
  SELECT * FROM substitution_rows
)
INSERT INTO silver.wc_match_events (
  edition_key, internal_match_id, source_name, source_version, source_match_id, source_event_id, event_index,
  team_internal_id, player_internal_id, event_type_id, event_type, period, minute, second,
  timestamp_label, possession, play_pattern, location_x, location_y, has_three_sixty_frame, payload, materialized_at
)
SELECT
  edition_key,
  internal_match_id,
  source_name,
  source_version,
  source_match_id,
  source_event_id,
  row_number() OVER (
    PARTITION BY edition_key, source_match_id
    ORDER BY minute NULLS LAST, minute_stoppage NULLS LAST, event_priority, source_event_id
  )::integer AS event_index,
  team_internal_id,
  player_internal_id,
  event_type_id,
  event_type,
  period,
  minute,
  second,
  timestamp_label,
  possession,
  play_pattern,
  location_x,
  location_y,
  has_three_sixty_frame,
  payload,
  :materialized_at
FROM unified
"""


INSERT_HISTORICAL_COVERAGE_SQL = """
WITH fixture_base AS (
  SELECT
    edition_key,
    substring(edition_key from '([0-9]{4})$')::integer AS edition_year,
    count(*) AS expected_match_count
  FROM silver.wc_fixtures
  WHERE edition_key LIKE :edition_pattern
    AND edition_key <> :edition_2018
    AND edition_key <> :edition_2022
  GROUP BY edition_key
),
lineup_actual AS (
  SELECT
    edition_key,
    count(DISTINCT internal_match_id) AS actual_match_count,
    count(*) AS actual_row_count
  FROM silver.wc_lineups
  WHERE source_name = :source_name
    AND edition_key LIKE :edition_pattern
    AND edition_key <> :edition_2018
    AND edition_key <> :edition_2022
  GROUP BY edition_key
),
event_actual AS (
  SELECT
    edition_key,
    count(DISTINCT internal_match_id) AS actual_match_count,
    count(*) AS actual_row_count
  FROM silver.wc_match_events
  WHERE source_name = :source_name
    AND edition_key LIKE :edition_pattern
    AND edition_key <> :edition_2018
    AND edition_key <> :edition_2022
  GROUP BY edition_key
)
INSERT INTO silver.wc_coverage_manifest (
  edition_key, domain_name, source_name, coverage_status,
  expected_match_count, actual_match_count, expected_row_count, actual_row_count, notes, computed_at
)
SELECT
  fb.edition_key,
  'lineups',
  :source_name,
  CASE
    WHEN fb.edition_year >= 1970 THEN 'PARTIAL_DOMAIN'
    ELSE 'PROVIDER_COVERAGE_GAP'
  END,
  fb.expected_match_count::integer,
  COALESCE(la.actual_match_count, 0)::integer,
  NULL::integer,
  COALESCE(la.actual_row_count, 0)::integer,
  CASE
    WHEN fb.edition_year >= 1970 THEN 'Lineups historicos parciais a partir de player_appearances do Fjelstul; cobertura de partidas completa, mas sem riqueza tática do StatsBomb.'
    ELSE 'Pre-1970 sem player_appearances no Fjelstul; gap explicito de lineup historico.'
  END,
  :materialized_at
FROM fixture_base fb
LEFT JOIN lineup_actual la
  ON la.edition_key = fb.edition_key
UNION ALL
SELECT
  fb.edition_key,
  'match_events',
  :source_name,
  CASE
    WHEN fb.edition_year >= 1970 THEN 'PARTIAL_DOMAIN'
    ELSE 'PROVIDER_COVERAGE_GAP'
  END,
  fb.expected_match_count::integer,
  COALESCE(ea.actual_match_count, 0)::integer,
  NULL::integer,
  COALESCE(ea.actual_row_count, 0)::integer,
  CASE
    WHEN fb.edition_year >= 1970 THEN 'Eventos discretos historicos via goals/bookings/substitutions do Fjelstul; sem completude observacional rica.'
    ELSE 'Pre-1970 com goals historicos no Fjelstul, mas sem bookings/substitutions; gap explicito de coverage.'
  END,
  :materialized_at
FROM fixture_base fb
LEFT JOIN event_actual ea
  ON ea.edition_key = fb.edition_key
"""


def _materialize_historical_partial_silver(conn) -> None:
    params = _params(_utc_now())
    conn.execute(text(INSERT_HISTORICAL_LINEUPS_SQL), params)
    conn.execute(text(INSERT_HISTORICAL_MATCH_EVENTS_SQL), params)
    conn.execute(text(INSERT_HISTORICAL_COVERAGE_SQL), params)


def _validate_outputs(conn) -> dict[str, Any]:
    params = _params(_utc_now())
    expected_lineup_rows = conn.execute(
        text(
            """
            SELECT count(*)
            FROM bronze.fjelstul_wc_player_appearances a
            WHERE a.edition_key LIKE :edition_pattern
              AND a.edition_key <> :edition_2018
              AND a.edition_key <> :edition_2022
            """
        ),
        params,
    ).scalar_one()
    expected_lineup_editions = conn.execute(
        text(
            """
            SELECT count(DISTINCT edition_key)
            FROM bronze.fjelstul_wc_player_appearances a
            WHERE a.edition_key LIKE :edition_pattern
              AND a.edition_key <> :edition_2018
              AND a.edition_key <> :edition_2022
            """
        ),
        params,
    ).scalar_one()
    expected_event_rows = conn.execute(
        text(
            """
            SELECT
              (SELECT count(*) FROM bronze.fjelstul_wc_goals
               WHERE edition_key LIKE :edition_pattern
                 AND edition_key <> :edition_2018
                 AND edition_key <> :edition_2022)
              +
              (SELECT count(*) FROM bronze.fjelstul_wc_bookings
               WHERE edition_key LIKE :edition_pattern
                 AND edition_key <> :edition_2018
                 AND edition_key <> :edition_2022)
              +
              (SELECT count(*) FROM bronze.fjelstul_wc_substitutions
               WHERE edition_key LIKE :edition_pattern
                 AND edition_key <> :edition_2018
                 AND edition_key <> :edition_2022)
            """
        ),
        params,
    ).scalar_one()
    expected_event_editions = conn.execute(
        text(
            """
            SELECT count(DISTINCT edition_key)
            FROM bronze.fjelstul_wc_goals
            WHERE edition_key LIKE :edition_pattern
              AND edition_key <> :edition_2018
              AND edition_key <> :edition_2022
            """
        ),
        params,
    ).scalar_one()

    results = {
        "lineup_rows": conn.execute(
            text(
                """
                SELECT count(*)
                FROM silver.wc_lineups
                WHERE source_name = :source_name
                  AND edition_key LIKE :edition_pattern
                  AND edition_key <> :edition_2018
                  AND edition_key <> :edition_2022
                """
            ),
            params,
        ).scalar_one(),
        "lineup_editions": conn.execute(
            text(
                """
                SELECT count(DISTINCT edition_key)
                FROM silver.wc_lineups
                WHERE source_name = :source_name
                  AND edition_key LIKE :edition_pattern
                  AND edition_key <> :edition_2018
                  AND edition_key <> :edition_2022
                """
            ),
            params,
        ).scalar_one(),
        "event_rows": conn.execute(
            text(
                """
                SELECT count(*)
                FROM silver.wc_match_events
                WHERE source_name = :source_name
                  AND edition_key LIKE :edition_pattern
                  AND edition_key <> :edition_2018
                  AND edition_key <> :edition_2022
                """
            ),
            params,
        ).scalar_one(),
        "event_editions": conn.execute(
            text(
                """
                SELECT count(DISTINCT edition_key)
                FROM silver.wc_match_events
                WHERE source_name = :source_name
                  AND edition_key LIKE :edition_pattern
                  AND edition_key <> :edition_2018
                  AND edition_key <> :edition_2022
                """
            ),
            params,
        ).scalar_one(),
        "lineup_duplicates": conn.execute(
            text(
                """
                SELECT count(*)
                FROM (
                  SELECT edition_key, internal_match_id, team_internal_id, player_internal_id, count(*) AS row_count
                  FROM silver.wc_lineups
                  WHERE source_name = :source_name
                    AND edition_key LIKE :edition_pattern
                    AND edition_key <> :edition_2018
                    AND edition_key <> :edition_2022
                  GROUP BY 1,2,3,4
                  HAVING count(*) > 1
                ) dup
                """
            ),
            params,
        ).scalar_one(),
        "event_duplicates": conn.execute(
            text(
                """
                SELECT count(*)
                FROM (
                  SELECT edition_key, source_name, source_match_id, source_event_id, count(*) AS row_count
                  FROM silver.wc_match_events
                  WHERE source_name = :source_name
                    AND edition_key LIKE :edition_pattern
                    AND edition_key <> :edition_2018
                    AND edition_key <> :edition_2022
                  GROUP BY 1,2,3,4
                  HAVING count(*) > 1
                ) dup
                """
            ),
            params,
        ).scalar_one(),
        "pre1970_lineup_rows": conn.execute(
            text(
                """
                SELECT count(*)
                FROM silver.wc_lineups
                WHERE source_name = :source_name
                  AND edition_key LIKE 'fifa_world_cup_mens__19%'
                  AND substring(edition_key from '([0-9]{4})$')::integer < 1970
                """
            ),
            params,
        ).scalar_one(),
        "rich_lineup_contamination": conn.execute(
            text(
                """
                SELECT count(*)
                FROM silver.wc_lineups
                WHERE source_name = :source_name
                  AND (
                    edition_key = :edition_2018
                    OR edition_key = :edition_2022
                  )
                """
            ),
            params,
        ).scalar_one(),
        "rich_event_contamination": conn.execute(
            text(
                """
                SELECT count(*)
                FROM silver.wc_match_events
                WHERE source_name = :source_name
                  AND (
                    edition_key = :edition_2018
                    OR edition_key = :edition_2022
                  )
                """
            ),
            params,
        ).scalar_one(),
        "lineup_coverage_rows": conn.execute(
            text(
                """
                SELECT count(*)
                FROM silver.wc_coverage_manifest
                WHERE source_name = :source_name
                  AND domain_name = 'lineups'
                  AND edition_key LIKE :edition_pattern
                  AND edition_key <> :edition_2018
                  AND edition_key <> :edition_2022
                """
            ),
            params,
        ).scalar_one(),
        "event_coverage_rows": conn.execute(
            text(
                """
                SELECT count(*)
                FROM silver.wc_coverage_manifest
                WHERE source_name = :source_name
                  AND domain_name = 'match_events'
                  AND edition_key LIKE :edition_pattern
                  AND edition_key <> :edition_2018
                  AND edition_key <> :edition_2022
                """
            ),
            params,
        ).scalar_one(),
        "lineup_gap_rows": conn.execute(
            text(
                """
                SELECT count(*)
                FROM silver.wc_coverage_manifest
                WHERE source_name = :source_name
                  AND domain_name = 'lineups'
                  AND coverage_status = 'PROVIDER_COVERAGE_GAP'
                  AND edition_key LIKE :edition_pattern
                  AND edition_key <> :edition_2018
                  AND edition_key <> :edition_2022
                """
            ),
            params,
        ).scalar_one(),
        "event_gap_rows": conn.execute(
            text(
                """
                SELECT count(*)
                FROM silver.wc_coverage_manifest
                WHERE source_name = :source_name
                  AND domain_name = 'match_events'
                  AND coverage_status = 'PROVIDER_COVERAGE_GAP'
                  AND edition_key LIKE :edition_pattern
                  AND edition_key <> :edition_2018
                  AND edition_key <> :edition_2022
                """
            ),
            params,
        ).scalar_one(),
    }

    expected_gap_rows = 8
    if int(results["lineup_rows"]) != int(expected_lineup_rows):
        raise RuntimeError(
            f"silver.wc_lineups historico parcial invalido: esperado={expected_lineup_rows} atual={results['lineup_rows']}"
        )
    if int(results["lineup_editions"]) != int(expected_lineup_editions):
        raise RuntimeError(
            f"silver.wc_lineups historico parcial invalido em edicoes: esperado={expected_lineup_editions} atual={results['lineup_editions']}"
        )
    if int(results["event_rows"]) != int(expected_event_rows):
        raise RuntimeError(
            f"silver.wc_match_events historico parcial invalido: esperado={expected_event_rows} atual={results['event_rows']}"
        )
    if int(results["event_editions"]) != int(expected_event_editions):
        raise RuntimeError(
            f"silver.wc_match_events historico parcial invalido em edicoes: esperado={expected_event_editions} atual={results['event_editions']}"
        )
    for key in (
        "lineup_duplicates",
        "event_duplicates",
        "pre1970_lineup_rows",
        "rich_lineup_contamination",
        "rich_event_contamination",
    ):
        if int(results[key]) != 0:
            raise RuntimeError(f"Silver historico parcial invalido para {key}: atual={results[key]}")
    if int(results["lineup_coverage_rows"]) != 20 or int(results["event_coverage_rows"]) != 20:
        raise RuntimeError(
            "silver.wc_coverage_manifest historico parcial invalido: "
            f"lineups={results['lineup_coverage_rows']} match_events={results['event_coverage_rows']}"
        )
    if int(results["lineup_gap_rows"]) != expected_gap_rows or int(results["event_gap_rows"]) != expected_gap_rows:
        raise RuntimeError(
            "silver.wc_coverage_manifest historico parcial com gaps inesperados: "
            f"lineups_gap={results['lineup_gap_rows']} match_events_gap={results['event_gap_rows']}"
        )
    return results


def normalize_world_cup_historical_partial_silver() -> dict[str, Any]:
    context = get_current_context()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    with StepMetrics(
        service="airflow",
        module="world_cup_historical_partial_silver_service",
        step="normalize_world_cup_historical_partial_silver",
        context=context,
        dataset="silver.world_cup_historical_partial",
        table="silver.wc_lineups/silver.wc_match_events/silver.wc_coverage_manifest",
    ):
        with engine.begin() as conn:
            _validate_prerequisites(conn)
            _delete_previous_rows(conn)
            _materialize_historical_partial_silver(conn)
            summary = _validate_outputs(conn)

    log_event(
        service="airflow",
        module="world_cup_historical_partial_silver_service",
        step="summary",
        status="success",
        context=context,
        dataset="silver.world_cup_historical_partial",
        row_count=int(summary["lineup_rows"]) + int(summary["event_rows"]),
        message=(
            "Silver historico parcial da Copa concluido | "
            f"lineup_rows={summary['lineup_rows']} | "
            f"event_rows={summary['event_rows']} | "
            f"lineup_editions={summary['lineup_editions']} | "
            f"event_editions={summary['event_editions']}"
        ),
    )
    return summary
