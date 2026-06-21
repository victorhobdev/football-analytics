from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class StepResult:
    name: str
    status: str
    duration_seconds: float
    return_code: int | None


def _run_command_step(name: str, command: list[str]) -> StepResult:
    print(f"\n[p2-verify] RUN {name}", flush=True)
    print(f"[p2-verify] CMD {' '.join(command)}", flush=True)
    started_at = time.perf_counter()
    result = subprocess.run(command, check=False)
    elapsed = time.perf_counter() - started_at
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"[p2-verify] {status} {name} ({elapsed:.2f}s)", flush=True)
    return StepResult(
        name=name,
        status=status,
        duration_seconds=elapsed,
        return_code=result.returncode,
    )


def _run_stats_queries_step(*, artifact_dir: Path, db_name: str, db_user: str) -> StepResult:
    step_name = "stats diagnostics queries"
    print(f"\n[p2-verify] RUN {step_name}", flush=True)
    started_at = time.perf_counter()

    query_files = [
        Path("platform/warehouse/queries/fixtures_missing_stats.sql"),
        Path("platform/warehouse/queries/stats_duplicates.sql"),
        Path("platform/warehouse/queries/coverage_by_season.sql"),
    ]
    psql_cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "postgres",
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        db_user,
        "-d",
        db_name,
        "-f",
        "-",
    ]

    any_fail = False
    for query_file in query_files:
        if not query_file.exists():
            any_fail = True
            output_file = artifact_dir / f"{query_file.stem}.txt"
            output_file.write_text(
                f"Arquivo de query nao encontrado: {query_file}\n",
                encoding="utf-8",
            )
            print(f"[p2-verify] FAIL missing query file {query_file}", flush=True)
            continue

        sql_text = query_file.read_text(encoding="utf-8")
        result = subprocess.run(
            psql_cmd,
            input=sql_text,
            text=True,
            capture_output=True,
            check=False,
        )

        output_file = artifact_dir / f"{query_file.stem}.txt"
        output_file.write_text(
            (result.stdout or "") + ("\n" if result.stdout else "") + (result.stderr or ""),
            encoding="utf-8",
        )

        if result.returncode == 0:
            print(f"[p2-verify] PASS {query_file} -> {output_file}", flush=True)
        else:
            any_fail = True
            print(f"[p2-verify] FAIL {query_file} -> {output_file}", flush=True)

    elapsed = time.perf_counter() - started_at
    status = "FAIL" if any_fail else "PASS"
    print(f"[p2-verify] {status} {step_name} ({elapsed:.2f}s)", flush=True)
    return StepResult(
        name=step_name,
        status=status,
        duration_seconds=elapsed,
        return_code=1 if any_fail else 0,
    )


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_root = Path(os.getenv("P2_VERIFY_ARTIFACTS_DIR", "artifacts"))
    artifact_dir = artifact_root / f"p2_verify_{run_id}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    db_name = os.getenv("P2_VERIFY_DB_NAME", "football_dw")
    db_user = os.getenv("P2_VERIFY_DB_USER", "football")
    pytest_python = next(
        (
            str(candidate)
            for candidate in (Path(".venv/Scripts/python.exe"), Path(".venv/bin/python"))
            if candidate.exists()
        ),
        sys.executable,
    )
    dbt_prefix = [
        "docker",
        "compose",
        "exec",
        "-T",
        "airflow-webserver",
        "dbt",
    ]

    steps: list[StepResult] = []
    started_at = time.perf_counter()

    unit_step = _run_command_step(
        name='pytest -m "not integration"',
        command=[pytest_python, "-m", "pytest", "-q", "-m", "not integration"],
    )
    steps.append(unit_step)
    if unit_step.status == "FAIL":
        steps.append(StepResult("stats diagnostics queries", "SKIPPED", 0.0, None))
        steps.append(StepResult("dbt test -s stg_match_statistics+", "SKIPPED", 0.0, None))
    else:
        queries_step = _run_stats_queries_step(
            artifact_dir=artifact_dir,
            db_name=db_name,
            db_user=db_user,
        )
        steps.append(queries_step)
        if queries_step.status == "FAIL":
            steps.append(StepResult("dbt test -s stg_match_statistics+", "SKIPPED", 0.0, None))
        else:
            dbt_step = _run_command_step(
                name="dbt test -s stg_match_statistics+",
                command=dbt_prefix
                + [
                    "test",
                    "-s",
                    "stg_match_statistics+",
                    "--project-dir",
                    "/opt/airflow/dbt",
                    "--profiles-dir",
                    "/opt/airflow/dbt",
                ],
            )
            steps.append(dbt_step)

    total_elapsed = time.perf_counter() - started_at
    overall_status = "PASS" if all(step.status == "PASS" for step in steps) else "FAIL"

    print("\n[p2-verify] SUMMARY", flush=True)
    for step in steps:
        print(f"[p2-verify] {step.status:<7} {step.name} ({step.duration_seconds:.2f}s)", flush=True)
    print(f"[p2-verify] ARTIFACTS {artifact_dir}", flush=True)
    print(f"[p2-verify] TOTAL   {total_elapsed:.2f}s", flush=True)
    print(f"[p2-verify] RESULT  {overall_status}", flush=True)

    return 0 if overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
