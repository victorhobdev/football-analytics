from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT / ".env"
REPORT_PATH = ROOT / "quality" / "external_coach_promotion_report.md"
SUMMARY_JSON_PATH = ROOT / "quality" / "external_coach_promotion_summary.json"

PROMOTION_SOURCE = "external_wikidata_P286"
WINDOW_START = "2020-01-01"
WINDOW_END = "2025-12-31"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promove candidatos externos de tecnico aprovados em staging para tabelas canonicas."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Executa em transacao e desfaz no final.")
    mode.add_argument("--execute", action="store_true", help="Grava a promocao no banco.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH))
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
    return datetime.now(timezone.utc).strftime("external_coach_promotion_%Y%m%dT%H%M%SZ")


def fetch_one(conn: psycopg.Connection[Any], sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    return dict(conn.execute(sql, params).fetchone())


def fetch_count_map(conn: psycopg.Connection[Any], sql: str) -> dict[str, int]:
    return {str(row["key"]): int(row["n"]) for row in conn.execute(sql).fetchall()}


def collect_counts(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    return fetch_one(
        conn,
        """
        select
          (select count(*) from mart.coach_identity) as coach_identity,
          (select count(*) from mart.coach_identity_source_ref) as coach_identity_source_ref,
          (select count(*) from mart.coach_tenure) as coach_tenure,
          (select count(*) from mart.fact_coach_match_assignment) as fact_assignment,
          (select count(*) from mart.fact_coach_match_assignment where is_public_eligible) as fact_public,
          (select count(*) from mart.fact_coach_match_assignment where source = %s) as external_fact_assignment,
          (select count(distinct coach_identity_id) from mart.fact_coach_match_assignment where source = %s) as external_fact_coaches
        """,
        (PROMOTION_SOURCE, PROMOTION_SOURCE),
    )


def preflight(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    gates = fetch_one(
        conn,
        """
        select
          (select count(*) from mart.stg_external_coach_assignment_candidates where promotion_status = 'promotable') as promotable_rows,
          (select count(distinct (match_id, team_id)) from mart.stg_external_coach_assignment_candidates where promotion_status = 'promotable') as promotable_match_teams,
          (select count(distinct candidate_coach_key) from mart.stg_external_coach_assignment_candidates where promotion_status = 'promotable') as promotable_coach_keys,
          (
            select count(*)
            from mart.stg_external_coach_assignment_candidates
            where promotion_status = 'promotable'
              and (match_date < date '2020-01-01' or match_date > date '2025-12-31')
          ) as outside_window,
          (
            select count(*)
            from mart.stg_external_coach_assignment_candidates c
            join mart.fact_coach_match_assignment f
              on f.match_id = c.match_id
             and f.team_id = c.team_id
            where c.promotion_status = 'promotable'
              and f.is_public_eligible = true
              and coalesce(f.source, '') <> %s
          ) as would_overwrite_protected_assignment,
          (
            select count(*)
            from (
              select match_id, team_id, count(distinct candidate_coach_key) as coaches
              from mart.stg_external_coach_assignment_candidates
              where promotion_status = 'promotable'
              group by match_id, team_id
              having count(distinct candidate_coach_key) > 1
            ) conflicts
          ) as unresolved_match_team_conflicts,
          (
            select count(*)
            from mart.stg_external_coach_candidate_resolution
            where classification = 'promotable_candidate'
              and role_candidate in ('assistant_candidate', 'unknown_role')
          ) as bad_roles,
          (
            select count(*)
            from mart.stg_external_coach_candidate_resolution
            where classification = 'promotable_candidate'
              and source <> 'wikidata_P286_team_to_person'
          ) as non_p286_candidates,
          (
            select count(*)
            from mart.stg_external_coach_candidate_resolution
            where classification = 'promotable_candidate'
              and (external_person_id is null or external_person_id !~ '^Q[0-9]+$')
          ) as invalid_external_person_id,
          (
            select count(*)
            from mart.stg_external_coach_candidate_resolution
            where classification = 'promotable_candidate'
              and (
                clipped_start_date is null
                or clipped_end_date is null
                or clipped_start_date > clipped_end_date
                or clipped_start_date < date '2020-01-01'
                or clipped_end_date > date '2025-12-31'
              )
          ) as invalid_dates,
          (
            select count(*)
            from mart.stg_external_coach_candidate_resolution
            where classification = 'promotable_candidate'
              and (
                coach_name_normalized is null
                or coach_name_normalized in ('not applicable', 'unknown', 'n a', 'na', 'none', 'null')
              )
          ) as invalid_names,
          (
            select count(*)
            from (
              select external_person_id, count(distinct coach_identity_id) as identities
              from mart.stg_external_coach_candidate_resolution
              where classification = 'promotable_candidate'
                and coach_identity_id is not null
              group by external_person_id
              having count(distinct coach_identity_id) > 1
            ) identity_conflicts
          ) as identity_conflicts
        """,
        (PROMOTION_SOURCE,),
    )
    blockers = {
        key: value
        for key, value in gates.items()
        if key not in {"promotable_rows", "promotable_match_teams", "promotable_coach_keys"} and int(value or 0) != 0
    }
    if int(gates["promotable_rows"] or 0) == 0:
        blockers["promotable_rows"] = 0
    return {"gates": gates, "blockers": blockers}


def execute_promotion(conn: psycopg.Connection[Any]) -> dict[str, int]:
    inserted_identities = fetch_one(
        conn,
        """
        with promoted as (
          select
            external_person_id,
            regexp_replace(external_person_id, '^Q', '')::bigint as wikidata_id,
            max(coach_name) as coach_name,
            max(candidate_confidence) as confidence,
            jsonb_agg(
              distinct jsonb_build_object(
                'source', source,
                'source_record_id', source_record_id,
                'source_url', source_url
              )
            ) as source_refs
          from mart.stg_external_coach_candidate_resolution r
          where classification = 'promotable_candidate'
            and source = 'wikidata_P286_team_to_person'
            and external_person_id ~ '^Q[0-9]+$'
            and exists (
              select 1
              from mart.stg_external_coach_assignment_candidates a
              where a.source = r.source
                and a.source_record_id = r.source_record_id
                and a.promotion_status = 'promotable'
            )
          group by external_person_id
        ),
        resolved as (
          select
            p.*
          from promoted p
          left join mart.coach_identity_source_ref ref
            on ref.external_person_id = p.external_person_id
           and ref.source in ('wikidata', 'wikidata_P286_team_to_person')
          left join mart.coach_identity existing
            on existing.provider = 'wikidata'
           and existing.provider_coach_id = p.wikidata_id
          left join mart.stg_external_coach_candidate_resolution r
            on r.external_person_id = p.external_person_id
           and r.classification = 'promotable_candidate'
           and r.coach_identity_id is not null
          where ref.coach_identity_id is null
            and existing.coach_identity_id is null
            and r.coach_identity_id is null
        ),
        inserted as (
          insert into mart.coach_identity (
            provider,
            provider_coach_id,
            canonical_name,
            display_name,
            aliases,
            image_url,
            identity_confidence,
            source_refs,
            updated_at
          )
          select
            'wikidata',
            wikidata_id,
            coach_name,
            coach_name,
            '[]'::jsonb,
            null,
            confidence,
            source_refs,
            now()
          from resolved
          on conflict (provider, provider_coach_id) do nothing
          returning coach_identity_id
        )
        select count(*) as inserted_identities
        from inserted
        """
    )["inserted_identities"]

    inserted_refs = fetch_one(
        conn,
        """
        with promoted as (
          select distinct
            r.source,
            r.external_person_id,
            r.source_url,
            r.candidate_confidence,
            r.payload,
            coalesce(
              r_resolution.canonical_coach_identity_id,
              exact_ref_resolution.canonical_coach_identity_id,
              generic_ref_resolution.canonical_coach_identity_id,
              wikidata_identity_resolution.canonical_coach_identity_id
            ) as coach_identity_id
          from mart.stg_external_coach_candidate_resolution r
          left join mart.v_coach_identity_resolution r_resolution
            on r_resolution.source_coach_identity_id = r.coach_identity_id
          left join mart.coach_identity_source_ref exact_ref
            on exact_ref.source = r.source
           and exact_ref.external_person_id = r.external_person_id
          left join mart.v_coach_identity_resolution exact_ref_resolution
            on exact_ref_resolution.source_coach_identity_id = exact_ref.coach_identity_id
          left join mart.coach_identity_source_ref generic_ref
            on generic_ref.source = 'wikidata'
           and generic_ref.external_person_id = r.external_person_id
          left join mart.v_coach_identity_resolution generic_ref_resolution
            on generic_ref_resolution.source_coach_identity_id = generic_ref.coach_identity_id
          left join mart.coach_identity wikidata_identity
            on wikidata_identity.provider = 'wikidata'
           and wikidata_identity.provider_coach_id = regexp_replace(r.external_person_id, '^Q', '')::bigint
          left join mart.v_coach_identity_resolution wikidata_identity_resolution
            on wikidata_identity_resolution.source_coach_identity_id = wikidata_identity.coach_identity_id
          where r.classification = 'promotable_candidate'
            and r.source = 'wikidata_P286_team_to_person'
            and r.external_person_id ~ '^Q[0-9]+$'
            and exists (
              select 1
              from mart.stg_external_coach_assignment_candidates a
              where a.source = r.source
                and a.source_record_id = r.source_record_id
                and a.promotion_status = 'promotable'
            )
        ),
        ref_rows as (
          select
            coach_identity_id,
            source,
            external_person_id,
            source_url,
            candidate_confidence,
            payload
          from promoted
          where coach_identity_id is not null
          union
          select
            coach_identity_id,
            'wikidata' as source,
            external_person_id,
            source_url,
            candidate_confidence,
            payload
          from promoted
          where coach_identity_id is not null
        ),
        deduped_ref_rows as (
          select
            coach_identity_id,
            source,
            external_person_id,
            max(source_url) as source_url,
            max(candidate_confidence) as candidate_confidence
          from ref_rows
          group by coach_identity_id, source, external_person_id
        ),
        inserted as (
          insert into mart.coach_identity_source_ref (
            coach_identity_id,
            source,
            external_person_id,
            external_person_url,
            confidence,
            payload,
            updated_at
          )
          select
            coach_identity_id,
            source,
            external_person_id,
            source_url,
            candidate_confidence,
            jsonb_build_object('source', source, 'external_person_id', external_person_id),
            now()
          from deduped_ref_rows
          on conflict (source, external_person_id) do update set
            coach_identity_id = excluded.coach_identity_id,
            external_person_url = excluded.external_person_url,
            confidence = greatest(mart.coach_identity_source_ref.confidence, excluded.confidence),
            updated_at = now()
          returning coach_identity_source_ref_id
        )
        select count(*) as inserted_refs
        from inserted
        """
    )["inserted_refs"]

    inserted_tenures = fetch_one(
        conn,
        """
        with identity_map as (
          select distinct
            r.source,
            r.source_record_id,
            r.external_person_id,
            coalesce(
              r_resolution.canonical_coach_identity_id,
              exact_ref_resolution.canonical_coach_identity_id,
              generic_ref_resolution.canonical_coach_identity_id,
              wikidata_identity_resolution.canonical_coach_identity_id
            ) as coach_identity_id
          from mart.stg_external_coach_candidate_resolution r
          left join mart.v_coach_identity_resolution r_resolution
            on r_resolution.source_coach_identity_id = r.coach_identity_id
          left join mart.coach_identity_source_ref exact_ref
            on exact_ref.source = r.source
           and exact_ref.external_person_id = r.external_person_id
          left join mart.v_coach_identity_resolution exact_ref_resolution
            on exact_ref_resolution.source_coach_identity_id = exact_ref.coach_identity_id
          left join mart.coach_identity_source_ref generic_ref
            on generic_ref.source = 'wikidata'
           and generic_ref.external_person_id = r.external_person_id
          left join mart.v_coach_identity_resolution generic_ref_resolution
            on generic_ref_resolution.source_coach_identity_id = generic_ref.coach_identity_id
          left join mart.coach_identity wikidata_identity
            on wikidata_identity.provider = 'wikidata'
           and wikidata_identity.provider_coach_id = regexp_replace(r.external_person_id, '^Q', '')::bigint
          left join mart.v_coach_identity_resolution wikidata_identity_resolution
            on wikidata_identity_resolution.source_coach_identity_id = wikidata_identity.coach_identity_id
          where r.external_person_id ~ '^Q[0-9]+$'
        ),
        tenure_rows as (
          select distinct
            im.coach_identity_id,
            r.team_id,
            case
              when r.role_candidate = 'interim_head_coach_candidate' then 'interim_head_coach'
              else 'head_coach'
            end as role,
            r.clipped_start_date as start_date,
            r.clipped_end_date as end_date,
            r.candidate_confidence,
            r.is_date_estimated,
            r.end_date_original is null as is_current_as_of_source
          from mart.stg_external_coach_candidate_resolution r
          join identity_map im
            on im.source = r.source
           and im.source_record_id = r.source_record_id
          where r.classification = 'promotable_candidate'
            and r.source = 'wikidata_P286_team_to_person'
            and im.coach_identity_id is not null
            and exists (
              select 1
              from mart.stg_external_coach_assignment_candidates a
              where a.source = r.source
                and a.source_record_id = r.source_record_id
                and a.promotion_status = 'promotable'
            )
        ),
        inserted as (
          insert into mart.coach_tenure (
            coach_identity_id,
            team_id,
            role,
            start_date,
            end_date,
            source,
            source_confidence,
            is_date_estimated,
            is_current_as_of_source,
            updated_at
          )
          select
            coach_identity_id,
            team_id,
            role,
            start_date,
            end_date,
            %s,
            max(candidate_confidence),
            bool_or(is_date_estimated),
            bool_or(is_current_as_of_source),
            now()
          from tenure_rows
          group by coach_identity_id, team_id, role, start_date, end_date
          on conflict (coach_identity_id, team_id, role, start_date, source) do update set
            end_date = excluded.end_date,
            source_confidence = greatest(mart.coach_tenure.source_confidence, excluded.source_confidence),
            is_date_estimated = excluded.is_date_estimated,
            is_current_as_of_source = excluded.is_current_as_of_source,
            updated_at = now()
          returning coach_tenure_id
        )
        select count(*) as inserted_tenures
        from inserted
        """,
        (PROMOTION_SOURCE,),
    )["inserted_tenures"]

    inserted_assignments = fetch_one(
        conn,
        """
        with identity_map as (
          select distinct
            r.source,
            r.source_record_id,
            coalesce(
              r_resolution.canonical_coach_identity_id,
              exact_ref_resolution.canonical_coach_identity_id,
              generic_ref_resolution.canonical_coach_identity_id,
              wikidata_identity_resolution.canonical_coach_identity_id
            ) as coach_identity_id
          from mart.stg_external_coach_candidate_resolution r
          left join mart.v_coach_identity_resolution r_resolution
            on r_resolution.source_coach_identity_id = r.coach_identity_id
          left join mart.coach_identity_source_ref exact_ref
            on exact_ref.source = r.source
           and exact_ref.external_person_id = r.external_person_id
          left join mart.v_coach_identity_resolution exact_ref_resolution
            on exact_ref_resolution.source_coach_identity_id = exact_ref.coach_identity_id
          left join mart.coach_identity_source_ref generic_ref
            on generic_ref.source = 'wikidata'
           and generic_ref.external_person_id = r.external_person_id
          left join mart.v_coach_identity_resolution generic_ref_resolution
            on generic_ref_resolution.source_coach_identity_id = generic_ref.coach_identity_id
          left join mart.coach_identity wikidata_identity
            on wikidata_identity.provider = 'wikidata'
           and wikidata_identity.provider_coach_id = regexp_replace(r.external_person_id, '^Q', '')::bigint
          left join mart.v_coach_identity_resolution wikidata_identity_resolution
            on wikidata_identity_resolution.source_coach_identity_id = wikidata_identity.coach_identity_id
          where r.external_person_id ~ '^Q[0-9]+$'
        ),
        assignment_rows as (
          select
            a.match_id,
            a.team_id,
            im.coach_identity_id,
            ct.coach_tenure_id,
            a.assignment_method,
            a.assignment_confidence,
            a.source_record_id
          from mart.stg_external_coach_assignment_candidates a
          join mart.stg_external_coach_candidate_resolution r
            on r.source = a.source
           and r.source_record_id = a.source_record_id
          join identity_map im
            on im.source = a.source
           and im.source_record_id = a.source_record_id
          join mart.coach_tenure ct
            on ct.coach_identity_id = im.coach_identity_id
           and ct.team_id = a.team_id
           and ct.role = case
             when a.role_candidate = 'interim_head_coach_candidate' then 'interim_head_coach'
             else 'head_coach'
           end
           and ct.start_date = r.clipped_start_date
           and ct.source = %s
          where a.promotion_status = 'promotable'
            and a.source = 'wikidata_P286_team_to_person'
            and im.coach_identity_id is not null
        ),
        inserted as (
          insert into mart.fact_coach_match_assignment (
            match_id,
            team_id,
            coach_identity_id,
            coach_tenure_id,
            assignment_method,
            assignment_confidence,
            conflict_reason,
            is_public_eligible,
            source,
            source_record_id,
            updated_at
          )
          select
            match_id,
            team_id,
            coach_identity_id,
            coach_tenure_id,
            assignment_method,
            assignment_confidence,
            null,
            true,
            %s,
            source_record_id,
            now()
          from assignment_rows
          on conflict (match_id, team_id) do update set
            coach_identity_id = excluded.coach_identity_id,
            coach_tenure_id = excluded.coach_tenure_id,
            assignment_method = excluded.assignment_method,
            assignment_confidence = excluded.assignment_confidence,
            conflict_reason = null,
            is_public_eligible = true,
            source = excluded.source,
            source_record_id = excluded.source_record_id,
            updated_at = now()
          where mart.fact_coach_match_assignment.source = %s
          returning match_id, team_id
        )
        select count(*) as inserted_assignments
        from inserted
        """,
        (PROMOTION_SOURCE, PROMOTION_SOURCE, PROMOTION_SOURCE),
    )["inserted_assignments"]

    return {
        "identities": int(inserted_identities),
        "identity_refs": int(inserted_refs),
        "tenures": int(inserted_tenures),
        "assignments": int(inserted_assignments),
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
            where f.source = %s
              and (m.date_day < date '2020-01-01' or m.date_day > date '2025-12-31')
          ) as external_outside_window,
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
            join mart.coach_tenure t on t.coach_tenure_id = f.coach_tenure_id
            where f.source = %s
              and t.role not in ('head_coach', 'interim_head_coach')
          ) as external_bad_roles,
          (
            select count(*)
            from mart.fact_coach_match_assignment f
            left join mart.coach_identity ci on ci.coach_identity_id = f.coach_identity_id
            where f.source = %s
              and (
                coalesce(ci.display_name, ci.canonical_name) is null
                or lower(coalesce(ci.display_name, ci.canonical_name)) in ('not applicable', 'unknown', 'n/a', 'na')
              )
          ) as external_invalid_names
        """,
        (PROMOTION_SOURCE, PROMOTION_SOURCE, PROMOTION_SOURCE),
    )


def build_report(summary: dict[str, Any]) -> None:
    before = summary["before"]
    after = summary["after"]
    delta = {
        key: int(after[key] or 0) - int(before[key] or 0)
        for key in ("coach_identity", "coach_identity_source_ref", "coach_tenure", "fact_assignment", "fact_public")
    }
    mode_label = "EXECUCAO" if summary["executed"] else "DRY-RUN"
    lines = [
        "# External coach promotion report",
        "",
        "## Escopo",
        "",
        f"- Modo: `{mode_label}`",
        f"- Fonte promovida: `{PROMOTION_SOURCE}`",
        f"- Janela: `{WINDOW_START}` ate `{WINDOW_END}`",
        "- Apenas candidatos `promotion_status = promotable`.",
        "- `review_needed` e `blocked_conflict` nao foram promovidos.",
        "",
        "## Preflight",
        "",
    ]
    for key, value in summary["preflight"]["gates"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Escritas", ""])
    for key, value in summary["writes"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Antes e depois", ""])
    for key in ("coach_identity", "coach_identity_source_ref", "coach_tenure", "fact_assignment", "fact_public"):
        lines.append(f"- `{key}`: `{before[key]}` -> `{after[key]}` (`+{delta[key]}`)")
    lines.extend(["", "## Qualidade pos-promocao", ""])
    for key, value in summary["quality"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Leitura",
            "",
            "- A promocao e idempotente: rodar de novo atualiza as mesmas linhas externas sem duplicar.",
            "- Assignments existentes de outras fontes nao sao sobrescritos.",
            "- A UI ainda precisa consumir `fact_coach_match_assignment` para refletir a melhoria na pagina de tecnicos.",
        ]
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
        before = collect_counts(conn)
        preflight_result = preflight(conn)
        if preflight_result["blockers"]:
            summary = {
                "run_id": run_id,
                "executed": False,
                "blocked": True,
                "preflight": preflight_result,
                "before": before,
                "after": before,
                "writes": {},
                "quality": {},
            }
            build_report(summary)
            print(json.dumps(summary, ensure_ascii=True, default=str))
            sys.exit(1)

        writes = execute_promotion(conn)
        after = collect_counts(conn)
        quality = collect_quality(conn)
        if execute:
            conn.commit()
        else:
            conn.rollback()

    summary = {
        "run_id": run_id,
        "executed": execute,
        "blocked": False,
        "preflight": preflight_result,
        "before": before,
        "after": after,
        "writes": writes,
        "quality": quality,
    }
    build_report(summary)
    print(json.dumps(summary, ensure_ascii=True, default=str))


if __name__ == "__main__":
    main()
