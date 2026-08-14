import unittest

from liquidity_scout.services import (
    build_verified_market_context,
    liquidity_depth_label,
    price_movement_label,
    volume_activity_label,
)


def report(**overrides):
    base = {
        "symbol": "AGI",
        "name": "Artificial General Intelligence",
        "price_usd": 0.25,
        "liquidity_usd": 6000,
        "volume_24h_usd": 600,
        "transactions_24h": 30,
        "holders": 1000,
        "holders_observed": [1000],
        "price_change_1h_pct": 1.5,
        "price_change_24h_pct": 4.0,
        "safety_grade": "A",
        "safety_score": 90,
        "created_at": "2026-01-01T00:00:00Z",
        "primary_pool": {
            "address": "P2",
            "pair": "AGI/USDC",
            "liquidity_usd": 5000,
        },
        "completeness": {
            "liquidity": True,
            "volume_24h": True,
            "transactions_24h": True,
            "holders": True,
            "price": True,
        },
    }
    base.update(overrides)
    return base


class MarketContextServiceTests(unittest.TestCase):
    def test_classification_thresholds_match_existing_policy(self):
        self.assertEqual(liquidity_depth_label(4999), "very thin")
        self.assertEqual(liquidity_depth_label(5000), "fairly thin")
        self.assertEqual(
            liquidity_depth_label(25000),
            "not qualitatively classified",
        )
        self.assertEqual(liquidity_depth_label(100000), "comparatively deep")

        self.assertEqual(volume_activity_label(999), "light")
        self.assertEqual(
            volume_activity_label(1000),
            "not qualitatively classified",
        )
        self.assertEqual(volume_activity_label(25000), "strong")

        self.assertEqual(price_movement_label(-10), "down sharply")
        self.assertEqual(
            price_movement_label(-3),
            "under noticeable selling pressure",
        )
        self.assertEqual(price_movement_label(3), "a solid upward move")
        self.assertEqual(price_movement_label(10), "up sharply")

    def test_missing_values_are_not_classified_as_zero(self):
        self.assertIsNone(liquidity_depth_label(None))
        self.assertIsNone(liquidity_depth_label("not-a-number"))
        self.assertIsNone(volume_activity_label(None))
        self.assertIsNone(price_movement_label(None))

    def test_complete_context_contains_only_requested_verified_fields(self):
        context = build_verified_market_context(
            report(),
            ["price", "liquidity", "volume24", "change24h", "safety"],
            format_usd=lambda value: f"${value:,.2f}",
            format_age=lambda _value: "7mo",
        )

        self.assertIn("Token: AGI (Artificial General Intelligence)", context)
        self.assertIn("Price: $0.25", context)
        self.assertIn("Liquidity: $6,000.00", context)
        self.assertIn("Liquidity classification: fairly thin", context)
        self.assertIn("Volume 24h: $600.00", context)
        self.assertIn("Volume classification: light", context)
        self.assertIn("Change 24h: +4.00%", context)
        self.assertIn(
            "24h price-movement classification: a solid upward move",
            context,
        )
        self.assertIn("Tokenomics Safety: A (90/100)", context)
        self.assertNotIn("Holders:", context)
        self.assertNotIn("Transactions 24h:", context)

    def test_incomplete_asset_wide_sums_are_lower_bounds_without_labels(self):
        incomplete = report(
            liquidity_usd=5000,
            volume_24h_usd=400,
            completeness={
                "liquidity": False,
                "volume_24h": False,
                "transactions_24h": False,
                "holders": True,
                "price": True,
            },
        )

        context = build_verified_market_context(
            incomplete,
            ["liquidity", "volume24"],
            format_usd=lambda value: f"${value:,.0f}",
        )

        self.assertIn(
            "Liquidity: at least $5,000 — incomplete XDEX pool data",
            context,
        )
        self.assertIn(
            "Volume 24h: at least $400 — incomplete XDEX pool data",
            context,
        )
        self.assertNotIn("Liquidity classification:", context)
        self.assertNotIn("Volume classification:", context)

    def test_conflicting_holders_remain_unverified(self):
        conflicted = report(
            holders=None,
            holders_observed=[900, 1000],
            completeness={
                "liquidity": True,
                "volume_24h": True,
                "transactions_24h": True,
                "holders": False,
                "price": True,
            },
        )

        context = build_verified_market_context(
            conflicted,
            ["holders"],
            format_usd=str,
        )

        self.assertIn(
            "Holders: Not verified — conflicting or incomplete XDEX pool observations",
            context,
        )
        self.assertNotIn("Holders: 1,000", context)


if __name__ == "__main__":
    unittest.main()
