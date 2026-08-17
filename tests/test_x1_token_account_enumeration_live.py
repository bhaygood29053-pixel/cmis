"""Opt-in read-only XENCAT token-account enumeration evidence probe.

The probe derives the token-program binding from a separately verified XENCAT
vault observation, performs one mint-filtered ``getProgramAccounts`` request,
and serializes only the sanitized count/set-digest artifact. A successful probe
never proves total coverage, absence of RPC truncation, holder semantics, or
beneficial-owner identity.
"""

import json
import os
import unittest

from liquidity_scout.providers.x1.rpc_token_account import (
    fetch_token_account_identity_raw,
)
from liquidity_scout.providers.x1.rpc_token_account_enumeration import (
    fetch_token_accounts_by_mint_raw,
)
from liquidity_scout.providers.x1.rpc_token_identity import (
    verify_x1_rpc_token_account_identity,
)
from liquidity_scout.providers.x1.token_account_enumeration_evidence import (
    build_x1_token_account_enumeration_artifact,
    derive_x1_token_program_binding,
)


RUN_LIVE = os.getenv("RUN_X1_TOKEN_ACCOUNT_ENUMERATION_LIVE") == "1"
OUTPUT_PATH = os.getenv("X1_TOKEN_ACCOUNT_ENUMERATION_OUTPUT")

XENCAT_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XENCAT_VAULT = "9ojBC34QUrubQASb1ktqkNn3kdFiUnqaBnLLgSeWbRm7"
SHARED_AUTHORITY = "9Dpjw2pB5kXJr6ZTHiqzEMfJPic3om9jgNacnwpLCoaU"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_TOKEN_ACCOUNT_ENUMERATION_LIVE=1 to run the read-only probe",
)
class X1TokenAccountEnumerationLiveTests(unittest.TestCase):
    def test_live_xencat_enumeration_candidate_without_totality_claim(self):
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
        artifact = build_x1_token_account_enumeration_artifact(
            program_binding,
            enumeration,
        )

        rendered = json.dumps(artifact, indent=2, sort_keys=True)
        print("X1 XENCAT token-account enumeration candidate")
        print(rendered)

        if OUTPUT_PATH:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
                handle.write(rendered)
                handle.write("\n")
            print(f"Sanitized enumeration evidence written to: {OUTPUT_PATH}")

        self.assertTrue(vault_verification["identity_verified"])
        self.assertTrue(program_binding["program_binding_verified_for_account"])
        self.assertFalse(program_binding["canonical_chain_token_program_verified"])
        self.assertEqual(artifact["mint"], XENCAT_MINT)
        self.assertTrue(artifact["artifact_sanitized"])
        self.assertTrue(
            artifact["enumeration"]["returned_account_identity_verified"]
        )
        self.assertTrue(
            artifact["enumeration"]["token_account_semantics_verified"]
        )
        self.assertGreaterEqual(
            artifact["enumeration"]["account_count_candidate"],
            0,
        )
        self.assertEqual(len(artifact["enumeration"]["account_set_sha256"]), 64)
        self.assertEqual(artifact["coverage"], "unverified")
        self.assertFalse(artifact["enumeration_complete"])
        self.assertFalse(artifact["truncation_absent_verified"])
        self.assertFalse(artifact["total_count_eligible"])
        self.assertFalse(artifact["holder_semantics_verified"])
        self.assertFalse(artifact["beneficial_owner_identity_verified"])
        self.assertFalse(artifact["cmis_promotable"])


if __name__ == "__main__":
    unittest.main()
