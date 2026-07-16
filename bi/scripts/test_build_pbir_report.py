import unittest

from bi.scripts.build_pbir_report import build_pages, mobile_positions


class PublicReportSpecificationTests(unittest.TestCase):
    def test_provider_slicer_exists_only_in_the_diagnostic_page(self) -> None:
        for _, display_name, visuals in build_pages():
            provider_fields = [
                projection
                for visual in visuals
                for projection in visual["visual"].get("query", {}).get("queryState", {}).get("Values", {}).get("projections", [])
                if projection.get("nativeQueryRef") == "provider"
            ]
            self.assertEqual(bool(provider_fields), display_name == "Diagnóstico de dados")

    def test_public_pages_stay_below_the_visual_density_limit(self) -> None:
        for _, display_name, visuals in build_pages():
            if display_name not in {"Diagnóstico de dados", "Detalhe do time", "Detalhe do jogador"}:
                self.assertLessEqual(len(visuals), 12, display_name)

    def test_venue_table_filters_out_teams_below_twenty_matches(self) -> None:
        _, _, visuals = next(page for page in build_pages() if page[1].endswith("Evolução e mando"))
        venue = next(visual for visual in visuals if visual["name"] == "c74fd5f4a12c58e56231")
        comparison = venue["filterConfig"]["filters"][0]["filter"]["Where"][0]["Condition"]["Comparison"]
        self.assertEqual(comparison["ComparisonKind"], 2)
        self.assertEqual(comparison["Right"]["Literal"]["Value"], "20L")

    def test_mobile_header_keeps_its_dark_panel_behind_the_title(self) -> None:
        _, _, visuals = next(page for page in build_pages() if page[1] == "1. Resumo executivo")
        positions = mobile_positions(visuals)
        panel, title = visuals[:2]
        self.assertEqual(positions[panel["name"]]["y"], 0)
        self.assertGreater(positions[title["name"]]["z"], positions[panel["name"]]["z"])


if __name__ == "__main__":
    unittest.main()
