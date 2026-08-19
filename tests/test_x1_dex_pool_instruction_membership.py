import unittest

from liquidity_scout.providers.x1.dex_pool_instruction_membership import (
    X1DexPoolInstructionMembershipError,
    verify_dex_pool_instruction_membership,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    XENDEX_AMM_PROGRAM_ID,
    XENDEX_STAKING_PROGRAM_ID,
)


SIGNATURE = "Signature111111111111111111111111111111111"
SIGNER = "Signer111111111111111111111111111111111111"
POOL = "Pool11111111111111111111111111111111111111"
OTHER = "Other1111111111111111111111111111111111111"
UNRECOGNIZED = "Unknown11111111111111111111111111111111111"


def _tx(*, instructions, inner=None, err=None, account_keys=None, signature=SIGNATURE):
    if account_keys is None:
        account_keys = [
            {"pubkey": SIGNER, "signer": True},
            {"pubkey": POOL, "signer": False},
            {"pubkey": XDEX_MAINNET_OBSERVED_PROGRAM_ID, "signer": False},
            {"pubkey": XENDEX_AMM_PROGRAM_ID, "signer": False},
            {"pubkey": OTHER, "signer": False},
        ]
    return {
        "slot": 123,
        "transaction": {
            "signatures": [signature],
            "message": {
                "accountKeys": account_keys,
                "instructions": instructions,
            },
        },
        "meta": {
            "err": err,
            "innerInstructions": [] if inner is None else inner,
        },
    }


class X1DexPoolInstructionMembershipTests(unittest.TestCase):
    def test_outer_xdex_instruction_exact_pool_account_is_verified(self):
        tx = _tx(
            instructions=[
                {
                    "programId": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                    "accounts": [POOL, OTHER],
                    "data": "abc",
                }
            ]
        )

        result = verify_dex_pool_instruction_membership(
            tx=tx,
            signature=SIGNATURE,
            pool_address=POOL,
            pool_identity_verified=True,
        )

        self.assertTrue(result["signature_identity_verified"])
        self.assertTrue(
            result["recognized_amm_instruction_pool_account_membership_verified"]
        )
        self.assertTrue(
            result[
                "successful_recognized_amm_instruction_pool_account_membership_verified"
            ]
        )
        self.assertEqual(result["hit_count"], 1)
        self.assertEqual(result["hits"][0]["location"], "outer")
        self.assertEqual(
            result["hits"][0]["program_id"],
            XDEX_MAINNET_OBSERVED_PROGRAM_ID,
        )
        self.assertFalse(result["pool_mutation_verified"])
        self.assertFalse(result["route_exclusivity_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_inner_xendex_instruction_resolves_program_and_pool_by_index(self):
        tx = _tx(
            instructions=[],
            inner=[
                {
                    "index": 0,
                    "instructions": [
                        {
                            "programIdIndex": 3,
                            "accounts": [1, 4],
                            "data": "inner",
                        }
                    ],
                }
            ],
        )

        result = verify_dex_pool_instruction_membership(
            tx=tx,
            signature=SIGNATURE,
            pool_address=POOL,
            pool_identity_verified=True,
        )

        self.assertTrue(
            result["recognized_amm_instruction_pool_account_membership_verified"]
        )
        self.assertEqual(result["hits"][0]["location"], "inner")
        self.assertEqual(result["hits"][0]["inner_group_index"], 0)
        self.assertEqual(result["hits"][0]["program_id"], XENDEX_AMM_PROGRAM_ID)

    def test_pool_in_message_account_keys_alone_is_not_membership_proof(self):
        tx = _tx(
            instructions=[
                {
                    "programId": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                    "accounts": [OTHER],
                }
            ]
        )
        result = verify_dex_pool_instruction_membership(
            tx=tx,
            signature=SIGNATURE,
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertFalse(
            result["recognized_amm_instruction_pool_account_membership_verified"]
        )
        self.assertEqual(result["hit_count"], 0)

    def test_pool_in_unrecognized_program_instruction_is_not_membership_proof(self):
        tx = _tx(
            instructions=[
                {
                    "programId": UNRECOGNIZED,
                    "accounts": [POOL],
                }
            ]
        )
        result = verify_dex_pool_instruction_membership(
            tx=tx,
            signature=SIGNATURE,
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertFalse(
            result["recognized_amm_instruction_pool_account_membership_verified"]
        )

    def test_xendex_staking_instruction_is_not_amm_membership_proof(self):
        tx = _tx(
            instructions=[
                {
                    "programId": XENDEX_STAKING_PROGRAM_ID,
                    "accounts": [POOL],
                }
            ]
        )
        result = verify_dex_pool_instruction_membership(
            tx=tx,
            signature=SIGNATURE,
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertFalse(
            result["recognized_amm_instruction_pool_account_membership_verified"]
        )

    def test_failed_transaction_preserves_membership_but_not_successful_membership(self):
        tx = _tx(
            instructions=[
                {
                    "programId": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                    "accounts": [POOL],
                }
            ],
            err={"InstructionError": [0, "Custom"]},
        )
        result = verify_dex_pool_instruction_membership(
            tx=tx,
            signature=SIGNATURE,
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertTrue(
            result["recognized_amm_instruction_pool_account_membership_verified"]
        )
        self.assertFalse(result["transaction_succeeded"])
        self.assertFalse(
            result[
                "successful_recognized_amm_instruction_pool_account_membership_verified"
            ]
        )

    def test_signature_mismatch_fails_closed(self):
        tx = _tx(instructions=[], signature="DifferentSignature")
        with self.assertRaisesRegex(
            X1DexPoolInstructionMembershipError,
            "signature does not match requested signature",
        ):
            verify_dex_pool_instruction_membership(
                tx=tx,
                signature=SIGNATURE,
                pool_address=POOL,
                pool_identity_verified=True,
            )

    def test_unverified_pool_identity_fails_closed(self):
        tx = _tx(instructions=[])
        with self.assertRaisesRegex(
            X1DexPoolInstructionMembershipError,
            "pool_identity_verified must be verified",
        ):
            verify_dex_pool_instruction_membership(
                tx=tx,
                signature=SIGNATURE,
                pool_address=POOL,
                pool_identity_verified=False,
            )

    def test_boolean_account_index_does_not_alias_integer_pool_index(self):
        tx = _tx(
            instructions=[
                {
                    "programId": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                    "accounts": [True],
                }
            ]
        )
        result = verify_dex_pool_instruction_membership(
            tx=tx,
            signature=SIGNATURE,
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertFalse(
            result["recognized_amm_instruction_pool_account_membership_verified"]
        )

    def test_dict_account_representation_is_supported(self):
        tx = _tx(
            instructions=[
                {
                    "programId": {"pubkey": XDEX_MAINNET_OBSERVED_PROGRAM_ID},
                    "accounts": [{"pubkey": POOL}, {"address": OTHER}],
                }
            ]
        )
        result = verify_dex_pool_instruction_membership(
            tx=tx,
            signature=SIGNATURE,
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertTrue(
            result["recognized_amm_instruction_pool_account_membership_verified"]
        )

    def test_multiple_hits_are_preserved_without_route_exclusivity_claim(self):
        tx = _tx(
            instructions=[
                {
                    "programId": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                    "accounts": [POOL],
                },
                {
                    "programId": XENDEX_AMM_PROGRAM_ID,
                    "accounts": [POOL],
                },
            ]
        )
        result = verify_dex_pool_instruction_membership(
            tx=tx,
            signature=SIGNATURE,
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertEqual(result["hit_count"], 2)
        self.assertTrue(
            result["recognized_amm_instruction_pool_account_membership_verified"]
        )
        self.assertFalse(result["route_exclusivity_verified"])


if __name__ == "__main__":
    unittest.main()
