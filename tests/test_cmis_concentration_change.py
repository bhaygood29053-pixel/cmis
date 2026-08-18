from datetime import datetime, timezone
import unittest

from liquidity_scout.cmis.concentration import build_top_account_concentration
from liquidity_scout.cmis.concentration_change import compare_top_account_concentration


class ConcentrationChangeTests(unittest.TestCase):
    def observation(self, amounts):
        return build_top_account_concentration(
            chain="x1",
            asset_id="mint-1",
            source="x1_rpc",
            supply_raw=1000,
            supply_decimals=0,
            accounts=[
                {"address": f"acct-{i}", "amount": amount, "decimals": 0}
                for i, amount in enumerate(amounts)
            ],
            supply_identity_verified=True,
            account_identity_verified=True,
        )

    def compare(self, before, after):
        return compare_top_account_concentration(
            before=before,
            after=after,
            before_observed_at=datetime(2026, 8, 18, 10, tzinfo=timezone.utc),
            after_observed_at=datetime(2026, 8, 18, 11, tzinfo=timezone.utc),
        )

    def test_reports_numeric_increase_without_behavior_label(self):
        result = self.compare(self.observation([200, 100]), self.observation([250, 100]))
        self.assertEqual(result["direction"], "INCREASE")
        self.assertEqual(result["delta_share"], "0.05")
        self.assertEqual(result["delta_bps"], "500.00")
        self.assertFalse(result["behavioral_interpretation_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_reports_decrease_and_no_change(self):
        self.assertEqual(
            self.compare(self.observation([300]), self.observation([200]))["direction"],
            "DECREASE",
        )
        self.assertEqual(
            self.compare(self.observation([200]), self.observation([200]))["direction"],
            "NO_CHANGE",
        )

    def test_rejects_incompatible_asset(self):
        after = self.observation([200])
        after["asset_id"] = "other-mint"
        with self.assertRaises(ValueError):
            self.compare(self.observation([200]), after)

    def test_rejects_forged_scope_or_promotion_flags(self):
        after = self.observation([200])
        after["scope_complete"] = True
        with self.assertRaises(ValueError):
            self.compare(self.observation([200]), after)

        after = self.observation([200])
        after["cmis_promotable"] = True
        with self.assertRaises(ValueError):
            self.compare(self.observation([200]), after)

    def test_rejects_zero_supply_observation_without_share(self):
        zero = build_top_account_concentration(
            chain="x1",
            asset_id="mint-1",
            source="x1_rpc",
            supply_raw=0,
            supply_decimals=0,
            accounts=[],
            supply_identity_verified=True,
            account_identity_verified=True,
        )
        with self.assertRaises(ValueError):
            self.compare(zero, self.observation([0]))

    def test_requires_ordered_timezone_aware_times(self):
        before = self.observation([200])
        after = self.observation([200])
        with self.assertRaises(ValueError):
            compare_top_account_concentration(
                before=before,
                after=after,
                before_observed_at=datetime(2026, 8, 18, 10),
                after_observed_at=datetime(2026, 8, 18, 11, tzinfo=timezone.utc),
            )
        with self.assertRaises(ValueError):
            compare_top_account_concentration(
                before=before,
                after=after,
                before_observed_at=datetime(2026, 8, 18, 11, tzinfo=timezone.utc),
                after_observed_at=datetime(2026, 8, 18, 10, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
