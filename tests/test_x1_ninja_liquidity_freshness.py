import unittest

from liquidity_scout.providers.x1.liquidity_freshness import (
    REFERENCE_POOL_ADDRESS,
    VERSION,
    evaluate_x1_ninja_liquidity_freshness,
)
from liquidity_scout.providers.x1.current_usdcx_usd_equivalence import (
    SCHEMA as USDCX_SCHEMA,
    X1_USDC_X_MINT,
)
from liquidity_scout.providers.x1.xdex_price_history_import import WRAPPED_XNT_MINT


ASSET = "Asset11111111111111111111111111111111111111"
P1 = "Pool111111111111111111111111111111111111111"
P2 = "Pool222222222222222222222222222222222222222"


def market(*, liquidity=500, addresses=(P1, P2), complete=True):
    return {
        "chain": "x1",
        "asset": {"mint": ASSET, "symbol": "TST"},
        "data": {
            "mint": ASSET,
            "liquidity_usd": liquidity,
            "lp_count": len(addresses),
            "contributing_pools": [
                {"address": address, "liquidity_usd": None}
                for address in addresses
            ],
            "completeness": {"liquidity": complete},
        },
    }


def row(address, *, xnt_reserve, asset_reserve, liquidity, mint_0=WRAPPED_XNT_MINT, mint_1=ASSET):
    return {
        "pool_address": address,
        "status": "ok",
        "provider": {
            "pooledBase": str(asset_reserve),
            "pooledQuote": str(xnt_reserve),
            "liquidity": str(liquidity),
        },
        "rpc": {
            "mint_0": mint_0,
            "mint_1": mint_1,
            "vault_0": f"{address}-v0",
            "vault_1": f"{address}-v1",
            "gross_reserve_0": str(xnt_reserve),
            "gross_reserve_1": str(asset_reserve),
            "gross_quote_per_base_ratio": str(xnt_reserve / asset_reserve),
            "rpc_reserve_ratio_verified": True,
        },
    }


def reference():
    return {
        "pool_address": REFERENCE_POOL_ADDRESS,
        "status": "ok",
        "provider": {},
        "rpc": {
            "mint_0": WRAPPED_XNT_MINT,
            "mint_1": X1_USDC_X_MINT,
            "vault_0": "ref-v0",
            "vault_1": "ref-v1",
            "gross_reserve_0": "50",
            "gross_reserve_1": "100",
            "gross_quote_per_base_ratio": "0.5",
            "rpc_reserve_ratio_verified": True,
        },
    }


def snapshot(*rows, before_time=995, after_time=997):
    return {
        "service": "x1_ninja_price_fact_time_snapshot",
        "version": "1.0",
        "chain": "x1",
        "status": "ok",
        "rpc_slot_bracket": {
            "before": {
                "slot": 10,
                "block_time": before_time,
                "block_time_verified": True,
            },
            "after": {
                "slot": 11,
                "block_time": after_time,
                "block_time_verified": True,
            },
        },
        "pools": [*rows, reference()],
        "provider_fact_time_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def equivalence():
    return {
        "schema": USDCX_SCHEMA,
        "status": "verified",
        "route_identity_verified": True,
        "source_usdc_usd_price_unit_verified": True,
        "source_usdc_usd_price_identity_verified": True,
        "source_usdc_usd_price_fresh": True,
        "source_usdc_usd_price": "1",
        "source_usdc_within_usd_tolerance": True,
        "destination_representation_value_equivalence_verified": True,
        "current_usdcx_usd_equivalence_verified": True,
        "execution_authorized": False,
    }


class X1NinjaLiquidityFreshnessTests(unittest.TestCase):
    def test_verifies_exact_aggregate_from_fresh_chain_state(self):
        # reference => 100 USDC.X / 50 XNT => $2/XNT.
        # P1 => 2 * 100 XNT * $2 = $400.
        # P2 => 2 * 25 XNT * $2 = $100.
        result = evaluate_x1_ninja_liquidity_freshness(
            market_envelope=market(),
            snapshot=snapshot(
                row(P1, xnt_reserve=100, asset_reserve=200, liquidity=400),
                row(P2, xnt_reserve=25, asset_reserve=50, liquidity=100),
            ),
            current_usdcx_usd_equivalence=equivalence(),
            evaluated_at=1000,
        )

        self.assertEqual(result["contract_version"], VERSION)
        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["all_contributing_pools_corroborated"])
        self.assertTrue(result["rpc_freshness"]["rpc_block_time_fresh"])
        self.assertEqual(result["xnt_usd_basis"]["derived_xnt_usd"], "2")
        self.assertEqual(result["derived_current_liquidity_sum_usd"], "500")
        self.assertTrue(
            result["market_vs_derived_current_aggregate"]["within_tolerance"]
        )
        self.assertTrue(result["current_value_reproduced_from_fresh_chain_state"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertTrue(result["liquidity_freshness_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_stale_rpc_bracket_fails_closed(self):
        result = evaluate_x1_ninja_liquidity_freshness(
            market_envelope=market(addresses=(P1,), liquidity=400),
            snapshot=snapshot(
                row(P1, xnt_reserve=100, asset_reserve=200, liquidity=400),
                before_time=800,
                after_time=801,
            ),
            current_usdcx_usd_equivalence=equivalence(),
            evaluated_at=1000,
        )
        self.assertFalse(result["liquidity_freshness_verified"])
        self.assertIn("rpc_block_time_stale_or_unverified", result["failures"])

    def test_missing_current_usdcx_equivalence_fails_closed(self):
        bad = equivalence()
        bad["current_usdcx_usd_equivalence_verified"] = False
        result = evaluate_x1_ninja_liquidity_freshness(
            market_envelope=market(addresses=(P1,), liquidity=400),
            snapshot=snapshot(
                row(P1, xnt_reserve=100, asset_reserve=200, liquidity=400)
            ),
            current_usdcx_usd_equivalence=bad,
            evaluated_at=1000,
        )
        self.assertFalse(result["liquidity_freshness_verified"])
        self.assertTrue(
            any(item.startswith("xnt_usd_basis_unverified:") for item in result["failures"])
        )

    def test_non_wrapped_xnt_pool_orientation_is_not_generalized(self):
        result = evaluate_x1_ninja_liquidity_freshness(
            market_envelope=market(addresses=(P1,), liquidity=400),
            snapshot=snapshot(
                row(
                    P1,
                    xnt_reserve=100,
                    asset_reserve=200,
                    liquidity=400,
                    mint_0=ASSET,
                    mint_1=WRAPPED_XNT_MINT,
                )
            ),
            current_usdcx_usd_equivalence=equivalence(),
            evaluated_at=1000,
        )
        self.assertFalse(result["liquidity_freshness_verified"])
        self.assertIn(
            "accepted_liquidity_semantics_require_wrapped_xnt_in_mint_0",
            result["pool_results"][0]["rejection_reasons"],
        )

    def test_aggregate_mismatch_fails_closed(self):
        result = evaluate_x1_ninja_liquidity_freshness(
            market_envelope=market(addresses=(P1,), liquidity=450),
            snapshot=snapshot(
                row(P1, xnt_reserve=100, asset_reserve=200, liquidity=400)
            ),
            current_usdcx_usd_equivalence=equivalence(),
            evaluated_at=1000,
        )
        self.assertFalse(result["liquidity_freshness_verified"])
        self.assertIn(
            "market_liquidity_does_not_match_derived_current_total",
            result["failures"],
        )

    def test_provider_reserve_mismatch_fails_closed(self):
        bad = row(P1, xnt_reserve=100, asset_reserve=200, liquidity=400)
        bad["provider"]["pooledQuote"] = "90"
        result = evaluate_x1_ninja_liquidity_freshness(
            market_envelope=market(addresses=(P1,), liquidity=400),
            snapshot=snapshot(bad),
            current_usdcx_usd_equivalence=equivalence(),
            evaluated_at=1000,
        )
        self.assertFalse(result["liquidity_freshness_verified"])
        self.assertIn(
            "provider_pooledQuote_does_not_match_rpc_xnt_reserve",
            result["pool_results"][0]["rejection_reasons"],
        )

    def test_pool_bound_fails_closed_without_sampling(self):
        addresses = tuple(f"Pool{index:03d}" for index in range(3))
        rows = [
            row(address, xnt_reserve=1, asset_reserve=2, liquidity=4)
            for address in addresses
        ]
        result = evaluate_x1_ninja_liquidity_freshness(
            market_envelope=market(addresses=addresses, liquidity=12),
            snapshot=snapshot(*rows),
            current_usdcx_usd_equivalence=equivalence(),
            evaluated_at=1000,
            max_pools=2,
        )
        self.assertFalse(result["liquidity_freshness_verified"])
        self.assertIn(
            "contributing_pool_count_exceeds_corroboration_bound",
            result["failures"],
        )

    def test_incomplete_market_liquidity_fails_closed(self):
        result = evaluate_x1_ninja_liquidity_freshness(
            market_envelope=market(addresses=(P1,), liquidity=400, complete=False),
            snapshot=snapshot(
                row(P1, xnt_reserve=100, asset_reserve=200, liquidity=400)
            ),
            current_usdcx_usd_equivalence=equivalence(),
            evaluated_at=1000,
        )
        self.assertFalse(result["liquidity_freshness_verified"])
        self.assertIn("market_liquidity_incomplete", result["failures"])


if __name__ == "__main__":
    unittest.main()
