import inspect
import unittest

import xdex_rankings as legacy
from liquidity_scout.services import market_rankings as service


class LegacyRankingsDelegationTests(unittest.TestCase):
    def test_legacy_module_reexports_canonical_ranking_functions(self):
        self.assertIs(legacy.rank_assets, service.rank_assets)
        self.assertIs(legacy.find_asset_rank, service.find_asset_rank)
        self.assertIs(legacy.format_top, service.format_top)

    def test_legacy_module_contains_no_ranking_implementation(self):
        source = inspect.getsource(legacy)

        self.assertIn("from liquidity_scout.services.market_rankings import", source)
        self.assertNotIn("def rank_assets", source)
        self.assertNotIn("def find_asset_rank", source)
        self.assertNotIn("def format_top", source)


if __name__ == "__main__":
    unittest.main()
