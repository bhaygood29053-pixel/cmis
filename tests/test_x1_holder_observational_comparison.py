import copy
import unittest

from liquidity_scout.providers.x1.holder_observational_comparison import (
    build_x1_holder_observational_comparison,
)


MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def holder_candidates(count=115):
    return {
        "service": "x1_ninja_holder_candidates",
        "version": "1.0",
        "chain": "x1",
        "status": "ok",
        "pool_address_requested": POOL,
        "pool_address_observed": POOL,
        "provider_observed_at": "2026-08-17T18:00:00Z",
        "holder_field_candidates": [
            {"field_path": "pool.holders", "raw_value": count}
        ],
        "token_metadata_candidates": {
            "base_token": {"address": MINT, "symbol": "XENCAT"},
            "quote_token": {"address": "So11111111111111111111111111111111111111112"},
        },
        "pool_identity_transport_consistent": True,
        "holder_field_semantics_verified": False,
        "holder_field_asset_binding_verified": False,
        "holder_uniqueness_semantics_verified": False,
        "holder_coverage_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
        "warnings": [],
        "errors": [],
    }


def enumeration(owners=("owner-a", "owner-a", "owner-b")):
    accounts = [
        {
            "address": f"account-{index}",
            "mint": MINT,
            "token_program_id": PROGRAM,
            "owner": owner,
            "state": "initialized",
        }
        for index, owner in enumerate(owners)
    ]
    return {
        "chain": "x1",
        "source": "X1 RPC",
        "method": "getProgramAccounts",
        "mint": MINT,
        "token_program_id": PROGRAM,
        "commitment": "confirmed",
        "slot": 72320855,
        "mint_filter": {"offset": 0, "bytes": MINT},
        "encoding": "jsonParsed",
        "with_context": True,
        "accounts": accounts,
        "account_count_candidate": len(accounts),
        "returned_account_identity_verified": True,
        "token_account_semantics_verified": True,
        "enumeration_complete": False,
        "truncation_absent_verified": False,
        "coverage": "unverified",
        "total_count_eligible": False,
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
        "warnings": [],
    }


class X1HolderObservationalComparisonTests(unittest.TestCase):
    def test_builds_sanitized_numeric_relations_without_semantic_promotion(self):
        result = build_x1_holder_observational_comparison(
            holder_candidates(2),
            enumeration(("owner-a", "owner-a", "owner-b")),
            expected_mint=MINT,
            field_path="pool.holders",
        )

        self.assertEqual(result["verification_status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(result["comparison_semantics_verified"])
        self.assertEqual(result["provider"]["lexical_holder_count_candidate"], 2)
        self.assertEqual(result["rpc"]["token_account_count_candidate"], 3)
        self.assertEqual(
            result["rpc"]["unique_token_account_authority_count_candidate"], 2
        )
        self.assertEqual(
            result["numeric_relations"]["rpc_account_count_minus_provider_candidate"],
            1,
        )
        self.assertFalse(
            result["numeric_relations"]["provider_candidate_equals_rpc_account_count"]
        )
        self.assertTrue(
            result["numeric_relations"][
                "provider_candidate_equals_rpc_unique_authority_count"
            ]
        )
        self.assertEqual(
            len(result["rpc"]["unique_token_account_authority_set_sha256"]), 64
        )
        self.assertTrue(result["artifact_sanitized"])
        self.assertFalse(result["holder_semantics_verified"])
        self.assertFalse(result["beneficial_owner_identity_verified"])
        self.assertFalse(result["cmis_promotable"])
        rendered = repr(result)
        self.assertNotIn("owner-a", rendered)
        self.assertNotIn("account-0", rendered)

    def test_owner_set_digest_is_order_stable(self):
        left = build_x1_holder_observational_comparison(
            holder_candidates(2),
            enumeration(("owner-a", "owner-b", "owner-a")),
            expected_mint=MINT,
            field_path="pool.holders",
        )
        right = build_x1_holder_observational_comparison(
            holder_candidates(2),
            enumeration(("owner-b", "owner-a", "owner-a")),
            expected_mint=MINT,
            field_path="pool.holders",
        )
        self.assertEqual(
            left["rpc"]["unique_token_account_authority_set_sha256"],
            right["rpc"]["unique_token_account_authority_set_sha256"],
        )

    def test_missing_owner_disables_unique_authority_candidate(self):
        observation = enumeration(("owner-a", "owner-b"))
        observation["accounts"][1]["owner"] = None
        result = build_x1_holder_observational_comparison(
            holder_candidates(2),
            observation,
            expected_mint=MINT,
            field_path="pool.holders",
        )
        self.assertFalse(
            result["rpc"]["authority_fields_present_for_all_returned_accounts"]
        )
        self.assertIsNone(
            result["rpc"]["unique_token_account_authority_count_candidate"]
        )
        self.assertIsNone(
            result["numeric_relations"][
                "provider_candidate_equals_rpc_unique_authority_count"
            ]
        )
        self.assertIn("token_account_authority_fields_incomplete", result["warnings"])

    def test_rejects_provider_semantic_promotion_claim(self):
        observation = holder_candidates(2)
        observation["holder_field_semantics_verified"] = True
        with self.assertRaisesRegex(ValueError, "unsupported provider semantic claim"):
            build_x1_holder_observational_comparison(
                observation,
                enumeration(),
                expected_mint=MINT,
                field_path="pool.holders",
            )

    def test_rejects_enumeration_totality_claim(self):
        observation = enumeration()
        observation["enumeration_complete"] = True
        with self.assertRaisesRegex(ValueError, "unsupported enumeration claim"):
            build_x1_holder_observational_comparison(
                holder_candidates(2),
                observation,
                expected_mint=MINT,
                field_path="pool.holders",
            )

    def test_rejects_wrong_mint_and_missing_provider_pool_mint(self):
        with self.assertRaisesRegex(ValueError, "enumeration mint mismatch"):
            build_x1_holder_observational_comparison(
                holder_candidates(2),
                {**enumeration(), "mint": "other"},
                expected_mint=MINT,
                field_path="pool.holders",
            )

        provider = holder_candidates(2)
        provider["token_metadata_candidates"]["base_token"]["address"] = "other"
        with self.assertRaisesRegex(ValueError, "not present in provider pool token metadata"):
            build_x1_holder_observational_comparison(
                provider,
                enumeration(),
                expected_mint=MINT,
                field_path="pool.holders",
            )

    def test_rejects_duplicate_or_non_integer_holder_candidate(self):
        provider = holder_candidates(2)
        provider["holder_field_candidates"].append(
            {"field_path": "pool.holders", "raw_value": 2}
        )
        with self.assertRaisesRegex(ValueError, "exactly one"):
            build_x1_holder_observational_comparison(
                provider,
                enumeration(),
                expected_mint=MINT,
                field_path="pool.holders",
            )

        provider = holder_candidates("2")
        with self.assertRaisesRegex(ValueError, "nonnegative integer"):
            build_x1_holder_observational_comparison(
                provider,
                enumeration(),
                expected_mint=MINT,
                field_path="pool.holders",
            )

    def test_does_not_mutate_inputs(self):
        provider = holder_candidates(2)
        rpc = enumeration()
        provider_before = copy.deepcopy(provider)
        rpc_before = copy.deepcopy(rpc)
        build_x1_holder_observational_comparison(
            provider,
            rpc,
            expected_mint=MINT,
            field_path="pool.holders",
        )
        self.assertEqual(provider, provider_before)
        self.assertEqual(rpc, rpc_before)


if __name__ == "__main__":
    unittest.main()
