import unittest
from decimal import Decimal

from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.providers.x1.transaction_semantics import (
    PoolLegMatch,
    VerificationReport,
)


class DummyMarket:
    def refresh_if_needed(self): pass
    def market_catalog(self): return {"pools": [], "source": "dummy"}


class DummySupply:
    pass


class DummyScanner:
    source = "dummy"
    def scan(self, **kwargs): return {}


def verified_report(*args, **kwargs):
    return VerificationReport(
        signature="sig",
        rpc_url="rpc",
        found=True,
        succeeded=True,
        slot=1,
        block_time=1786632211,
        block_time_iso="2026-08-13T14:43:31+00:00",
        fee_lamports=0,
        primary_signer="signer",
        dex_protocol="XDEX",
        xdex_amm_invoked=True,
        xendex_amm_invoked=False,
        xendex_staking_invoked=False,
        program_ids=["sEsY"],
        token_deltas=[],
        signer_token_deltas=[],
        signer_native_xnt_delta=Decimal("0"),
        signer_native_xnt_delta_before_fee=Decimal("0"),
        inferred_side="BUY",
        inferred_asset_mint="asset",
        inferred_quote_mint="quote",
        inferred_quote_amount=Decimal("1"),
        pool_leg_match=PoolLegMatch(
            side="BUY", owner="pool", asset_mint="asset",
            asset_account="a", asset_amount=Decimal("1"),
            quote_mint="quote", quote_account="q", quote_amount=Decimal("1"),
            amount_match=True, evidence="exact",
        ),
        verification_basis="EXACT_POOL_LEG_AMOUNTS",
        inference_reason="exact",
        expected_side="BUY",
        expected_mint=None,
        expectation_match=True,
        verification_level="PROVIDER_SIDE_ONCHAIN_CONFIRMED",
    )


class TradeAwareGatewayTests(unittest.TestCase):
    def test_dispatches_trade_verification_without_using_market_lookup(self):
        # Bypass EvidenceAware initialization so this unit test stays isolated
        # from DB/RPC defaults; production initialization is covered by existing
        # CMIS runtime tests.
        gateway = object.__new__(TradeAwareCMISGateway)
        gateway.x1_trade_rpc_url = "rpc"
        gateway.x1_trade_verifier = verified_report

        response = gateway.dispatch({
            "service": "trade_verification",
            "chain": "x1",
            "params": {
                "event": {
                    "type": "buy",
                    "txHash": "sig",
                    "poolAddress": "pool",
                    "slot": 1,
                    "timestamp": "2026-08-13T14:43:31.000Z",
                    "amountToken": "1",
                    "amountNative": "1",
                }
            },
        })
        self.assertEqual(response["status"], "ok")
        self.assertTrue(response["data"]["side_verified"])


if __name__ == "__main__":
    unittest.main()
