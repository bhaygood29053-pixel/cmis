import unittest

from liquidity_scout.providers.x1.holder_count_crosscheck import compare_x1_holder_count_evidence


MINT = "Mint111111111111111111111111111111111111111"


def semantic_proof(**overrides):
    value = {
        "service": "x1_ninja_holder_semantic_proof",
        "chain": "x1",
        "asset_mint": MINT,
        "raw_count": 115,
        "counted_entity": "token_accounts",
        "coverage": "total",
        "semantic_contract_verified": True,
        "rpc_total_token_account_count_comparison_eligible": True,
        "cmis_promotable": False,
    }
    value.update(overrides)
    return value


def independent(**overrides):
    value = {
        "source": "x1_rpc_full_token_account_scan",
        "chain": "x1",
        "fact_type": "total_token_account_count",
        "asset_mint": MINT,
        "count": 115,
        "counted_entity": "token_accounts",
        "coverage": "total",
        "identity_verified": True,
        "coverage_verified": True,
    }
    value.update(overrides)
    return value


class HolderCountCrosscheckTests(unittest.TestCase):
    def test_exact_total_token_account_counts_agree(self):
        result = compare_x1_holder_count_evidence(semantic_proof(), independent())
        self.assertEqual(result["verification_status"], "AGREEMENT")
        self.assertTrue(result["agreement"])
        self.assertTrue(result["comparison_semantics_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_different_exact_counts_conflict_without_averaging(self):
        result = compare_x1_holder_count_evidence(semantic_proof(), independent(count=114))
        self.assertEqual(result["verification_status"], "CONFLICT")
        self.assertFalse(result["agreement"])
        self.assertEqual(result["provider_count"], 115)
        self.assertEqual(result["independent_count"], 114)

    def test_largest_accounts_list_cannot_verify_total_holder_count(self):
        result = compare_x1_holder_count_evidence(
            semantic_proof(),
            independent(
                fact_type="largest_token_accounts",
                coverage="partial",
                coverage_verified=False,
                count=20,
            ),
        )
        self.assertEqual(result["verification_status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("independent_fact_not_total_token_account_count", result["rejection_reasons"])
        self.assertIn("independent_coverage_not_total", result["rejection_reasons"])

    def test_beneficial_owner_provider_semantics_are_not_coerced(self):
        result = compare_x1_holder_count_evidence(
            semantic_proof(
                counted_entity="beneficial_owners",
                rpc_total_token_account_count_comparison_eligible=False,
            ),
            independent(),
        )
        self.assertEqual(result["verification_status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("provider_semantics_not_total_token_accounts", result["rejection_reasons"])
        self.assertIn("provider_counted_entity_not_token_accounts", result["rejection_reasons"])

    def test_partial_provider_coverage_is_not_coerced(self):
        result = compare_x1_holder_count_evidence(
            semantic_proof(coverage="partial", rpc_total_token_account_count_comparison_eligible=False),
            independent(),
        )
        self.assertEqual(result["verification_status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("provider_coverage_not_total", result["rejection_reasons"])

    def test_unverified_provider_semantics_fail_closed(self):
        result = compare_x1_holder_count_evidence(
            semantic_proof(semantic_contract_verified=False), independent()
        )
        self.assertEqual(result["verification_status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("provider_semantic_contract_unverified", result["rejection_reasons"])

    def test_mint_mismatch_fails_closed(self):
        result = compare_x1_holder_count_evidence(
            semantic_proof(), independent(asset_mint="OtherMint")
        )
        self.assertEqual(result["verification_status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("asset_mint_mismatch", result["rejection_reasons"])

    def test_same_provider_is_not_independent(self):
        result = compare_x1_holder_count_evidence(
            semantic_proof(), independent(source="x1_ninja")
        )
        self.assertEqual(result["verification_status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("independent_source_not_distinct", result["rejection_reasons"])

    def test_boolean_counts_are_rejected(self):
        result = compare_x1_holder_count_evidence(
            semantic_proof(raw_count=True), independent(count=False)
        )
        self.assertEqual(result["verification_status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("provider_count_invalid", result["rejection_reasons"])
        self.assertIn("independent_count_invalid", result["rejection_reasons"])

    def test_input_types_are_enforced(self):
        with self.assertRaises(TypeError):
            compare_x1_holder_count_evidence([], independent())
        with self.assertRaises(TypeError):
            compare_x1_holder_count_evidence(semantic_proof(), [])


if __name__ == "__main__":
    unittest.main()
