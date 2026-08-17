import copy
import unittest

from liquidity_scout.providers.x1.ninja_holder_semantics import (
    PROOF_STATUS,
    validate_x1_ninja_holder_semantic_proof,
)


POOL = "pool111"
BASE_MINT = "base-mint"
QUOTE_MINT = "quote-mint"


def candidates():
    return {
        "service": "x1_ninja_holder_candidates",
        "version": "1.0",
        "chain": "x1",
        "status": "ok",
        "pool_address_requested": POOL,
        "pool_address_observed": POOL,
        "holder_field_candidates": [
            {"field_path": "pool.holders", "raw_value": 115}
        ],
        "token_metadata_candidates": {
            "base_token": {
                "address": BASE_MINT,
                "symbol": "BASE",
                "name": "Base Token",
                "decimals": 6,
            },
            "quote_token": {
                "address": QUOTE_MINT,
                "symbol": "XNT",
                "name": "Wrapped XNT",
                "decimals": 9,
            },
        },
        "pool_identity_transport_consistent": True,
        "holder_field_semantics_verified": False,
        "holder_field_asset_binding_verified": False,
        "holder_uniqueness_semantics_verified": False,
        "holder_coverage_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
    }


def manifest():
    return {
        "proof_status": PROOF_STATUS,
        "proof_version": "test-1",
        "pool_address": POOL,
        "field_path": "pool.holders",
        "asset_role": "base_token",
        "asset_mint": BASE_MINT,
        "counted_entity": "token_accounts",
        "coverage": "total",
        "evidence_refs": ["test://external-holder-semantics-proof"],
    }


class X1NinjaHolderSemanticsTests(unittest.TestCase):
    def test_explicit_total_token_account_semantics_becomes_comparison_eligible_only(self):
        result = validate_x1_ninja_holder_semantic_proof(candidates(), manifest())

        self.assertTrue(result["semantic_contract_verified"])
        self.assertTrue(result["asset_binding_verified"])
        self.assertTrue(result["counted_entity_semantics_verified"])
        self.assertTrue(result["coverage_semantics_verified"])
        self.assertEqual(result["raw_count"], 115)
        self.assertEqual(result["counted_entity"], "token_accounts")
        self.assertEqual(result["coverage"], "total")
        self.assertTrue(result["rpc_total_token_account_count_comparison_eligible"])
        self.assertFalse(result["beneficial_owner_semantics_verified"])
        self.assertFalse(result["external_evidence_authenticity_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(result["rejection_reasons"], [])

    def test_beneficial_owner_semantics_do_not_become_rpc_token_account_count_comparable(self):
        item = manifest()
        item["counted_entity"] = "beneficial_owners"

        result = validate_x1_ninja_holder_semantic_proof(candidates(), item)

        self.assertTrue(result["semantic_contract_verified"])
        self.assertTrue(result["beneficial_owner_semantics_verified"])
        self.assertFalse(result["rpc_total_token_account_count_comparison_eligible"])
        self.assertFalse(result["cmis_promotable"])

    def test_partial_token_account_coverage_is_not_total_count_comparable(self):
        item = manifest()
        item["coverage"] = "partial"

        result = validate_x1_ninja_holder_semantic_proof(candidates(), item)

        self.assertTrue(result["semantic_contract_verified"])
        self.assertFalse(result["rpc_total_token_account_count_comparison_eligible"])
        self.assertFalse(result["cmis_promotable"])

    def test_current_xencat_candidate_without_external_proof_stays_unverified(self):
        observed = candidates()
        observed["pool_address_requested"] = (
            "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
        )
        observed["pool_address_observed"] = observed["pool_address_requested"]
        observed["token_metadata_candidates"]["base_token"]["address"] = (
            "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
        )
        proof = {
            "proof_status": "asserted_only",
            "pool_address": observed["pool_address_requested"],
            "field_path": "pool.holders",
            "asset_role": "base_token",
            "asset_mint": observed["token_metadata_candidates"]["base_token"][
                "address"
            ],
            "counted_entity": "token_accounts",
            "coverage": "total",
            "evidence_refs": [],
        }

        result = validate_x1_ninja_holder_semantic_proof(observed, proof)

        self.assertEqual(result["raw_count"], 115)
        self.assertFalse(result["semantic_contract_verified"])
        self.assertIn("semantic_proof_status_unproven", result["rejection_reasons"])
        self.assertIn("semantic_evidence_refs_missing", result["rejection_reasons"])
        self.assertFalse(result["rpc_total_token_account_count_comparison_eligible"])
        self.assertFalse(result["cmis_promotable"])

    def test_unobserved_field_path_is_rejected(self):
        item = manifest()
        item["field_path"] = "pool.otherHolders"

        result = validate_x1_ninja_holder_semantic_proof(candidates(), item)

        self.assertFalse(result["semantic_contract_verified"])
        self.assertIn("holder_field_path_not_observed", result["rejection_reasons"])

    def test_non_integer_holder_value_is_rejected(self):
        observed = candidates()
        observed["holder_field_candidates"][0]["raw_value"] = "115"

        result = validate_x1_ninja_holder_semantic_proof(observed, manifest())

        self.assertFalse(result["semantic_contract_verified"])
        self.assertIn(
            "holder_count_value_not_nonnegative_integer",
            result["rejection_reasons"],
        )

    def test_asset_mint_binding_mismatch_is_rejected(self):
        item = manifest()
        item["asset_mint"] = "other-mint"

        result = validate_x1_ninja_holder_semantic_proof(candidates(), item)

        self.assertFalse(result["semantic_contract_verified"])
        self.assertIn("asset_mint_binding_mismatch", result["rejection_reasons"])

    def test_pool_mismatch_and_missing_evidence_are_rejected(self):
        item = manifest()
        item["pool_address"] = "other-pool"
        item["evidence_refs"] = []

        result = validate_x1_ninja_holder_semantic_proof(candidates(), item)

        self.assertFalse(result["semantic_contract_verified"])
        self.assertIn("pool_identity_mismatch", result["rejection_reasons"])
        self.assertIn("semantic_evidence_refs_missing", result["rejection_reasons"])

    def test_upstream_candidate_rejection_blocks_semantics(self):
        observed = candidates()
        observed["status"] = "error"
        observed["pool_identity_transport_consistent"] = False

        result = validate_x1_ninja_holder_semantic_proof(observed, manifest())

        self.assertFalse(result["semantic_contract_verified"])
        self.assertIn(
            "holder_candidate_observation_rejected",
            result["rejection_reasons"],
        )
        self.assertIn(
            "pool_identity_transport_unverified",
            result["rejection_reasons"],
        )

    def test_unsupported_entity_and_coverage_are_rejected(self):
        item = manifest()
        item["counted_entity"] = "people"
        item["coverage"] = "maybe"

        result = validate_x1_ninja_holder_semantic_proof(candidates(), item)

        self.assertFalse(result["semantic_contract_verified"])
        self.assertIn(
            "counted_entity_semantics_unsupported",
            result["rejection_reasons"],
        )
        self.assertIn("coverage_semantics_unsupported", result["rejection_reasons"])

    def test_inputs_must_be_mappings(self):
        with self.assertRaisesRegex(TypeError, "holder_candidates must be a mapping"):
            validate_x1_ninja_holder_semantic_proof([], manifest())
        with self.assertRaisesRegex(TypeError, "manifest must be a mapping"):
            validate_x1_ninja_holder_semantic_proof(candidates(), [])


if __name__ == "__main__":
    unittest.main()
