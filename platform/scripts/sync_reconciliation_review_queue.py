from __future__ import annotations

import os
from typing import Any

import psycopg
from psycopg.rows import dict_row


DEFAULT_DSN = "postgresql://football:football@127.0.0.1:5432/football_dw"


def _dsn() -> str:
    return os.getenv("FOOTBALL_PG_DSN") or os.getenv("DATABASE_URL") or DEFAULT_DSN


def _upsert_match_queue(conn: psycopg.Connection[Any]) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            delete from control.entity_reconciliation_review_queue
            where entity_type = 'match'
              and source in (
                select distinct source
                from control.v_match_reconciliation_audit
                where review_status <> 'auto_approved'
              );
            """
        )
        cursor.execute(
            """
            with candidates as (
              select
                'match'::text as entity_type,
                source,
                source_entity_id,
                canonical_match_id as candidate_canonical_id,
                null::text as candidate_competition_key,
                case
                  when review_status = 'manual_review' then 'pending'
                  when review_status = 'blocked' then 'blocked'
                  else 'pending'
                end as status,
                identity_status as reason,
                trim(concat(home_team_name_raw, ' vs ', away_team_name_raw)) as source_label,
                source_evidence as evidence
              from control.v_match_reconciliation_audit
              where review_status <> 'auto_approved'
            )
            insert into control.entity_reconciliation_review_queue (
              entity_type,
              source,
              source_entity_id,
              candidate_canonical_id,
              candidate_competition_key,
              status,
              reason,
              source_label,
              evidence
            )
            select
              entity_type,
              source,
              source_entity_id,
              candidate_canonical_id,
              candidate_competition_key,
              status,
              reason,
              source_label,
              coalesce(evidence, '{}'::jsonb)
            from candidates;
            """
        )
        cursor.execute(
            """
            select count(*)
            from control.entity_reconciliation_review_queue
            where entity_type = 'match'
              and source in (
                select distinct source
                from control.v_match_reconciliation_audit
                where review_status <> 'auto_approved'
              );
            """
        )
        row = cursor.fetchone()
    return int(next(iter(row.values())) if row else 0)


def _upsert_player_queue(conn: psycopg.Connection[Any]) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            delete from control.entity_reconciliation_review_queue
            where entity_type = 'player'
              and source in (
                select distinct source
                from control.v_player_reconciliation_audit
                where review_status <> 'auto_approved'
              );
            """
        )
        cursor.execute(
            """
            with candidates as (
              select
                'player'::text as entity_type,
                source,
                source_entity_id,
                canonical_player_id as candidate_canonical_id,
                null::text as candidate_competition_key,
                case
                  when review_status = 'manual_review' then 'pending'
                  when review_status = 'blocked' then 'blocked'
                  else 'pending'
                end as status,
                identity_status as reason,
                player_name_raw as source_label,
                source_evidence as evidence
              from control.v_player_reconciliation_audit
              where review_status <> 'auto_approved'
            )
            insert into control.entity_reconciliation_review_queue (
              entity_type,
              source,
              source_entity_id,
              candidate_canonical_id,
              candidate_competition_key,
              status,
              reason,
              source_label,
              evidence
            )
            select
              entity_type,
              source,
              source_entity_id,
              candidate_canonical_id,
              candidate_competition_key,
              status,
              reason,
              source_label,
              coalesce(evidence, '{}'::jsonb)
            from candidates;
            """
        )
        cursor.execute(
            """
            select count(*)
            from control.entity_reconciliation_review_queue
            where entity_type = 'player'
              and source in (
                select distinct source
                from control.v_player_reconciliation_audit
                where review_status <> 'auto_approved'
              );
            """
        )
        row = cursor.fetchone()
    return int(next(iter(row.values())) if row else 0)


def main() -> None:
    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        match_rows = _upsert_match_queue(conn)
        player_rows = _upsert_player_queue(conn)
        conn.commit()
    print(
        {
            "matchQueueRowsUpserted": match_rows,
            "playerQueueRowsUpserted": player_rows,
            "totalRowsUpserted": match_rows + player_rows,
        }
    )


if __name__ == "__main__":
    main()
