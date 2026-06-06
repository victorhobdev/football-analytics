from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from _repo_root import resolve_repo_root
from typing import Any

import psycopg
from psycopg.rows import dict_row


ROOT = resolve_repo_root()
DEFAULT_ENV_PATH = ROOT / ".env"
MIGRATION_PATH = ROOT / "db" / "migrations" / "20260425160000_coach_identity_alias_layer.sql"
REPORT_PATH = ROOT / "platform" / "reports" / "quality" / "coach_identity_alias_application_report.md"
SUMMARY_JSON_PATH = ROOT / "platform" / "reports" / "quality" / "coach_identity_alias_application_summary.json"
WINDOW_START = "2020-01-01"
WINDOW_END = "2025-12-31"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aplica aliases aprovados de tecnicos sem remover as identidades antigas."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Executa em transacao e desfaz no final.")
    mode.add_argument("--execute", action="store_true", help="Grava a aplicacao dos aliases no banco.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--apply-schema", action="store_true")
    return parser.parse_args()


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def resolve_setting(name: str, env_values: dict[str, str], default: str | None = None) -> str | None:
    return os.getenv(name) or env_values.get(name) or default


def resolve_pg_dsn(env_values: dict[str, str]) -> str:
    dsn = (
        resolve_setting("FOOTBALL_PG_DSN", env_values)
        or resolve_setting("DATABASE_URL", env_values)
        or "postgresql://football:football@localhost:5432/football_dw"
    )
    dsn = dsn.replace("postgresql+psycopg2://", "postgresql://")
    dsn = dsn.replace("postgres+psycopg2://", "postgresql://")
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn.removeprefix("postgres://")
    if "@postgres:" in dsn and not os.getenv("RUNNING_IN_DOCKER"):
        dsn = dsn.replace("@postgres:", "@localhost:")
    if "@postgres/" in dsn and not os.getenv("RUNNING_IN_DOCKER"):
        dsn = dsn.replace("@postgres/", "@localhost:5432/")
    return dsn


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("coach_alias_application_%Y%m%dT%H%M%SZ")


def fetch_one(conn: psycopg.Connection[Any], sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    return dict(conn.execute(sql, params).fetchone())


def fetch_all(conn: psycopg.Connection[Any], sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def apply_schema(conn: psycopg.Connection[Any]) -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    up_sql = sql.split("-- migrate:down", 1)[0].replace("-- migrate:up", "", 1)
    conn.execute(up_sql)


def collect_state(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    return {
        "counts": fetch_one(
            conn,
            """
            with public_assignments as (
              select
                f.match_id,
                f.team_id,
                f.coach_identity_id,
                coalesce(ci.display_name, ci.canonical_name) as coach_name
              from mart.fact_coach_match_assignment f
              join mart.fact_matches m
                on m.match_id = f.match_id
              left join mart.coach_identity ci
                on ci.coach_identity_id = f.coach_identity_id
              where f.is_public_eligible
                and m.date_day between %s::date and %s::date
            )
            select
              (select count(*) from mart.coach_identity_alias where is_active and status = 'active') as active_coach_aliases,
              (select count(*) from mart.team_identity_alias where is_active and status = 'active') as active_team_aliases,
              (select count(distinct coach_identity_id) from public_assignments) as assigned_identity_distinct,
              (
                select count(distinct lower(regexp_replace(coalesce(coach_name, ''), '[^[:alnum:]]+', ' ', 'g')))
                from public_assignments
                where coach_name is not null
              ) as assigned_name_norm_distinct,
              (select count(*) from public_assignments) as public_assignment_rows,
              (
                select count(*)
                from public_assignments p
                join mart.coach_identity_alias a
                  on a.alias_coach_identity_id = p.coach_identity_id
                where a.is_active
                  and a.status = 'active'
              ) as rows_still_on_alias_identity
            """,
            (WINDOW_START, WINDOW_END),
        ),
        "alias_rows": fetch_all(
            conn,
            """
            select
              a.coach_identity_alias_id,
              coalesce(c.display_name, c.canonical_name) as canonical_name,
              a.canonical_coach_identity_id,
              coalesce(alias_ci.display_name, alias_ci.canonical_name) as alias_identity_name,
              a.alias_coach_identity_id,
              a.alias_source,
              a.external_person_id,
              a.alias_name,
              a.match_method,
              a.confidence
            from mart.coach_identity_alias a
            join mart.coach_identity c
              on c.coach_identity_id = a.canonical_coach_identity_id
            left join mart.coach_identity alias_ci
              on alias_ci.coach_identity_id = a.alias_coach_identity_id
            where a.is_active
              and a.status = 'active'
            order by a.coach_identity_alias_id
            """,
        ),
        "team_alias_rows": fetch_all(
            conn,
            """
            select
              a.team_identity_alias_id,
              t.team_name,
              a.team_id,
              a.alias_source,
              a.external_team_id,
              a.alias_name,
              a.match_method,
              a.confidence
            from mart.team_identity_alias a
            join mart.dim_team t
              on t.team_id = a.team_id
            where a.is_active
              and a.status = 'active'
            order by a.team_identity_alias_id
            """,
        ),
    }


def refresh_canonical_alias_payloads(conn: psycopg.Connection[Any]) -> int:
    rows = conn.execute(
        """
        update mart.coach_identity ci
        set
          aliases = (
            select jsonb_agg(distinct alias_item)
            from (
              select jsonb_array_elements(ci.aliases) as alias_item
              union all
              select jsonb_build_object(
                'name', a.alias_name,
                'source', a.alias_source,
                'external_person_id', a.external_person_id,
                'alias_coach_identity_id', a.alias_coach_identity_id,
                'match_method', a.match_method
              ) as alias_item
              from mart.coach_identity_alias a
              where a.canonical_coach_identity_id = ci.coach_identity_id
                and a.is_active
                and a.status = 'active'
                and a.alias_name is not null
            ) aliases
          ),
          updated_at = now()
        where exists (
          select 1
          from mart.coach_identity_alias a
          where a.canonical_coach_identity_id = ci.coach_identity_id
            and a.is_active
            and a.status = 'active'
        )
        returning ci.coach_identity_id
        """
    ).fetchall()
    return len(rows)


def execute_alias_application(conn: psycopg.Connection[Any]) -> dict[str, int]:
    refreshed_identities = refresh_canonical_alias_payloads(conn)
    moved_refs = conn.execute(
        """
        update mart.coach_identity_source_ref ref
        set
          coach_identity_id = a.canonical_coach_identity_id,
          payload = coalesce(ref.payload, '{}'::jsonb) || jsonb_build_object(
            'alias_applied', true,
            'previous_coach_identity_id', ref.coach_identity_id,
            'coach_identity_alias_id', a.coach_identity_alias_id
          ),
          updated_at = now()
        from mart.coach_identity_alias a
        where a.is_active
          and a.status = 'active'
          and a.alias_coach_identity_id is not null
          and ref.coach_identity_id = a.alias_coach_identity_id
        returning ref.coach_identity_source_ref_id
        """
    ).fetchall()
    moved_non_conflicting_tenures = conn.execute(
        """
        update mart.coach_tenure ct
        set
          coach_identity_id = a.canonical_coach_identity_id,
          updated_at = now()
        from mart.coach_identity_alias a
        where a.is_active
          and a.status = 'active'
          and a.alias_coach_identity_id is not null
          and ct.coach_identity_id = a.alias_coach_identity_id
          and not exists (
            select 1
            from mart.coach_tenure existing
            where existing.coach_identity_id = a.canonical_coach_identity_id
              and existing.team_id = ct.team_id
              and existing.role = ct.role
              and existing.start_date is not distinct from ct.start_date
              and existing.source = ct.source
          )
        returning ct.coach_tenure_id
        """
    ).fetchall()
    moved_assignments = conn.execute(
        """
        update mart.fact_coach_match_assignment f
        set
          coach_identity_id = a.canonical_coach_identity_id,
          updated_at = now()
        from mart.coach_identity_alias a
        where a.is_active
          and a.status = 'active'
          and a.alias_coach_identity_id is not null
          and f.coach_identity_id = a.alias_coach_identity_id
        returning f.match_id, f.team_id
        """
    ).fetchall()
    updated_resolution_stage = conn.execute(
        """
        update mart.stg_external_coach_candidate_resolution r
        set
          coach_identity_id = a.canonical_coach_identity_id,
          identity_match_method = coalesce(r.identity_match_method, 'coach_alias_identity'),
          updated_at = now()
        from mart.coach_identity_alias a
        where a.is_active
          and a.status = 'active'
          and a.alias_coach_identity_id is not null
          and r.coach_identity_id = a.alias_coach_identity_id
        returning r.source_record_id
        """
    ).fetchall()
    updated_assignment_stage = conn.execute(
        """
        update mart.stg_external_coach_assignment_candidates c
        set
          coach_identity_id = a.canonical_coach_identity_id,
          updated_at = now()
        from mart.coach_identity_alias a
        where a.is_active
          and a.status = 'active'
          and a.alias_coach_identity_id is not null
          and c.coach_identity_id = a.alias_coach_identity_id
        returning c.source_record_id
        """
    ).fetchall()
    return {
        "refreshed_canonical_identity_alias_payloads": refreshed_identities,
        "moved_source_refs": len(moved_refs),
        "moved_non_conflicting_tenures": len(moved_non_conflicting_tenures),
        "moved_fact_assignments": len(moved_assignments),
        "updated_resolution_stage_rows": len(updated_resolution_stage),
        "updated_assignment_stage_rows": len(updated_assignment_stage),
    }


def collect_quality(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    return fetch_one(
        conn,
        """
        select
          (
            select count(*)
            from mart.fact_coach_match_assignment f
            join mart.fact_matches m on m.match_id = f.match_id
            where m.date_day < date '2020-01-01'
               or m.date_day > date '2025-12-31'
          ) as public_assignments_outside_window,
          (
            select count(*)
            from (
              select match_id, team_id, count(*) as rows
              from mart.fact_coach_match_assignment
              group by match_id, team_id
              having count(*) > 1
            ) duplicates
          ) as duplicate_match_team_rows,
          (
            select count(*)
            from mart.fact_coach_match_assignment f
            join mart.coach_identity_alias a
              on a.alias_coach_identity_id = f.coach_identity_id
            where a.is_active
              and a.status = 'active'
          ) as rows_still_on_alias_identity
        """
    )


def build_report(summary: dict[str, Any]) -> None:
    before = summary["before"]["counts"]
    after = summary["after"]["counts"]
    lines = [
        "# Coach identity alias application report",
        "",
        "## Escopo",
        "",
        f"- Run: `{summary['run_id']}`",
        f"- Modo: `{'EXECUCAO' if summary['executed'] else 'DRY-RUN'}`",
        f"- Janela de validacao publica: `{WINDOW_START}` ate `{WINDOW_END}`.",
        "- Identidades antigas foram preservadas em `mart.coach_identity`.",
        "- A unificacao publica ocorre por `mart.coach_identity_alias` e pela reatribuicao das facts para a identidade canonica.",
        "",
        "## Antes e depois",
        "",
    ]
    for key in before:
        lines.append(f"- `{key}`: `{before[key]}` -> `{after[key]}`")
    lines.extend(["", "## Escritas", ""])
    for key, value in summary["writes"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Qualidade", ""])
    for key, value in summary["quality"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Aliases de tecnico ativos", ""])
    for row in summary["after"]["alias_rows"]:
        lines.append(
            f"- `{row['canonical_name']}` <= `{row.get('alias_identity_name') or row.get('alias_name')}` "
            f"({row['alias_source']}:{row.get('external_person_id') or '-'})"
        )
    lines.extend(["", "## Aliases de clube ativos", ""])
    for row in summary["after"]["team_alias_rows"]:
        lines.append(
            f"- `{row['team_name']}` <= `{row.get('alias_name') or row.get('external_team_id')}` "
            f"({row['alias_source']}:{row.get('external_team_id') or '-'})"
        )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> None:
    args = parse_args()
    execute = bool(args.execute)
    run_id = utc_run_id()
    env_values = load_env_file(Path(args.env_file))
    dsn = resolve_pg_dsn(env_values)
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=15) as conn:
        if args.apply_schema:
            apply_schema(conn)
        before = collect_state(conn)
        writes = execute_alias_application(conn)
        after = collect_state(conn)
        quality = collect_quality(conn)
        if execute:
            conn.commit()
        else:
            conn.rollback()
    summary = {
        "run_id": run_id,
        "executed": execute,
        "before": before,
        "after": after,
        "writes": writes,
        "quality": quality,
    }
    build_report(summary)
    print(json.dumps(summary, ensure_ascii=True, default=str))


if __name__ == "__main__":
    main()
