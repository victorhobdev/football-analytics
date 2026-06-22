from __future__ import annotations

import ast
import json
import os
import re
import sys
import time
from pathlib import Path
from statistics import mean, median
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import psycopg
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_RESULTS_PATH = REPO_ROOT / "dbt" / "target" / "run_results.json"
DBT_LOG_PATH = REPO_ROOT / "dbt" / "logs" / "dbt.log"
WAREHOUSE_SERVICE_PATH = REPO_ROOT / "infra" / "airflow" / "dags" / "common" / "services" / "warehouse_service.py"
MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
ENV_PATH = REPO_ROOT / ".env"
SENSITIVE_TABLES = [
    ("raw", "match_events"),
    ("raw", "fixture_lineups"),
    ("raw", "fixture_player_statistics"),
    ("mart", "fact_matches"),
    ("mart", "fact_fixture_player_stats"),
    ("mart", "player_match_summary"),
]
PG_SETTINGS = [
    "shared_preload_libraries",
    "shared_buffers",
    "work_mem",
    "maintenance_work_mem",
    "effective_cache_size",
    "max_connections",
]


def _build_default_pg_dsn() -> str:
    user = os.getenv("POSTGRES_USER", "football")
    password = os.getenv("POSTGRES_PASSWORD", "football")
    database = os.getenv("POSTGRES_DB", "football_dw")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def _load_env_file() -> None:
    if not ENV_PATH.exists():
        return

    for raw_line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _normalize_psycopg_dsn(raw_dsn: str) -> str:
    normalized = raw_dsn.replace("postgresql+psycopg2://", "postgresql://").replace(
        "postgres+psycopg2://", "postgres://"
    )
    parsed = urlsplit(normalized)

    hostname = parsed.hostname or "localhost"
    if hostname in {"postgres", "football-postgres"}:
        hostname = "localhost"

    username = parsed.username or os.getenv("POSTGRES_USER", "football")
    password = parsed.password or os.getenv("POSTGRES_PASSWORD", "football")
    port = parsed.port or 5432
    database_path = parsed.path or f"/{os.getenv('POSTGRES_DB', 'football_dw')}"
    scheme = "postgresql" if parsed.scheme.startswith("postgres") else parsed.scheme
    netloc = f"{username}:{password}@{hostname}:{port}"
    if parsed.query:
        return urlunsplit((scheme, netloc, database_path, parsed.query, ""))
    return urlunsplit((scheme, netloc, database_path, "", ""))


def _fetch_all(conn: psycopg.Connection[Any], query: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params or [])
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def _fetch_one(conn: psycopg.Connection[Any], query: str, params: list[Any] | None = None) -> dict[str, Any]:
    rows = _fetch_all(conn, query, params)
    if not rows:
        raise RuntimeError(f"No rows returned for query: {query}")
    return rows[0]


def _parse_dbt_run_results() -> dict[str, Any]:
    payload = json.loads(RUN_RESULTS_PATH.read_text(encoding="utf-8"))
    models: list[dict[str, Any]] = []

    for result in payload.get("results", []):
        unique_id = str(result.get("unique_id") or "")
        if not unique_id.startswith("model.football_analytics."):
            continue
        adapter_response = result.get("adapter_response") or {}
        models.append(
            {
                "unique_id": unique_id,
                "execution_time_s": round(float(result.get("execution_time") or 0.0), 3),
                "status": result.get("status"),
                "rows_affected": adapter_response.get("rows_affected"),
                "message": adapter_response.get("message"),
            }
        )

    models.sort(key=lambda item: item["execution_time_s"], reverse=True)
    return {
        "model_count": len(models),
        "top_models": models[:20],
    }


def _extract_dbt_total_runtime_s() -> float | None:
    if not DBT_LOG_PATH.exists():
        return None

    log_text = DBT_LOG_PATH.read_text(encoding="utf-8", errors="ignore")
    matches = re.findall(r"\(([0-9]+(?:\.[0-9]+)?)s\)", log_text)
    if not matches:
        return None
    return round(float(matches[-1]), 2)


def _load_events_target_columns() -> list[str]:
    source = WAREHOUSE_SERVICE_PATH.read_text(encoding="utf-8")
    module = ast.parse(source)
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "EVENTS_TARGET_COLUMNS":
                return [str(ast.literal_eval(element)) for element in node.value.elts]  # type: ignore[attr-defined]
    raise RuntimeError("EVENTS_TARGET_COLUMNS not found in warehouse_service.py")


def _migration_files_with_match_events() -> list[Path]:
    matching: list[Path] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "raw.match_events" in text:
            matching.append(path)
    return matching


def _reconcile_match_events_drift(
    conn: psycopg.Connection[Any],
    events_target_columns: list[str],
) -> dict[str, Any]:
    live_columns = _fetch_all(
        conn,
        """
        select column_name, data_type, is_nullable
        from information_schema.columns
        where table_schema = 'raw'
          and table_name = 'match_events'
        order by ordinal_position;
        """,
    )
    live_column_names = [row["column_name"] for row in live_columns]
    live_indexes = _fetch_all(
        conn,
        """
        select indexname, indexdef
        from pg_indexes
        where schemaname = 'raw'
          and tablename = 'match_events'
        order by indexname;
        """,
    )
    migration_files = _migration_files_with_match_events()
    migration_hits: list[dict[str, Any]] = []
    missing_in_repo: list[str] = []

    for column in events_target_columns:
        referenced_files: list[str] = []
        for migration_file in migration_files:
            text = migration_file.read_text(encoding="utf-8", errors="ignore").lower()
            if column.lower() in text:
                referenced_files.append(migration_file.name)
        migration_hits.append(
            {
                "column": column,
                "exists_live": column in live_column_names,
                "referenced_in_match_events_migrations": referenced_files,
            }
        )
        if column in live_column_names and not referenced_files:
            missing_in_repo.append(column)

    conflict_index = next(
        (
            index
            for index in live_indexes
            if "provider" in str(index["indexdef"]).lower()
            and "fixture_id" in str(index["indexdef"]).lower()
            and "event_id" in str(index["indexdef"]).lower()
            and "unique" in str(index["indexdef"]).lower()
        ),
        None,
    )

    return {
        "live_columns": live_columns,
        "live_indexes": live_indexes,
        "events_target_columns": events_target_columns,
        "column_references": migration_hits,
        "columns_present_live_but_not_referenced_in_match_events_migrations": missing_in_repo,
        "live_conflict_index": conflict_index,
        "status": (
            "confirmed_drift"
            if missing_in_repo or conflict_index is not None
            else "no_confirmed_drift"
        ),
    }


def _collect_sensitive_table_columns(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for schema_name, table_name in SENSITIVE_TABLES:
        columns = _fetch_all(
            conn,
            """
            select column_name, data_type, is_nullable
            from information_schema.columns
            where table_schema = %s
              and table_name = %s
            order by ordinal_position;
            """,
            [schema_name, table_name],
        )
        result.append(
            {
                "schema": schema_name,
                "table": table_name,
                "column_count": len(columns),
                "columns": columns,
            }
        )
    return result


def _collect_sample_context(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    match_row = _fetch_one(
        conn,
        """
        with latest_match as (
            select
                fm.match_id,
                fm.league_id,
                fm.season,
                fm.competition_key,
                fm.season_label,
                fm.home_team_id,
                fm.away_team_id,
                fm.date_day
            from mart.fact_matches fm
            order by fm.date_day desc nulls last, fm.match_id desc
            limit 1
        )
        select
            lm.match_id,
            lm.league_id,
            lm.season,
            lm.competition_key,
            lm.season_label,
            lm.home_team_id,
            home_team.team_name as home_team_name,
            lm.away_team_id,
            away_team.team_name as away_team_name,
            lm.date_day
        from latest_match lm
        left join mart.dim_team home_team
          on home_team.team_id = lm.home_team_id
        left join mart.dim_team away_team
          on away_team.team_id = lm.away_team_id;
        """,
    )
    player_row = _fetch_one(
        conn,
        """
        select
            pms.player_id,
            pms.player_name,
            pms.team_id,
            pms.team_name,
            pms.match_id,
            pms.season,
            pms.match_date
        from mart.player_match_summary pms
        where pms.match_id = %s
          and pms.player_id is not null
        order by pms.minutes_played desc nulls last, pms.player_id asc
        limit 1;
        """,
        [match_row["match_id"]],
    )
    return {
        "match": match_row,
        "player": player_row,
        "team": {
            "team_id": match_row["home_team_id"],
            "team_name": match_row["home_team_name"],
        },
    }


def _collect_pg_settings(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    placeholders = ", ".join(["%s"] * len(PG_SETTINGS))
    return _fetch_all(
        conn,
        f"""
        select name, setting, unit, context, source
        from pg_settings
        where name in ({placeholders})
        order by name;
        """,
        list(PG_SETTINGS),
    )


def _collect_physical_inventory(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    database_size = _fetch_one(
        conn,
        """
        select
            current_database() as database_name,
            pg_database_size(current_database()) as database_bytes,
            pg_size_pretty(pg_database_size(current_database())) as database_size_pretty;
        """,
    )
    largest_tables = _fetch_all(
        conn,
        """
        select
            n.nspname as schemaname,
            c.relname as tablename,
            c.reltuples::bigint as est_rows,
            pg_total_relation_size(c.oid) as total_bytes,
            pg_relation_size(c.oid) as table_bytes,
            pg_indexes_size(c.oid) as index_bytes,
            pg_size_pretty(pg_total_relation_size(c.oid)) as total_size_pretty
        from pg_class c
        inner join pg_namespace n
          on n.oid = c.relnamespace
        where c.relkind = 'r'
          and n.nspname in ('raw', 'mart', 'gold')
        order by pg_total_relation_size(c.oid) desc
        limit 25;
        """,
    )
    mart_index_counts = _fetch_all(
        conn,
        """
        select schemaname, tablename, count(*) as index_count
        from pg_indexes
        where schemaname = 'mart'
        group by schemaname, tablename
        order by index_count desc, tablename asc;
        """,
    )
    return {
        "database_size": database_size,
        "largest_tables": largest_tables,
        "mart_index_counts": mart_index_counts,
    }


def _explain_baselines(conn: psycopg.Connection[Any], sample_context: dict[str, Any]) -> list[dict[str, Any]]:
    match_id = sample_context["match"]["match_id"]
    player_id = sample_context["player"]["player_id"]
    explain_specs = [
        {
            "name": "match_center_player_stats",
            "sql": """
            EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            select
                fps.player_id::text as player_id,
                fps.player_name,
                fps.team_id::text as team_id,
                coalesce(fps.team_name, team.team_name) as team_name,
                fps.position_name,
                fps.is_starter,
                fps.minutes_played,
                fps.goals,
                fps.assists,
                fps.shots_total,
                fps.shots_on_goal,
                fps.passes_total,
                fps.key_passes,
                fps.tackles,
                fps.interceptions,
                fps.duels,
                fps.fouls_committed,
                fps.yellow_cards,
                fps.red_cards,
                fps.goalkeeper_saves,
                fps.clean_sheets,
                fps.xg,
                fps.rating
            from mart.fact_fixture_player_stats fps
            left join mart.dim_team team
              on team.team_id = fps.team_id
            where fps.match_id = %s
            order by fps.team_id asc, fps.rating desc nulls last, fps.player_name asc;
            """,
            "params": [match_id],
        },
        {
            "name": "player_contexts",
            "sql": """
            EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            with player_contexts as (
                select
                    dc.league_id,
                    dc.league_name,
                    pms.season,
                    max(pms.match_date) as last_match_date,
                    count(distinct pms.match_id) as matches_played
                from mart.player_match_summary pms
                inner join mart.dim_competition dc
                  on dc.competition_sk = pms.competition_sk
                where pms.player_id = %s
                group by dc.league_id, dc.league_name, pms.season
            )
            select
                league_id,
                league_name,
                season,
                last_match_date,
                matches_played
            from player_contexts
            order by
                last_match_date desc nulls last,
                matches_played desc,
                season desc,
                league_id asc;
            """,
            "params": [player_id],
        },
    ]
    explains: list[dict[str, Any]] = []
    for spec in explain_specs:
        row = _fetch_one(conn, spec["sql"], spec["params"])
        plan_root = row["QUERY PLAN"][0]
        explains.append(
            {
                "name": spec["name"],
                "plan": plan_root,
                "execution_time_ms": plan_root.get("Execution Time"),
                "planning_time_ms": plan_root.get("Planning Time"),
            }
        )
    return explains


def _pg_stat_statements_available(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    availability = _fetch_one(
        conn,
        """
        select
            setting as shared_preload_libraries
        from pg_settings
        where name = 'shared_preload_libraries';
        """,
    )
    installed = _fetch_all(
        conn,
        """
        select extname, extversion
        from pg_extension
        where extname = 'pg_stat_statements';
        """,
    )
    return {
        "shared_preload_libraries": availability["shared_preload_libraries"],
        "installed": bool(installed),
        "extension": installed[0] if installed else None,
    }


def _reset_pg_stat_statements(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute("select pg_stat_statements_reset();")


def _collect_top_sql(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    return _fetch_all(
        conn,
        """
        select
            queryid,
            calls,
            round(total_exec_time::numeric, 3) as total_exec_ms,
            round(mean_exec_time::numeric, 3) as mean_exec_ms,
            rows,
            shared_blks_hit,
            shared_blks_read,
            temp_blks_read,
            temp_blks_written,
            regexp_replace(query, '\\s+', ' ', 'g') as query
        from pg_stat_statements
        where dbid = (select oid from pg_database where datname = current_database())
          and query not ilike '%%pg_stat_statements%%'
          and query not ilike '%%information_schema%%'
          and query not ilike '%%pg_catalog%%'
        order by total_exec_time desc
        limit 20;
        """,
    )


def _build_endpoint_specs(sample_context: dict[str, Any]) -> list[dict[str, Any]]:
    match_row = sample_context["match"]
    player_row = sample_context["player"]
    return [
        {
            "name": "matches_list",
            "path": "/api/v1/matches",
            "params": {
                "competitionId": str(match_row["league_id"]),
                "seasonId": str(match_row["season"]),
                "pageSize": "20",
            },
        },
        {
            "name": "match_center",
            "path": f"/api/v1/matches/{match_row['match_id']}",
            "params": {
                "competitionId": str(match_row["league_id"]),
                "seasonId": str(match_row["season"]),
            },
        },
        {
            "name": "player_profile",
            "path": f"/api/v1/players/{player_row['player_id']}",
            "params": {
                "competitionId": str(match_row["league_id"]),
                "seasonId": str(match_row["season"]),
                "recentMatchesLimit": "10",
            },
        },
        {
            "name": "team_profile",
            "path": f"/api/v1/teams/{match_row['home_team_id']}",
            "params": {
                "competitionId": str(match_row["league_id"]),
                "seasonId": str(match_row["season"]),
                "recentMatchesLimit": "10",
            },
        },
        {
            "name": "rankings_player_goals",
            "path": "/api/v1/rankings/player-goals",
            "params": {
                "competitionId": str(match_row["league_id"]),
                "seasonId": str(match_row["season"]),
                "pageSize": "20",
            },
        },
    ]


def _measure_endpoints(sample_context: dict[str, Any]) -> list[dict[str, Any]]:
    sys.path.insert(0, str(REPO_ROOT))
    from api.src.main import app

    endpoint_specs = _build_endpoint_specs(sample_context)
    results: list[dict[str, Any]] = []

    with TestClient(app) as client:
        for spec in endpoint_specs:
            durations_ms: list[float] = []
            status_codes: list[int] = []
            payload_sizes: list[int] = []
            for _ in range(3):
                started_at = time.perf_counter()
                response = client.get(spec["path"], params=spec["params"])
                elapsed_ms = (time.perf_counter() - started_at) * 1000
                durations_ms.append(round(elapsed_ms, 3))
                status_codes.append(response.status_code)
                payload_sizes.append(len(response.content))
                if response.status_code != 200:
                    raise RuntimeError(
                        f"Endpoint baseline failed for {spec['name']} "
                        f"status={response.status_code} body={response.text[:400]}"
                    )
            results.append(
                {
                    "name": spec["name"],
                    "path": spec["path"],
                    "params": spec["params"],
                    "status_codes": status_codes,
                    "durations_ms": durations_ms,
                    "latency_min_ms": round(min(durations_ms), 3),
                    "latency_median_ms": round(float(median(durations_ms)), 3),
                    "latency_mean_ms": round(float(mean(durations_ms)), 3),
                    "latency_max_ms": round(max(durations_ms), 3),
                    "payload_size_bytes_median": int(median(payload_sizes)),
                }
            )

    return results


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# DB Tuning Capture - {report['label']}")
    lines.append("")
    lines.append(f"Generated at: `{report['generated_at']}`")
    lines.append("")
    lines.append("## Instrumentation")
    lines.append("")
    availability = report["observability"]["pg_stat_statements"]
    lines.append(f"- shared_preload_libraries: `{availability['shared_preload_libraries']}`")
    lines.append(f"- extension installed: `{availability['installed']}`")
    lines.append("")
    lines.append("## Endpoint Baseline")
    lines.append("")
    for endpoint in report["endpoint_baseline"]:
        lines.append(
            f"- `{endpoint['name']}` `{endpoint['path']}` "
            f"mean={endpoint['latency_mean_ms']} ms "
            f"median={endpoint['latency_median_ms']} ms "
            f"max={endpoint['latency_max_ms']} ms"
        )
    lines.append("")
    lines.append("## dbt Baseline")
    lines.append("")
    total_runtime = report["dbt_baseline"]["total_runtime_s"]
    lines.append(f"- total runtime from dbt.log: `{total_runtime}` s")
    for model in report["dbt_baseline"]["top_models"][:10]:
        lines.append(
            f"- `{model['unique_id']}` "
            f"{model['execution_time_s']} s "
            f"rows={model['rows_affected']}"
        )
    lines.append("")
    lines.append("## Physical Inventory")
    lines.append("")
    db_size = report["physical_inventory"]["database_size"]
    lines.append(
        f"- database `{db_size['database_name']}` size: "
        f"`{db_size['database_size_pretty']}`"
    )
    for table in report["physical_inventory"]["largest_tables"][:10]:
        lines.append(
            f"- `{table['schemaname']}.{table['tablename']}` "
            f"size=`{table['total_size_pretty']}` "
            f"rows_est={table['est_rows']}"
        )
    lines.append("")
    lines.append("## Schema Drift")
    lines.append("")
    drift = report["schema_reconciliation"]["match_events"]
    lines.append(f"- status: `{drift['status']}`")
    if drift["columns_present_live_but_not_referenced_in_match_events_migrations"]:
        lines.append(
            "- live columns not referenced in committed `raw.match_events` migrations: "
            + ", ".join(f"`{column}`" for column in drift["columns_present_live_but_not_referenced_in_match_events_migrations"])
        )
    else:
        lines.append("- no live-only columns detected in `raw.match_events` reconciliation.")
    lines.append("")
    lines.append("## Top SQL")
    lines.append("")
    for item in report["observability"]["top_sql"][:10]:
        lines.append(
            f"- calls=`{item['calls']}` total=`{item['total_exec_ms']}` ms "
            f"mean=`{item['mean_exec_ms']}` ms "
            f"buffers=`{int(item['shared_blks_hit']) + int(item['shared_blks_read'])}` "
            f"query=`{item['query'][:180]}`"
        )
    lines.append("")
    lines.append("## Explain Baselines")
    lines.append("")
    for explain in report["explain_baselines"]:
        lines.append(
            f"- `{explain['name']}` planning=`{round(float(explain['planning_time_ms'] or 0.0), 3)}` ms "
            f"execution=`{round(float(explain['execution_time_ms'] or 0.0), 3)}` ms"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    _load_env_file()
    raw_dsn = os.getenv("FOOTBALL_PG_DSN") or os.getenv("DATABASE_URL") or _build_default_pg_dsn()
    dsn = _normalize_psycopg_dsn(raw_dsn)
    os.environ["FOOTBALL_PG_DSN"] = dsn
    os.environ["DATABASE_URL"] = dsn
    output_label = sys.argv[1] if len(sys.argv) > 1 else "wave0"
    artifact_dir = REPO_ROOT / "artifacts" / "db_tuning" / output_label
    artifact_dir.mkdir(parents=True, exist_ok=True)

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        generated_at = _fetch_one(conn, "select now()::text as generated_at;")["generated_at"]
        observability = {
            "pg_stat_statements": _pg_stat_statements_available(conn),
            "pg_settings": _collect_pg_settings(conn),
        }
        sample_context = _collect_sample_context(conn)
        physical_inventory = _collect_physical_inventory(conn)
        sensitive_table_columns = _collect_sensitive_table_columns(conn)
        explain_baselines = _explain_baselines(conn, sample_context)
        schema_reconciliation = {
            "match_events": _reconcile_match_events_drift(conn, _load_events_target_columns()),
            "sensitive_tables": sensitive_table_columns,
        }
        dbt_baseline = _parse_dbt_run_results()
        dbt_baseline["total_runtime_s"] = _extract_dbt_total_runtime_s()

        if not observability["pg_stat_statements"]["installed"]:
            raise RuntimeError("pg_stat_statements is not installed. Wave 0 instrumentation is incomplete.")

        _reset_pg_stat_statements(conn)
        endpoint_baseline = _measure_endpoints(sample_context)
        top_sql = _collect_top_sql(conn)
        observability["top_sql"] = top_sql

    report = {
        "label": output_label,
        "generated_at": generated_at,
        "sample_context": sample_context,
        "observability": observability,
        "endpoint_baseline": endpoint_baseline,
        "dbt_baseline": dbt_baseline,
        "physical_inventory": physical_inventory,
        "schema_reconciliation": schema_reconciliation,
        "explain_baselines": explain_baselines,
    }

    json_path = artifact_dir / "baseline.json"
    md_path = artifact_dir / "baseline.md"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True, default=str),
        encoding="utf-8",
    )
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
