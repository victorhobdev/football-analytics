from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class StepResult:
    name: str
    command: list[str]
    status: str
    duration_seconds: float
    return_code: int | None


def _run_step(*, name: str, command: list[str], cwd: Path) -> StepResult:
    print(f"\n[backend-data-gate] RUN {name}", flush=True)
    print(f"[backend-data-gate] CWD {cwd}", flush=True)
    print(f"[backend-data-gate] CMD {' '.join(command)}", flush=True)
    started_at = time.perf_counter()
    result = subprocess.run(command, cwd=cwd, check=False)
    elapsed = time.perf_counter() - started_at
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"[backend-data-gate] {status} {name} ({elapsed:.2f}s)", flush=True)
    return StepResult(
        name=name,
        command=command,
        status=status,
        duration_seconds=elapsed,
        return_code=result.returncode,
    )


def _docker_stack_precheck(*, cwd: Path) -> StepResult:
    docker_executable = shutil.which("docker") or shutil.which("docker.exe")
    if docker_executable is None:
        return StepResult(
            name="docker compose ps --status running",
            command=["docker", "compose", "ps", "--status", "running"],
            status="FAIL",
            duration_seconds=0.0,
            return_code=None,
        )

    command = [docker_executable, "compose", "ps", "--status", "running"]
    started_at = time.perf_counter()
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    elapsed = time.perf_counter() - started_at

    required_services = ("airflow-webserver", "football_airflow_webserver", "postgres", "football-postgres")
    has_airflow = "airflow-webserver" in result.stdout or "football_airflow_webserver" in result.stdout
    has_postgres = "postgres" in result.stdout or "football-postgres" in result.stdout
    status = "PASS" if result.returncode == 0 and has_airflow and has_postgres else "FAIL"

    if status == "FAIL":
        print("[backend-data-gate] docker stack precheck failed.", flush=True)
        if result.stdout:
            print(f"[backend-data-gate] STDOUT\n{result.stdout}", flush=True)
        if result.stderr:
            print(f"[backend-data-gate] STDERR\n{result.stderr}", flush=True)
        print(
            "[backend-data-gate] Expected running services: airflow-webserver and postgres in docker compose.",
            flush=True,
        )

    return StepResult(
        name="docker compose ps --status running",
        command=command,
        status=status,
        duration_seconds=elapsed,
        return_code=result.returncode,
    )


def _write_summary(*, artifact_dir: Path, mode: str, results: list[StepResult], total_elapsed: float) -> Path:
    summary_path = artifact_dir / "summary.txt"
    overall_status = "PASS" if all(result.status == "PASS" for result in results) else "FAIL"
    lines = [
        f"mode={mode}",
        f"result={overall_status}",
        f"total_seconds={total_elapsed:.2f}",
        "",
        "steps:",
    ]
    for result in results:
        lines.append(
            f"- {result.status:<7} {result.name} ({result.duration_seconds:.2f}s) :: {' '.join(result.command)}"
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Executa o gate minimo de readiness operacional do backend/BFF e da stack de dados."
    )
    parser.add_argument(
        "--mode",
        choices=("gate", "full"),
        default="gate",
        help="gate = lint + testes unitarios backend/dados; full = gate + validacao live da stack via integration tests",
    )
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Diretorio raiz para gravar o resumo da execucao.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    python_executable = Path(sys.executable)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    artifact_dir = Path(args.artifacts_dir) / f"backend_data_gate_{args.mode}_{run_id}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    steps: list[tuple[str, list[str]]] = [
        ("python -m ruff check . --select E9,F63,F7,F82", [str(python_executable), "-m", "ruff", "check", ".", "--select", "E9,F63,F7,F82"]),
        (
            'python -m pytest -q api/tests tests -m "not integration"',
            [str(python_executable), "-m", "pytest", "-q", "api/tests", "tests", "-m", "not integration"],
        ),
    ]

    started_at = time.perf_counter()
    results: list[StepResult] = []

    for index, (name, command) in enumerate(steps):
        step_result = _run_step(name=name, command=command, cwd=repo_root)
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
            total_elapsed = time.perf_counter() - started_at
            summary_path = _write_summary(
                artifact_dir=artifact_dir,
                mode=args.mode,
                results=results,
                total_elapsed=total_elapsed,
            )
            print(f"\n[backend-data-gate] ARTIFACTS {summary_path}", flush=True)
            print(f"[backend-data-gate] RESULT  FAIL", flush=True)
            return 1

    if args.mode == "full":
        precheck_result = _docker_stack_precheck(cwd=repo_root)
        results.append(precheck_result)
        if precheck_result.status == "PASS":
            results.append(
                _run_step(
                    name='python -m pytest -q tests -m "integration"',
                    command=[str(python_executable), "-m", "pytest", "-q", "tests", "-m", "integration"],
                    cwd=repo_root,
                )
            )

    total_elapsed = time.perf_counter() - started_at
    summary_path = _write_summary(
        artifact_dir=artifact_dir,
        mode=args.mode,
        results=results,
        total_elapsed=total_elapsed,
    )
    overall_status = "PASS" if all(result.status == "PASS" for result in results) else "FAIL"

    print("\n[backend-data-gate] SUMMARY", flush=True)
    for result in results:
        print(f"[backend-data-gate] {result.status:<7} {result.name} ({result.duration_seconds:.2f}s)", flush=True)
    print(f"[backend-data-gate] ARTIFACTS {summary_path}", flush=True)
    print(f"[backend-data-gate] TOTAL   {total_elapsed:.2f}s", flush=True)
    print(f"[backend-data-gate] RESULT  {overall_status}", flush=True)

    return 0 if overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
