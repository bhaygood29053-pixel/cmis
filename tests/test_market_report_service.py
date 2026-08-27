import unittest
from types import SimpleNamespace

from liquidity_scout.services import build_market_report


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
        "address": mint,
    }


def pool(
    address,
    base,
    quote,
    *,
    liquidity=None,
    volume24h=None,
    txns24h=None,
    holders=None,
    price=None,
    change1=None,
    change24=None,
    safety_grade=None,
    safety_score=None,
):
    row = {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "createdAt": "2026-01-01T00:00:00Z",
        "marketCap": 12345,
        "fdv": 23456,
    }
    values = {
        "liquidity": liquidity,
        "volume24h": volume24h,
        "txns24h": txns24h,
        "holders": holders,
        "priceUsd": price,
        "priceChange1h": change1,
        "priceChange24h": change24,
        "safetyGrade": safety_grade,
        "safetyScore": safety_score,
    }
    for key, value in values.items():
        if value is not None:
            row[key] = value
    return row


class MarketReportServiceTests(unittest.TestCase):
    def setUp(self):
        self.xnt = token("XNT", "MINT_XNT", "Wrapped XNT")
        self.agi = token("AGI", "MINT_AGI", "Artificial General Intelligence")
        self.usdc = token("USDC", "MINT_USDC", "USD Coin")

    def test_aggregates_distinct_lps_and_keeps_primary_pool_metrics(self):
        primary = pool(
            "P2",
            self.agi,
            self.usdc,
            liquidity=5000,
            volume24h=100,
            txns24h=10,
            holders=1000,
            price=0.25,
            change1=1.5,
            change24=4.0,
            safety_grade="A",
            safety_score=90,
        )
        secondary = pool(
            "P1",
            self.agi,
            self.xnt,
            liquidity=1000,
            volume24h=500,
            txns24h=20,
            holders=1000,
            price=0.20,
            change1=-2.0,
            change24=-5.0,
            safety_grade="B",
            safety_score=70,
        )
        matches = [
            (primary, "base", self.agi, 90),
            (secondary, "base", self.agi, 90),
            (secondary, "base", self.agi, 90),
        ]
        catalog = SimpleNamespace(xnt_price_usd=None, last_refresh=123.0)

        report = build_market_report("AGI", matches, catalog)

        self.assertEqual(report["lp_count"], 2)
        self.assertEqual(report["liquidity_usd"], 6000)
        self.assertEqual(report["volume_24h_usd"], 600)
        self.assertEqual(report["transactions_24h"], 30)
        self.assertIsNone(report["holders"])
        self.assertEqual(report["holders_reported"], 1000)
        self.assertEqual(report["holders_observed"], [1000])
        self.assertFalse(report["completeness"]["holders"])
        self.assertEqual(report["holder_semantics"]["counted_entity"], "unverified")
        self.assertEqual(report["holder_semantics"]["coverage"], "unverified")
        self.assertTrue(report["holder_semantics"]["provider_rows_complete"])
        self.assertTrue(report["holder_semantics"]["provider_rows_consistent"])
        self.assertFalse(report["holder_semantics"]["holder_semantics_verified"])
        self.assertFalse(report["holder_semantics"]["beneficial_owner_identity_verified"])
        self.assertEqual(report["price_usd"], 0.25)
        self.assertEqual(report["price_change_24h_pct"], 4.0)
        self.assertEqual(report["safety_grade"], "A")
        self.assertEqual(report["primary_pool"]["address"], "P2")
        self.assertEqual(report["primary_pool"]["liquidity_usd"], 5000)
        self.assertEqual(report["provenance"]["source"], "X1.Ninja/XDEX")
        self.assertEqual(report["provenance"]["catalog_last_refresh_unix"], 123.0)
        self.assertTrue(report["completeness"]["liquidity"])
        self.assertTrue(report["completeness"]["volume_24h"])
        self.assertFalse(report["market_cap_verified"])
        self.assertFalse(report["fdv_verified"])

    def test_xnt_reference_overrides_primary_pool_price(self):
        primary = pool(
            "PX",
            self.xnt,
            self.usdc,
            liquidity=9000,
            volume24h=100,
            txns24h=5,
            holders=500,
            price=0.40,
        )
        catalog = SimpleNamespace(xnt_price_usd="0.55", last_refresh=1.0)

        report = build_market_report(
            "XNT",
            [(primary, "base", self.xnt, 90)],
            catalog,
        )

        self.assertEqual(report["price_usd"], 0.55)
        self.assertEqual(report["price_source"], "x1_ninja_xnt_reference")
        self.assertEqual(report["primary_pool"]["price_usd"], 0.40)

    def test_missing_and_conflicting_pool_values_preserve_uncertainty(self):
        primary = pool(
            "P1",
            self.agi,
            self.xnt,
            liquidity=1000,
            txns24h=5,
            holders=100,
            price=0.10,
        )
        primary["volume24h"] = "not-a-number"

        secondary = pool(
            "P2",
            self.agi,
            self.usdc,
            volume24h=200,
            holders=120,
            price=0.09,
        )

        report = build_market_report(
            "AGI",
            [
                (primary, "base", self.agi, 90),
                (secondary, "base", self.agi, 90),
            ],
            SimpleNamespace(xnt_price_usd=None, last_refresh=0),
        )

        self.assertEqual(report["liquidity_usd"], 1000)
        self.assertFalse(report["completeness"]["liquidity"])
        self.assertEqual(report["volume_24h_usd"], 200)
        self.assertFalse(report["completeness"]["volume_24h"])
        self.assertEqual(report["transactions_24h"], 5)
        self.assertFalse(report["completeness"]["transactions_24h"])
        self.assertIsNone(report["holders"])
        self.assertIsNone(report["holders_reported"])
        self.assertEqual(report["holders_observed"], [100, 120])
        self.assertEqual(report["holders_observed_max"], 120)
        self.assertFalse(report["holder_semantics"]["provider_rows_consistent"])
        self.assertFalse(report["holder_semantics"]["holder_semantics_verified"])
        self.assertFalse(report["completeness"]["holders"])
        self.assertIsNone(report["provenance"]["catalog_last_refresh_unix"])

    def test_empty_matches_are_rejected(self):
        with self.assertRaises(ValueError):
            build_market_report(
                "AGI",
                [],
                SimpleNamespace(xnt_price_usd=None, last_refresh=0),
            )


if __name__ == "__main__":
    unittest.main()
