from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DSN = "postgresql://football:football@127.0.0.1:5432/football_dw"


def _dsn() -> str:
    return (
        os.getenv("FOOTBALL_PG_DSN")
        or os.getenv("DATABASE_URL")
        or DEFAULT_DSN
    )


def _fetch_one(conn: psycopg.Connection[Any], query: str) -> dict[str, Any]:
    with conn.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()
    return dict(row) if row else {}


def _fetch_all(conn: psycopg.Connection[Any], query: str) -> list[dict[str, Any]]:
    with conn.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def build_report(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    published = _fetch_one(
        conn,
        """
        select
          (select count(*) from mart.fact_matches) as published_matches,
          (select count(distinct player_id) from mart.dim_player) as published_players,
          (select count(distinct competition_key) from mart.fact_matches where competition_key is not null) as published_competitions,
          (select count(distinct (competition_key, season_label)) from mart.fact_matches where competition_key is not null) as published_competition_seasons;
        """,
    )
    raw_totals = _fetch_all(
        conn,
        """
        select 'raw.tm_games' as source_name, count(*)::bigint as rows_count from raw.tm_games
        union all
        select 'raw.tm_players', count(*)::bigint from raw.tm_players
        union all
        select 'raw.elo_matches', count(*)::bigint from raw.elo_matches
        union all
        select 'raw.statsbomb_matches', count(*)::bigint from raw.statsbomb_matches
        union all
        select 'raw.brasileirao_matches', count(*)::bigint from raw.brasileirao_matches
        order by source_name;
        """,
    )
    match_audit = _fetch_all(
        conn,
        """
        select
          source,
          review_status,
          identity_status,
          count(*)::bigint as rows_count
        from control.v_match_reconciliation_audit
        group by source, review_status, identity_status
        order by source, review_status, identity_status;
        """,
    )
    player_audit = _fetch_all(
        conn,
        """
        select
          source,
          review_status,
          identity_status,
          count(*)::bigint as rows_count
        from control.v_player_reconciliation_audit
        group by source, review_status, identity_status
        order by source, review_status, identity_status;
        """,
    )
    pending_queue = _fetch_all(
        conn,
        """
        select
          entity_type,
          status,
          count(*)::bigint as rows_count
        from control.entity_reconciliation_review_queue
        group by entity_type, status
        order by entity_type, status;
        """,
    )
    external_publication = _fetch_all(
        conn,
        """
        select
          source,
          publication_status,
          count(*)::bigint as rows_count
        from control.external_match_publication_xref
        group by source, publication_status
        order by source, publication_status;
        """,
    )
    depth_facts = _fetch_one(
        conn,
        """
        select
          case
            when to_regclass('mart.fact_match_odds') is not null
              then (select count(*) from mart.fact_match_odds)
            else 0
          end as published_match_odds,
          case
            when to_regclass('mart.fact_elo_match_team_stats') is not null
              then (select count(*) from mart.fact_elo_match_team_stats)
            else 0
          end as published_elo_match_team_stats,
          case
            when to_regclass('mart.fact_transfermarkt_transfers') is not null
              then (select count(*) from mart.fact_transfermarkt_transfers)
            else 0
          end as published_transfermarkt_transfers,
          case
            when to_regclass('mart.fact_transfermarkt_player_valuations') is not null
              then (select count(*) from mart.fact_transfermarkt_player_valuations)
            else 0
          end as published_transfermarkt_player_valuations,
          case
            when to_regclass('mart.fact_transfermarkt_appearances') is not null
              then (select count(*) from mart.fact_transfermarkt_appearances)
            else 0
          end as published_transfermarkt_appearances,
          case
            when to_regclass('mart.fact_transfermarkt_lineups') is not null
              then (select count(*) from mart.fact_transfermarkt_lineups)
            else 0
          end as published_transfermarkt_lineups,
          case
            when to_regclass('mart.fact_transfermarkt_match_events') is not null
              then (select count(*) from mart.fact_transfermarkt_match_events)
            else 0
          end as published_transfermarkt_match_events;
        """,
    )
    competition_overlap = _fetch_all(
        conn,
        """
        select
          cpm.competition_key,
          array_agg(cpm.provider order by cpm.provider) as providers,
          count(*)::int as provider_count
        from control.competition_provider_map cpm
        group by cpm.competition_key
        having count(*) > 1
        order by provider_count desc, cpm.competition_key;
        """,
    )

    return {
        "published": published,
        "rawTotals": raw_totals,
        "matchAudit": match_audit,
        "playerAudit": player_audit,
        "pendingReviewQueue": pending_queue,
        "externalPublication": external_publication,
        "depthFacts": depth_facts,
        "competitionOverlap": competition_overlap,
    }


def main() -> None:
    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        report = build_report(conn)
    print(json.dumps(report, ensure_ascii=True, indent=2, default=str))


if __name__ == "__main__":
    main()
