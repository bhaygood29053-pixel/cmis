from __future__ import annotations

from copy import deepcopy
import unittest

from liquidity_scout.services.cmis_large_trade_discovery import (
    CONTRACT_VERSION,
    LargeTradeDiscoveryError,
    RANKING_SCOPE,
    SERVICE,
    build_large_trade_discovery_response,
)


ASSET = "agi-mint"
POOL_A = "pool-a"
POOL_B = "pool-b"
QUOTE = "usdcx-mint"
END = 1_788_696_000
START = END - 86_400


def scope():
    return {
        "contract_version": "x1_ninja_current_pool_scope/v1",
        "chain": "x1",
        "asset_mint": ASSET,
        "market_contributing_pool_addresses": [POOL_A, POOL_B],
        "current_catalog_exact_mint_pool_addresses": [POOL_A, POOL_B],
        "market_pool_count": 2,
        "current_catalog_exact_mint_pool_count": 2,
        "provider_scoped_pool_universe_verified": True,
        "global_xdex_pool_universe_verified": False,
        "execution_authorized": False,
    }


def swap(
    signature,
    *,
    slot,
    usd,
    asset_delta,
    counter_delta,
    block_time,
):
    return {
        "signature": signature,
        "slot": slot,
        "block_time": block_time,
        "classification": "EXACT_POOL_SWAP",
        "membership_verified": True,
        "asset_vault_delta_ui": str(asset_delta),
        "counter_vault_delta_ui": str(counter_delta),
        "quote_mint": QUOTE,
        "quote_volume": str(counter_delta).lstrip("-"),
        "historical_usd_value_verified": True,
        "usd_value": str(usd),
        "usd_evidence": {
            "historical_usd_value_verified": True,
            "fact_time_verified": True,
        },
    }


def window(pool, rows):
    return {
        "contract_version": "x1_pool_24h_chain_activity/v1",
        "chain": "x1",
        "pool_address": pool,
        "asset_mint": ASSET,
        "counter_mint": QUOTE,
        "requested_window": {
            "start_epoch": str(START),
            "end_epoch": str(END),
            "duration_seconds": "86400",
        },
        "history_range_proven": True,
        "history_integrity_verified": True,
        "all_successful_transactions_verified": True,
        "all_pool_relevant_transactions_classified": True,
        "transactions_24h_window_coverage_verified": True,
        "swap_count_semantics_verified": True,
        "verified_transactions_24h": len(rows),
        "quote_volume_semantics_verified": True,
        "verified_quote_volume_24h": str(
            sum(abs(float(row["counter_vault_delta_ui"])) for row in rows)
        ),
        "verified_quote_volume_unit": QUOTE,
        "usd_valuation_coverage_verified": True,
        "nonzero_volume_usd_semantics_verified": bool(rows),
        "usd_valuation_basis": (
            "verified_historical_quote_usd_value_per_exact_swap"
            if rows
            else "exact_zero_swap_volume_requires_no_price_conversion"
        ),
        "verified_volume_24h_usd": str(
            sum(float(row["usd_value"]) for row in rows)
        ),
        "volume_24h_value_verified": True,
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "read_only": True,
        "execution_authorized": False,
        "transactions": rows,
    }


def wallets():
    return [
        {
            "chain": "x1",
            "transaction_signature": "buy-big",
            "wallet": "wallet-big",
            "asset_id": ASSET,
            "activity_type": "BUY",
            "block_slot": 20,
            "observed_at": "2026-09-06T12:00:00Z",
            "verification": {
                "wallet_identity_verified": True,
                "asset_identity_verified": True,
                "transaction_identity_verified": True,
                "trade_direction_verified": True,
            },
            "classification_authorized": False,
            "complete_wallet_history_proven": False,
        },
        {
            "chain": "x1",
            "transaction_signature": "sell-big",
            "wallet": "wallet-sell",
            "asset_id": ASSET,
            "activity_type": "SELL",
            "block_slot": 30,
            "observed_at": "2026-09-06T12:01:00Z",
            "verification": {
                "wallet_identity_verified": True,
                "asset_identity_verified": True,
                "transaction_identity_verified": True,
                "trade_direction_verified": True,
            },
            "classification_authorized": False,
            "complete_wallet_history_proven": False,
        },
    ]


def windows():
    return [
        window(
            POOL_A,
            [
                swap(
                    "buy-small",
                    slot=10,
                    usd="100",
                    asset_delta="-1000",
                    counter_delta="100",
                    block_time=START + 10,
                ),
                swap(
                    "buy-big",
                    slot=20,
                    usd="500",
                    asset_delta="-4000",
                    counter_delta="500",
                    block_time=START + 20,
                ),
            ],
        ),
        window(
            POOL_B,
            [
                swap(
                    "sell-big",
                    slot=30,
                    usd="700",
                    asset_delta="5000",
                    counter_delta="-700",
                    block_time=START + 30,
                ),
                swap(
                    "buy-mid",
                    slot=40,
                    usd="300",
                    asset_delta="-2500",
                    counter_delta="300",
                    block_time=START + 40,
                ),
            ],
        ),
    ]


class LargeTradeDiscoveryTests(unittest.TestCase):
    def build(self, **overrides):
        args = {
            "requested_asset_mint": ASSET,
            "pool_scope_evidence": scope(),
            "pool_windows": windows(),
            "evaluated_at": END,
            "direction": "ANY",
            "limit": 5,
            "wallet_observations": wallets(),
            "trusted_trade_price_impact_evidence_ids": {
                "buy-big": "tpi:buy-big",
                "sell-big": "tpi:sell-big",
            },
        }
        args.update(overrides)
        return build_large_trade_discovery_response(**args)

    def test_ranks_verified_usd_notional_and_derives_direction(self):
        result = self.build()

        self.assertEqual(result["service"], SERVICE)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["asset"]["mint"], ASSET)
        data = result["data"]
        self.assertEqual(data["contract_version"], CONTRACT_VERSION)
        self.assertEqual(data["ranking_scope"], RANKING_SCOPE)
        self.assertEqual(data["exact_swap_count_examined"], 4)
        self.assertEqual(data["eligible_trade_count"], 4)
        self.assertEqual(data["result_count"], 4)
        self.assertTrue(data["ranking_complete_for_scope"])
        self.assertTrue(data["public_service_promoted"])
        self.assertFalse(data["scout_reliance_promoted"])
        self.assertFalse(data["execution_authorized"])

        ranked = data["results"]
        self.assertEqual(
            [row["transaction_signature"] for row in ranked],
            ["sell-big", "buy-big", "buy-mid", "buy-small"],
        )
        self.assertEqual(
            [row["direction"] for row in ranked],
            ["SELL", "BUY", "BUY", "BUY"],
        )
        self.assertEqual(ranked[0]["verified_usd_notional"], "700")
        self.assertTrue(ranked[0]["usd_notional_verified"])
        self.assertEqual(ranked[0]["wallet_address"], "wallet-sell")
        self.assertTrue(ranked[0]["wallet_attribution_verified"])
        self.assertFalse(ranked[0]["real_world_wallet_owner_verified"])
        self.assertEqual(
            ranked[0]["trade_price_impact_evidence_id"],
            "tpi:sell-big",
        )
        self.assertTrue(ranked[0]["trade_price_impact_handoff_ready"])

        boundaries = data["evidence_boundaries"]
        self.assertFalse(
            boundaries["global_x1_dex_trade_ranking_authorized"]
        )
        self.assertFalse(
            boundaries["wallet_owner_identity_inference_authorized"]
        )
        self.assertFalse(
            boundaries["whale_insider_manipulator_label_authorized"]
        )
        self.assertFalse(boundaries["intent_inference_authorized"])
        self.assertFalse(
            boundaries["whole_market_price_impact_claim_authorized"]
        )
        self.assertFalse(
            boundaries["automatic_risk_conclusion_authorized"]
        )
        self.assertFalse(boundaries["trade_recommendation_authorized"])
        self.assertFalse(result["confidence"]["source_independence_verified"])
        self.assertIsNone(result["risk"])

    def test_buy_filter_answers_biggest_verified_buy_in_bounded_scope(self):
        result = self.build(direction="BUY", limit=1)
        data = result["data"]

        self.assertEqual(data["requested_direction"], "BUY")
        self.assertEqual(data["requested_limit"], 1)
        self.assertEqual(data["eligible_trade_count"], 3)
        self.assertEqual(data["result_count"], 1)

        top = data["results"][0]
        self.assertEqual(top["rank"], 1)
        self.assertEqual(top["transaction_signature"], "buy-big")
        self.assertEqual(top["direction"], "BUY")
        self.assertEqual(top["verified_usd_notional"], "500")
        self.assertEqual(top["asset_amount"], "4000")
        self.assertEqual(top["quote_amount"], "500")
        self.assertEqual(top["wallet_address"], "wallet-big")
        self.assertTrue(top["trade_price_impact_handoff_ready"])

    def test_missing_wallet_attribution_does_not_block_ranking_or_invent_owner(self):
        result = self.build(
            direction="BUY",
            limit=2,
            wallet_observations=[],
            trusted_trade_price_impact_evidence_ids={},
        )
        rows = result["data"]["results"]

        self.assertEqual(
            [row["transaction_signature"] for row in rows],
            ["buy-big", "buy-mid"],
        )
        self.assertTrue(result["data"]["ranking_complete_for_scope"])
        self.assertFalse(
            result["confidence"]["wallet_attribution_complete_for_results"]
        )
        for row in rows:
            self.assertIsNone(row["wallet_address"])
            self.assertFalse(row["wallet_attribution_verified"])
            self.assertFalse(row["real_world_wallet_owner_verified"])
            self.assertIsNone(row["trade_price_impact_evidence_id"])
            self.assertFalse(row["trade_price_impact_handoff_ready"])

    def test_ties_are_deterministic_by_slot_then_signature(self):
        tied = windows()
        tied[0]["transactions"][0]["usd_value"] = "500"
        tied[1]["transactions"][1]["usd_value"] = "500"
        result = self.build(
            pool_windows=tied,
            direction="BUY",
            wallet_observations=[],
            trusted_trade_price_impact_evidence_ids={},
        )

        self.assertEqual(
            [row["transaction_signature"] for row in result["data"]["results"]],
            ["buy-small", "buy-big", "buy-mid"],
        )

    def test_empty_verified_pool_scope_returns_complete_empty_ranking(self):
        empty_scope = scope()
        empty_scope["market_contributing_pool_addresses"] = []
        empty_scope["current_catalog_exact_mint_pool_addresses"] = []
        empty_scope["market_pool_count"] = 0
        empty_scope["current_catalog_exact_mint_pool_count"] = 0

        result = self.build(
            pool_scope_evidence=empty_scope,
            pool_windows=[],
            wallet_observations=[],
            trusted_trade_price_impact_evidence_ids={},
        )
        data = result["data"]
        self.assertTrue(data["ranking_complete_for_scope"])
        self.assertEqual(data["pool_scope"]["pool_count"], 0)
        self.assertEqual(data["exact_swap_count_examined"], 0)
        self.assertEqual(data["eligible_trade_count"], 0)
        self.assertEqual(data["results"], [])

    def test_incomplete_provider_scoped_pool_scope_fails_closed(self):
        bad = scope()
        bad["provider_scoped_pool_universe_verified"] = False
        with self.assertRaisesRegex(
            LargeTradeDiscoveryError,
            "provider_scoped_pool_universe_verified",
        ):
            self.build(pool_scope_evidence=bad)

    def test_global_pool_scope_must_remain_unverified(self):
        bad = scope()
        bad["global_xdex_pool_universe_verified"] = True
        with self.assertRaisesRegex(
            LargeTradeDiscoveryError,
            "global_xdex_pool_universe_verified",
        ):
            self.build(pool_scope_evidence=bad)

    def test_missing_pool_window_fails_closed(self):
        with self.assertRaisesRegex(
            LargeTradeDiscoveryError,
            "pool window set",
        ):
            self.build(pool_windows=windows()[:1])

    def test_unaligned_pool_windows_fail_closed(self):
        bad = windows()
        bad[1]["requested_window"]["start_epoch"] = str(START - 1)
        bad[1]["requested_window"]["end_epoch"] = str(END - 1)
        with self.assertRaisesRegex(
            LargeTradeDiscoveryError,
            "time aligned",
        ):
            self.build(pool_windows=bad)

    def test_stale_24h_window_fails_closed(self):
        with self.assertRaisesRegex(
            LargeTradeDiscoveryError,
            "current to evaluated_at",
        ):
            self.build(evaluated_at=END + 121)

    def test_unverified_usd_value_fails_closed(self):
        bad = windows()
        bad[0]["transactions"][1][
            "historical_usd_value_verified"
        ] = False
        with self.assertRaisesRegex(
            LargeTradeDiscoveryError,
            "historical_usd_value_verified",
        ):
            self.build(pool_windows=bad)

    def test_duplicate_signature_across_pools_fails_closed(self):
        bad = windows()
        bad[1]["transactions"][0]["signature"] = "buy-big"
        with self.assertRaisesRegex(
            LargeTradeDiscoveryError,
            "duplicate exact-swap signature",
        ):
            self.build(pool_windows=bad)

    def test_wallet_direction_disagreement_fails_closed(self):
        bad_wallets = wallets()
        bad_wallets[0]["activity_type"] = "SELL"
        with self.assertRaisesRegex(
            LargeTradeDiscoveryError,
            "wallet attribution direction disagrees",
        ):
            self.build(wallet_observations=bad_wallets)

    def test_wallet_identity_must_be_verified(self):
        bad_wallets = wallets()
        bad_wallets[0]["verification"]["wallet_identity_verified"] = False
        with self.assertRaisesRegex(
            LargeTradeDiscoveryError,
            "wallet_identity_verified",
        ):
            self.build(wallet_observations=bad_wallets)

    def test_handoff_id_cannot_reference_unknown_transaction(self):
        with self.assertRaisesRegex(
            LargeTradeDiscoveryError,
            "outside discovery evidence",
        ):
            self.build(
                trusted_trade_price_impact_evidence_ids={
                    "unknown-signature": "tpi:unknown",
                }
            )


if __name__ == "__main__":
    unittest.main()
