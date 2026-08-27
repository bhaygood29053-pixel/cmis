import unittest

from liquidity_scout.services import format_field_line


def usd(value):
    return f"${float(value):,.0f}"


def base_snapshot(report):
    return {
        "symbol": "AGI",
        "token_address": "MINT_AGI",
        "price": "$0",
        "price_usd_value": 0,
        "age": "7mo",
        "holders": 0,
        "txns24": 0,
        "vol24": 0,
        "change1": 0,
        "change24": 0,
        "liquidity": 0,
        "pool_count": report.get("lp_count", 1),
        "safety": "N/A",
        "pool_address": "",
        "_market_report": report,
    }


class MarketPresentationUncertaintyTests(unittest.TestCase):
    def test_missing_structured_values_are_not_displayed_as_compatibility_zeroes(self):
        report = {
            "price_usd": None,
            "holders": None,
            "holders_observed": [],
            "transactions_24h": None,
            "volume_24h_usd": None,
            "price_change_1h_pct": None,
            "price_change_24h_pct": None,
            "liquidity_usd": None,
            "lp_count": 2,
            "safety_grade": None,
            "safety_score": None,
            "primary_pool": {"address": None},
            "completeness": {
                "holders": False,
                "transactions_24h": False,
                "volume_24h": False,
                "liquidity": False,
            },
        }
        snap = base_snapshot(report)

        self.assertEqual(
            format_field_line("price", snap, format_usd=usd),
            "• Price: Not available from verified data",
        )
        self.assertEqual(
            format_field_line("volume24", snap, format_usd=usd),
            "• Volume 24h: Not available from verified data",
        )
        self.assertEqual(
            format_field_line("liquidity", snap, format_usd=usd),
            "• Liquidity: Not available from verified data • Pools: 2",
        )
        self.assertNotIn(
            "$0",
            format_field_line("liquidity", snap, format_usd=usd),
        )

    def test_partial_structured_sums_are_displayed_as_lower_bounds(self):
        report = {
            "price_usd": 0.25,
            "holders": None,
            "holders_observed": [1000, 1200],
            "transactions_24h": 10,
            "volume_24h_usd": 500,
            "price_change_1h_pct": 1.0,
            "price_change_24h_pct": -2.0,
            "liquidity_usd": 5000,
            "lp_count": 2,
            "safety_grade": "A",
            "safety_score": 90,
            "primary_pool": {"address": "P2"},
            "completeness": {
                "holders": False,
                "transactions_24h": False,
                "volume_24h": False,
                "liquidity": False,
            },
        }
        snap = base_snapshot(report)

        self.assertEqual(
            format_field_line("txns24", snap, format_usd=usd),
            "• Transactions 24h: at least 10 — incomplete XDEX pool data",
        )
        self.assertEqual(
            format_field_line("volume24", snap, format_usd=usd),
            "• Volume 24h: at least $500 — incomplete XDEX pool data",
        )
        self.assertEqual(
            format_field_line("liquidity", snap, format_usd=usd),
            "• Liquidity: at least $5,000 — incomplete XDEX pool data • Pools: 2",
        )
        self.assertEqual(
            format_field_line("holders", snap, format_usd=usd),
            "• Holders: Not verified — provider observations conflict or are incomplete; counted-entity and coverage semantics are unverified",
        )


if __name__ == "__main__":
    unittest.main()
