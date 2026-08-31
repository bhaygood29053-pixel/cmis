import unittest

from liquidity_scout.tokenomics.burn_metrics import build_burn_metrics


DAY = 24 * 60 * 60
NOW = 10_000_000


def event(kind, raw_amount, block_time):
    return {
        "kind": kind,
        "raw_amount": str(raw_amount),
        "block_time": block_time,
    }


class BurnMetricsTests(unittest.TestCase):
    def build(self, events, **overrides):
        kwargs = {
            "decimals": 2,
            "observed_at": NOW,
            "coverage_verified": True,
            "coverage_start_time": NOW - (60 * DAY),
            "coverage_end_time": NOW,
        }
        kwargs.update(overrides)
        return build_burn_metrics(events, **kwargs)

    def test_current_window_burn_rate_emission_ratio_and_period_change(self):
        report = self.build([
            event("burn", 1500, NOW - 100),
            event("mint", 1000, NOW - 200),
            event("burn", 1000, NOW - DAY - 100),
        ])

        self.assertEqual(report["mint_events_observed"], 1)
        self.assertEqual(report["minted_raw_observed"], "1000")
        self.assertEqual(report["burn_events_observed"], 2)
        self.assertEqual(report["burned_raw_observed"], "2500")
        self.assertTrue(report["observed_event_totals_verified"])
        self.assertEqual(report["verified_burned_raw_observed"], "2500")
        self.assertEqual(report["verified_burned_observed"], "25")

        current = report["windows"]["24h"]
        self.assertEqual(current["burned_raw"], "1500")
        self.assertEqual(current["burned_tokens"], "15")
        self.assertEqual(current["burn_events"], 1)
        self.assertEqual(current["minted_raw"], "1000")
        self.assertEqual(current["burn_to_emission_ratio"], "1.5")
        self.assertEqual(current["net_issuance_raw"], "-500")
        self.assertEqual(current["net_issuance_tokens"], "-5")
        self.assertEqual(current["issuance_state"], "DEFLATIONARY")

        change = current["period_over_period"]
        self.assertEqual(change["prior_burned_raw"], "1000")
        self.assertEqual(change["percent_change"], "50")
        self.assertEqual(change["change_state"], "AVAILABLE")

    def test_numeric_zero_raw_amount_is_valid(self):
        report = self.build([
            event("burn", 0, NOW - 10),
        ])

        current = report["windows"]["1h"]
        self.assertEqual(current["status"], "ok")
        self.assertEqual(current["burned_raw"], "0")
        self.assertEqual(current["burn_events"], 1)
        self.assertEqual(report["malformed_events"], 0)

    def test_burn_without_emission_does_not_manufacture_infinity(self):
        report = self.build([
            event("burn", 250, NOW - 10),
        ])

        current = report["windows"]["1h"]
        self.assertIsNone(current["burn_to_emission_ratio"])
        self.assertEqual(current["issuance_state"], "BURN_WITHOUT_EMISSION")
        self.assertEqual(current["net_issuance_raw"], "-250")

    def test_new_burn_activity_has_null_percent_change_when_prior_is_zero(self):
        report = self.build([
            event("burn", 500, NOW - 10),
        ])

        change = report["windows"]["24h"]["period_over_period"]
        self.assertIsNone(change["percent_change"])
        self.assertEqual(change["change_state"], "NEW_BURN_ACTIVITY")

    def test_zero_to_zero_comparison_is_explicit(self):
        report = self.build([])

        current = report["windows"]["24h"]
        self.assertEqual(current["issuance_state"], "NO_ACTIVITY")
        self.assertIsNone(current["burn_to_emission_ratio"])
        self.assertEqual(
            current["period_over_period"]["percent_change"],
            "0",
        )
        self.assertEqual(
            current["period_over_period"]["change_state"],
            "NO_CHANGE_ZERO_BASE",
        )

    def test_insufficient_time_depth_hides_window_values(self):
        report = self.build(
            [event("burn", 500, NOW - 10)],
            coverage_start_time=NOW - (12 * 60 * 60),
        )

        one_hour = report["windows"]["1h"]
        self.assertEqual(one_hour["status"], "ok")
        self.assertEqual(one_hour["burned_raw"], "500")

        day = report["windows"]["24h"]
        self.assertEqual(day["status"], "unavailable")
        self.assertIsNone(day["burned_raw"])
        self.assertEqual(day["issuance_state"], "INSUFFICIENT_COVERAGE")

    def test_malformed_event_withholds_verified_observed_burn_amount(self):
        report = self.build([
            event("burn", 500, NOW - 10),
            {"kind": "burn", "raw_amount": "not-a-number", "block_time": NOW - 20},
        ])

        self.assertEqual(report["burned_raw_observed"], "500")
        self.assertFalse(report["observed_event_totals_verified"])
        self.assertIsNone(report["verified_burned_raw_observed"])
        self.assertIsNone(report["verified_burned_observed"])
    def test_missing_block_time_fails_closed_for_all_time_buckets(self):
        report = self.build([
            event("burn", 500, None),
        ])

        self.assertEqual(report["burned_raw_observed"], "500")
        self.assertEqual(report["burn_events_observed"], 1)
        self.assertEqual(report["untimed_events"], 1)
        self.assertFalse(report["time_buckets_verified"])
        for window in report["windows"].values():
            self.assertEqual(window["status"], "unavailable")
            self.assertIsNone(window["burned_raw"])

    def test_future_block_time_fails_closed_for_time_buckets(self):
        report = self.build([
            event("burn", 500, NOW + 1),
        ])

        self.assertEqual(report["future_timed_events"], 1)
        self.assertFalse(report["time_buckets_verified"])
        self.assertEqual(report["windows"]["1h"]["status"], "unavailable")

    def test_fractional_block_time_is_not_silently_truncated(self):
        report = self.build([
            event("burn", 500, NOW - 0.5),
        ])

        self.assertEqual(report["untimed_events"], 1)
        self.assertFalse(report["time_buckets_verified"])
        self.assertEqual(report["windows"]["1h"]["status"], "unavailable")

    def test_fractional_observed_at_is_rejected(self):
        with self.assertRaises(ValueError):
            self.build([], observed_at=NOW + 0.5)

    def test_fractional_decimals_are_rejected(self):
        with self.assertRaises(ValueError):
            self.build([], decimals=2.5)

    def test_window_boundary_is_start_exclusive_end_inclusive(self):
        report = self.build([
            event("burn", 100, NOW - DAY),
            event("burn", 200, NOW),
            event("burn", 300, NOW - DAY + 1),
        ])

        current = report["windows"]["24h"]
        self.assertEqual(current["burned_raw"], "500")
        self.assertEqual(current["burn_events"], 2)

        prior = current["period_over_period"]
        self.assertEqual(prior["prior_burned_raw"], "100")


if __name__ == "__main__":
    unittest.main()
