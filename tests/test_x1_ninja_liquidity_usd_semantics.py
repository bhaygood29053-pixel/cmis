from __future__ import annotations

import unittest

from liquidity_scout.providers.x1.ninja_liquidity_usd_semantics import (
    verify_ninja_liquidity_usd_semantics,
)
from liquidity_scout.providers.x1.ninja_pooled_reserve_semantics import DIRECT_MAPPING
from liquidity_scout.providers.x1.xdex_price_history_import import WRAPPED_XNT_MINT


def xnt_usd_evidence(**overrides):
    value = {
        "price_usd": "2",
        "price_usd_verified": True,
        "provider_fact_time_verified": True,
        "freshness_verified": True,
        "same_time_scope_verified": True,
        "source": "independent verified XNT/USD fixture",
    }
    value.update(overrides)
    return value


def sample(index: int):
    asset_reserve = 10 * index
    xnt_reserve = 5 * index
    return {
        "pool_address": f"POOL{index}",
        "mint_0": WRAPPED_XNT_MINT,
        "mint_1": f"ASSET{index}",
        "vault_0": f"XNT_VAULT{index}",
        "vault_1": f"ASSET_VAULT{index}",
        "rpc_vault_0_reserve": str(xnt_reserve),
        "rpc_vault_1_reserve": str(asset_reserve),
        "mapping_verified": True,
    }


def upstream(samples):
    return {
        "status": "verified",
        "pooled_reserve_semantics_verified": True,
        "stable_mapping": DIRECT_MAPPING,
        "samples": samples,
    }


def ninja_pools(*, mismatch_pool: str | None = None):
    rows = []
    for index in range(1, 6):
        # XNT/USD=2, XNT reserve=5*i, asset reserve=10*i, so each side
        # is worth $10*i and the two-sided pool valuation is $20*i.
        liquidity = 20 * index
        if mismatch_pool == f"POOL{index}":
            liquidity += 3
        rows.append({"address": f"POOL{index}", "liquidity": str(liquidity)})
    return rows


class X1NinjaLiquidityUsdSemanticsTests(unittest.TestCase):
    def test_verifies_two_sided_usd_liquidity_without_provider_price_usd(self):
        samples = [sample(index) for index in range(1, 6)]
        result = verify_ninja_liquidity_usd_semantics(
            ninja_pools=ninja_pools(),
            xdex_pools=[],
            xnt_usd_evidence=xnt_usd_evidence(),
            pooled_reserve_provider=lambda **_kwargs: upstream(samples),
        )

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["xnt_usd_input_verified"])
        self.assertTrue(result["upstream_pooled_reserve_semantics_verified"])
        self.assertEqual(result["verified_sample_count"], 5)
        self.assertTrue(result["liquidity_two_sided_valuation_verified"])
        self.assertTrue(result["x1_ninja_liquidity_usd_semantics_verified"])
        self.assertTrue(result["liquidity_usd_semantics_verified"])
        self.assertFalse(result["liquidity_freshness_verified"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

        for row in result["samples"]:
            self.assertTrue(row["two_sided_comparison"]["within_tolerance"])
            self.assertFalse(
                row["one_sided_diagnostics"]["asset_side"]["within_tolerance"]
            )
            self.assertFalse(
                row["one_sided_diagnostics"]["xnt_side"]["within_tolerance"]
            )

    def test_rejects_unverified_xnt_usd_input_before_reserve_use(self):
        called = False

        def provider(**_kwargs):
            nonlocal called
            called = True
            return upstream([sample(index) for index in range(1, 6)])

        result = verify_ninja_liquidity_usd_semantics(
            ninja_pools=ninja_pools(),
            xdex_pools=[],
            xnt_usd_evidence=xnt_usd_evidence(freshness_verified=False),
            pooled_reserve_provider=provider,
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["xnt_usd_input_verified"])
        self.assertFalse(result["liquidity_usd_semantics_verified"])
        self.assertFalse(called)

    def test_wrong_wrapped_xnt_position_fails_closed(self):
        samples = [sample(index) for index in range(1, 6)]
        samples[2]["mint_0"] = "NOT_XNT"
        result = verify_ninja_liquidity_usd_semantics(
            ninja_pools=ninja_pools(),
            xdex_pools=[],
            xnt_usd_evidence=xnt_usd_evidence(),
            pooled_reserve_provider=lambda **_kwargs: upstream(samples),
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["liquidity_usd_semantics_verified"])
        self.assertIn(
            "wrapped_xnt_position_unverified",
            result["samples"][2]["rejection_reasons"],
        )

    def test_material_provider_liquidity_mismatch_blocks_semantic_promotion(self):
        samples = [sample(index) for index in range(1, 6)]
        result = verify_ninja_liquidity_usd_semantics(
            ninja_pools=ninja_pools(mismatch_pool="POOL4"),
            xdex_pools=[],
            xnt_usd_evidence=xnt_usd_evidence(),
            pooled_reserve_provider=lambda **_kwargs: upstream(samples),
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["verified_sample_count"], 4)
        self.assertFalse(result["liquidity_usd_semantics_verified"])
        self.assertIn(
            "provider_liquidity_does_not_match_two_sided_rpc_valuation",
            result["samples"][3]["rejection_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
