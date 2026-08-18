import unittest

from liquidity_scout.cmis.concentration_threshold import evaluate_concentration_threshold


class ConcentrationThresholdEvaluationTests(unittest.TestCase):
    def _change(self, *, delta_numerator="1", delta_denominator="100", direction="INCREASE"):
        before_num = 2
        before_den = 10
        delta_num = int(delta_numerator)
        delta_den = int(delta_denominator)
        # Use a fixture with exact compatible before/after ratios. The default
        # moves from 20% to 21% (+100 bps).
        if (delta_num, delta_den) == (1, 100):
            after = {"numerator": "21", "denominator": "100"}
            delta_share = "0.01"
            delta_bps = "100"
        elif (delta_num, delta_den) == (-1, 100):
            after = {"numerator": "19", "denominator": "100"}
            delta_share = "-0.01"
            delta_bps = "-100"
        elif (delta_num, delta_den) == (0, 1):
            after = {"numerator": "1", "denominator": "5"}
            delta_share = "0"
            delta_bps = "0"
        else:
            raise AssertionError("unsupported test fixture")
        return {
            "schema": "cmis_top_account_concentration_change.v1",
            "chain": "x1",
            "asset_id": "mint-1",
            "source": "x1-rpc",
            "scope": "observed_top_token_accounts",
            "requested_account_limit": 20,
            "observed_account_count": 20,
            "before_observed_at": "2026-08-18T12:00:00Z",
            "after_observed_at": "2026-08-18T13:00:00Z",
            "before_share_exact": {"numerator": str(before_num), "denominator": str(before_den)},
            "after_share_exact": after,
            "delta_share_exact": {
                "numerator": delta_numerator,
                "denominator": delta_denominator,
            },
            "before_share": "0.2",
            "after_share": "0.21" if direction == "INCREASE" else "0.19" if direction == "DECREASE" else "0.2",
            "delta_share": delta_share,
            "delta_bps": delta_bps,
            "direction": direction,
            "identity_verified": True,
            "scope_complete": False,
            "holder_semantics_verified": False,
            "beneficial_owner_identity_verified": False,
            "behavioral_interpretation_verified": False,
            "cmis_promotable": False,
            "limitations": [],
        }

    def test_explicit_threshold_exceeded_without_behavioral_promotion(self):
        result = evaluate_concentration_threshold(
            change=self._change(),
            policy_id="concentration-monitor",
            policy_version="1.0.0",
            absolute_delta_threshold_bps="75",
        )

        self.assertEqual(result["status"], "EXCEEDS_THRESHOLD")
        self.assertTrue(result["threshold_exceeded"])
        self.assertFalse(result["threshold_matched"])
        self.assertEqual(result["absolute_delta_bps"], "100")
        self.assertEqual(result["policy"]["absolute_delta_threshold_bps"], "75")
        self.assertFalse(result["behavioral_interpretation_verified"])
        self.assertFalse(result["risk_interpretation_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_exact_threshold_is_distinct_from_exceeded(self):
        result = evaluate_concentration_threshold(
            change=self._change(),
            policy_id="concentration-monitor",
            policy_version="1.0.0",
            absolute_delta_threshold_bps=100,
        )
        self.assertEqual(result["status"], "AT_THRESHOLD")
        self.assertFalse(result["threshold_exceeded"])
        self.assertTrue(result["threshold_matched"])

    def test_decrease_uses_absolute_magnitude_without_distribution_label(self):
        result = evaluate_concentration_threshold(
            change=self._change(delta_numerator="-1", direction="DECREASE"),
            policy_id="concentration-monitor",
            policy_version="1.0.0",
            absolute_delta_threshold_bps="50",
        )
        self.assertEqual(result["status"], "EXCEEDS_THRESHOLD")
        self.assertEqual(result["direction"], "DECREASE")
        self.assertEqual(result["absolute_delta_bps"], "100")
        self.assertIn(
            "threshold_crossing_does_not_establish_accumulation_or_distribution",
            result["limitations"],
        )

    def test_no_change_can_be_within_threshold(self):
        result = evaluate_concentration_threshold(
            change=self._change(delta_numerator="0", delta_denominator="1", direction="NO_CHANGE"),
            policy_id="concentration-monitor",
            policy_version="1.0.0",
            absolute_delta_threshold_bps="1",
        )
        self.assertEqual(result["status"], "WITHIN_THRESHOLD")
        self.assertEqual(result["absolute_delta_bps"], "0")

    def test_no_hidden_default_threshold_is_available(self):
        with self.assertRaisesRegex(ValueError, "absolute_delta_threshold_bps"):
            evaluate_concentration_threshold(
                change=self._change(),
                policy_id="concentration-monitor",
                policy_version="1.0.0",
                absolute_delta_threshold_bps=None,
            )

    def test_boolean_threshold_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute_delta_threshold_bps"):
            evaluate_concentration_threshold(
                change=self._change(),
                policy_id="concentration-monitor",
                policy_version="1.0.0",
                absolute_delta_threshold_bps=True,
            )

    def test_forged_promotable_change_is_rejected(self):
        change = self._change()
        change["cmis_promotable"] = True
        with self.assertRaisesRegex(ValueError, "cmis_promotable"):
            evaluate_concentration_threshold(
                change=change,
                policy_id="concentration-monitor",
                policy_version="1.0.0",
                absolute_delta_threshold_bps="50",
            )

    def test_inconsistent_exact_delta_is_rejected(self):
        change = self._change()
        change["delta_share_exact"] = {"numerator": "2", "denominator": "100"}
        with self.assertRaisesRegex(ValueError, "exact ratios are inconsistent"):
            evaluate_concentration_threshold(
                change=change,
                policy_id="concentration-monitor",
                policy_version="1.0.0",
                absolute_delta_threshold_bps="50",
            )

    def test_policy_identity_is_required(self):
        with self.assertRaisesRegex(ValueError, "policy_id"):
            evaluate_concentration_threshold(
                change=self._change(),
                policy_id=" ",
                policy_version="1.0.0",
                absolute_delta_threshold_bps="50",
            )


if __name__ == "__main__":
    unittest.main()
