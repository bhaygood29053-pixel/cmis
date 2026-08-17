import unittest

from liquidity_scout.cmis.assets import DEFAULT_ASSET_REGISTRY
from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from tests.test_cmis_verified_asset_activity_gateway import (
    FakeMarket,
    history_fetcher,
    verified_report,
)


class FakeChainWindowEnumerator:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.fail:
            raise RuntimeError("chain scan unavailable")
        return {
            "service": "chain_window_dex_activity",
            "version": "1.4",
            "chain": "x1",
            "asset_mint": kwargs["asset_mint"],
            "requested_window": {
                "start_epoch": kwargs["start_epoch"],
                "end_epoch": kwargs["end_epoch"],
                "membership_basis": "X1_RPC_BLOCK_TIME",
            },
            "selected_pool_count": len(kwargs["pools"]),
            "pools": [],
            "summary": {
                "selected_pool_chain_window_complete": True,
                "asset_window_complete": False,
                "asset_window_completion_promoted": False,
                "unique_window_transaction_count": 0,
                "verified_buy_transaction_count": 0,
                "verified_sell_transaction_count": 0,
            },
            "transactions": [],
        }


class VerifiedAssetActivityWindowGatewayTests(unittest.TestCase):
    def make_gateway(self):
        gateway = object.__new__(TradeAwareCMISGateway)
        gateway.x1_market_provider = FakeMarket()
        gateway.asset_registry = DEFAULT_ASSET_REGISTRY
        gateway.x1_trade_rpc_url = "rpc"
        gateway.x1_trade_verifier = verified_report
        gateway.x1_trade_history_fetcher = history_fetcher
        # 2026-08-13T15:00:00Z: both fake 14:43:31Z trades are in 1h.
        gateway.x1_activity_now_fn = lambda: 1786633200
        return gateway

    def test_window_request_filters_by_verified_chain_time(self):
        result = self.make_gateway().dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {"max_pools": 5, "window": "1h"},
        })

        self.assertEqual(result["data"]["activity_window"]["label"], "1h")
        self.assertEqual(
            result["data"]["activity_window"][
                "processed_event_count_in_window"
            ],
            2,
        )
        self.assertEqual(
            result["data"]["window_activity"][
                "verified_transaction_count"
            ],
            2,
        )
        # Existing fake transport does not claim pagination/range semantics.
        self.assertFalse(
            result["confidence"]["window_coverage_complete"]
        )
        self.assertNotIn(
            "chain_window_dex_activity",
            result["data"],
        )
        self.assertEqual(result["status"], "partial")

    def test_chain_window_opt_in_attaches_selected_pool_chain_proof(self):
        gateway = self.make_gateway()
        enumerator = FakeChainWindowEnumerator()
        gateway.x1_chain_window_enumerator = enumerator

        result = gateway.dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {
                "max_pools": 5,
                "window": "1h",
                "chain_window": True,
                "chain_page_size": 500,
                "chain_max_signatures_per_pool": 750,
            },
        })

        self.assertEqual(len(enumerator.calls), 1)
        call = enumerator.calls[0]
        self.assertEqual(call["asset_mint"], "agi-mint")
        self.assertEqual(call["start_epoch"], 1786629600)
        self.assertEqual(call["end_epoch"], 1786633200)
        self.assertEqual(call["rpc_url"], "rpc")
        self.assertEqual(call["page_size"], 500)
        self.assertEqual(call["max_signatures_per_pool"], 750)
        self.assertEqual(
            [item["pool_address"] for item in call["pools"]],
            ["pool-1", "pool-2"],
        )

        chain = result["data"]["chain_window_dex_activity"]
        self.assertEqual(chain["service"], "chain_window_dex_activity")
        self.assertTrue(
            result["confidence"]["selected_pool_chain_window_complete"]
        )
        self.assertTrue(
            result["confidence"]["selected_pool_chain_window_empty"]
        )
        self.assertEqual(
            result["confidence"]["chain_window_unique_transaction_count"],
            0,
        )
        # Selected pool ranges are stronger evidence, but the gateway must not
        # convert them into a globally exhaustive asset-window claim.
        self.assertFalse(
            result["confidence"]["chain_window_asset_window_complete"]
        )
        self.assertFalse(
            result["confidence"]["chain_window_asset_completion_promoted"]
        )
        self.assertFalse(result["confidence"]["window_coverage_complete"])

    def test_chain_window_failure_fails_closed_without_losing_provider_activity(self):
        gateway = self.make_gateway()
        gateway.x1_chain_window_enumerator = FakeChainWindowEnumerator(fail=True)

        result = gateway.dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {"window": "1h", "chain_window": True},
        })

        self.assertEqual(
            result["data"]["window_activity"]["verified_transaction_count"],
            2,
        )
        self.assertFalse(
            result["confidence"]["selected_pool_chain_window_complete"]
        )
        self.assertTrue(any(
            item.get("code") == "chain_window_enumeration_unavailable"
            for item in result["warnings"]
        ))
        self.assertEqual(result["status"], "partial")

    def test_chain_window_requires_supported_window(self):
        result = self.make_gateway().dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {"chain_window": True},
        })
        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["errors"][0]["code"],
            "chain_window_requires_window",
        )

    def test_invalid_chain_window_flag_is_rejected(self):
        result = self.make_gateway().dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {"window": "1h", "chain_window": "yes"},
        })
        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["errors"][0]["code"],
            "invalid_activity_bound",
        )

    def test_invalid_window_is_rejected(self):
        result = self.make_gateway().dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {"window": "2h"},
        })
        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["errors"][0]["code"],
            "invalid_activity_window",
        )


if __name__ == "__main__":
    unittest.main()
