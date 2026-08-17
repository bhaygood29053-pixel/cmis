import unittest

from liquidity_scout.providers.x1.ninja_reserve_semantics import (
    validate_reserve_semantic_proof,
)


POOL = "pool111"
ASSET_MINT = "assetmint"
COUNTER_MINT = "countermint"
ASSET_VAULT = "assetvault"
COUNTER_VAULT = "countervault"


def pool_detail():
    return {
        "chain": "x1",
        "pool_address_requested": POOL,
        "raw_response": {
            "reserves": {"asset": "1234500", "counter": 987600},
        },
    }


def identity():
    return {
        "chain": "x1",
        "pool_address": POOL,
        "asset_mint": ASSET_MINT,
        "asset_vault": ASSET_VAULT,
        "counter_mint": COUNTER_MINT,
        "counter_vault": COUNTER_VAULT,
        "identity_verified": True,
    }


def manifest():
    return {
        "proof_status": "externally_proven",
        "proof_version": "fixture-1",
        "pool_address": POOL,
        "evidence_refs": ["live-probe-artifact:example"],
        "asset": {
            "field_path": "reserves.asset",
            "unit": "provider_declared_raw_units",
            "decimals": 6,
            "mint": ASSET_MINT,
            "vault": ASSET_VAULT,
        },
        "counter": {
            "field_path": "reserves.counter",
            "unit": "provider_declared_raw_units",
            "decimals": 6,
            "mint": COUNTER_MINT,
            "vault": COUNTER_VAULT,
        },
    }


class ReserveSemanticProofGateTests(unittest.TestCase):
    def test_accepts_only_explicit_consistent_binding(self):
        result = validate_reserve_semantic_proof(pool_detail(), identity(), manifest())
        self.assertTrue(result["semantic_contract_verified"])
        self.assertTrue(result["reserve_field_roles_verified"])
        self.assertTrue(result["identity_binding_verified"])
        self.assertEqual(result["roles"]["asset"]["raw_value"], "1234500")
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["value_agreement_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(result["rejection_reasons"], [])

    def test_rejects_unproven_manifest(self):
        proof = manifest()
        proof["proof_status"] = "candidate"
        result = validate_reserve_semantic_proof(pool_detail(), identity(), proof)
        self.assertFalse(result["semantic_contract_verified"])
        self.assertIn("semantic_proof_status_unproven", result["rejection_reasons"])

    def test_rejects_pool_scope_mismatch(self):
        proof = manifest()
        proof["pool_address"] = "otherpool"
        result = validate_reserve_semantic_proof(pool_detail(), identity(), proof)
        self.assertIn("pool_identity_mismatch", result["rejection_reasons"])

    def test_rejects_unverified_vault_identity(self):
        vaults = identity()
        vaults["identity_verified"] = False
        result = validate_reserve_semantic_proof(pool_detail(), vaults, manifest())
        self.assertIn("vault_identity_unverified", result["rejection_reasons"])

    def test_rejects_mint_or_vault_mismatch(self):
        proof = manifest()
        proof["asset"]["mint"] = "wrongmint"
        proof["counter"]["vault"] = "wrongvault"
        result = validate_reserve_semantic_proof(pool_detail(), identity(), proof)
        self.assertIn("asset_mint_identity_mismatch", result["rejection_reasons"])
        self.assertIn("counter_vault_identity_mismatch", result["rejection_reasons"])

    def test_rejects_missing_or_nonnumeric_field(self):
        proof = manifest()
        proof["asset"]["field_path"] = "reserves.missing"
        detail = pool_detail()
        detail["raw_response"]["reserves"]["counter"] = "not-a-number"
        result = validate_reserve_semantic_proof(detail, identity(), proof)
        self.assertIn("asset_field_path_not_found", result["rejection_reasons"])
        self.assertIn("counter_reserve_value_not_numeric", result["rejection_reasons"])

    def test_rejects_same_field_for_both_roles(self):
        proof = manifest()
        proof["counter"]["field_path"] = proof["asset"]["field_path"]
        result = validate_reserve_semantic_proof(pool_detail(), identity(), proof)
        self.assertIn("reserve_field_paths_not_distinct", result["rejection_reasons"])

    def test_rejects_missing_evidence_references(self):
        proof = manifest()
        proof["evidence_refs"] = []
        result = validate_reserve_semantic_proof(pool_detail(), identity(), proof)
        self.assertIn("semantic_evidence_refs_missing", result["rejection_reasons"])

    def test_rejects_array_path_instead_of_guessing_element(self):
        proof = manifest()
        proof["asset"]["field_path"] = "reserves[].asset"
        result = validate_reserve_semantic_proof(pool_detail(), identity(), proof)
        self.assertIn("asset_field_path_not_found", result["rejection_reasons"])

    def test_rejects_invalid_decimals(self):
        proof = manifest()
        proof["asset"]["decimals"] = -1
        result = validate_reserve_semantic_proof(pool_detail(), identity(), proof)
        self.assertIn("asset_decimals_invalid", result["rejection_reasons"])


if __name__ == "__main__":
    unittest.main()
