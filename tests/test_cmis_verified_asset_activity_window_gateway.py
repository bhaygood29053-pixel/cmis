import unittest

from liquidity_scout.cmis.assets import DEFAULT_ASSET_REGISTRY
from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from tests.test_cmis_verified_asset_activity_gateway import (
    FakeMarket,
    history_fetcher,
    verified_report,
)


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
        self.assertEqual(result["status"], "partial")

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
