from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_ROOT = REPO_ROOT / "images"
DEFAULT_TARGET_ROOT = REPO_ROOT / "frontend" / "public" / "images" / "competition-season" / "editions"
DEFAULT_GENERATED_MODULE = (
    REPO_ROOT / "frontend" / "src" / "features" / "competitions" / "utils" / "champion-media.generated.ts"
)
DEFAULT_MANIFEST_PATH = DEFAULT_TARGET_ROOT / "manifest.json"
DEFAULT_CHAMPIONS_MANIFEST_PATH = REPO_ROOT / "data" / "visual_assets" / "manifests" / "champions.json"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".jfif", ".png", ".webp", ".avif"}

SOURCE_BASE_TO_COMPETITION_KEY = {
    "bundesliga": "bundesliga",
    "campeonato_brasileiro_serie_a": "brasileirao_a",
    "campeonato_brasileiro_serie_b": "brasileirao_b",
    "copa_do_brasil": "copa_do_brasil",
    "copa_libertadores_da_america": "libertadores",
    "copa_sudamericana": "sudamericana",
    "fifa_intercontinental_cup": "fifa_intercontinental_cup",
    "la_liga": "la_liga",
    "liga_portugal": "primeira_liga",
    "ligue_1": "ligue_1",
    "premier_league": "premier_league",
    "serie_a_italia": "serie_a_italy",
    "supercopa_do_brasil": "supercopa_do_brasil",
    "uefa_champions_league": "champions_league",
}

SEASON_TOKEN_PATTERN = re.compile(r"^(?P<start_year>\d{4})(?:_(?P<end_year>\d{4}))?$")


@dataclass(frozen=True)
class EditionAsset:
    competition_key: str
    season_label: str
    edition_key: str
    source_relative_path: str
    source_folder: str
    source_file: str
    public_filename: str
    public_src: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seleciona uma imagem por pasta de edicao em ./images, copia para "
            "frontend/public e gera o mapa de artwork usado pelo frontend."
        )
    )
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_SOURCE_ROOT),
        help="Diretorio raiz da ingestao bruta das imagens por edicao.",
    )
    parser.add_argument(
        "--target-root",
        default=str(DEFAULT_TARGET_ROOT),
        help="Diretorio publico de destino no frontend.",
    )
    parser.add_argument(
        "--generated-module",
        default=str(DEFAULT_GENERATED_MODULE),
        help="Arquivo TypeScript gerado com o mapa edition -> src.",
    )
    parser.add_argument(
        "--manifest-path",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Manifesto JSON gerado com a trilha source -> destino.",
    )
    parser.add_argument(
        "--champions-manifest-path",
        default=str(DEFAULT_CHAMPIONS_MANIFEST_PATH),
        help="Manifesto opcional de fotos de campeao em data/visual_assets para sobrepor assets brutos.",
    )
    return parser.parse_args()


def parse_folder_name(folder_name: str) -> tuple[str, str]:
    ordered_bases = sorted(SOURCE_BASE_TO_COMPETITION_KEY.keys(), key=len, reverse=True)
    for base in ordered_bases:
        prefix = f"{base}_"
        if not folder_name.startswith(prefix):
            continue

        season_token = folder_name.removeprefix(prefix)
        season_match = SEASON_TOKEN_PATTERN.fullmatch(season_token)
        if not season_match:
            raise RuntimeError(f"Token de temporada fora do padrao esperado: {folder_name}")

        start_year = season_match.group("start_year")
        end_year = season_match.group("end_year")
        season_label = start_year if end_year is None else f"{start_year}/{end_year}"
        return SOURCE_BASE_TO_COMPETITION_KEY[base], season_label

    raise RuntimeError(f"Base de competicao sem alias configurado: {folder_name}")


def build_public_season_token(season_label: str) -> str:
    return season_label.replace("/", "_")


def normalize_public_extension(extension: str) -> str:
    return ".jpg" if extension == ".jfif" else extension


def build_edition_asset(
    *,
    competition_key: str,
    season_label: str,
    source_path: Path,
) -> EditionAsset:
    public_extension = normalize_public_extension(source_path.suffix.lower())
    public_filename = f"{competition_key}__{build_public_season_token(season_label)}{public_extension}"
    public_src = f"/images/competition-season/editions/{public_filename}"

    return EditionAsset(
        competition_key=competition_key,
        season_label=season_label,
        edition_key=f"{competition_key}::{season_label}",
        source_relative_path=source_path.relative_to(REPO_ROOT).as_posix(),
        source_folder=source_path.parent.name,
        source_file=source_path.name,
        public_filename=public_filename,
        public_src=public_src,
    )


def pick_stable_random_file(files: list[Path], folder_name: str) -> Path:
    ordered_files = sorted(files, key=lambda item: item.name.lower())
    digest = hashlib.sha256(folder_name.encode("utf-8")).hexdigest()
    return ordered_files[int(digest, 16) % len(ordered_files)]


def collect_source_root_assets(source_root: Path) -> list[EditionAsset]:
    if not source_root.exists():
        raise RuntimeError(f"Diretorio de origem nao encontrado: {source_root}")

    edition_assets: list[EditionAsset] = []
    seen_edition_keys: set[str] = set()

    folders = sorted((path for path in source_root.iterdir() if path.is_dir()), key=lambda item: item.name.lower())
    for folder in folders:
        competition_key, season_label = parse_folder_name(folder.name)
        edition_key = f"{competition_key}::{season_label}"
        if edition_key in seen_edition_keys:
            raise RuntimeError(f"Edicao duplicada na ingestao bruta: {edition_key}")
        seen_edition_keys.add(edition_key)

        candidate_files = sorted(
            [
                file_path
                for file_path in folder.iterdir()
                if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS
            ],
            key=lambda item: item.name.lower(),
        )
        if not candidate_files:
            raise RuntimeError(f"Pasta sem imagem suportada: {folder.name}")

        selected_file = pick_stable_random_file(candidate_files, folder.name)
        edition_assets.append(
            build_edition_asset(
                competition_key=competition_key,
                season_label=season_label,
                source_path=selected_file,
            )
        )

    if not edition_assets:
        raise RuntimeError("Nenhuma pasta de edicao encontrada em ./images.")

    return edition_assets


def collect_champion_manifest_assets(champions_manifest_path: Path) -> list[EditionAsset]:
    if not champions_manifest_path.exists():
        return []

    payload = json.loads(champions_manifest_path.read_text(encoding="utf-8"))
    edition_assets: list[EditionAsset] = []
    allowed_statuses = {"downloaded", "cached_local"}

    for entry in payload.get("entries", []):
        if entry.get("status") not in allowed_statuses:
            continue

        competition_key = str(entry.get("competition_key") or "").strip()
        season_label = str(entry.get("season_label") or "").strip()
        local_path = str(entry.get("local_path") or "").strip()
        if not competition_key or not season_label or not local_path:
            continue

        source_path = (REPO_ROOT / Path(local_path.replace("\\", "/"))).resolve()
        if not source_path.exists() or source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        edition_assets.append(
            build_edition_asset(
                competition_key=competition_key,
                season_label=season_label,
                source_path=source_path,
            )
        )

    return edition_assets


def collect_edition_assets(source_root: Path, champions_manifest_path: Path) -> list[EditionAsset]:
    source_root_assets = collect_source_root_assets(source_root)
    champion_manifest_assets = collect_champion_manifest_assets(champions_manifest_path)
    assets_by_edition = {
        asset.edition_key: asset
        for asset in source_root_assets
    }

    for asset in champion_manifest_assets:
        assets_by_edition[asset.edition_key] = asset

    return sorted(assets_by_edition.values(), key=lambda item: (item.competition_key, item.season_label))


def copy_assets(source_root: Path, target_root: Path, edition_assets: list[EditionAsset]) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    for asset in edition_assets:
        source_path = REPO_ROOT / Path(asset.source_relative_path)
        target_path = target_root / asset.public_filename
        shutil.copy2(source_path, target_path)


def write_generated_module(generated_module_path: Path, edition_assets: list[EditionAsset]) -> None:
    generated_module_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "// Generated by tools/publish_champion_edition_assets.py. Do not edit manually.",
        "",
        "export const CHAMPION_ARTWORK_BY_EDITION: Record<string, { src: string }> = {",
    ]

    for asset in sorted(edition_assets, key=lambda item: (item.competition_key, item.season_label)):
        lines.append(f'  // {asset.source_relative_path}')
        lines.append(f'  "{asset.edition_key}": {{ src: "{asset.public_src}" }},')

    lines.extend(
        [
            "};",
            "",
        ]
    )

    generated_module_path.write_text("\n".join(lines), encoding="utf-8")


def write_manifest(manifest_path: Path, source_root: Path, target_root: Path, edition_assets: list[EditionAsset]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": utc_now(),
        "source_root": source_root.relative_to(REPO_ROOT).as_posix(),
        "target_root": target_root.relative_to(REPO_ROOT).as_posix(),
        "summary": {
            "editions_total": len(edition_assets),
            "competitions_total": len({asset.competition_key for asset in edition_assets}),
        },
        "entries": [asdict(asset) for asset in sorted(edition_assets, key=lambda item: (item.competition_key, item.season_label))],
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    source_root = Path(args.source_root).resolve()
    target_root = Path(args.target_root).resolve()
    generated_module_path = Path(args.generated_module).resolve()
    manifest_path = Path(args.manifest_path).resolve()
    champions_manifest_path = Path(args.champions_manifest_path).resolve()

    edition_assets = collect_edition_assets(
        source_root=source_root,
        champions_manifest_path=champions_manifest_path,
    )
    copy_assets(source_root=source_root, target_root=target_root, edition_assets=edition_assets)
    write_generated_module(generated_module_path=generated_module_path, edition_assets=edition_assets)
    write_manifest(
        manifest_path=manifest_path,
        source_root=source_root,
        target_root=target_root,
        edition_assets=edition_assets,
    )

    print(
        json.dumps(
            {
                "generated_at": utc_now(),
                "source_root": source_root.as_posix(),
                "target_root": target_root.as_posix(),
                "generated_module": generated_module_path.as_posix(),
                "manifest_path": manifest_path.as_posix(),
                "editions_total": len(edition_assets),
                "competitions_total": len({asset.competition_key for asset in edition_assets}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
