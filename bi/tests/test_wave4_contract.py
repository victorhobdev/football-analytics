from __future__ import annotations

import json
import unittest
from pathlib import Path

from bi.scripts.export_powerbi_snapshots import (
    DEFAULT_SNAPSHOT_DIR,
    QUERIES,
    build_manifest,
    parse_args,
    resolve_snapshot_dir,
)


ROOT = Path(__file__).resolve().parents[2]
REPORT_PAGES = ROOT / "bi" / "FootballAnalytics_DesempenhoCompetitivo.Report" / "definition" / "pages"
POWER_QUERY = ROOT / "bi" / "power-query"
MODEL_TABLES = ROOT / "bi" / "FootballAnalytics_DesempenhoCompetitivo.SemanticModel" / "definition" / "tables"


class SnapshotContractTests(unittest.TestCase):
    def test_cli_path_has_precedence_and_relative_paths_use_repository_root(self) -> None:
        resolved = resolve_snapshot_dir("bi/data/test-snapshots", {"BI_SNAPSHOT_DIR": "ignored"}, root=ROOT)
        self.assertEqual(resolved, (ROOT / "bi" / "data" / "test-snapshots").resolve())

    def test_environment_path_is_used_when_cli_is_omitted(self) -> None:
        resolved = resolve_snapshot_dir(None, {"BI_SNAPSHOT_DIR": "bi/data/env-snapshots"}, root=ROOT)
        self.assertEqual(resolved, (ROOT / "bi" / "data" / "env-snapshots").resolve())

    def test_default_is_the_documented_shared_snapshot_directory(self) -> None:
        self.assertEqual(resolve_snapshot_dir(None, {}, root=ROOT), DEFAULT_SNAPSHOT_DIR.resolve())

    def test_cli_exposes_output_directory(self) -> None:
        self.assertEqual(parse_args(["--output-dir", "bi/data/cli-snapshots"]).output_dir, "bi/data/cli-snapshots")

    def test_manifest_keeps_the_seven_snapshot_contract(self) -> None:
        manifest = build_manifest({"DimDate": {"rows": 1, "bytes": 2, "sha256": "hash"}})
        self.assertEqual(manifest["source"], "PostgreSQL mart")
        self.assertEqual(manifest["tables"]["DimDate"]["rows"], 1)
        self.assertEqual(len(QUERIES), 7)

    def test_report_pages_and_visuals_match_the_versioned_contract(self) -> None:
        pages = [json.loads(path.read_text(encoding="utf-8")) for path in REPORT_PAGES.glob("*/page.json")]
        public_pages = [page for page in pages if "pageBinding" not in page]
        drillthrough_pages = [page for page in pages if "pageBinding" in page]
        visual_count = sum(len(list((REPORT_PAGES / page["name"] / "visuals").glob("*/visual.json"))) for page in pages)

        self.assertEqual(len(pages), 8)
        self.assertEqual(len(public_pages), 6)
        self.assertEqual(len(drillthrough_pages), 2)
        self.assertEqual(visual_count, 94)

    def test_screenshots_are_declared_as_partial_evidence(self) -> None:
        screenshots = {path.stem for path in (ROOT / "bi" / "screenshots").glob("*.png")}
        self.assertEqual(screenshots, {"01-panorama", "02-times", "03-evolucao-mando", "04-jogadores", "05-cobertura"})
        self.assertLess(len(screenshots), 6)

    def test_power_query_sources_use_the_shared_parameter(self) -> None:
        for source in POWER_QUERY.glob("*.m"):
            text = source.read_text(encoding="utf-8")
            self.assertIn("SnapshotRoot &", text, source.name)
            self.assertNotIn("C:\\\\Users\\\\Public", text, source.name)

        for table in MODEL_TABLES.glob("*.tmdl"):
            text = table.read_text(encoding="utf-8")
            if "partition " in text and " = m" in text:
                self.assertIn("SnapshotRoot &", text, table.name)
                self.assertNotIn("C:\\\\Users\\\\Public", text, table.name)


if __name__ == "__main__":
    unittest.main()
