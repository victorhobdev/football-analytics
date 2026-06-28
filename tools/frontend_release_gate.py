from __future__ import annotations

import argparse
import shutil
import subprocess
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
    print(f"\n[frontend-release] RUN {name}", flush=True)
    print(f"[frontend-release] CWD {cwd}", flush=True)
    print(f"[frontend-release] CMD {' '.join(command)}", flush=True)
    started_at = time.perf_counter()
    result = subprocess.run(command, cwd=cwd, check=False)
    elapsed = time.perf_counter() - started_at
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"[frontend-release] {status} {name} ({elapsed:.2f}s)", flush=True)
    return StepResult(
        name=name,
        command=command,
        status=status,
        duration_seconds=elapsed,
        return_code=result.returncode,
    )


def _write_summary(
    *,
    artifact_dir: Path,
    mode: str,
    frontend_dir: Path,
    results: list[StepResult],
    total_elapsed: float,
) -> Path:
    summary_path = artifact_dir / "summary.txt"
    overall_status = "PASS" if all(result.status == "PASS" for result in results) else "FAIL"
    lines = [
        f"mode={mode}",
        f"frontend_dir={frontend_dir}",
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
        description="Executa o gate minimo de release/demo do frontend e opcionalmente a regressao completa."
    )
    parser.add_argument(
        "--mode",
        choices=("gate", "full"),
        default="gate",
        help="gate = validate:release + build; full = gate + regression completa",
    )
    parser.add_argument(
        "--frontend-dir",
        default="frontend",
        help="Diretorio do frontend a validar.",
    )
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Diretorio raiz para gravar o resumo da execucao.",
    )
    args = parser.parse_args()

    frontend_dir = Path(args.frontend_dir).resolve()
    artifacts_root = Path(args.artifacts_dir)
    artifact_dir = artifacts_root / f"frontend_release_gate_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    pnpm_executable = shutil.which("pnpm") or shutil.which("pnpm.cmd")

    if not frontend_dir.exists():
        raise SystemExit(f"[frontend-release] frontend dir not found: {frontend_dir}")
    if pnpm_executable is None:
        raise SystemExit("[frontend-release] pnpm executable not found in PATH")

    steps: list[tuple[str, list[str]]] = [
        ("pnpm validate:release", [pnpm_executable, "validate:release"]),
        ("pnpm build", [pnpm_executable, "build"]),
    ]
    if args.mode == "full":
        steps.append(("pnpm test:regression", [pnpm_executable, "test:regression"]))

    started_at = time.perf_counter()
    results: list[StepResult] = []

    for index, (name, command) in enumerate(steps):
        step_result = _run_step(name=name, command=command, cwd=frontend_dir)
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
    summary_path = _write_summary(
        artifact_dir=artifact_dir,
        mode=args.mode,
        frontend_dir=frontend_dir,
        results=results,
        total_elapsed=total_elapsed,
    )
    overall_status = "PASS" if all(result.status == "PASS" for result in results) else "FAIL"

    print("\n[frontend-release] SUMMARY", flush=True)
    for result in results:
        print(f"[frontend-release] {result.status:<7} {result.name} ({result.duration_seconds:.2f}s)", flush=True)
    print(f"[frontend-release] ARTIFACTS {summary_path}", flush=True)
    print(f"[frontend-release] TOTAL   {total_elapsed:.2f}s", flush=True)
    print(f"[frontend-release] RESULT  {overall_status}", flush=True)

    return 0 if overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
