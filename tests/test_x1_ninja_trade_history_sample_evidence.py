from decimal import Decimal
import unittest

from liquidity_scout.providers.x1.ninja_history import X1_NINJA_SOURCE
from liquidity_scout.providers.x1.ninja_trade_history_sample_evidence import (
    X1NinjaTradeHistorySampleEvidenceError,
    verify_ninja_trade_history_sample,
)
from liquidity_scout.providers.x1.transaction_semantics import VerificationReport


POOL = "Pool11111111111111111111111111111111111111"
OTHER_POOL = "Pool22222222222222222222222222222222222222"
WALLET = "Wallet1111111111111111111111111111111111111"
MINT = "Mint11111111111111111111111111111111111111"
QUOTE = "Quote1111111111111111111111111111111111111"


def _row(signature: str, slot: int, *, side: str = "BUY", pool: str = POOL):
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
        "type": side,
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


def _report(
    signature: str,
    slot: int,
    *,
    side: str = "BUY",
    maker: str = WALLET,
    verification_basis: str = "SIGNER_OR_ROUTED_BALANCE_DIRECTION",
    verification_level: str = "PROVIDER_SIDE_ONCHAIN_CONFIRMED",
    found: bool = True,
    succeeded: bool = True,
):
    return VerificationReport(
        signature=signature,
        rpc_url="https://rpc.mainnet.x1.xyz",
        found=found,
        succeeded=succeeded,
        slot=slot,
        block_time=1787073600 + slot,
        block_time_iso="2026-08-18T12:00:00+00:00",
        fee_lamports=5000,
        primary_signer=maker,
        dex_protocol="XDEX",
        xdex_amm_invoked=True,
        xendex_amm_invoked=False,
        xendex_staking_invoked=False,
        program_ids=["recognized-xdex-program"],
        token_deltas=[],
        signer_token_deltas=[],
        signer_native_xnt_delta=Decimal("0"),
        signer_native_xnt_delta_before_fee=Decimal("0"),
        inferred_side=side,
        inferred_asset_mint=MINT,
        inferred_quote_mint=QUOTE,
        inferred_quote_amount=Decimal("1"),
        pool_leg_match=None,
        verification_basis=verification_basis,
        inference_reason="deterministic test evidence",
        expected_side=side,
        expected_mint=MINT,
        expectation_match=True,
        verification_level=verification_level,
    )


class X1NinjaTradeHistorySampleEvidenceTests(unittest.TestCase):
    def test_binds_transaction_identity_and_observes_newest_first_order(self):
        rows = [_row("sig-2", 200), _row("sig-1", 199, side="SELL")]
        result = verify_ninja_trade_history_sample(
            observation=_observation(rows),
            verification_reports={
                "sig-2": _report("sig-2", 200),
                "sig-1": _report("sig-1", 199, side="SELL"),
            },
            pool_address=POOL,
            pool_identity_verified=True,
        )

        self.assertTrue(result["sample_transaction_identity_binding_complete"])
        self.assertTrue(result["sample_row_pool_identity_match_complete"])
        self.assertFalse(result["sample_transaction_pool_membership_verified"])
        self.assertTrue(result["sample_maker_primary_signer_match_complete"])
        self.assertTrue(result["sample_provider_slot_rpc_match_complete"])
        self.assertTrue(result["sample_wallet_side_rpc_match_complete"])
        self.assertEqual(
            result["returned_order_observation"],
            "newest_to_oldest_by_verified_rpc_slot_observed",
        )
        self.assertFalse(
            result["semantics"]["transaction_pool_membership_verified"]
        )
        self.assertFalse(result["semantics"]["rpc_source_independence_verified"])
        self.assertFalse(result["semantics"]["ordering_contract_verified"])
        self.assertFalse(result["semantics"]["pagination_or_range_verified"])
        self.assertFalse(result["semantics"]["history_exhaustive_verified"])
        self.assertFalse(result["semantics"]["retention_verified"])
        self.assertFalse(result["semantics"]["finality_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertNotIn("amountNative", result["rows"][0])
        self.assertNotIn("priceUsd", result["rows"][0])
        self.assertNotIn("timestamp", result["rows"][0])

    def test_reversed_rpc_slots_are_observed_but_not_promoted(self):
        rows = [_row("sig-old", 199), _row("sig-new", 200)]
        result = verify_ninja_trade_history_sample(
            observation=_observation(rows),
            verification_reports={
                "sig-old": _report("sig-old", 199),
                "sig-new": _report("sig-new", 200),
            },
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertTrue(result["sample_transaction_identity_binding_complete"])
        self.assertEqual(
            result["returned_order_observation"],
            "not_newest_to_oldest_by_verified_rpc_slot_observed",
        )
        self.assertFalse(result["semantics"]["ordering_contract_verified"])

    def test_missing_rpc_report_keeps_transaction_identity_incomplete(self):
        rows = [_row("sig-2", 200), _row("sig-1", 199)]
        result = verify_ninja_trade_history_sample(
            observation=_observation(rows),
            verification_reports={"sig-2": _report("sig-2", 200)},
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertFalse(result["sample_rpc_report_binding_complete"])
        self.assertFalse(result["sample_transaction_identity_binding_complete"])
        self.assertEqual(result["returned_order_observation"], "unavailable")
        self.assertFalse(result["cmis_promotable"])

    def test_row_pool_mismatch_does_not_change_transaction_identity_binding(self):
        rows = [_row("sig-1", 200, pool=OTHER_POOL)]
        result = verify_ninja_trade_history_sample(
            observation=_observation(rows),
            verification_reports={"sig-1": _report("sig-1", 200)},
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertTrue(result["sample_transaction_identity_binding_complete"])
        self.assertFalse(result["sample_row_pool_identity_match_complete"])
        self.assertFalse(result["sample_transaction_pool_membership_verified"])
        self.assertFalse(result["semantics"]["sample_row_pool_identity_crosscheck"])
        self.assertFalse(
            result["semantics"]["transaction_pool_membership_verified"]
        )
        self.assertIn(
            "provider_row_pool_does_not_match_verified_pool_for_every_row",
            result["warnings"],
        )

    def test_exact_pool_leg_side_does_not_become_wallet_level_side_evidence(self):
        rows = [_row("sig-1", 200)]
        result = verify_ninja_trade_history_sample(
            observation=_observation(rows),
            verification_reports={
                "sig-1": _report(
                    "sig-1",
                    200,
                    verification_basis="EXACT_POOL_LEG_AMOUNTS",
                )
            },
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertTrue(result["sample_transaction_identity_binding_complete"])
        self.assertFalse(result["sample_wallet_side_rpc_match_complete"])
        self.assertFalse(result["semantics"]["sample_provider_side_crosscheck"])
        self.assertIn(
            "provider_side_not_confirmed_for_every_sampled_row",
            result["warnings"],
        )

    def test_provider_side_case_is_not_normalized(self):
        rows = [_row("sig-1", 200, side="buy")]
        result = verify_ninja_trade_history_sample(
            observation=_observation(rows),
            verification_reports={"sig-1": _report("sig-1", 200, side="BUY")},
            pool_address=POOL,
            pool_identity_verified=True,
        )
        self.assertTrue(result["sample_transaction_identity_binding_complete"])
        self.assertFalse(result["sample_wallet_side_rpc_match_complete"])
        self.assertFalse(result["semantics"]["sample_provider_side_crosscheck"])

    def test_local_bound_samples_only_returned_prefix(self):
        rows = [
            _row("sig-3", 203),
            _row("sig-2", 202),
            _row("sig-1", 201),
        ]
        result = verify_ninja_trade_history_sample(
            observation=_observation(rows),
            verification_reports={
                "sig-3": _report("sig-3", 203),
                "sig-2": _report("sig-2", 202),
            },
            pool_address=POOL,
            pool_identity_verified=True,
            max_rows=2,
        )
        self.assertEqual(result["returned_row_count"], 3)
        self.assertEqual(result["sample_size"], 2)
        self.assertTrue(result["sample_is_returned_prefix"])
        self.assertTrue(result["sample_truncated_by_local_verifier"])
        self.assertTrue(result["sample_transaction_identity_binding_complete"])
        self.assertEqual(
            [row["transaction_id"] for row in result["rows"]],
            ["sig-3", "sig-2"],
        )
        self.assertIn("local_verifier_sample_truncated", result["warnings"])
        self.assertFalse(result["semantics"]["pagination_or_range_verified"])

    def test_duplicate_txhash_fails_closed(self):
        rows = [_row("sig-1", 200), _row("sig-1", 199)]
        with self.assertRaisesRegex(
            X1NinjaTradeHistorySampleEvidenceError,
            "duplicate X1.Ninja txHash",
        ):
            verify_ninja_trade_history_sample(
                observation=_observation(rows),
                verification_reports={"sig-1": _report("sig-1", 200)},
                pool_address=POOL,
                pool_identity_verified=True,
            )

    def test_unverified_pool_identity_fails_closed(self):
        with self.assertRaisesRegex(
            X1NinjaTradeHistorySampleEvidenceError,
            "pool_identity_verified must be verified",
        ):
            verify_ninja_trade_history_sample(
                observation=_observation([_row("sig-1", 200)]),
                verification_reports={"sig-1": _report("sig-1", 200)},
                pool_address=POOL,
                pool_identity_verified=False,
            )

    def test_input_cannot_claim_pagination_is_already_verified(self):
        observation = _observation([_row("sig-1", 200)])
        observation["semantics"]["pagination_or_range_verified"] = True
        with self.assertRaisesRegex(
            X1NinjaTradeHistorySampleEvidenceError,
            "pagination_or_range_verified must remain explicitly unverified",
        ):
            verify_ninja_trade_history_sample(
                observation=observation,
                verification_reports={"sig-1": _report("sig-1", 200)},
                pool_address=POOL,
                pool_identity_verified=True,
            )

    def test_contract_count_must_match_raw_rows(self):
        observation = _observation([_row("sig-1", 200)])
        observation["contract"]["returned_trade_count"] = 2
        with self.assertRaisesRegex(
            X1NinjaTradeHistorySampleEvidenceError,
            "returned_trade_count must exactly match",
        ):
            verify_ninja_trade_history_sample(
                observation=observation,
                verification_reports={"sig-1": _report("sig-1", 200)},
                pool_address=POOL,
                pool_identity_verified=True,
            )


if __name__ == "__main__":
    unittest.main()
