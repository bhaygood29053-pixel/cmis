import unittest

from liquidity_scout.providers.x1.pool_vault_identity import (
    extract_pool_vault_identity,
)


class X1PoolVaultIdentityTests(unittest.TestCase):
    def _proof(self):
        return {
            "service": "canonical_pool_vault_coupling",
            "version": "1.4.9",
            "chain": "x1",
            "pool_address": "POOL",
            "asset_mint": "ASSET",
            "status": "canonical_pool_vault_coupling_proven",
            "canonical_vault_mapping_candidate": {
                "asset_account": "ASSET_VAULT",
                "counter_account": "COUNTER_VAULT",
                "counter_mint": "COUNTER",
                "shared_owner": "OWNER",
            },
            "summary": {
                "canonical_vault_mapping_proven": True,
                "unique_pool_coupled_family": True,
            },
        }

    def test_extracts_identity_but_does_not_promote_reserve_semantics(self):
        result = extract_pool_vault_identity(
            self._proof(),
            expected_pool_address="POOL",
            expected_asset_mint="ASSET",
        )
        self.assertTrue(result["identity_verified"])
        self.assertEqual(result["asset_vault"], "ASSET_VAULT")
        self.assertEqual(result["counter_vault"], "COUNTER_VAULT")
        self.assertFalse(result["reserve_semantics_verified"])
        self.assertFalse(result["reserve_units_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(result["rejection_reasons"], [])

    def test_rejects_unproven_status(self):
        proof = self._proof()
        proof["status"] = "no_pool_vault_coupling_proven"
        result = extract_pool_vault_identity(proof)
        self.assertFalse(result["identity_verified"])
        self.assertIn("canonical_coupling_status_unproven", result["rejection_reasons"])

    def test_rejects_non_unique_summary(self):
        proof = self._proof()
        proof["summary"]["unique_pool_coupled_family"] = False
        result = extract_pool_vault_identity(proof)
        self.assertFalse(result["identity_verified"])
        self.assertIn("unique_pool_coupled_family_unproven", result["rejection_reasons"])

    def test_rejects_incomplete_candidate(self):
        proof = self._proof()
        del proof["canonical_vault_mapping_candidate"]["counter_mint"]
        result = extract_pool_vault_identity(proof)
        self.assertFalse(result["identity_verified"])
        self.assertIn("counter_mint_missing", result["rejection_reasons"])

    def test_rejects_scope_mismatch(self):
        result = extract_pool_vault_identity(
            self._proof(),
            expected_pool_address="OTHER_POOL",
            expected_asset_mint="OTHER_MINT",
        )
        self.assertFalse(result["identity_verified"])
        self.assertIn("pool_scope_mismatch", result["rejection_reasons"])
        self.assertIn("asset_mint_scope_mismatch", result["rejection_reasons"])

    def test_rejects_same_vault_for_both_legs(self):
        proof = self._proof()
        proof["canonical_vault_mapping_candidate"]["counter_account"] = "ASSET_VAULT"
        result = extract_pool_vault_identity(proof)
        self.assertFalse(result["identity_verified"])
        self.assertIn("vault_accounts_not_distinct", result["rejection_reasons"])

    def test_rejects_same_mint_for_both_legs(self):
        proof = self._proof()
        proof["canonical_vault_mapping_candidate"]["counter_mint"] = "ASSET"
        result = extract_pool_vault_identity(proof)
        self.assertFalse(result["identity_verified"])
        self.assertIn("vault_mints_not_distinct", result["rejection_reasons"])

    def test_rejects_wrong_chain(self):
        proof = self._proof()
        proof["chain"] = "solana"
        result = extract_pool_vault_identity(proof)
        self.assertFalse(result["identity_verified"])
        self.assertIn("wrong_chain", result["rejection_reasons"])

    def test_requires_mapping_input(self):
        with self.assertRaises(TypeError):
            extract_pool_vault_identity(None)


if __name__ == "__main__":
    unittest.main()
