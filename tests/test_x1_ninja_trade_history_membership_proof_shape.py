import unittest

from liquidity_scout.providers.x1.ninja_trade_history_pool_membership import (
    X1NinjaTradeHistoryPoolMembershipError,
    _validate_membership_proof,
)


POOL = "Pool11111111111111111111111111111111111111"
SIGNATURE = "sig-1"


def _proof():
    return {
        "contract_version": "x1_transaction_pool_membership/v3",
        "chain": "x1",
        "transaction_signature": SIGNATURE,
        "transaction_instruction_evidence_bound": True,
        "pool_address": POOL,
        "asset_mint": "Mint11111111111111111111111111111111111111",
        "asset_vault": "AssetVault111111111111111111111111111111111",
        "counter_mint": "Quote1111111111111111111111111111111111111",
        "counter_vault": "QuoteVault111111111111111111111111111111111",
        "shared_owner": "PoolAuthority1111111111111111111111111111111",
        "transaction_found": True,
        "transaction_succeeded": True,
        "recognized_amm_invoked": True,
        "recognized_amm_instruction_count": 1,
        "selected_pool_instruction_verified": True,
        "selected_pool_instruction_count": 1,
        "selected_pool_instruction_evidence": [
            {
                "program_id": "recognized-xdex-program",
                "scope": "outer",
                "group_index": None,
                "instruction_index": 1,
            }
        ],
        "asset_vault_mutated": True,
        "counter_vault_mutated": True,
        "vault_authority_verified": True,
        "transaction_pool_membership_verified": True,
        "provider_row_pool_claim_verified": None,
        "source_independence_verified": None,
        "history_completeness_verified": None,
        "finality_semantics_verified": None,
        "amount_semantics_verified": None,
        "price_semantics_verified": None,
        "cmis_promotable": False,
        "rejection_reasons": [],
    }


class X1NinjaTradeHistoryMembershipProofShapeTests(unittest.TestCase):
    def test_positive_genuine_shaped_proof_is_accepted(self):
        self.assertTrue(
            _validate_membership_proof(
                signature=SIGNATURE,
                expected_pool=POOL,
                proof=_proof(),
            )
        )

    def test_positive_proof_requires_identity_fields(self):
        forged = _proof()
        del forged["asset_mint"]
        with self.assertRaisesRegex(
            X1NinjaTradeHistoryPoolMembershipError,
            "asset_mint",
        ):
            _validate_membership_proof(
                signature=SIGNATURE,
                expected_pool=POOL,
                proof=forged,
            )

    def test_empty_selected_instruction_mapping_is_rejected(self):
        forged = _proof()
        forged["selected_pool_instruction_evidence"] = [{}]
        with self.assertRaisesRegex(
            X1NinjaTradeHistoryPoolMembershipError,
            "program_id",
        ):
            _validate_membership_proof(
                signature=SIGNATURE,
                expected_pool=POOL,
                proof=forged,
            )

    def test_selected_instruction_scope_and_group_index_are_typed(self):
        forged = _proof()
        forged["selected_pool_instruction_evidence"][0]["scope"] = "inner"
        forged["selected_pool_instruction_evidence"][0]["group_index"] = None
        with self.assertRaisesRegex(
            X1NinjaTradeHistoryPoolMembershipError,
            "group_index",
        ):
            _validate_membership_proof(
                signature=SIGNATURE,
                expected_pool=POOL,
                proof=forged,
            )


if __name__ == "__main__":
    unittest.main()
