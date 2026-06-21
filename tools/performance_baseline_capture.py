from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "artifacts"


@dataclass(frozen=True)
class EndpointCase:
    area: str
    name: str
    path: str


DEFAULT_CASES = [
    EndpointCase("home", "home", "/api/v1/home"),
    EndpointCase("players", "players_list", "/api/v1/players?pageSize=20"),
    EndpointCase("matches", "matches_list", "/api/v1/matches?pageSize=20"),
    EndpointCase("teams", "teams_list", "/api/v1/teams?pageSize=20"),
    EndpointCase("market", "market_transfers", "/api/v1/market/transfers?pageSize=24"),
    EndpointCase("rankings", "ranking_player_goals", "/api/v1/rankings/player-goals?pageSize=20"),
]


def resolve_base_url(cli_value: str | None) -> str:
    env_value = os.getenv("FOOTBALL_BASELINE_BASE_URL") or os.getenv("NEXT_PUBLIC_BFF_BASE_URL")
    base_url = (cli_value or env_value or "http://127.0.0.1:8000").strip()
    return base_url[:-1] if base_url.endswith("/") else base_url


def make_request(url: str, timeout_s: float) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    started_at = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout_s) as response:
            body = response.read()
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            payload_text = body.decode("utf-8", errors="replace")
            payload_json: Any | None = None
            try:
                payload_json = json.loads(payload_text)
            except json.JSONDecodeError:
                payload_json = None

            return {
                "ok": True,
                "status": response.status,
                "elapsed_ms": round(elapsed_ms, 2),
                "bytes": len(body),
                "headers": dict(response.headers.items()),
                "json": payload_json,
            }
    except HTTPError as error:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        body = error.read()
        return {
            "ok": False,
            "status": error.code,
            "elapsed_ms": round(elapsed_ms, 2),
            "bytes": len(body),
            "headers": dict(error.headers.items()),
            "error": f"HTTP {error.code}",
            "body_preview": body.decode("utf-8", errors="replace")[:500],
        }
    except URLError as error:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        return {
            "ok": False,
            "status": None,
            "elapsed_ms": round(elapsed_ms, 2),
            "bytes": 0,
            "headers": {},
            "error": f"URL error: {error.reason}",
        }


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    elapsed_values = [float(run["elapsed_ms"]) for run in runs]
    bytes_values = [int(run["bytes"]) for run in runs]
    statuses = [run.get("status") for run in runs]
    return {
        "run_count": len(runs),
        "ok_count": sum(1 for run in runs if run.get("ok")),
        "statuses": statuses,
        "elapsed_ms": {
            "min": round(min(elapsed_values), 2),
            "median": round(statistics.median(elapsed_values), 2),
            "max": round(max(elapsed_values), 2),
            "mean": round(statistics.fmean(elapsed_values), 2),
        },
        "bytes": {
            "min": min(bytes_values),
            "median": int(statistics.median(bytes_values)),
            "max": max(bytes_values),
            "mean": round(statistics.fmean(bytes_values), 2),
        },
    }


def build_cases(selected: list[str]) -> list[EndpointCase]:
    if not selected:
        return DEFAULT_CASES

    selected_names = {value.strip() for value in selected if value.strip()}
    return [case for case in DEFAULT_CASES if case.name in selected_names]


def write_summary_markdown(
    *,
    destination: Path,
    base_url: str,
    repeat_count: int,
    timeout_s: float,
    captured_at: str,
    results: list[dict[str, Any]],
) -> None:
    lines = [
        "# Performance Baseline Capture",
        "",
        f"- Captured at: `{captured_at}`",
        f"- Base URL: `{base_url}`",
        f"- Repetitions per endpoint: `{repeat_count}`",
        f"- Timeout: `{timeout_s}` seconds",
        "",
        "## Results",
        "",
    ]

    for result in results:
        summary = result["summary"]
        lines.extend(
            [
                f"### {result['name']}",
                "",
                f"- Area: `{result['area']}`",
                f"- Path: `{result['path']}`",
                f"- Statuses: `{summary['statuses']}`",
                f"- Latency median: `{summary['elapsed_ms']['median']} ms`",
                f"- Latency min/max: `{summary['elapsed_ms']['min']} / {summary['elapsed_ms']['max']} ms`",
                f"- Payload median: `{summary['bytes']['median']} bytes`",
                f"- Payload min/max: `{summary['bytes']['min']} / {summary['bytes']['max']} bytes`",
                "",
            ]
        )

    destination.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Captura baseline simples de endpoints quentes do BFF.")
    parser.add_argument("--base-url", default=None, help="Base URL do BFF. Default: env ou http://127.0.0.1:8000")
    parser.add_argument("--repeat", type=int, default=3, help="Numero de repeticoes por endpoint.")
    parser.add_argument("--timeout", type=float, default=15.0, help="Timeout por request, em segundos.")
    parser.add_argument("--case", action="append", default=[], help="Executa apenas um case por nome. Pode repetir.")
    parser.add_argument(
        "--artifacts-dir",
        default=str(DEFAULT_ARTIFACTS_DIR),
        help="Diretorio para gravar artefatos de baseline.",
    )
    args = parser.parse_args()

    base_url = resolve_base_url(args.base_url)
    cases = build_cases(args.case)
    if not cases:
        raise SystemExit("Nenhum case selecionado para captura.")

    if args.repeat <= 0:
        raise SystemExit("--repeat precisa ser maior que zero.")

    artifact_root = Path(args.artifacts_dir)
    captured_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = artifact_root / f"performance_baseline_{captured_at}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for case in cases:
        url = f"{base_url}{case.path}"
        runs = [make_request(url, args.timeout) for _ in range(args.repeat)]
        results.append(
            {
                "area": case.area,
                "name": case.name,
                "path": case.path,
                "url": url,
                "runs": runs,
                "summary": summarize_runs(runs),
            }
        )

    json_path = artifact_dir / "results.json"
    md_path = artifact_dir / "summary.md"
    payload = {
        "captured_at": captured_at,
        "base_url": base_url,
        "repeat": args.repeat,
        "timeout_seconds": args.timeout,
        "results": results,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    write_summary_markdown(
        destination=md_path,
        base_url=base_url,
        repeat_count=args.repeat,
        timeout_s=args.timeout,
        captured_at=captured_at,
        results=results,
    )

    print(f"[performance-baseline] wrote {json_path}")
    print(f"[performance-baseline] wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
