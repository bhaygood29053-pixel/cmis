import unittest
from types import SimpleNamespace
from unittest.mock import patch

import moltgrid_signal_v12_ollama as legacy


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
        "address": mint,
    }


def pool(address, base, quote, liquidity, volume24h=0, holders=1000):
    return {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "liquidity": liquidity,
        "volume24h": volume24h,
        "txns24h": 10,
        "holders": holders,
        "priceUsd": 0.25,
        "priceChange1h": 1.5,
        "priceChange24h": 4.0,
        "safetyGrade": "A",
        "safetyScore": 90,
        "createdAt": "2026-01-01T00:00:00Z",
    }


class LegacySnapshotDelegationTests(unittest.TestCase):
    def setUp(self):
        self.agi = token("AGI", "MINT_AGI", "Artificial General Intelligence")
        self.xnt = token("XNT", "MINT_XNT", "Wrapped XNT")
        self.usdc = token("USDC", "MINT_USDC", "USD Coin")
        self.catalog = SimpleNamespace(xnt_price_usd=None, last_refresh=123.0)

    def test_compact_snapshot_delegates_to_moltgrid_bridge(self):
        matches = ["matches"]

        with patch.object(
            legacy,
            "bridge_compact_asset_snapshot",
            return_value={"delegated": True},
        ) as delegated:
            result = legacy.compact_asset_snapshot("AGI", matches, self.catalog)

        self.assertEqual(result, {"delegated": True})
        delegated.assert_called_once_with(legacy, "AGI", matches, self.catalog)

    def test_snapshot_uses_asset_wide_multi_lp_metrics(self):
        primary = pool("P1", self.agi, self.usdc, 5000, 100)
        secondary = pool("P2", self.agi, self.xnt, 1000, 500)
        matches = [
            (primary, "base", self.agi, 90),
            (secondary, "base", self.agi, 90),
        ]

        snap = legacy.compact_asset_snapshot("AGI", matches, self.catalog)

        self.assertEqual(snap["liquidity"], 6000)
        self.assertEqual(snap["vol24"], 600)
        self.assertEqual(snap["txns24"], 20)
        self.assertEqual(snap["pool_count"], 2)
        self.assertEqual(snap["primary_liquidity"], 5000)
        self.assertEqual(snap["_market_report"]["liquidity_usd"], 6000)
        self.assertEqual(snap["_market_report"]["volume_24h_usd"], 600)

    def test_snapshot_preserves_missing_liquidity_in_structured_metadata(self):
        primary = pool("P1", self.agi, self.usdc, None, 100)
        matches = [(primary, "base", self.agi, 90)]

        snap = legacy.compact_asset_snapshot("AGI", matches, self.catalog)

        self.assertEqual(snap["liquidity"], 0)
        self.assertIsNone(snap["_market_report"]["liquidity_usd"])
        self.assertFalse(snap["_market_report"]["completeness"]["liquidity"])

    def test_snapshot_keeps_holder_conflict_unverified_in_report(self):
        primary = pool("P1", self.agi, self.usdc, 5000, 100, holders=1000)
        secondary = pool("P2", self.agi, self.xnt, 1000, 500, holders=1200)
        matches = [
            (primary, "base", self.agi, 90),
            (secondary, "base", self.agi, 90),
        ]

        snap = legacy.compact_asset_snapshot("AGI", matches, self.catalog)

        self.assertEqual(snap["holders"], 1200)
        self.assertIsNone(snap["_market_report"]["holders"])
        self.assertEqual(snap["_market_report"]["holders_observed"], [1000, 1200])
        self.assertFalse(snap["_market_report"]["completeness"]["holders"])


if __name__ == "__main__":
    unittest.main()
