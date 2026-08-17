import unittest

from liquidity_scout.providers.x1.reserve_rpc_identity import (
    bind_x1_reserve_rpc_identities,
)


POOL = "pool111"
OWNER = "owner111"


def vault_identity():
    return {
        "chain": "x1",
        "pool_address": POOL,
        "asset_vault": "asset-vault",
        "asset_mint": "asset-mint",
        "counter_vault": "counter-vault",
        "counter_mint": "counter-mint",
        "shared_owner": OWNER,
        "identity_verified": True,
    }


def proof(account, mint, slot):
    return {
        "service": "x1_rpc_token_account_identity",
        "version": "1.0",
        "chain": "x1",
        "account": account,
        "mint": mint,
        "authority": OWNER,
        "slot": slot,
        "expected": {
            "account": account,
            "mint": mint,
            "authority": OWNER,
        },
        "identity_verified": True,
        "cmis_promotable": False,
        "rejection_reasons": [],
    }


def rpc_identities():
    return {
        "asset": proof("asset-vault", "asset-mint", 10),
        "counter": proof("counter-vault", "counter-mint", 11),
    }


class X1ReserveRPCIdentityBindingTests(unittest.TestCase):
    def test_binds_both_roles_exactly_without_auto_promotion(self):
        result = bind_x1_reserve_rpc_identities(vault_identity(), rpc_identities())
        self.assertTrue(result["identity_binding_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(result["rejection_reasons"], [])
        self.assertTrue(result["roles"]["asset"]["identity_verified"])
        self.assertTrue(result["roles"]["counter"]["identity_verified"])

    def test_missing_role_fails_closed(self):
        identities = rpc_identities()
        del identities["counter"]
        result = bind_x1_reserve_rpc_identities(vault_identity(), identities)
        self.assertFalse(result["identity_binding_verified"])
        self.assertIn("counter:rpc_identity_missing", result["rejection_reasons"])

    def test_observed_mint_mismatch_fails_closed(self):
        identities = rpc_identities()
        identities["asset"]["mint"] = "other-mint"
        result = bind_x1_reserve_rpc_identities(vault_identity(), identities)
        self.assertFalse(result["identity_binding_verified"])
        self.assertIn("asset:rpc_mint_identity_mismatch", result["rejection_reasons"])

    def test_authority_mismatch_fails_closed(self):
        identities = rpc_identities()
        identities["counter"]["authority"] = "other-owner"
        result = bind_x1_reserve_rpc_identities(vault_identity(), identities)
        self.assertFalse(result["identity_binding_verified"])
        self.assertIn(
            "counter:rpc_authority_identity_mismatch",
            result["rejection_reasons"],
        )

    def test_expected_scope_mismatch_fails_closed(self):
        identities = rpc_identities()
        identities["asset"]["expected"]["account"] = "other-vault"
        result = bind_x1_reserve_rpc_identities(vault_identity(), identities)
        self.assertFalse(result["identity_binding_verified"])
        self.assertIn(
            "asset:rpc_expected_account_scope_mismatch",
            result["rejection_reasons"],
        )

    def test_unverified_upstream_identity_fails_closed(self):
        identity = vault_identity()
        identity["identity_verified"] = False
        result = bind_x1_reserve_rpc_identities(identity, rpc_identities())
        self.assertFalse(result["identity_binding_verified"])
        self.assertIn("vault_identity_unverified", result["rejection_reasons"])

    def test_inputs_must_be_mappings(self):
        with self.assertRaisesRegex(TypeError, "rpc_identities must be a mapping"):
            bind_x1_reserve_rpc_identities(vault_identity(), [])


if __name__ == "__main__":
    unittest.main()
