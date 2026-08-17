import copy
import unittest

from liquidity_scout.providers.x1.token_account_enumeration_evidence import (
    build_x1_token_account_enumeration_artifact,
    derive_x1_token_program_binding,
)


def observation():
    return {
        "chain": "x1",
        "source": "X1 RPC",
        "method": "getAccountInfo",
        "account": "vault1",
        "encoding": "jsonParsed",
        "slot": 100,
        "mint": "mint1",
        "authority": "authority1",
        "parsed_program": "spl-token",
        "account_program_owner": "program1",
        "token_account_fields_parsed": True,
        "raw_response": {"secret_transport": True},
        "rpc_url": "https://rpc.example",
    }


def verification():
    return {
        "service": "x1_rpc_token_account_identity",
        "version": "1.0",
        "chain": "x1",
        "account": "vault1",
        "mint": "mint1",
        "authority": "authority1",
        "slot": 100,
        "identity_verified": True,
        "cmis_promotable": False,
        "rejection_reasons": [],
    }


def enumeration(addresses=None):
    if addresses is None:
        addresses = ["acct2", "acct1"]
    return {
        "chain": "x1",
        "source": "X1 RPC",
        "method": "getProgramAccounts",
        "mint": "mint1",
        "token_program_id": "program1",
        "commitment": "confirmed",
        "slot": 105,
        "mint_filter": {"offset": 0, "bytes": "mint1"},
        "encoding": "jsonParsed",
        "with_context": True,
        "accounts": [
            {
                "address": address,
                "mint": "mint1",
                "token_program_id": "program1",
                "owner": f"owner-{index}",
                "state": "initialized",
                "raw_secret": "do-not-copy",
            }
            for index, address in enumerate(addresses)
        ],
        "account_count_candidate": len(addresses),
        "returned_account_identity_verified": True,
        "token_account_semantics_verified": True,
        "enumeration_complete": False,
        "truncation_absent_verified": False,
        "coverage": "unverified",
        "total_count_eligible": False,
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
        "warnings": [
            "getProgramAccounts_success_does_not_prove_provider_truncation_absent"
        ],
        "raw_response": {"secret_transport": True},
        "rpc_url": "https://rpc.example",
    }


class X1TokenAccountEnumerationEvidenceTests(unittest.TestCase):
    def test_derives_program_binding_only_from_verified_account_identity(self):
        result = derive_x1_token_program_binding(observation(), verification())

        self.assertEqual(result["token_program_id"], "program1")
        self.assertEqual(result["account"], "vault1")
        self.assertEqual(result["mint"], "mint1")
        self.assertTrue(result["program_binding_verified_for_account"])
        self.assertFalse(result["canonical_chain_token_program_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertNotIn("raw_response", result)
        self.assertNotIn("rpc_url", result)

    def test_unverified_identity_cannot_bind_program(self):
        bad = verification()
        bad["identity_verified"] = False
        bad["rejection_reasons"] = ["mint_identity_mismatch"]

        with self.assertRaisesRegex(ValueError, "token_account_identity_unverified"):
            derive_x1_token_program_binding(observation(), bad)

    def test_observation_and_verification_must_describe_same_fact(self):
        bad = verification()
        bad["mint"] = "other-mint"

        with self.assertRaisesRegex(ValueError, "verified_mint_mismatch"):
            derive_x1_token_program_binding(observation(), bad)

    def test_program_owner_is_required(self):
        source = observation()
        source["account_program_owner"] = None

        with self.assertRaisesRegex(ValueError, "account_program_owner_missing"):
            derive_x1_token_program_binding(source, verification())

    def test_builds_sanitized_nonpromotable_enumeration_artifact(self):
        binding = derive_x1_token_program_binding(observation(), verification())
        result = build_x1_token_account_enumeration_artifact(
            binding,
            enumeration(),
        )

        self.assertEqual(
            result["evidence_type"],
            "x1_token_account_enumeration_candidate",
        )
        self.assertEqual(result["mint"], "mint1")
        self.assertEqual(result["enumeration"]["account_count_candidate"], 2)
        self.assertEqual(len(result["enumeration"]["account_set_sha256"]), 64)
        self.assertEqual(result["coverage"], "unverified")
        self.assertFalse(result["enumeration_complete"])
        self.assertFalse(result["truncation_absent_verified"])
        self.assertFalse(result["total_count_eligible"])
        self.assertFalse(result["holder_semantics_verified"])
        self.assertFalse(result["beneficial_owner_identity_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertTrue(result["artifact_sanitized"])
        rendered = repr(result)
        self.assertNotIn("raw_secret", rendered)
        self.assertNotIn("secret_transport", rendered)
        self.assertNotIn("https://rpc.example", rendered)
        self.assertNotIn("owner-0", rendered)

    def test_account_set_digest_is_order_stable(self):
        binding = derive_x1_token_program_binding(observation(), verification())
        first = build_x1_token_account_enumeration_artifact(
            binding,
            enumeration(["acct1", "acct2", "acct3"]),
        )
        second = build_x1_token_account_enumeration_artifact(
            binding,
            enumeration(["acct3", "acct1", "acct2"]),
        )

        self.assertEqual(
            first["enumeration"]["account_set_sha256"],
            second["enumeration"]["account_set_sha256"],
        )

    def test_zero_account_candidate_is_valid_but_not_total(self):
        binding = derive_x1_token_program_binding(observation(), verification())
        result = build_x1_token_account_enumeration_artifact(
            binding,
            enumeration([]),
        )

        self.assertEqual(result["enumeration"]["account_count_candidate"], 0)
        self.assertFalse(result["total_count_eligible"])
        self.assertEqual(result["coverage"], "unverified")

    def test_mint_or_program_mismatch_fails_closed(self):
        binding = derive_x1_token_program_binding(observation(), verification())
        bad_mint = enumeration()
        bad_mint["mint"] = "other-mint"
        with self.assertRaisesRegex(ValueError, "mint does not match"):
            build_x1_token_account_enumeration_artifact(binding, bad_mint)

        bad_program = enumeration()
        bad_program["token_program_id"] = "other-program"
        with self.assertRaisesRegex(ValueError, "token program does not match"):
            build_x1_token_account_enumeration_artifact(binding, bad_program)

    def test_account_entries_are_revalidated_before_digest(self):
        binding = derive_x1_token_program_binding(observation(), verification())
        bad = enumeration()
        bad["accounts"][0]["mint"] = "other-mint"
        with self.assertRaisesRegex(ValueError, "account mint mismatch"):
            build_x1_token_account_enumeration_artifact(binding, bad)

        duplicate = enumeration(["acct1", "acct1"])
        with self.assertRaisesRegex(ValueError, "addresses are duplicated"):
            build_x1_token_account_enumeration_artifact(binding, duplicate)

    def test_upstream_completeness_or_promotion_claims_are_rejected(self):
        binding = derive_x1_token_program_binding(observation(), verification())
        for field in (
            "enumeration_complete",
            "truncation_absent_verified",
            "total_count_eligible",
            "holder_semantics_verified",
            "beneficial_owner_identity_verified",
            "cmis_promotable",
        ):
            with self.subTest(field=field):
                bad = enumeration()
                bad[field] = True
                with self.assertRaisesRegex(
                    ValueError,
                    "unsupported promotion/coverage claims",
                ):
                    build_x1_token_account_enumeration_artifact(binding, bad)

    def test_binding_cannot_claim_canonical_program_or_promotion(self):
        binding = derive_x1_token_program_binding(observation(), verification())
        for field in (
            "canonical_chain_token_program_verified",
            "cmis_promotable",
        ):
            with self.subTest(field=field):
                bad = copy.deepcopy(binding)
                bad[field] = True
                with self.assertRaises(ValueError):
                    build_x1_token_account_enumeration_artifact(
                        bad,
                        enumeration(),
                    )

    def test_inputs_must_be_mappings(self):
        with self.assertRaisesRegex(TypeError, "observation must be a mapping"):
            derive_x1_token_program_binding([], verification())
        with self.assertRaisesRegex(TypeError, "identity_verification must be a mapping"):
            derive_x1_token_program_binding(observation(), [])
        with self.assertRaisesRegex(TypeError, "program_binding must be a mapping"):
            build_x1_token_account_enumeration_artifact([], enumeration())
        with self.assertRaisesRegex(TypeError, "enumeration must be a mapping"):
            build_x1_token_account_enumeration_artifact(
                derive_x1_token_program_binding(observation(), verification()),
                [],
            )


if __name__ == "__main__":
    unittest.main()
