import unittest
from unittest.mock import patch

import moltgrid_signal_v12_ollama as legacy
from liquidity_scout.integrations import moltgrid as bridge
from liquidity_scout.services import (
    liquidity_depth_label as service_liquidity_depth_label,
    price_movement_label as service_price_movement_label,
    volume_activity_label as service_volume_activity_label,
)


class LegacyMarketContextDelegationTests(unittest.TestCase):
    def test_classifiers_come_from_reusable_services(self):
        self.assertIs(legacy.liquidity_depth_label, service_liquidity_depth_label)
        self.assertIs(legacy.volume_activity_label, service_volume_activity_label)
        self.assertIs(legacy.price_movement_label, service_price_movement_label)

    def test_verified_context_delegates_to_moltgrid_bridge(self):
        snap = {"title": "AGI", "liquidity": 3522}
        fields = ["liquidity"]

        with patch.object(
            legacy,
            "bridge_verified_snapshot_context",
            return_value="delegated",
        ) as delegated:
            result = legacy.verified_snapshot_context(snap, fields)

        self.assertEqual(result, "delegated")
        delegated.assert_called_once_with(legacy, snap, fields)

    def test_legacy_snapshot_fallback_behavior_is_preserved(self):
        snap = {"title": "AGI", "liquidity": 3522}

        context = legacy.verified_snapshot_context(snap, ["liquidity"])

        self.assertIn("Liquidity: $3,522", context)
        self.assertIn("Liquidity classification: very thin", context)

    def test_structured_context_preserves_missing_liquidity_uncertainty(self):
        snap = {
            "title": "AGI",
            "_market_report": {
                "symbol": "AGI",
                "name": "AGI",
                "liquidity_usd": None,
                "completeness": {"liquidity": False},
            },
        }

        context = legacy.verified_snapshot_context(snap, ["liquidity"])

        self.assertIn("Liquidity: Not available from verified data", context)
        self.assertNotIn("Liquidity: $0", context)
        self.assertNotIn("Liquidity classification:", context)


if __name__ == "__main__":
    unittest.main()
