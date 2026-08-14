import unittest
from types import SimpleNamespace
from unittest.mock import patch

from liquidity_scout.integrations import moltgrid


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
        "address": mint,
    }


def pool(address, base, quote, liquidity, volume24h=0):
    return {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "liquidity": liquidity,
        "volume24h": volume24h,
    }


class MoltGridMarketBridgeTests(unittest.TestCase):
    def setUp(self):
        self.xnt = token("XNT", "MINT_XNT", "Wrapped XNT")
        self.agi = token("AGI", "MINT_AGI", "Artificial General Intelligence")
        self.usdc = token("USDC", "MINT_USDC", "USD Coin")

    def test_wire_market_core_replaces_only_market_globals(self):
        original_main = object()
        listener = SimpleNamespace(
            XDEXCatalog=object(),
            resolve_asset=object(),
            resolve_multiple_assets=object(),
            main=original_main,
        )

        result = moltgrid.wire_market_core(listener)

        self.assertIs(result, listener)
        self.assertIs(listener.XDEXCatalog, moltgrid.MoltGridXDEXCatalog)
        self.assertIs(listener.resolve_asset, moltgrid.resolve_asset)
        self.assertIs(
            listener.resolve_multiple_assets,
            moltgrid.resolve_multiple_assets,
        )
        self.assertIs(listener.main, original_main)

    def test_single_asset_resolution_uses_core_pool_ordering(self):
        pools = [
            pool("P1", self.agi, self.xnt, 1000, 500),
            pool("P2", self.agi, self.usdc, 5000, 100),
        ]

        term, matches = moltgrid.resolve_asset("What is AGI doing?", pools)

        self.assertEqual(term.upper(), "AGI")
        self.assertEqual(matches[0][0]["address"], "P2")
        self.assertEqual(len(matches), 2)

    def test_ambiguous_symbol_fails_closed_for_listener(self):
        same_one = token("SAME", "MINT_ONE", "Same One")
        same_two = token("SAME", "MINT_TWO", "Same Two")
        pools = [
            pool("P1", same_one, self.xnt, 1000),
            pool("P2", same_two, self.usdc, 5000),
        ]

        term, matches = moltgrid.resolve_asset("What is SAME doing?", pools)

        self.assertIsNone(term)
        self.assertEqual(matches, [])

    def test_multi_asset_ambiguity_fails_closed_for_listener(self):
        same_one = token("SAME", "MINT_ONE", "Same One")
        same_two = token("SAME", "MINT_TWO", "Same Two")
        pools = [
            pool("P1", same_one, self.xnt, 1000),
            pool("P2", same_two, self.usdc, 5000),
        ]

        resolved = moltgrid.resolve_multiple_assets(
            "Compare SAME vs XNT",
            pools,
        )

        self.assertEqual(resolved, [])

    def test_main_runs_wired_legacy_listener(self):
        calls = []
        listener = SimpleNamespace(main=lambda: calls.append("main"))

        with patch.object(moltgrid, "load_listener", return_value=listener):
            moltgrid.main()

        self.assertEqual(calls, ["main"])


if __name__ == "__main__":
    unittest.main()
