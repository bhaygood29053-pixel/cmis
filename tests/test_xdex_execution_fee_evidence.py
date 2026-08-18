import unittest

from liquidity_scout.providers.x1.xdex_execution_fee_evidence import (
    AMM_CONFIG,
    POOL,
    X1_PROGRAM,
    XENCAT_MINT,
    XNT_MINT,
    classify_xdex_execution_fee_sequence_evidence,
)


ACCEPTED = {
    "chain": "x1",
    "program": X1_PROGRAM,
    "pool": POOL,
    "amm_config": AMM_CONFIG,
    "asset_a_mint": XENCAT_MINT,
    "asset_b_mint": XNT_MINT,
    "configured_fee_ppm": 2800,
    "supported_candidate_ppm": 2800,
    "rejected_candidate_ppm": 3000,
    "swap_count": 23,
    "seed_swap_count": 2,
    "holdout_swap_count": 21,
    "first_slot": 66_617_613,
    "last_slot": 72_301_970,
    "gross_vault_balances_observed": True,
    "state_contiguous": True,
    "both_directions_observed": True,
    "opposite_direction_seed_verified": True,
    "holdout_validation_performed": True,
    "fee_accounting_model_corroborated": True,
    "initial_fee_counters_inferred": True,
    "initial_fee_counters_observed": False,
    "supported_max_abs_error_raw": 406,
    "supported_sum_abs_error_raw": 1_115,
    "rejected_max_abs_error_raw": 1_557_603_301,
    "rejected_sum_abs_error_raw": 2_513_561_183,
    "quote_baseline_verified": True,
    "quote_baseline_ppm": 3000,
}


class XDEXExecutionFeeEvidenceTests(unittest.TestCase):
    def test_accepted_sequence_is_strongly_corroborated_but_bounded(self):
        result = classify_xdex_execution_fee_sequence_evidence(ACCEPTED)

        self.assertEqual(result["status"], "STRONGLY_CORROBORATED")
        self.assertEqual(result["scope"], "BOUNDED")
        self.assertTrue(result["bounded_execution_model_supported"])
        self.assertEqual(result["bounded_supported_execution_fee_ppm"], 2800)
        self.assertFalse(result["executed_fee_global_verified"])
        self.assertTrue(result["quote_execution_divergence_localized"])
        self.assertFalse(result["hidden_fee_attribution_verified"])
        self.assertFalse(result["private_backend_reason_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])

    def test_exact_accepted_error_metrics_are_preserved(self):
        result = classify_xdex_execution_fee_sequence_evidence(ACCEPTED)

        self.assertEqual(result["supported_max_abs_error_raw"], 406)
        self.assertEqual(result["supported_sum_abs_error_raw"], 1_115)
        self.assertEqual(result["rejected_max_abs_error_raw"], 1_557_603_301)
        self.assertEqual(result["rejected_sum_abs_error_raw"], 2_513_561_183)
        self.assertEqual(result["swap_count"], 23)
        self.assertEqual(result["holdout_swap_count"], 21)

    def test_gross_vault_observation_alone_remains_insufficient(self):
        observation = dict(ACCEPTED)
        observation["state_contiguous"] = False
        observation["both_directions_observed"] = False
        observation["opposite_direction_seed_verified"] = False
        observation["holdout_validation_performed"] = False
        observation["fee_accounting_model_corroborated"] = False
        observation["initial_fee_counters_inferred"] = False

        result = classify_xdex_execution_fee_sequence_evidence(observation)

        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(result["bounded_execution_model_supported"])
        self.assertIsNone(result["bounded_supported_execution_fee_ppm"])
        self.assertIn(
            "gross_vault_balances_alone_are_not_execution_fee_proof",
            result["warnings"],
        )

    def test_rejection_must_clear_strict_1000x_error_gate(self):
        observation = dict(ACCEPTED)
        observation["supported_max_abs_error_raw"] = 10
        observation["supported_sum_abs_error_raw"] = 10
        observation["rejected_max_abs_error_raw"] = 10_000
        observation["rejected_sum_abs_error_raw"] = 10_000

        result = classify_xdex_execution_fee_sequence_evidence(observation)

        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(result["requirements"]["rejected_candidate_materially_worse"])

    def test_unverified_quote_baseline_cannot_localize_divergence(self):
        observation = dict(ACCEPTED)
        observation["quote_baseline_verified"] = False

        result = classify_xdex_execution_fee_sequence_evidence(observation)

        self.assertEqual(result["status"], "STRONGLY_CORROBORATED")
        self.assertFalse(result["quote_execution_divergence_localized"])
        self.assertIn(
            "quote_baseline_not_independently_verified_in_this_observation",
            result["warnings"],
        )

    def test_different_quote_baseline_cannot_localize_3000_divergence(self):
        observation = dict(ACCEPTED)
        observation["quote_baseline_ppm"] = 3200

        result = classify_xdex_execution_fee_sequence_evidence(observation)

        self.assertEqual(result["status"], "STRONGLY_CORROBORATED")
        self.assertFalse(result["quote_execution_divergence_localized"])
        self.assertIn(
            "quote_baseline_does_not_match_rejected_execution_candidate",
            result["warnings"],
        )

    def test_wrong_pool_is_rejected(self):
        observation = dict(ACCEPTED)
        observation["pool"] = "other-pool"
        with self.assertRaisesRegex(ValueError, "accepted XENCAT/native-XNT pool"):
            classify_xdex_execution_fee_sequence_evidence(observation)

    def test_truthy_string_cannot_forge_state_continuity(self):
        observation = dict(ACCEPTED)
        observation["state_contiguous"] = "true"
        with self.assertRaisesRegex(TypeError, "literal boolean"):
            classify_xdex_execution_fee_sequence_evidence(observation)

    def test_boolean_cannot_be_raw_error_integer(self):
        observation = dict(ACCEPTED)
        observation["supported_max_abs_error_raw"] = True
        with self.assertRaisesRegex(TypeError, "must be an integer"):
            classify_xdex_execution_fee_sequence_evidence(observation)

    def test_holdout_accounting_must_match_total_sequence(self):
        observation = dict(ACCEPTED)
        observation["holdout_swap_count"] = 20
        with self.assertRaisesRegex(ValueError, "must equal swap_count"):
            classify_xdex_execution_fee_sequence_evidence(observation)

    def test_directly_observed_historical_counters_require_new_contract(self):
        observation = dict(ACCEPTED)
        observation["initial_fee_counters_observed"] = True
        with self.assertRaisesRegex(ValueError, "require a new contract"):
            classify_xdex_execution_fee_sequence_evidence(observation)

    def test_sum_error_cannot_be_smaller_than_max_error(self):
        observation = dict(ACCEPTED)
        observation["supported_sum_abs_error_raw"] = 405
        with self.assertRaisesRegex(ValueError, "cannot be smaller"):
            classify_xdex_execution_fee_sequence_evidence(observation)

    def test_mapping_is_required(self):
        with self.assertRaisesRegex(TypeError, "mapping"):
            classify_xdex_execution_fee_sequence_evidence([])


if __name__ == "__main__":
    unittest.main()
