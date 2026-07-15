import unittest

from bi.scripts.build_pbir_report import build_pages


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


if __name__ == "__main__":
    unittest.main()
