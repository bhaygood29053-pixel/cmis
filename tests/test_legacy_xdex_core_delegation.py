import unittest

import moltgrid_signal_v12_ollama as legacy
from liquidity_scout.integrations import moltgrid as bridge
from liquidity_scout.market import resolver as core_resolver


class LegacyXDEXCoreDelegationTests(unittest.TestCase):
    def test_catalog_and_resolvers_come_from_bridge(self):
        self.assertIs(legacy.XDEXCatalog, bridge.MoltGridXDEXCatalog)
        self.assertIs(legacy.resolve_asset, bridge.resolve_asset)
        self.assertIs(legacy.resolve_multiple_assets, bridge.resolve_multiple_assets)

    def test_resolver_helpers_come_from_reusable_core(self):
        self.assertIs(legacy.asset_key, core_resolver.asset_key)
        self.assertIs(legacy.candidate_terms, core_resolver.candidate_terms)
        self.assertIs(legacy.find_matches_for_term, core_resolver.find_matches_for_term)
        self.assertIs(legacy.pool_address, core_resolver.pool_address)
        self.assertIs(
            legacy.explicitly_requests_multiple_assets,
            core_resolver.explicitly_requests_multiple_assets,
        )

    def test_exact_asset_resolution_preserves_listener_contract(self):
        pools = [
            {
                "address": "POOL_AGI_XNT",
                "liquidity": 3500,
                "volume24h": 1400,
                "baseToken": {
                    "symbol": "AGI",
                    "name": "Artificial General Intelligence",
                    "mint": "AGI_MINT",
                    "address": "AGI_MINT",
                },
                "quoteToken": {
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "mint": "XNT_MINT",
                    "address": "XNT_MINT",
                },
            }
        ]

        term, matches = legacy.resolve_asset("What is AGI doing?", pools)

        self.assertEqual(term, "AGI")
        self.assertTrue(matches)
        self.assertEqual(matches[0][2]["mint"], "AGI_MINT")

    def test_ambiguous_symbol_fails_closed_at_listener_boundary(self):
        pools = [
            {
                "address": "POOL_ONE",
                "liquidity": 5000,
                "volume24h": 1000,
                "baseToken": {
                    "symbol": "DUP",
                    "name": "Duplicate One",
                    "mint": "DUP_MINT_ONE",
                },
                "quoteToken": {"symbol": "XNT", "mint": "XNT_MINT"},
            },
            {
                "address": "POOL_TWO",
                "liquidity": 6000,
                "volume24h": 900,
                "baseToken": {
                    "symbol": "DUP",
                    "name": "Duplicate Two",
                    "mint": "DUP_MINT_TWO",
                },
                "quoteToken": {"symbol": "XNT", "mint": "XNT_MINT"},
            },
        ]

        term, matches = legacy.resolve_asset("What is DUP doing?", pools)

        self.assertIsNone(term)
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
