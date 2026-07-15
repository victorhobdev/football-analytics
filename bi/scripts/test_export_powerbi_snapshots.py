import unittest

from bi.scripts.export_powerbi_snapshots import QUERIES


class PublicScopeQueriesTests(unittest.TestCase):
    def test_public_facts_use_the_shared_provider_precedence(self) -> None:
        for table in ("FactMatch", "FactTeamMatch", "FactPlayerMatch"):
            query = QUERIES[table]
            self.assertIn("preferred_scopes", query)
            self.assertIn("when 'sportmonks' then 1", query)
            self.assertIn("when 'dataset_brasileirao' then 2", query)
            self.assertIn("when 'transfermarkt' then 3", query)
            self.assertIn("when 'eloratings' then 4", query)

    def test_scope_dimension_keeps_a_diagnostic_flag(self) -> None:
        self.assertIn("is_preferred_public_scope", QUERIES["DimScope"])
        self.assertIn("control.competitions", QUERIES["DimScope"])


if __name__ == "__main__":
    unittest.main()
