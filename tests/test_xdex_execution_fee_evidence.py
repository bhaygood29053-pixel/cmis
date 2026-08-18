import unittest

from liquidity_scout.providers.x1.xdex_execution_fee_evidence import (
    classify_xdex_execution_fee_evidence,
)


BASE = {
    "chain": "x1",
    "signature": "sig-1",
    "pool": "pool-1",
    "amm_config": "config-1",
    "configured_fee_ppm": 2800,
    "candidate_fee_ppm": 3000,
    "gross_vault_balances_observed": True,
    "active_reserves_verified": False,
    "fee_counters_verified": False,
}


class XDEXExecutionFeeEvidenceTests(unittest.TestCase):
    def test_gross_vault_diagnostics_remain_insufficient(self):
        result = classify_xdex_execution_fee_evidence(BASE)
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(
            result["reason"], "gross_vault_balances_do_not_prove_active_reserves"
        )
        self.assertFalse(result["executed_fee_semantics_verified"])
        self.assertIsNone(result["executed_fee_ppm"])
        self.assertFalse(result["active_reserve_comparison_eligible"])
        self.assertFalse(result["cmis_promotable"])
        self.assertIn(
            "gross_vault_curve_diagnostics_are_not_execution_fee_proof",
            result["warnings"],
        )

    def test_verified_active_reserves_only_make_curve_comparison_eligible(self):
        observation = dict(BASE)
        observation["active_reserves_verified"] = True
        observation["fee_counters_verified"] = True
        result = classify_xdex_execution_fee_evidence(observation)
        self.assertEqual(result["status"], "ACTIVE_RESERVE_COMPARISON_ELIGIBLE")
        self.assertTrue(result["active_reserve_comparison_eligible"])
        self.assertFalse(result["executed_fee_semantics_verified"])
        self.assertIsNone(result["executed_fee_ppm"])

    def test_direct_transaction_fee_evidence_can_verify_executed_rate(self):
        observation = dict(BASE)
        observation["direct_fee_source"] = "swap_event"
        observation["direct_trade_fee_ppm"] = 2800
        result = classify_xdex_execution_fee_evidence(observation)
        self.assertEqual(result["status"], "DIRECT_FEE_EVIDENCE")
        self.assertTrue(result["executed_fee_semantics_verified"])
        self.assertEqual(result["executed_fee_ppm"], 2800)
        self.assertFalse(result["cmis_promotable"])

    def test_direct_execution_fee_disagreement_is_preserved(self):
        observation = dict(BASE)
        observation["direct_fee_source"] = "diagnostic_log"
        observation["direct_trade_fee_ppm"] = 3000
        result = classify_xdex_execution_fee_evidence(observation)
        self.assertTrue(result["executed_fee_semantics_verified"])
        self.assertIn("executed_fee_differs_from_configured_fee", result["warnings"])

    def test_direct_fee_requires_source(self):
        observation = dict(BASE)
        observation["direct_trade_fee_ppm"] = 2800
        with self.assertRaisesRegex(ValueError, "requires direct_fee_source"):
            classify_xdex_execution_fee_evidence(observation)

    def test_source_requires_direct_fee(self):
        observation = dict(BASE)
        observation["direct_fee_source"] = "swap_event"
        with self.assertRaisesRegex(ValueError, "requires direct_trade_fee_ppm"):
            classify_xdex_execution_fee_evidence(observation)

    def test_unknown_direct_source_is_rejected(self):
        observation = dict(BASE)
        observation["direct_fee_source"] = "provider_guess"
        observation["direct_trade_fee_ppm"] = 2800
        with self.assertRaisesRegex(ValueError, "accepted execution-evidence source"):
            classify_xdex_execution_fee_evidence(observation)

    def test_boolean_ppm_is_rejected(self):
        observation = dict(BASE)
        observation["configured_fee_ppm"] = True
        with self.assertRaisesRegex(TypeError, "integer ppm"):
            classify_xdex_execution_fee_evidence(observation)

    def test_truthy_string_cannot_forge_verification_flag(self):
        observation = dict(BASE)
        observation["active_reserves_verified"] = "false"
        with self.assertRaisesRegex(TypeError, "literal boolean"):
            classify_xdex_execution_fee_evidence(observation)

    def test_wrong_chain_is_rejected(self):
        observation = dict(BASE)
        observation["chain"] = "solana"
        with self.assertRaisesRegex(ValueError, "chain must be x1"):
            classify_xdex_execution_fee_evidence(observation)

    def test_mapping_is_required(self):
        with self.assertRaisesRegex(TypeError, "mapping"):
            classify_xdex_execution_fee_evidence([])


if __name__ == "__main__":
    unittest.main()
