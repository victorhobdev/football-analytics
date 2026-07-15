"""Validate the checked-in BI artifact structure with the Python standard library."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


class ValidationError(RuntimeError):
    """Raised when a required BI artifact is missing or malformed."""


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid JSON: {path}") from exc


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise ValidationError(f"missing file: {path}")


def _inside(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError(f"path escapes BI root: {path}") from exc
    return resolved


def _validate_pbip(bi_root: Path) -> list[str]:
    pbip_path = bi_root / "FootballAnalytics_DesempenhoCompetitivo.pbip"
    pbip = _load_json(pbip_path)
    if not isinstance(pbip, dict):
        raise ValidationError(f"PBIP root must be an object: {pbip_path}")

    artifacts = pbip.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValidationError(f"PBIP has no artifacts: {pbip_path}")
    report_entry = artifacts[0]
    if not isinstance(report_entry, dict) or not isinstance(report_entry.get("report"), dict):
        raise ValidationError(f"PBIP report artifact is missing: {pbip_path}")
    report_relative_path = report_entry["report"].get("path")
    if not isinstance(report_relative_path, str):
        raise ValidationError(f"PBIP report path is missing: {pbip_path}")

    report_root = _inside(bi_root, bi_root / report_relative_path)
    report_definition = report_root / "definition.pbir"
    report = _load_json(report_definition)
    if not isinstance(report, dict):
        raise ValidationError(f"PBIR root must be an object: {report_definition}")

    dataset_reference = report.get("datasetReference", {}).get("byPath", {})
    dataset_relative_path = dataset_reference.get("path") if isinstance(dataset_reference, dict) else None
    if not isinstance(dataset_relative_path, str):
        raise ValidationError(f"PBIR dataset path is missing: {report_definition}")
    semantic_root = _inside(bi_root, report_root / dataset_relative_path)

    _load_json(semantic_root / "definition.pbism")
    semantic_definition = semantic_root / "definition"
    for file_name in ("database.tmdl", "model.tmdl", "relationships.tmdl"):
        _require_file(semantic_definition / file_name)

    table_files = sorted((semantic_definition / "tables").glob("*.tmdl"))
    if not table_files:
        raise ValidationError(f"no TMDL tables found: {semantic_definition / 'tables'}")
    relationship_text = (semantic_definition / "relationships.tmdl").read_text(encoding="utf-8")
    relationship_count = sum(line.startswith("relationship ") for line in relationship_text.splitlines())
    if relationship_count == 0:
        raise ValidationError(f"no TMDL relationships found: {semantic_definition / 'relationships.tmdl'}")

    report_definition_root = report_root / "definition"
    page_files = sorted(report_definition_root.glob("pages/*/page.json"))
    visual_files = sorted(report_definition_root.glob("pages/*/visuals/*/visual.json"))
    if not page_files:
        raise ValidationError(f"no PBIR pages found: {report_definition_root / 'pages'}")
    if not visual_files:
        raise ValidationError(f"no PBIR visuals found: {report_definition_root / 'pages'}")
    for json_path in sorted(report_definition_root.rglob("*.json")):
        _load_json(json_path)

    public_pages = 0
    diagnostic_pages = 0
    for page_path in page_files:
        page = _load_json(page_path)
        if not isinstance(page, dict):
            raise ValidationError(f"PBIR page root must be an object: {page_path}")
        display_name = page.get("displayName")
        hidden = page.get("visibility") == "HiddenInViewMode"
        if display_name == "Diagnóstico de dados":
            diagnostic_pages += 1
            if not hidden:
                raise ValidationError(f"diagnostic page must be hidden: {page_path}")
        if hidden:
            continue
        public_pages += 1
        page_visuals = sorted((page_path.parent / "visuals").glob("*/visual.json"))
        if len(page_visuals) > 12:
            raise ValidationError(f"public page exceeds 12 visuals: {page_path}")
        if any('"Property": "provider"' in path.read_text(encoding="utf-8") for path in page_visuals):
            raise ValidationError(f"public page exposes provider: {page_path}")
        for visual_path in page_visuals:
            visual = _load_json(visual_path)
            if not isinstance(visual, dict):
                raise ValidationError(f"PBIR visual root must be an object: {visual_path}")
            if visual.get("position", {}).get("y") != 12 and not (visual_path.parent / "mobile.json").is_file():
                raise ValidationError(f"public visual is missing its mobile layout: {visual_path}")

    if diagnostic_pages != 1:
        raise ValidationError("exactly one hidden diagnostic page is required")

    dim_scope = (semantic_definition / "tables" / "DimScope.tmdl").read_text(encoding="utf-8")
    if "column is_preferred_public_scope" not in dim_scope:
        raise ValidationError("DimScope is missing the preferred public scope flag")

    return [
        "PBIP JSON valid",
        f"PBIR pages valid ({len(page_files)} pages)",
        f"PBIR visuals valid ({len(visual_files)} visuals)",
        f"TMDL structure valid ({len(table_files)} tables, {relationship_count} relationships)",
        f"Public BI contract valid ({public_pages} public pages, provider hidden)",
    ]


def _validate_pbix(bi_root: Path) -> str:
    pbix_path = bi_root / "FootballAnalytics_DesempenhoCompetitivo.pbix"
    try:
        with zipfile.ZipFile(pbix_path) as archive:
            if archive.testzip() is not None:
                raise ValidationError(f"PBIX CRC check failed: {pbix_path}")
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValidationError(f"PBIX is not a readable ZIP: {pbix_path}") from exc

    required_entries = {"[Content_Types].xml", "Metadata", "Report/definition/report.json"}
    missing_entries = required_entries - names
    if missing_entries:
        raise ValidationError(f"PBIX entries missing: {sorted(missing_entries)}")
    return f"PBIX ZIP valid ({len(names)} entries)"


def validate_artifacts(bi_root: Path) -> list[str]:
    """Return structural checks for the repository's PBIP and PBIX artifacts."""

    bi_root = bi_root.resolve()
    _require_file(bi_root / "FootballAnalytics_DesempenhoCompetitivo.pbip")
    _require_file(bi_root / "FootballAnalytics_DesempenhoCompetitivo.pbix")
    return _validate_pbip(bi_root) + [_validate_pbix(bi_root)]


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]) if argv else Path(__file__).resolve().parents[1]
    try:
        checks = validate_artifacts(root)
    except ValidationError as exc:
        print(f"BI structural validation failed: {exc}", file=sys.stderr)
        return 1
    for check in checks:
        print(f"PASS {check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
