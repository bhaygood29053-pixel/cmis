import inspect
import unittest

import moltgrid_signal_v12_ollama as legacy
from liquidity_scout.market import resolver as core_resolver


class LegacyVolumeRankingCleanupTests(unittest.TestCase):
    def test_dead_volume_ranking_implementation_is_removed(self):
        for name in (
            "aggregate_asset_activity",
            "get_asset_rank",
            "format_volume_rank_answer",
        ):
            self.assertFalse(hasattr(legacy, name), name)

    def test_live_rank_route_uses_packaged_ranking_service(self):
        asset_rank_source = inspect.getsource(legacy.format_asset_rank_answer)
        pool_answer_source = inspect.getsource(legacy.format_pool_answer)

        self.assertIn("rankings.find_asset_rank", asset_rank_source)
        self.assertNotIn("get_asset_rank", asset_rank_source)
        self.assertIn("wants_asset_rank", pool_answer_source)
        self.assertIn("format_asset_rank_answer", pool_answer_source)
        self.assertTrue(callable(legacy.wants_volume_rank))

    def test_resolver_asset_key_compatibility_export_is_preserved(self):
        self.assertIs(legacy.asset_key, core_resolver.asset_key)


if __name__ == "__main__":
    unittest.main()
