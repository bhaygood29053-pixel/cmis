from decimal import Decimal
import unittest

from liquidity_scout.providers.x1.ninja_history import X1_NINJA_SOURCE
from liquidity_scout.providers.x1.ninja_trade_history_pool_membership import (
    X1NinjaTradeHistoryPoolMembershipError,
    verify_ninja_trade_history_pool_membership,
)
from liquidity_scout.providers.x1.transaction_semantics import VerificationReport


POOL = "Pool11111111111111111111111111111111111111"
OTHER_POOL = "Pool22222222222222222222222222222222222222"
WALLET = "Wallet1111111111111111111111111111111111111"
MINT = "Mint11111111111111111111111111111111111111"
QUOTE = "Quote1111111111111111111111111111111111111"


def _row(signature: str, slot: int, *, pool: str = POOL):
    return {
        "amountNative": "1.25",
        "amountToken": "100",
        "amountUsd": "9.99",
        "id": f"row-{signature}",
        "maker": WALLET,
        "poolAddress": pool,
        "priceNative": "0.0125",
        "priceUsd": "0.0999",
        "slot": slot,
        "timestamp": 1787073600 + slot,
        "txHash": signature,
        "type": "BUY",
    }


def _observation(rows):
    return {
        "chain": "x1",
        "source": X1_NINJA_SOURCE,
        "pool_address": POOL,
        "raw_response": {
            "lastUpdated": 1787079999,
            "total": len(rows),
            "trades": rows,
        },
        "contract": {
            "response_contract_verified": True,
            "trade_row_shape_verified": True,
            "returned_trade_count": len(rows),
        },
        "semantics": {
            "trade_rows_verified": True,
            "side_classification_verified": False,
            "token_amount_units_verified": False,
            "usd_value_source_verified": False,
            "lp_event_semantics_verified": False,
            "transaction_signature_verified": False,
            "finality_verified": False,
            "pagination_or_range_verified": False,
        },
        "cmis_promotable": False,
    }


def _report(signature: str, slot: int):
    return VerificationReport(
        signature=signature,
        rpc_url="https://rpc.mainnet.x1.xyz",
        found=True,
        succeeded=True,
        slot=slot,
        block_time=1787073600 + slot,
        block_time_iso="2026-08-18T12:00:00+00:00",
        fee_lamports=5000,
        primary_signer=WALLET,
        dex_protocol="XDEX",
        xdex_amm_invoked=True,
        xendex_amm_invoked=False,
        xendex_staking_invoked=False,
        program_ids=["recognized-xdex-program"],
        token_deltas=[],
        signer_token_deltas=[],
        signer_native_xnt_delta=Decimal("0"),
        signer_native_xnt_delta_before_fee=Decimal("0"),
        inferred_side="BUY",
        inferred_asset_mint=MINT,
        inferred_quote_mint=QUOTE,
        inferred_quote_amount=Decimal("1"),
        pool_leg_match=None,
        verification_basis="SIGNER_OR_ROUTED_BALANCE_DIRECTION",
        inference_reason="deterministic test evidence",
        expected_side="BUY",
        expected_mint=MINT,
        expectation_match=True,
        verification_level="PROVIDER_SIDE_ONCHAIN_CONFIRMED",
    )


def _proof(
    signature: str,
    *,
    pool: str = POOL,
    verified: bool = True,
    rejection_reasons=None,
):
    if rejection_reasons is None:
        rejection_reasons = [] if verified else ["selected_pool_not_verified"]
    return {
        "contract_version": "x1_transaction_pool_membership/v3",
        "chain": "x1",
        "transaction_signature": signature,
        "transaction_instruction_evidence_bound": True,
        "pool_address": pool,
        "asset_mint": MINT,
        "asset_vault": "AssetVault111111111111111111111111111111111",
        "counter_mint": QUOTE,
        "counter_vault": "QuoteVault111111111111111111111111111111111",
        "shared_owner": "PoolAuthority1111111111111111111111111111111",
        "transaction_found": True,
        "transaction_succeeded": True,
        "recognized_amm_invoked": True,
        "recognized_amm_instruction_count": 1,
        "selected_pool_instruction_verified": verified,
        "selected_pool_instruction_count": 1 if verified else 0,
        "selected_pool_instruction_evidence": [],
        "asset_vault_mutated": verified,
        "counter_vault_mutated": verified,
        "vault_authority_verified": verified,
        "transaction_pool_membership_verified": verified,
        "provider_row_pool_claim_verified": None,
        "source_independence_verified": None,
        "history_completeness_verified": None,
        "finality_semantics_verified": None,
        "amount_semantics_verified": None,
        "price_semantics_verified": None,
        "cmis_promotable": False,
        "rejection_reasons": rejection_reasons,
    }


class X1NinjaTradeHistoryPoolMembershipTests(unittest.TestCase):
    def test_every_sampled_row_can_be_bound_to_exact_pool_membership(self):
        rows = [_row("sig-2", 200), _row("sig-1", 199)]
        result = verify_ninja_trade_history_pool_membership(
            observation=_observation(rows),
            verification_reports={
                "sig-2": _report("sig-2", 200),
                "sig-1": _report("sig-1", 199),
            },
            transaction_pool_membership_evidence={
                "sig-2": _proof("sig-2"),
                "sig-1": _proof("sig-1"),
            },
            pool_address=POOL,
            pool_identity_verified=True,
        )

        self.assertTrue(result["sample_transaction_pool_membership_verified"])
        self.assertTrue(result["sample_provider_row_pool_claim_onchain_verified"])
        self.assertTrue(result["semantics"]["transaction_pool_membership_verified"])
        self.assertTrue(
            result["semantics"]["provider_row_pool_claim_onchain_verified"]
        )
        self.assertTrue(result["rows"][0]["transaction_pool_membership_verified"])
        self.assertTrue(result["rows"][0]["provider_row_pool_claim_onchain_verified"])
        self.assertNotIn(
            "transaction_pool_membership_not_verified_for_every_sampled_row",
            result["warnings"],
        )
        self.assertFalse(result["semantics"]["history_exhaustive_verified"])
        self.assertFalse(result["semantics"]["finality_verified"])
        self.assertFalse(result["semantics"]["amount_price_units_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_missing_membership_proof_fails_closed_for_sample(self):
        rows = [_row("sig-2", 200), _row("sig-1", 199)]
        result = verify_ninja_trade_history_pool_membership(
            observation=_observation(rows),
            verification_reports={
                "sig-2": _report("sig-2", 200),
                "sig-1": _report("sig-1", 199),
            },
            transaction_pool_membership_evidence={"sig-2": _proof("sig-2")},
            pool_address=POOL,
            pool_identity_verified=True,
        )

        self.assertFalse(result["sample_transaction_pool_membership_verified"])
        self.assertFalse(result["sample_provider_row_pool_claim_onchain_verified"])
        self.assertFalse(result["rows"][1]["transaction_pool_membership_evidence_present"])
        self.assertIn(
            "transaction_pool_membership_not_verified_for_every_sampled_row",
            result["warnings"],
        )

    def test_valid_negative_membership_proof_is_preserved_as_false(self):
        rows = [_row("sig-1", 200)]
        result = verify_ninja_trade_history_pool_membership(
            observation=_observation(rows),
            verification_reports={"sig-1": _report("sig-1", 200)},
            transaction_pool_membership_evidence={
                "sig-1": _proof("sig-1", verified=False)
            },
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertFalse(result["sample_transaction_pool_membership_verified"])
        self.assertFalse(result["rows"][0]["transaction_pool_membership_verified"])
        self.assertFalse(result["rows"][0]["provider_row_pool_claim_onchain_verified"])

    def test_membership_proof_signature_must_match_sampled_txhash(self):
        rows = [_row("sig-1", 200)]
        bad = _proof("different-signature")
        with self.assertRaisesRegex(
            X1NinjaTradeHistoryPoolMembershipError,
            "signature does not match sampled txHash",
        ):
            verify_ninja_trade_history_pool_membership(
                observation=_observation(rows),
                verification_reports={"sig-1": _report("sig-1", 200)},
                transaction_pool_membership_evidence={"sig-1": bad},
                pool_address=POOL,
                pool_identity_verified=True,
            )

    def test_membership_proof_pool_must_match_selected_verified_pool(self):
        rows = [_row("sig-1", 200)]
        with self.assertRaisesRegex(
            X1NinjaTradeHistoryPoolMembershipError,
            "pool does not match selected verified pool",
        ):
            verify_ninja_trade_history_pool_membership(
                observation=_observation(rows),
                verification_reports={"sig-1": _report("sig-1", 200)},
                transaction_pool_membership_evidence={
                    "sig-1": _proof("sig-1", pool=OTHER_POOL)
                },
                pool_address=POOL,
                pool_identity_verified=True,
            )

    def test_forged_positive_membership_cannot_hide_rejection_reason(self):
        rows = [_row("sig-1", 200)]
        forged = _proof(
            "sig-1",
            verified=True,
            rejection_reasons=["asset_vault_owner_mismatch"],
        )
        with self.assertRaisesRegex(
            X1NinjaTradeHistoryPoolMembershipError,
            "verification flag disagrees with rejection reasons",
        ):
            verify_ninja_trade_history_pool_membership(
                observation=_observation(rows),
                verification_reports={"sig-1": _report("sig-1", 200)},
                transaction_pool_membership_evidence={"sig-1": forged},
                pool_address=POOL,
                pool_identity_verified=True,
            )

    def test_forged_positive_membership_requires_structural_evidence(self):
        rows = [_row("sig-1", 200)]
        forged = _proof("sig-1")
        forged["vault_authority_verified"] = False
        with self.assertRaisesRegex(
            X1NinjaTradeHistoryPoolMembershipError,
            "missing required structural evidence",
        ):
            verify_ninja_trade_history_pool_membership(
                observation=_observation(rows),
                verification_reports={"sig-1": _report("sig-1", 200)},
                transaction_pool_membership_evidence={"sig-1": forged},
                pool_address=POOL,
                pool_identity_verified=True,
            )

    def test_only_v3_membership_contract_is_accepted(self):
        rows = [_row("sig-1", 200)]
        bad = _proof("sig-1")
        bad["contract_version"] = "x1_transaction_pool_membership/v2"
        with self.assertRaisesRegex(
            X1NinjaTradeHistoryPoolMembershipError,
            "contract version is unsupported",
        ):
            verify_ninja_trade_history_pool_membership(
                observation=_observation(rows),
                verification_reports={"sig-1": _report("sig-1", 200)},
                transaction_pool_membership_evidence={"sig-1": bad},
                pool_address=POOL,
                pool_identity_verified=True,
            )

    def test_membership_proof_cannot_smuggle_unrelated_verified_claims(self):
        rows = [_row("sig-1", 200)]
        bad = _proof("sig-1")
        bad["history_completeness_verified"] = True
        with self.assertRaisesRegex(
            X1NinjaTradeHistoryPoolMembershipError,
            "history_completeness_verified must remain unproven",
        ):
            verify_ninja_trade_history_pool_membership(
                observation=_observation(rows),
                verification_reports={"sig-1": _report("sig-1", 200)},
                transaction_pool_membership_evidence={"sig-1": bad},
                pool_address=POOL,
                pool_identity_verified=True,
            )

    def test_row_pool_label_mismatch_cannot_be_rescued_by_membership_proof(self):
        rows = [_row("sig-1", 200, pool=OTHER_POOL)]
        result = verify_ninja_trade_history_pool_membership(
            observation=_observation(rows),
            verification_reports={"sig-1": _report("sig-1", 200)},
            transaction_pool_membership_evidence={"sig-1": _proof("sig-1")},
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertTrue(result["sample_transaction_pool_membership_verified"])
        self.assertFalse(result["sample_provider_row_pool_claim_onchain_verified"])
        self.assertFalse(result["rows"][0]["provider_row_pool_claim_onchain_verified"])


if __name__ == "__main__":
    unittest.main()
