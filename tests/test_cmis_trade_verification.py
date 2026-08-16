import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.transaction_semantics import (
    VerificationReport,
    PoolLegMatch,
)
from liquidity_scout.services.cmis_trade_verification import (
    build_x1_trade_verification_response,
)


SIG = "F4HMz4Y6BHRvj5ZgSbzaAiQD9KomEiEghcUH797RZ5ALVqhWooKrQzQgXzx3brTbYDWV5T2dwyxrhC56k5bnxsP"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
ASSET = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
WXNT = "So11111111111111111111111111111111111111112"


def row(side="buy"):
    return {
        "type": side,
        "txHash": SIG,
        "poolAddress": POOL,
        "slot": 71338200,
        "timestamp": "2026-08-13T14:43:31.000Z",
        "amountToken": "6561.5290459999815",
        "amountNative": "0.28000000000000114",
    }


def report(level="PROVIDER_SIDE_ONCHAIN_CONFIRMED", side="BUY", match=True):
    leg = PoolLegMatch(
        side=side,
        owner="PoolOwner",
        asset_mint=ASSET,
        asset_account="AssetVault",
        asset_amount=Decimal("6561.529046"),
        quote_mint=WXNT,
        quote_account="QuoteVault",
        quote_amount=Decimal("0.28"),
        amount_match=True,
        evidence="exact leg",
    )
    return VerificationReport(
        signature=SIG,
        rpc_url="rpc",
        found=True,
        succeeded=True,
        slot=71338200,
        block_time=1786632211,
        block_time_iso="2026-08-13T14:43:31+00:00",
        fee_lamports=1,
        primary_signer="Signer",
        dex_protocol="XDEX",
        xdex_amm_invoked=True,
        xendex_amm_invoked=False,
        xendex_staking_invoked=False,
        program_ids=["sEsY"],
        token_deltas=[],
        signer_token_deltas=[],
        signer_native_xnt_delta=Decimal("-0.28"),
        signer_native_xnt_delta_before_fee=Decimal("-0.28"),
        inferred_side=side,
        inferred_asset_mint=ASSET,
        inferred_quote_mint=WXNT,
        inferred_quote_amount=Decimal("0.28"),
        pool_leg_match=leg,
        verification_basis="EXACT_POOL_LEG_AMOUNTS",
        inference_reason="exact",
        expected_side="BUY",
        expected_mint=None,
        expectation_match=match,
        verification_level=level,
    )


class CMISTradeVerificationTests(unittest.TestCase):
    def test_confirmed_trade_is_ok_and_verified(self):
        response = build_x1_trade_verification_response(
            row(),
            verifier=lambda *args, **kwargs: report(),
        )
        self.assertEqual(response["status"], "ok")
        self.assertTrue(response["data"]["side_verified"])
        self.assertEqual(response["data"]["side"], "BUY")
        self.assertEqual(response["confidence"]["level"], "on_chain_verified")
        self.assertTrue(response["data"]["identity"]["identity_verified"])

    def test_direction_conflict_is_ambiguous(self):
        response = build_x1_trade_verification_response(
            row(),
            verifier=lambda *args, **kwargs: report(
                level="PROVIDER_ONCHAIN_DIRECTION_MISMATCH",
                side="SELL",
                match=False,
            ),
        )
        self.assertEqual(response["status"], "ambiguous")
        self.assertFalse(response["data"]["side_verified"])

    def test_lp_event_stays_gated(self):
        event = row()
        event["type"] = "remove_liquidity"
        response = build_x1_trade_verification_response(
            event,
            verifier=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("verifier must not run")
            ),
        )
        self.assertEqual(response["status"], "partial")
        self.assertEqual(
            response["data"]["verification_level"],
            "PROVIDER_EVENT_SEMANTICS_GATED",
        )

    def test_timestamp_mismatch_prevents_full_promotion(self):
        event = row()
        event["timestamp"] = "2026-08-13T14:45:00.000Z"
        response = build_x1_trade_verification_response(
            event,
            verifier=lambda *args, **kwargs: report(),
        )
        self.assertEqual(response["status"], "partial")
        self.assertFalse(response["data"]["side_verified"])

    def test_rpc_failure_preserves_provider_as_unverified(self):
        response = build_x1_trade_verification_response(
            row(),
            verifier=lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("rpc unavailable")
            ),
        )
        self.assertEqual(response["status"], "partial")
        self.assertFalse(response["data"]["side_verified"])
        self.assertEqual(
            response["data"]["verification_level"],
            "CHAIN_VERIFICATION_UNAVAILABLE",
        )


if __name__ == "__main__":
    unittest.main()
