import unittest
from decimal import Decimal

from liquidity_scout.cmis.assets import DEFAULT_ASSET_REGISTRY
from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.providers.x1.transaction_semantics import (
    PoolLegMatch,
    VerificationReport,
)


def pool(address, liquidity):
    return {
        "address": address,
        "baseToken": {
            "symbol": "AGI",
            "name": "AGI",
            "mint": "agi-mint",
        },
        "quoteToken": {
            "symbol": "XNT",
            "name": "XNT",
            "mint": "So11111111111111111111111111111111111111112",
        },
        "liquidity": liquidity,
        "volume24h": 100,
        "txns24h": 5,
        "holders": 100,
        "priceUsd": 1,
    }


class FakeMarket:
    def __init__(self):
        self.pools = [pool("pool-1", 1000), pool("pool-2", 500)]
        self.xnt_price_usd = 1
        self.last_refresh = 123.0

    def refresh_if_needed(self):
        return self

    def market_catalog(self):
        return {
            "chain": "x1",
            "source": "provider",
            "pools": list(self.pools),
            "xnt_price_usd": self.xnt_price_usd,
            "observed_at": self.last_refresh,
        }


def history_fetcher(address):
    side = "buy" if address == "pool-1" else "sell"
    rows = [{
        "amountNative": "1",
        "amountToken": "2",
        "amountUsd": "3",
        "id": "id-" + address,
        "maker": "maker",
        "poolAddress": address,
        "priceNative": "0.5",
        "priceUsd": "1.5",
        "slot": 1,
        "timestamp": "2026-08-13T14:43:31.000Z",
        "txHash": "sig-" + address,
        "type": side,
    }]
    return {
        "chain": "x1",
        "source": "provider",
        "pool_address": address,
        "observed_at": 124.0,
        "raw_response": {
            "lastUpdated": "now",
            "total": len(rows),
            "trades": rows,
        },
    }


def verified_report(signature, **kwargs):
    side = kwargs["expected_side"]
    return VerificationReport(
        signature=signature,
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
        inferred_side=side,
        inferred_asset_mint="agi-mint",
        inferred_quote_mint="quote",
        inferred_quote_amount=Decimal("1"),
        pool_leg_match=PoolLegMatch(
            side=side,
            owner="pool",
            asset_mint="agi-mint",
            asset_account="asset-account",
            asset_amount=Decimal("2"),
            quote_mint="quote",
            quote_account="quote-account",
            quote_amount=Decimal("1"),
            amount_match=True,
            evidence="exact",
        ),
        verification_basis="EXACT_POOL_LEG_AMOUNTS",
        inference_reason="exact",
        expected_side=side,
        expected_mint=None,
        expectation_match=True,
        verification_level="PROVIDER_SIDE_ONCHAIN_CONFIRMED",
    )


class VerifiedAssetActivityGatewayTests(unittest.TestCase):
    def make_gateway(self):
        gateway = object.__new__(TradeAwareCMISGateway)
        gateway.x1_market_provider = FakeMarket()
        gateway.asset_registry = DEFAULT_ASSET_REGISTRY
        gateway.x1_trade_rpc_url = "rpc"
        gateway.x1_trade_verifier = verified_report
        gateway.x1_trade_history_fetcher = history_fetcher
        return gateway

    def test_asset_request_discovers_all_pools_and_verifies_activity(self):
        result = self.make_gateway().dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {"max_pools": 5, "per_pool_limit": 5},
        })

        self.assertEqual(result["service"], "verified_asset_activity")
        self.assertEqual(result["asset"]["mint"], "agi-mint")
        self.assertEqual(result["data"]["matched_pool_count"], 2)
        self.assertEqual(result["data"]["verified_trade_count"], 2)
        self.assertEqual(result["data"]["verified_buy_count"], 1)
        self.assertEqual(result["data"]["verified_sell_count"], 1)
        self.assertEqual(result["status"], "ok")

    def test_pool_bound_is_explicit_partial_coverage(self):
        result = self.make_gateway().dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {"max_pools": 1, "per_pool_limit": 5},
        })
        self.assertEqual(result["data"]["matched_pool_count"], 2)
        self.assertEqual(result["data"]["selected_pool_count"], 1)
        self.assertEqual(result["status"], "partial")


if __name__ == "__main__":
    unittest.main()
