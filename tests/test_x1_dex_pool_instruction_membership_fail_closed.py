import unittest

from liquidity_scout.providers.x1.dex_pool_instruction_membership import (
    X1DexPoolInstructionMembershipError,
    verify_dex_pool_instruction_membership,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
)


SIGNATURE = "Signature111111111111111111111111111111111"
SIGNER = "Signer111111111111111111111111111111111111"
POOL = "Pool11111111111111111111111111111111111111"


def _base_tx():
    return {
        "transaction": {
            "signatures": [SIGNATURE],
            "message": {
                "accountKeys": [
                    {"pubkey": SIGNER, "signer": True},
                    {"pubkey": POOL, "signer": False},
                    {"pubkey": XDEX_MAINNET_OBSERVED_PROGRAM_ID, "signer": False},
                ],
                "instructions": [
                    {
                        "programId": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                        "accounts": [POOL],
                    }
                ],
            },
        },
        "meta": {"err": None, "innerInstructions": []},
    }


class X1DexPoolInstructionMembershipFailClosedTests(unittest.TestCase):
    def test_missing_explicit_meta_err_does_not_become_success(self):
        tx = _base_tx()
        tx["meta"].pop("err")
        with self.assertRaisesRegex(
            X1DexPoolInstructionMembershipError,
            "meta.err is required",
        ):
            verify_dex_pool_instruction_membership(
                tx=tx,
                signature=SIGNATURE,
                pool_address=POOL,
                pool_identity_verified=True,
            )

    def test_missing_transaction_signature_fails_closed(self):
        tx = _base_tx()
        tx["transaction"]["signatures"] = []
        with self.assertRaisesRegex(
            X1DexPoolInstructionMembershipError,
            "signatures must contain",
        ):
            verify_dex_pool_instruction_membership(
                tx=tx,
                signature=SIGNATURE,
                pool_address=POOL,
                pool_identity_verified=True,
            )

    def test_out_of_range_index_cannot_create_false_membership(self):
        tx = _base_tx()
        tx["transaction"]["message"]["instructions"] = [
            {
                "programId": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                "accounts": [999],
            }
        ]
        result = verify_dex_pool_instruction_membership(
            tx=tx,
            signature=SIGNATURE,
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertFalse(
            result["recognized_amm_instruction_pool_account_membership_verified"]
        )
        self.assertFalse(
            result[
                "successful_recognized_amm_instruction_pool_account_membership_verified"
            ]
        )
        self.assertTrue(result["transaction_success_state_verified"])
        self.assertFalse(result["pool_mutation_verified"])
        self.assertFalse(result["cmis_promotable"])


if __name__ == "__main__":
    unittest.main()
