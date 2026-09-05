import copy
import unittest

from liquidity_scout.providers.x1.warp_bridge_flow_integration import (
    CONTRACT as WARP_BRIDGE_FLOW_CONTRACT,
)
from liquidity_scout.services.cmis_bridge_to_xdex_utilization import (
    BridgeToXdexUtilizationError,
    CONTRACT_VERSION,
    POOL_METRIC_CONTRACT,
    POOL_UNIVERSE_CONTRACT,
    VALUE_BASIS_CONTRACT,
    build_bridge_to_xdex_utilization,
)


WSOL_X = "JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8"
ROUTE_ID = "warp-solana-x1-wsol"
AS_OF = 1_788_600_000.0


def bridge_integration(*, supply_raw=10_000_000_000):
    return {
        "contract": WARP_BRIDGE_FLOW_CONTRACT,
        "route_id": ROUTE_ID,
        "destination": {
            "chain": "x1",
            "asset_id": WSOL_X,
            "asset_id_kind": "mint",
        },
        "integration_verified": True,
        "execution_authorized": False,
        "flow": {
            "as_of": AS_OF,
            "decimals": 9,
            "bridged_supply": {
                "verified": True,
                "amount_raw": supply_raw,
                "decimals": 9,
            },
            "windows": {
                "24h": {
                    "current": {
                        "coverage_complete": True,
                        "inflow_raw": 2_000_000_000,
                        "outflow_raw": 1_000_000_000,
                        "net_flow_raw": 1_000_000_000,
                    }
                }
            },
        },
    }


def pool_universe(*, unresolved=None):
    return {
        "contract": POOL_UNIVERSE_CONTRACT,
        "representation_mint": WSOL_X,
        "enumeration_verified": True,
        "all_pool_identities_verified": True,
        "pool_addresses": ["PoolA", "PoolB"],
        "unresolved_pools": list(unresolved or []),
        "execution_authorized": False,
    }


def metric(address, liquidity, volume, *, observed_at=AS_OF - 30):
    return {
        "contract": POOL_METRIC_CONTRACT,
        "pool_address": address,
        "representation_mint": WSOL_X,
        "exact_pool_identity_verified": True,
        "contains_representation_mint": True,
        "liquidity_semantics_verified": True,
        "liquidity_freshness_verified": True,
        "volume_24h_semantics_verified": True,
        "volume_24h_freshness_verified": True,
        "liquidity_value": liquidity,
        "volume_24h_value": volume,
        "value_unit": "USD",
        "observed_at": observed_at,
        "execution_authorized": False,
    }


def metrics():
    return [
        metric("PoolA", "300", "400"),
        metric("PoolB", "200", "600"),
    ]


def value_basis(*, price="100", observed_at=AS_OF - 20):
    return {
        "contract": VALUE_BASIS_CONTRACT,
        "evidence_id": "wsol-usd-current",
        "asset_mint": WSOL_X,
        "unit": "USD",
        "price_per_token": price,
        "price_semantics_verified": True,
        "price_freshness_verified": True,
        "observed_at": observed_at,
        "execution_authorized": False,
    }


class BridgeToXdexUtilizationTests(unittest.TestCase):
    def test_builds_verified_same_unit_utilization(self):
        result = build_bridge_to_xdex_utilization(
            bridge_integration=bridge_integration(),
            pool_universe=pool_universe(),
            pool_metrics=metrics(),
            value_basis=value_basis(),
        )
        self.assertEqual(result["contract"], CONTRACT_VERSION)
        self.assertEqual(result["xdex_pool_count"], 2)
        self.assertEqual(result["verified_xdex_liquidity_value"], "500")
        self.assertEqual(result["verified_xdex_volume_24h_value"], "1000")
        self.assertEqual(result["bridged_supply_token_amount"], "10")
        self.assertEqual(result["bridged_supply_value"], "1000")
        self.assertEqual(result["bridge_to_xdex_liquidity_ratio"], "0.5")
        self.assertEqual(
            result["bridge_gross_flow_24h_to_xdex_volume_24h_ratio"],
            "0.3",
        )
        self.assertEqual(
            result["bridge_net_flow_24h_to_xdex_volume_24h_ratio"],
            "0.1",
        )
        self.assertTrue(result["comparable_value_basis_verified"])
        self.assertTrue(result["utilization_verified"])
        self.assertTrue(result["market_activity_24h_verified"])
        self.assertTrue(result["issue_410_acceptance_verified"])
        self.assertFalse(result["causal_bridge_to_xdex_claim_authorized"])
        self.assertFalse(result["adoption_claim_authorized"])
        self.assertFalse(result["risk_promotion_authorized"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_rejects_unresolved_pool_universe(self):
        with self.assertRaisesRegex(
            BridgeToXdexUtilizationError,
            "unresolved pools",
        ):
            build_bridge_to_xdex_utilization(
                bridge_integration=bridge_integration(),
                pool_universe=pool_universe(unresolved=["UnknownPool"]),
                pool_metrics=metrics(),
                value_basis=value_basis(),
            )

    def test_rejects_missing_pool_metric_coverage(self):
        with self.assertRaisesRegex(
            BridgeToXdexUtilizationError,
            "do not cover exact pool universe",
        ):
            build_bridge_to_xdex_utilization(
                bridge_integration=bridge_integration(),
                pool_universe=pool_universe(),
                pool_metrics=metrics()[:1],
                value_basis=value_basis(),
            )

    def test_rejects_duplicate_pool_metric(self):
        duplicate = [metric("PoolA", "300", "400"), metric("PoolA", "200", "600")]
        with self.assertRaisesRegex(
            BridgeToXdexUtilizationError,
            "duplicate pool metric",
        ):
            build_bridge_to_xdex_utilization(
                bridge_integration=bridge_integration(),
                pool_universe={
                    **pool_universe(),
                    "pool_addresses": ["PoolA"],
                },
                pool_metrics=duplicate,
                value_basis=value_basis(),
            )

    def test_rejects_non_usd_pool_metric(self):
        bad = metrics()
        bad[0]["value_unit"] = "WSOL"
        with self.assertRaisesRegex(
            BridgeToXdexUtilizationError,
            "value_unit must be USD",
        ):
            build_bridge_to_xdex_utilization(
                bridge_integration=bridge_integration(),
                pool_universe=pool_universe(),
                pool_metrics=bad,
                value_basis=value_basis(),
            )

    def test_rejects_stale_market_metric_even_if_boolean_claims_fresh(self):
        bad = metrics()
        bad[0]["observed_at"] = AS_OF - 301
        with self.assertRaisesRegex(BridgeToXdexUtilizationError, "is stale"):
            build_bridge_to_xdex_utilization(
                bridge_integration=bridge_integration(),
                pool_universe=pool_universe(),
                pool_metrics=bad,
                value_basis=value_basis(),
            )

    def test_rejects_stale_value_basis(self):
        with self.assertRaisesRegex(BridgeToXdexUtilizationError, "is stale"):
            build_bridge_to_xdex_utilization(
                bridge_integration=bridge_integration(),
                pool_universe=pool_universe(),
                pool_metrics=metrics(),
                value_basis=value_basis(observed_at=AS_OF - 301),
            )

    def test_rejects_wrong_representation_mint(self):
        bad = value_basis()
        bad["asset_mint"] = "WrongMint"
        with self.assertRaisesRegex(
            BridgeToXdexUtilizationError,
            "asset mint mismatch",
        ):
            build_bridge_to_xdex_utilization(
                bridge_integration=bridge_integration(),
                pool_universe=pool_universe(),
                pool_metrics=metrics(),
                value_basis=bad,
            )

    def test_zero_bridged_supply_keeps_ratio_unavailable(self):
        result = build_bridge_to_xdex_utilization(
            bridge_integration=bridge_integration(supply_raw=0),
            pool_universe=pool_universe(),
            pool_metrics=metrics(),
            value_basis=value_basis(),
        )
        self.assertIsNone(result["bridge_to_xdex_liquidity_ratio"])
        self.assertEqual(
            result["bridge_to_xdex_liquidity_ratio_state"],
            "undefined_zero_bridged_supply",
        )
        self.assertFalse(result["utilization_verified"])

    def test_zero_xdex_volume_keeps_flow_volume_relationship_unavailable(self):
        zero_volume = [
            metric("PoolA", "300", "0"),
            metric("PoolB", "200", "0"),
        ]
        result = build_bridge_to_xdex_utilization(
            bridge_integration=bridge_integration(),
            pool_universe=pool_universe(),
            pool_metrics=zero_volume,
            value_basis=value_basis(),
        )
        self.assertTrue(result["utilization_verified"])
        self.assertIsNone(
            result["bridge_gross_flow_24h_to_xdex_volume_24h_ratio"]
        )
        self.assertIsNone(
            result["bridge_net_flow_24h_to_xdex_volume_24h_ratio"]
        )
        self.assertEqual(
            result["bridge_flow_to_xdex_volume_ratio_state"],
            "undefined_zero_xdex_volume",
        )

    def test_rejects_bridge_net_flow_inconsistency(self):
        bad = bridge_integration()
        bad = copy.deepcopy(bad)
        bad["flow"]["windows"]["24h"]["current"]["net_flow_raw"] = 5
        with self.assertRaisesRegex(
            BridgeToXdexUtilizationError,
            "net flow does not equal",
        ):
            build_bridge_to_xdex_utilization(
                bridge_integration=bad,
                pool_universe=pool_universe(),
                pool_metrics=metrics(),
                value_basis=value_basis(),
            )

    def test_verified_zero_current_pool_set_does_not_invent_24h_volume(self):
        zero_universe = {
            "contract": POOL_UNIVERSE_CONTRACT,
            "representation_mint": WSOL_X,
            "enumeration_verified": True,
            "all_pool_identities_verified": True,
            "pool_addresses": [],
            "unresolved_pools": [],
            "verified_zero_set": True,
            "current_liquidity_zero_verified": True,
            "volume_24h_window_coverage_verified": False,
            "scope": "verified_xdex_program_family",
            "execution_authorized": False,
        }
        result = build_bridge_to_xdex_utilization(
            bridge_integration=bridge_integration(),
            pool_universe=zero_universe,
            pool_metrics=[],
            value_basis=value_basis(),
        )
        self.assertEqual(result["verified_xdex_liquidity_value"], "0")
        self.assertIsNone(result["verified_xdex_volume_24h_value"])
        self.assertEqual(result["bridge_to_xdex_liquidity_ratio"], "0")
        self.assertTrue(result["verified_zero_pool_set"])
        self.assertTrue(result["current_liquidity_zero_verified"])
        self.assertFalse(result["volume_24h_window_coverage_verified"])
        self.assertFalse(result["market_activity_24h_verified"])
        self.assertEqual(
            result["bridge_flow_to_xdex_volume_ratio_state"],
            "unavailable_unverified_volume_window",
        )
        self.assertTrue(result["utilization_verified"])
        self.assertFalse(result["issue_410_acceptance_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_empty_pool_universe_without_verified_zero_proof_is_rejected(self):
        bad_universe = {
            "contract": POOL_UNIVERSE_CONTRACT,
            "representation_mint": WSOL_X,
            "enumeration_verified": True,
            "all_pool_identities_verified": True,
            "pool_addresses": [],
            "unresolved_pools": [],
            "execution_authorized": False,
        }
        with self.assertRaisesRegex(
            BridgeToXdexUtilizationError,
            "explicit verified_zero_set",
        ):
            build_bridge_to_xdex_utilization(
                bridge_integration=bridge_integration(),
                pool_universe=bad_universe,
                pool_metrics=[],
                value_basis=value_basis(),
            )


if __name__ == "__main__":
    unittest.main()
