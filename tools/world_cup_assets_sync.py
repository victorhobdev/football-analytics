from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
VISUAL_ASSETS_ROOT = REPO_ROOT / "data" / "visual_assets"
MANIFESTS_DIR = VISUAL_ASSETS_ROOT / "manifests"
WC_OVERLAY_MANIFEST_PATH = VISUAL_ASSETS_ROOT / "wc_pipeline" / "wc_overlay_manifest.json"
WC_TEAM_MANIFEST_PATH = VISUAL_ASSETS_ROOT / "wc_pipeline" / "wc_team_asset_manifest.json"
WC_PLAYER_MANIFEST_PATH = VISUAL_ASSETS_ROOT / "wc_pipeline" / "wc_player_asset_manifest.json"
COMPETITIONS_OVERRIDES_PATH = MANIFESTS_DIR / "competitions.overrides.json"
CLUBS_OVERRIDES_PATH = MANIFESTS_DIR / "clubs.overrides.json"
PLAYERS_OVERRIDES_PATH = MANIFESTS_DIR / "players.overrides.json"
BASE_MANIFEST_NAMES = ("competitions.json", "clubs.json", "players.json", "summary.json")
OVERRIDES_MANIFEST_NAMES = (
    "competitions.overrides.json",
    "clubs.overrides.json",
    "players.overrides.json",
)
GENERATED_SOURCE_KIND = "world_cup_assets_sync"
PUBLISHABLE_SOURCE_KINDS = {
    GENERATED_SOURCE_KIND,
    "manual_local_override",
    "manual_override",
    "wc_reconciliation_use_base",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materializa manifests oficiais de override da Copa do Mundo e sincroniza "
            "o delta de assets/manifests para um target_root de producao."
        )
    )
    parser.add_argument(
        "--target-root",
        help=(
            "Diretorio raiz do visual_assets em producao. Ex.: "
            "/srv/football-analytics/visual_assets ou docroot servido por Nginx/CDN."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nao copia arquivos para o target_root. Ainda atualiza os manifests locais e valida o bundle.",
    )
    return parser.parse_args()


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def to_relative_visual_assets_path(local_path: str) -> Path:
    normalized = local_path.replace("\\", "/")
    prefix = "data/visual_assets/"
    if not normalized.startswith(prefix):
        raise ValueError(f"local_path fora de data/visual_assets: {local_path}")
    return Path(normalized[len(prefix) :])


def source_path_from_local_path(local_path: str) -> Path:
    return REPO_ROOT / Path(local_path.replace("\\", "/"))


def manifest_key(entry: dict[str, Any]) -> str:
    if entry.get("entity_key") is not None:
        return f"key:{entry['entity_key']}"
    return f"id:{entry.get('entity_id')}"


def merge_generated_entries(
    existing_entries: list[dict[str, Any]],
    generated_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    generated_keys = {manifest_key(entry) for entry in generated_entries}
    merged: list[dict[str, Any]] = []
    for entry in existing_entries:
        entry_source_kind = str(entry.get("source_kind") or "")
        key = manifest_key(entry)
        if key in generated_keys:
            if entry_source_kind == GENERATED_SOURCE_KIND:
                continue
            if entry_source_kind in {"manual_override", "wc_reconciliation_use_base"}:
                merged.append(entry)
                generated_keys.remove(key)
                continue
            continue
        merged.append(entry)
    generated_by_key = {manifest_key(entry): entry for entry in generated_entries}
    for key in sorted(generated_keys):
        merged.append(generated_by_key[key])
    return merged


def build_competitions_overrides() -> dict[str, Any]:
    overlay_manifest = load_json(WC_OVERLAY_MANIFEST_PATH, default={"entries": []})
    entries = []
    for item in overlay_manifest.get("entries", []):
        if item.get("entity_type") != "competition" or item.get("status") != "ok":
            continue
        entries.append(
            {
                "entity_key": item["asset_id"],
                "entity_name": item.get("display_name"),
                "source_kind": GENERATED_SOURCE_KIND,
                "local_path": item["local_path"],
                "content_type": item.get("content_type", "image/png"),
                "status": "published",
                "generated_at": utc_now(),
            }
        )
    existing = load_json(COMPETITIONS_OVERRIDES_PATH, default={"entries": []})
    merged = merge_generated_entries(existing.get("entries", []), entries)
    payload = {
        "generated_at": utc_now(),
        "entries": merged,
    }
    write_json(COMPETITIONS_OVERRIDES_PATH, payload)
    return payload


def build_clubs_overrides() -> dict[str, Any]:
    team_manifest = load_json(WC_TEAM_MANIFEST_PATH, default={"entries": []})
    entries = []
    for item in team_manifest.get("entries", []):
        if item.get("status") != "published" or not item.get("asset_path"):
            continue
        entries.append(
            {
                "entity_key": item["team_slug"],
                "entity_name": item.get("display_name"),
                "source_kind": GENERATED_SOURCE_KIND,
                "local_path": item["asset_path"],
                "content_type": "image/png",
                "status": "published",
                "source": item.get("source"),
                "source_url": item.get("source_url"),
                "generated_at": utc_now(),
            }
        )
    existing = load_json(CLUBS_OVERRIDES_PATH, default={"entries": []})
    merged = merge_generated_entries(existing.get("entries", []), entries)
    payload = {
        "generated_at": utc_now(),
        "entries": merged,
    }
    write_json(CLUBS_OVERRIDES_PATH, payload)
    return payload


def build_players_overrides() -> dict[str, Any]:
    player_overlay_manifest = load_json(WC_PLAYER_MANIFEST_PATH, default={"entries": []})
    existing = load_json(PLAYERS_OVERRIDES_PATH, default={"entries": []})
    entries = []
    for item in player_overlay_manifest.get("entries", []):
        if item.get("status") != "published" or not item.get("published_path"):
            continue
        entries.append(
            {
                "entity_id": item["wc_player_id"],
                "entity_name": item.get("player_name"),
                "source_kind": GENERATED_SOURCE_KIND,
                "local_path": item["published_path"],
                "content_type": "image/png",
                "status": "published_world_cup_overlay",
                "source": item.get("source"),
                "confidence": item.get("confidence_score", item.get("confidence")),
                "candidate_title": item.get("matched_page_title", item.get("candidate_title")),
                "candidate_page_url": item.get("matched_url", item.get("candidate_page_url")),
                "generated_at": utc_now(),
            }
        )
    merged = merge_generated_entries(existing.get("entries", []), entries)
    payload = {
        "generated_at": utc_now(),
        "entries": merged,
    }
    write_json(PLAYERS_OVERRIDES_PATH, payload)
    return payload


def referenced_world_cup_files(
    competitions_overrides: dict[str, Any],
    clubs_overrides: dict[str, Any],
    players_overrides: dict[str, Any],
) -> list[Path]:
    files: list[Path] = []
    for payload in (competitions_overrides, clubs_overrides, players_overrides):
        for entry in payload.get("entries", []):
            local_path = entry.get("local_path")
            source_kind = str(entry.get("source_kind") or "")
            if not isinstance(local_path, str):
                continue
            if source_kind not in PUBLISHABLE_SOURCE_KINDS:
                continue
            files.append(source_path_from_local_path(local_path))
    return sorted({path.resolve() for path in files})


def validate_override_payload(
    payload: dict[str, Any],
    *,
    root: Path,
    label: str,
) -> list[str]:
    errors: list[str] = []
    for entry in payload.get("entries", []):
        local_path = entry.get("local_path")
        source_kind = str(entry.get("source_kind") or "")
        if not isinstance(local_path, str):
            continue
        if source_kind not in PUBLISHABLE_SOURCE_KINDS:
            continue
        candidate = root / to_relative_visual_assets_path(local_path)
        if not candidate.exists():
            errors.append(f"{label}:missing:{candidate.as_posix()}")
    return errors


def sync_to_target_root(
    target_root: Path,
    *,
    competitions_overrides: dict[str, Any],
    clubs_overrides: dict[str, Any],
    players_overrides: dict[str, Any],
) -> list[Path]:
    copied_paths: list[Path] = []
    target_root.mkdir(parents=True, exist_ok=True)

    for manifest_name in BASE_MANIFEST_NAMES:
        source_manifest = MANIFESTS_DIR / manifest_name
        if not source_manifest.exists():
            continue
        destination_manifest = target_root / "manifests" / manifest_name
        destination_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_manifest, destination_manifest)
        copied_paths.append(destination_manifest)

    for manifest_name in OVERRIDES_MANIFEST_NAMES:
        source_manifest = MANIFESTS_DIR / manifest_name
        if not source_manifest.exists():
            continue
        destination_manifest = target_root / "manifests" / manifest_name
        destination_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_manifest, destination_manifest)
        copied_paths.append(destination_manifest)

    for source_path in referenced_world_cup_files(
        competitions_overrides,
        clubs_overrides,
        players_overrides,
    ):
        relative_target = source_path.relative_to(VISUAL_ASSETS_ROOT)
        destination_path = target_root / relative_target
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        copied_paths.append(destination_path)

    return copied_paths


def main() -> None:
    args = parse_args()

    competitions_overrides = build_competitions_overrides()
    clubs_overrides = build_clubs_overrides()
    players_overrides = build_players_overrides()

    source_errors = []
    source_errors.extend(
        validate_override_payload(competitions_overrides, root=VISUAL_ASSETS_ROOT, label="source:competitions")
    )
    source_errors.extend(validate_override_payload(clubs_overrides, root=VISUAL_ASSETS_ROOT, label="source:clubs"))
    source_errors.extend(validate_override_payload(players_overrides, root=VISUAL_ASSETS_ROOT, label="source:players"))

    copied_paths: list[Path] = []
    target_errors: list[str] = []
    if args.target_root:
        target_root = Path(args.target_root).resolve()
        if not args.dry_run:
            copied_paths = sync_to_target_root(
                target_root,
                competitions_overrides=competitions_overrides,
                clubs_overrides=clubs_overrides,
                players_overrides=players_overrides,
            )
        target_errors.extend(
            validate_override_payload(competitions_overrides, root=target_root, label="target:competitions")
        )
        target_errors.extend(validate_override_payload(clubs_overrides, root=target_root, label="target:clubs"))
        target_errors.extend(validate_override_payload(players_overrides, root=target_root, label="target:players"))

    summary = {
        "generated_at": utc_now(),
        "competitions_overrides_entries": len(competitions_overrides.get("entries", [])),
        "clubs_overrides_entries": len(clubs_overrides.get("entries", [])),
        "players_overrides_entries": len(players_overrides.get("entries", [])),
        "world_cup_referenced_files": len(
            referenced_world_cup_files(competitions_overrides, clubs_overrides, players_overrides)
        ),
        "source_validation_errors": source_errors,
        "target_root": str(Path(args.target_root).resolve()) if args.target_root else None,
        "target_validation_errors": target_errors,
        "copied_files_count": len(copied_paths),
        "dry_run": bool(args.dry_run),
    }
    print(json.dumps(summary, ensure_ascii=False))
    if source_errors or target_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
