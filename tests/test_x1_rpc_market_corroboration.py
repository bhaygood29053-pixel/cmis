from __future__ import annotations

import unittest

from liquidity_scout.providers.x1.rpc_market_corroboration import (
    evaluate_rpc_market_corroboration,
)


POOL = "Pool111111111111111111111111111111111111"


def market(address: str = POOL):
    return {
        "data": {
            "primary_pool": {"address": address},
        }
    }


def snapshot(*, before_time=995, after_time=997, pooled_base="10", pooled_quote="20", price_native="2"):
    return {
        "service": "x1_ninja_price_fact_time_snapshot",
        "chain": "x1",
        "status": "ok",
        "rpc_slot_bracket": {
            "before": {
                "slot": 100,
                "block_time": before_time,
                "block_time_verified": True,
            },
            "after": {
                "slot": 101,
                "block_time": after_time,
                "block_time_verified": True,
            },
        },
        "pools": [
            {
                "pool_address": POOL,
                "status": "ok",
                "provider": {
                    "priceNative": price_native,
                    "pooledBase": pooled_base,
                    "pooledQuote": pooled_quote,
                },
                "rpc": {
                    "mint_0": "XNT",
                    "mint_1": "ASSET",
                    "vault_0": "Vault0",
                    "vault_1": "Vault1",
                    "gross_reserve_0": "20",
                    "gross_reserve_1": "10",
                    "gross_quote_per_base_ratio": "2",
                    "rpc_reserve_ratio_verified": True,
                },
            }
        ],
    }


class X1RPCMarketCorroborationTests(unittest.TestCase):
    def test_exact_current_pool_can_be_chain_corroborated_without_promoting_freshness(self):
        result = evaluate_rpc_market_corroboration(
            market(),
            snapshot(),
            evaluated_at=1000,
        )

        self.assertEqual(result["contract_version"], "x1_rpc_market_corroboration/v1")
        self.assertTrue(result["primary_pool_identity_verified"])
        self.assertTrue(result["rpc_slot_bracket_verified"])
        self.assertTrue(result["rpc_block_time_fresh"])
        self.assertTrue(result["vault_identity_verified"])
        self.assertTrue(result["provider_reserve_values_match_rpc"])
        self.assertTrue(result["provider_price_native_matches_rpc_ratio"])
        self.assertTrue(result["reserve_chain_corroboration_verified"])
        self.assertTrue(result["price_native_chain_corroboration_verified"])
        self.assertTrue(result["chain_corroboration_verified"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_stale_rpc_block_times_fail_closed(self):
        result = evaluate_rpc_market_corroboration(
            market(),
            snapshot(before_time=800, after_time=801),
            evaluated_at=1000,
        )

        self.assertTrue(result["rpc_slot_bracket_verified"])
        self.assertFalse(result["rpc_block_time_fresh"])
        self.assertFalse(result["reserve_chain_corroboration_verified"])
        self.assertIn("rpc_block_time_not_fresh", result["failures"])

    def test_wrong_primary_pool_fails_closed(self):
        result = evaluate_rpc_market_corroboration(
            market("DifferentPool"),
            snapshot(),
            evaluated_at=1000,
        )

        self.assertFalse(result["primary_pool_identity_verified"])
        self.assertFalse(result["chain_corroboration_verified"])
        self.assertIn("primary_pool_identity_unverified", result["failures"])

    def test_provider_reserve_mismatch_fails_closed(self):
        result = evaluate_rpc_market_corroboration(
            market(),
            snapshot(pooled_base="11"),
            evaluated_at=1000,
        )

        self.assertFalse(result["provider_reserve_values_match_rpc"])
        self.assertFalse(result["reserve_chain_corroboration_verified"])
        self.assertIn("provider_reserve_values_do_not_match_rpc", result["failures"])

    def test_price_mismatch_is_separate_from_reserve_corroboration(self):
        result = evaluate_rpc_market_corroboration(
            market(),
            snapshot(price_native="2.1"),
            evaluated_at=1000,
        )

        self.assertTrue(result["reserve_chain_corroboration_verified"])
        self.assertFalse(result["provider_price_native_matches_rpc_ratio"])
        self.assertFalse(result["price_native_chain_corroboration_verified"])
        self.assertFalse(result["chain_corroboration_verified"])


if __name__ == "__main__":
    unittest.main()
