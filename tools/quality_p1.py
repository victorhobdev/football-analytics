from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StepResult:
    name: str
    command: list[str]
    status: str
    duration_seconds: float
    return_code: int | None


def _run_step(name: str, command: list[str]) -> StepResult:
    print(f"\n[quality-p1] RUN {name}", flush=True)
    print(f"[quality-p1] CMD {' '.join(command)}", flush=True)
    started_at = time.perf_counter()
    result = subprocess.run(command, check=False)
    elapsed = time.perf_counter() - started_at
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"[quality-p1] {status} {name} ({elapsed:.2f}s)", flush=True)
    return StepResult(
        name=name,
        command=command,
        status=status,
        duration_seconds=elapsed,
        return_code=result.returncode,
    )


def main() -> int:
    model_name = os.getenv("QUALITY_P1_MODEL", "standings_evolution")
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

    steps: list[tuple[str, list[str]]] = [
        ("pytest -m \"not integration\"", [pytest_python, "-m", "pytest", "-q", "-m", "not integration"]),
        (
            f"dbt run -s {model_name}",
            dbt_prefix
            + [
                "run",
                "-s",
                model_name,
                "--project-dir",
                "/opt/airflow/dbt",
                "--profiles-dir",
                "/opt/airflow/dbt",
            ],
        ),
        (
            f"dbt test -s {model_name}",
            dbt_prefix
            + [
                "test",
                "-s",
                model_name,
                "--project-dir",
                "/opt/airflow/dbt",
                "--profiles-dir",
                "/opt/airflow/dbt",
            ],
        ),
    ]

    started_at = time.perf_counter()
    results: list[StepResult] = []

    for index, (name, command) in enumerate(steps):
        step_result = _run_step(name=name, command=command)
        results.append(step_result)
        if step_result.status == "FAIL":
            for skipped_name, skipped_command in steps[index + 1 :]:
                results.append(
                    StepResult(
                        name=skipped_name,
                        command=skipped_command,
                        status="SKIPPED",
                        duration_seconds=0.0,
                        return_code=None,
                    )
                )
            break

    total_elapsed = time.perf_counter() - started_at
    overall_status = "PASS" if all(result.status == "PASS" for result in results) else "FAIL"

    print("\n[quality-p1] SUMMARY", flush=True)
    for result in results:
        print(f"[quality-p1] {result.status:<7} {result.name} ({result.duration_seconds:.2f}s)", flush=True)
    print(f"[quality-p1] TOTAL   {total_elapsed:.2f}s", flush=True)
    print(f"[quality-p1] RESULT  {overall_status}", flush=True)

    return 0 if overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
