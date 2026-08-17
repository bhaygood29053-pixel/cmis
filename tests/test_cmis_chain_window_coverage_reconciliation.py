import unittest

from liquidity_scout.cmis.assets import DEFAULT_ASSET_REGISTRY
from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from tests.test_cmis_verified_asset_activity_gateway import (
    FakeMarket,
    history_fetcher,
    verified_report,
)
from tests.test_cmis_verified_asset_activity_window_gateway import (
    FakeChainWindowEnumerator,
)


class ChainWindowCoverageReconciliationTests(unittest.TestCase):
    def make_gateway(self):
        gateway = object.__new__(TradeAwareCMISGateway)
        gateway.x1_market_provider = FakeMarket()
        gateway.asset_registry = DEFAULT_ASSET_REGISTRY
        gateway.x1_trade_rpc_url = "rpc"
        gateway.x1_trade_verifier = verified_report
        gateway.x1_trade_history_fetcher = history_fetcher
        gateway.x1_activity_now_fn = lambda: 1786633200
        gateway.x1_chain_window_enumerator = FakeChainWindowEnumerator()
        return gateway

    def test_selected_pool_chain_proof_is_distinct_from_asset_completeness(self):
        result = self.make_gateway().dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {"window": "1h", "chain_window": True},
        })

        confidence = result["confidence"]
        window = result["data"]["activity_window"]

        self.assertFalse(confidence["provider_window_coverage_complete"])
        self.assertTrue(confidence["selected_pool_chain_window_complete"])
        self.assertFalse(confidence["chain_window_asset_window_complete"])

        self.assertFalse(window["provider_coverage_complete"])
        self.assertTrue(window["selected_pool_chain_coverage_complete"])
        self.assertEqual(
            window["selected_pool_chain_coverage_basis"],
            "X1_RPC_ADDRESS_HISTORY",
        )
        self.assertFalse(window["asset_window_complete"])
        self.assertEqual(window["effective_coverage_scope"], "selected_pools")

        warning_codes = {
            item.get("code")
            for item in result["warnings"]
            if isinstance(item, dict)
        }
        self.assertNotIn("activity_window_range_not_proven", warning_codes)
        self.assertIn("activity_window_asset_scope_not_proven", warning_codes)

        asset_scope_warning = next(
            item
            for item in result["warnings"]
            if isinstance(item, dict)
            and item.get("code") == "activity_window_asset_scope_not_proven"
        )
        self.assertIn("selected pool", asset_scope_warning["message"].lower())
        self.assertIn("global", asset_scope_warning["message"].lower())

        # Backward-compatible provider-derived aggregate remains fail-closed.
        self.assertFalse(confidence["window_coverage_complete"])
        self.assertEqual(result["status"], "partial")


if __name__ == "__main__":
    unittest.main()
