import unittest

from liquidity_scout.cmis.assets import DEFAULT_ASSET_REGISTRY
from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.cmis.verified_xdex_program_scope_gateway import (
    VerifiedXDEXProgramScopeMixin,
)
from tests.test_cmis_verified_asset_activity_gateway import (
    FakeMarket,
    history_fetcher,
    verified_report,
)


class ScopeTestGateway(VerifiedXDEXProgramScopeMixin, TradeAwareCMISGateway):
    pass


class FakeProgramPoolSetResolver:
    def __init__(self, *, complete=True):
        self.complete = complete
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "service": "verified_program_asset_pool_set",
            "version": "1.5.5",
            "status": (
                "recognized_program_asset_pool_set_structurally_verified"
                if self.complete
                else "partial"
            ),
            "program_id": "xdex-program",
            "account_space": 637,
            "mint_offsets": [168, 200],
            "vault_offsets": [72, 104],
            "pools": [
                {
                    "pool_address": "pool-1",
                    "pair": "AGI/XNT",
                    "mint_0": "quote",
                    "mint_1": "agi-mint",
                    "catalog_listed": True,
                    "pool_state_structural_role_verified": True,
                    "recent_recognized_instruction_coupling_observed": True,
                },
                {
                    "pool_address": "pool-hidden-1",
                    "pair": "USDC.X/AGI",
                    "mint_0": "usdc",
                    "mint_1": "agi-mint",
                    "catalog_listed": False,
                    "pool_state_structural_role_verified": True,
                    "recent_recognized_instruction_coupling_observed": True,
                },
                {
                    "pool_address": "pool-hidden-2",
                    "pair": "AGI/OTHER",
                    "mint_0": "agi-mint",
                    "mint_1": "other",
                    "catalog_listed": False,
                    "pool_state_structural_role_verified": True,
                    "recent_recognized_instruction_coupling_observed": True,
                },
            ],
            "summary": {
                "verified_program_pool_count": 3,
                "catalog_asset_pool_count": 1,
                "noncatalog_verified_program_pool_count": 2,
                "recognized_program_asset_pool_set_structurally_verified": (
                    self.complete
                ),
                "recognized_program_registry_globally_exhaustive": False,
                "global_onchain_pool_discovery_proven": False,
            },
            "errors": [],
        }


class FakeChainWindowEnumerator:
    def __init__(self, *, complete=True):
        self.complete = complete
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "service": "chain_window_dex_activity",
            "version": "1.4",
            "chain": "x1",
            "asset_mint": kwargs["asset_mint"],
            "selected_pool_count": len(kwargs["pools"]),
            "pools": [],
            "summary": {
                "selected_pool_chain_window_complete": self.complete,
                "asset_window_complete": False,
                "asset_window_completion_promoted": False,
                "unique_window_transaction_count": 0,
                "verified_buy_transaction_count": 0,
                "verified_sell_transaction_count": 0,
            },
            "transactions": [],
        }


class VerifiedXDEXProgramScopeGatewayTests(unittest.TestCase):
    def make_gateway(self, *, resolver=None, enumerator=None):
        gateway = object.__new__(ScopeTestGateway)
        gateway.x1_market_provider = FakeMarket()
        gateway.asset_registry = DEFAULT_ASSET_REGISTRY
        gateway.x1_trade_rpc_url = "rpc"
        gateway.x1_trade_verifier = verified_report
        gateway.x1_trade_history_fetcher = history_fetcher
        gateway.x1_activity_now_fn = lambda: 1786633200
        gateway.x1_verified_program_pool_set_resolver = (
            resolver or FakeProgramPoolSetResolver()
        )
        gateway.x1_chain_window_enumerator = (
            enumerator or FakeChainWindowEnumerator()
        )
        return gateway

    def test_scope_uses_verified_program_pool_set_for_chain_window(self):
        resolver = FakeProgramPoolSetResolver()
        enumerator = FakeChainWindowEnumerator()
        gateway = self.make_gateway(resolver=resolver, enumerator=enumerator)

        result = gateway.dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {
                "window": "1h",
                "chain_window": True,
                "verified_xdex_program_scope": True,
                "chain_page_size": 500,
                "chain_max_signatures_per_pool": 750,
            },
        })

        self.assertEqual(len(resolver.calls), 1)
        self.assertEqual(resolver.calls[0]["asset_mint"], "agi-mint")
        self.assertEqual(len(enumerator.calls), 1)
        call = enumerator.calls[0]
        self.assertEqual(
            [row["pool_address"] for row in call["pools"]],
            ["pool-1", "pool-hidden-1", "pool-hidden-2"],
        )
        self.assertEqual(call["page_size"], 500)
        self.assertEqual(call["max_signatures_per_pool"], 750)

        confidence = result["confidence"]
        self.assertTrue(confidence["xdex_program_asset_pool_set_complete"])
        self.assertTrue(confidence["xdex_program_chain_window_complete"])
        self.assertTrue(confidence["xdex_program_asset_window_complete"])
        self.assertFalse(confidence["x1_all_dex_asset_window_complete"])
        self.assertFalse(confidence["chain_window_asset_window_complete"])
        self.assertFalse(confidence["global_onchain_pool_discovery_proven"])

        window = result["data"]["activity_window"]
        self.assertTrue(window["xdex_program_coverage_complete"])
        self.assertEqual(
            window["effective_coverage_scope"],
            "verified_xdex_program",
        )
        self.assertFalse(window["x1_all_dex_asset_window_complete"])

        compact = result["data"]["verified_xdex_program_pool_set"]
        self.assertEqual(compact["program_id"], "xdex-program")
        self.assertEqual(len(compact["pools"]), 3)
        self.assertNotIn("evidence", compact)

        warning_codes = {
            row.get("code")
            for row in result.get("warnings", [])
            if isinstance(row, dict)
        }
        self.assertIn(
            "activity_window_all_x1_dex_scope_not_proven",
            warning_codes,
        )
        self.assertNotIn("activity_window_asset_scope_not_proven", warning_codes)
        self.assertEqual(result["status"], "partial")

    def test_scope_flag_off_preserves_legacy_selected_pool_chain_scan(self):
        resolver = FakeProgramPoolSetResolver()
        enumerator = FakeChainWindowEnumerator()
        gateway = self.make_gateway(resolver=resolver, enumerator=enumerator)

        result = gateway.dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {
                "window": "1h",
                "chain_window": True,
                "verified_xdex_program_scope": False,
            },
        })

        self.assertEqual(resolver.calls, [])
        self.assertEqual(len(enumerator.calls), 1)
        self.assertEqual(
            [row["pool_address"] for row in enumerator.calls[0]["pools"]],
            ["pool-1", "pool-2"],
        )
        self.assertNotIn(
            "xdex_program_asset_window_complete",
            result["confidence"],
        )

    def test_scope_requires_chain_window_true(self):
        result = self.make_gateway().dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {
                "window": "1h",
                "verified_xdex_program_scope": True,
            },
        })

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["errors"][0]["code"],
            "verified_xdex_program_scope_requires_chain_window",
        )

    def test_unverified_program_pool_set_fails_closed_and_keeps_provider_data(self):
        resolver = FakeProgramPoolSetResolver(complete=False)
        enumerator = FakeChainWindowEnumerator()
        gateway = self.make_gateway(resolver=resolver, enumerator=enumerator)

        result = gateway.dispatch({
            "service": "verified_asset_activity",
            "chain": "x1",
            "asset": "AGI",
            "params": {
                "window": "1h",
                "chain_window": True,
                "verified_xdex_program_scope": True,
            },
        })

        self.assertEqual(enumerator.calls, [])
        self.assertEqual(
            result["data"]["window_activity"]["verified_transaction_count"],
            2,
        )
        self.assertFalse(result["confidence"]["xdex_program_asset_window_complete"])
        self.assertFalse(result["confidence"]["x1_all_dex_asset_window_complete"])
        self.assertTrue(any(
            row.get("code") == "verified_xdex_program_scope_unavailable"
            for row in result.get("warnings", [])
            if isinstance(row, dict)
        ))
        self.assertEqual(result["status"], "partial")

    def test_runtime_gateway_composes_verified_scope_mixin(self):
        self.assertTrue(
            issubclass(RuntimeCMISGateway, VerifiedXDEXProgramScopeMixin)
        )


if __name__ == "__main__":
    unittest.main()
