import unittest

from liquidity_scout.providers.x1.reserve_evidence import (
    BASE_UNITS,
    build_x1_reserve_evidence_pair,
)


POOL = "pool111"
MINT = "mint111"
VAULT = "vault111"


def semantic_proof():
    return {
        "chain": "x1",
        "pool_address": POOL,
        "semantic_contract_verified": True,
        "identity_binding_verified": True,
        "roles": {
            "asset": {
                "field_path": "reserves.asset",
                "raw_value": "42000000",
                "unit": BASE_UNITS,
                "decimals": 6,
                "mint": MINT,
                "vault": VAULT,
            },
            "counter": {
                "field_path": "reserves.counter",
                "raw_value": "9000000",
                "unit": BASE_UNITS,
                "decimals": 6,
                "mint": "mint222",
                "vault": "vault222",
            },
        },
    }


def rpc_balance():
    return {
        "chain": "x1",
        "source": "X1 RPC",
        "method": "getTokenAccountBalance",
        "account": VAULT,
        "slot": 123456,
        "amount": "42000000",
        "decimals": 6,
    }


class X1ReserveEvidenceTests(unittest.TestCase):
    def test_builds_same_identity_evidence_without_auto_promotion(self):
        result = build_x1_reserve_evidence_pair(
            semantic_proof(), rpc_balance(), role="asset", observed_at=1000.0
        )
        self.assertTrue(result["evidence_ready"])
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(result["provider"]["subject_id"], result["rpc"]["subject_id"])
        self.assertEqual(result["provider"]["normalized_value"], "42")
        self.assertEqual(result["rpc"]["normalized_value"], "42")
        self.assertEqual(result["rpc"]["block_slot"], 123456)
        self.assertFalse(result["provider"]["freshness_verified"])

    def test_freshness_is_explicit_not_inferred(self):
        result = build_x1_reserve_evidence_pair(
            semantic_proof(), rpc_balance(), role="asset", observed_at=1000.0,
            freshness_verified=True,
        )
        self.assertTrue(result["provider"]["freshness_verified"])
        self.assertTrue(result["rpc"]["freshness_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_rejects_unverified_semantic_contract(self):
        proof = semantic_proof()
        proof["semantic_contract_verified"] = False
        result = build_x1_reserve_evidence_pair(proof, rpc_balance(), role="asset", observed_at=1)
        self.assertFalse(result["evidence_ready"])
        self.assertIn("semantic_contract_unverified", result["rejection_reasons"])

    def test_rejects_unknown_provider_unit(self):
        proof = semantic_proof()
        proof["roles"]["asset"]["unit"] = "provider_units"
        result = build_x1_reserve_evidence_pair(proof, rpc_balance(), role="asset", observed_at=1)
        self.assertIn("provider_unit_not_token_base_units", result["rejection_reasons"])

    def test_rejects_rpc_vault_mismatch(self):
        rpc = rpc_balance()
        rpc["account"] = "other-vault"
        result = build_x1_reserve_evidence_pair(semantic_proof(), rpc, role="asset", observed_at=1)
        self.assertIn("rpc_vault_mismatch", result["rejection_reasons"])

    def test_rejects_decimal_mismatch(self):
        rpc = rpc_balance()
        rpc["decimals"] = 9
        result = build_x1_reserve_evidence_pair(semantic_proof(), rpc, role="asset", observed_at=1)
        self.assertIn("decimal_mismatch", result["rejection_reasons"])

    def test_rejects_non_integer_provider_base_units(self):
        proof = semantic_proof()
        proof["roles"]["asset"]["raw_value"] = "42.0"
        result = build_x1_reserve_evidence_pair(proof, rpc_balance(), role="asset", observed_at=1)
        self.assertIn("provider_base_units_invalid", result["rejection_reasons"])

    def test_rejects_invalid_role(self):
        with self.assertRaisesRegex(ValueError, "role must be asset or counter"):
            build_x1_reserve_evidence_pair(semantic_proof(), rpc_balance(), role="other", observed_at=1)


if __name__ == "__main__":
    unittest.main()
