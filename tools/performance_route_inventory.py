from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_APP_DIR = REPO_ROOT / "frontend" / "src" / "app" / "(platform)"
FRONTEND_SRC_DIR = REPO_ROOT / "frontend" / "src"
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "artifacts"

ENDPOINT_PATTERN = re.compile(r'"(/api/v1/[^"]+)"')
USE_QUERY_PATTERN = re.compile(r"\buseQuery\s*\(")
USE_QUERIES_PATTERN = re.compile(r"\buseQueries\s*\(")
USE_CLIENT_PATTERN = re.compile(r'^[\s\ufeff]*"use client";', re.MULTILINE)


@dataclass(frozen=True)
class RouteFile:
    route: str
    path: Path


def normalize_route(path: Path) -> str:
    relative = path.relative_to(FRONTEND_APP_DIR)
    without_name = relative.parent if relative.name == "page.tsx" else relative
    route = "/" + "/".join(without_name.parts)
    return route.replace("/(home)", "").replace("/[...missing]", "/*missing") or "/"


def collect_route_files() -> list[RouteFile]:
    result: list[RouteFile] = []
    for path in sorted(FRONTEND_APP_DIR.rglob("page.tsx")):
        result.append(RouteFile(route=normalize_route(path), path=path))
    return result


def collect_frontend_endpoints() -> dict[str, list[str]]:
    endpoint_map: dict[str, list[str]] = {}
    for path in sorted(FRONTEND_SRC_DIR.rglob("*.ts*")):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")
        matches = sorted(set(match.group(1) for match in ENDPOINT_PATTERN.finditer(text)))
        if matches:
            endpoint_map[str(path.relative_to(REPO_ROOT))] = matches
    return endpoint_map


def build_route_inventory() -> list[dict[str, object]]:
    endpoint_map = collect_frontend_endpoints()
    route_files = collect_route_files()
    inventory: list[dict[str, object]] = []

    for route_file in route_files:
        try:
            text = route_file.path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = route_file.path.read_text(encoding="utf-8", errors="ignore")

        related_files: list[str] = []
        route_dir = route_file.path.parent
        for candidate in sorted(route_dir.glob("*.ts*")):
            if candidate.name == "page.tsx":
                related_files.append(str(candidate.relative_to(REPO_ROOT)))
                continue
            if candidate.suffix not in {".ts", ".tsx"}:
                continue
            related_files.append(str(candidate.relative_to(REPO_ROOT)))

        discovered_endpoints: list[str] = []
        for relative_path, endpoints in endpoint_map.items():
            if relative_path in related_files:
                discovered_endpoints.extend(endpoints)

        inventory.append(
            {
                "route": route_file.route,
                "page_file": str(route_file.path.relative_to(REPO_ROOT)),
                "is_client_page": bool(USE_CLIENT_PATTERN.search(text)),
                "use_query_count": len(USE_QUERY_PATTERN.findall(text)),
                "use_queries_count": len(USE_QUERIES_PATTERN.findall(text)),
                "related_files": related_files,
                "discovered_endpoints": sorted(set(discovered_endpoints)),
            }
        )

    return inventory


def write_markdown(path: Path, inventory: list[dict[str, object]], captured_at: str) -> None:
    lines = [
        "# Performance Route Inventory",
        "",
        f"- Captured at: `{captured_at}`",
        f"- Routes inventoried: `{len(inventory)}`",
        "",
        "## Routes",
        "",
    ]

    for item in inventory:
        endpoints = item["discovered_endpoints"]
        related_files = item["related_files"]
        lines.extend(
            [
                f"### {item['route']}",
                "",
                f"- Page file: `{item['page_file']}`",
                f"- Client page: `{item['is_client_page']}`",
                f"- `useQuery` count in page file: `{item['use_query_count']}`",
                f"- `useQueries` count in page file: `{item['use_queries_count']}`",
                f"- Related files: `{len(related_files)}`",
                f"- Discovered endpoints: `{endpoints}`",
                "",
            ]
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera inventario estatico de rotas e endpoints do frontend.")
    parser.add_argument(
        "--artifacts-dir",
        default=str(DEFAULT_ARTIFACTS_DIR),
        help="Diretorio onde gravar os artefatos.",
    )
    args = parser.parse_args()

    artifact_root = Path(args.artifacts_dir)
    captured_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = artifact_root / f"performance_route_inventory_{captured_at}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    inventory = build_route_inventory()
    json_path = artifact_dir / "inventory.json"
    md_path = artifact_dir / "summary.md"

    json_path.write_text(json.dumps({"captured_at": captured_at, "routes": inventory}, indent=2), encoding="utf-8")
    write_markdown(md_path, inventory, captured_at)

    print(f"[performance-route-inventory] wrote {json_path}")
    print(f"[performance-route-inventory] wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
