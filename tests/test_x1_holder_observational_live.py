"""Opt-in read-only XENCAT holder observational comparison probe.

This probe observes X1.Ninja's lexical holder-looking field and an X1 RPC
mint-filtered token-account enumeration in the same test run. It serializes only
the sanitized numeric comparison. Numeric agreement or disagreement never proves
provider holder semantics, total RPC coverage, wallet identity, beneficial
ownership, freshness equivalence, or CMIS promotion.
"""

import json
import os
import unittest

from liquidity_scout.providers.x1.holder_observational_comparison import (
    build_x1_holder_observational_comparison,
)
from liquidity_scout.providers.x1.ninja_holder_candidates import (
    extract_x1_ninja_holder_candidates,
)
from liquidity_scout.providers.x1.ninja_pool_detail import fetch_pool_detail_raw
from liquidity_scout.providers.x1.rpc_token_account import fetch_token_account_identity_raw
from liquidity_scout.providers.x1.rpc_token_account_enumeration import (
    fetch_token_accounts_by_mint_raw,
)
from liquidity_scout.providers.x1.rpc_token_identity import (
    verify_x1_rpc_token_account_identity,
)
from liquidity_scout.providers.x1.token_account_enumeration_evidence import (
    derive_x1_token_program_binding,
)


RUN_LIVE = os.getenv("RUN_X1_HOLDER_OBSERVATIONAL_LIVE") == "1"
OUTPUT_PATH = os.getenv("X1_HOLDER_OBSERVATIONAL_OUTPUT")

XENCAT_POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
XENCAT_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XENCAT_VAULT = "9ojBC34QUrubQASb1ktqkNn3kdFiUnqaBnLLgSeWbRm7"
SHARED_AUTHORITY = "9Dpjw2pB5kXJr6ZTHiqzEMfJPic3om9jgNacnwpLCoaU"
HOLDER_FIELD_PATH = "pool.holders"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_HOLDER_OBSERVATIONAL_LIVE=1 to run the read-only probe",
)
class X1HolderObservationalLiveTests(unittest.TestCase):
    def test_live_xencat_numeric_relations_without_holder_semantic_promotion(self):
        pool_detail = fetch_pool_detail_raw(XENCAT_POOL)
        holder_candidates = extract_x1_ninja_holder_candidates(
            pool_detail,
            expected_pool_address=XENCAT_POOL,
        )

        vault_observation = fetch_token_account_identity_raw(XENCAT_VAULT)
        vault_verification = verify_x1_rpc_token_account_identity(
            vault_observation,
            expected_account=XENCAT_VAULT,
            expected_mint=XENCAT_MINT,
            expected_authority=SHARED_AUTHORITY,
        )
        program_binding = derive_x1_token_program_binding(
            vault_observation,
            vault_verification,
        )
        enumeration = fetch_token_accounts_by_mint_raw(
            XENCAT_MINT,
            token_program_id=program_binding["token_program_id"],
        )

        comparison = build_x1_holder_observational_comparison(
            holder_candidates,
            enumeration,
            expected_mint=XENCAT_MINT,
            field_path=HOLDER_FIELD_PATH,
        )

        rendered = json.dumps(comparison, indent=2, sort_keys=True)
        print("X1 XENCAT holder observational comparison")
        print(rendered)

        if OUTPUT_PATH:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
                handle.write(rendered)
                handle.write("\n")
            print(f"Sanitized holder observational evidence written to: {OUTPUT_PATH}")

        self.assertTrue(vault_verification["identity_verified"])
        self.assertTrue(program_binding["program_binding_verified_for_account"])
        self.assertEqual(comparison["verification_status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(comparison["comparison_semantics_verified"])
        self.assertEqual(comparison["expected_mint"], XENCAT_MINT)
        self.assertEqual(comparison["provider"]["field_path"], HOLDER_FIELD_PATH)
        self.assertTrue(comparison["provider"]["pool_contains_expected_mint"])
        self.assertGreaterEqual(comparison["rpc"]["token_account_count_candidate"], 0)
        self.assertFalse(comparison["rpc"]["enumeration_complete"])
        self.assertFalse(comparison["rpc"]["truncation_absent_verified"])
        self.assertFalse(comparison["holder_semantics_verified"])
        self.assertFalse(comparison["beneficial_owner_identity_verified"])
        self.assertFalse(comparison["cmis_promotable"])
        self.assertTrue(comparison["artifact_sanitized"])


if __name__ == "__main__":
    unittest.main()
