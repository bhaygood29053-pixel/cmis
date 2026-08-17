import unittest

from liquidity_scout.providers.x1.token_account_total_contract import (
    validate_total_token_account_observation,
)


MINT = "Mint111"


def valid_observation(**overrides):
    value = {
        "chain": "x1",
        "source": "X1 RPC bounded token-program scan",
        "method": "getProgramAccounts",
        "fact_type": "total_token_account_count",
        "mint": MINT,
        "counted_entity": "token_accounts",
        "coverage": "total",
        "count": 115,
        "mint_identity_verified": True,
        "mint_filter_verified": True,
        "enumeration_complete": True,
        "truncation_absent_verified": True,
        "token_account_semantics_verified": True,
    }
    value.update(overrides)
    return value


class TotalTokenAccountObservationContractTests(unittest.TestCase):
    def test_accepts_only_explicit_complete_same_mint_token_account_observation(self):
        result = validate_total_token_account_observation(
            valid_observation(), expected_mint=MINT
        )
        self.assertEqual(result["verification_status"], "verified_total_token_account_observation")
        self.assertEqual(result["count"], 115)
        self.assertTrue(result["coverage_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_rejects_partial_or_unproven_enumeration(self):
        for field, value in (
            ("coverage", "partial"),
            ("enumeration_complete", False),
            ("truncation_absent_verified", False),
            ("mint_filter_verified", False),
        ):
            with self.subTest(field=field):
                result = validate_total_token_account_observation(
                    valid_observation(**{field: value}), expected_mint=MINT
                )
                self.assertEqual(result["verification_status"], "insufficient_evidence")
                self.assertIsNone(result["count"])

    def test_rejects_largest_accounts_even_if_mislabeled_total(self):
        result = validate_total_token_account_observation(
            valid_observation(method="getTokenLargestAccounts"), expected_mint=MINT
        )
        self.assertIn("largest_accounts_not_total_coverage", result["rejection_reasons"])

    def test_rejects_wallet_or_beneficial_owner_semantics(self):
        for entity in ("wallet_addresses", "beneficial_owners"):
            with self.subTest(entity=entity):
                result = validate_total_token_account_observation(
                    valid_observation(counted_entity=entity), expected_mint=MINT
                )
                self.assertEqual(result["verification_status"], "insufficient_evidence")

    def test_rejects_mint_mismatch_wrong_chain_and_invalid_count(self):
        cases = (
            valid_observation(mint="OtherMint"),
            valid_observation(chain="solana"),
            valid_observation(count=True),
            valid_observation(count=-1),
        )
        for observation in cases:
            with self.subTest(observation=observation):
                result = validate_total_token_account_observation(
                    observation, expected_mint=MINT
                )
                self.assertEqual(result["verification_status"], "insufficient_evidence")

    def test_invalid_input_fails_closed(self):
        result = validate_total_token_account_observation([], expected_mint=MINT)
        self.assertEqual(result["verification_status"], "insufficient_evidence")
        with self.assertRaises(ValueError):
            validate_total_token_account_observation({}, expected_mint="")


if __name__ == "__main__":
    unittest.main()
