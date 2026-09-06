from copy import deepcopy
import unittest

from liquidity_scout.services.cmis_trade_price_impact_intelligence import (
    CONTRACT_VERSION,
    SERVICE,
    TradePriceImpactIntelligenceError,
    build_trade_price_impact_intelligence_response,
)


ASSET = "AssetMint111"
POOL = "Pool111"
WALLET = "Wallet111"
TARGET = "TargetSig111"
NEXT = "NextSig222"


def wallet_observation():
    return {
        "chain": "x1",
        "wallet": WALLET,
        "activity_type": "BUY",
        "transaction_signature": TARGET,
        "observed_at": "2026-09-06T12:00:00Z",
        "block_slot": 100,
        "asset_id": ASSET,
        "verification": {
            "wallet_identity_verified": True,
            "asset_identity_verified": True,
            "transaction_identity_verified": True,
            "amount_verified": False,
            "trade_direction_verified": True,
        },
        "classification_authorized": False,
        "complete_wallet_history_proven": False,
    }


def execution_evidence(signature=TARGET, slot=100, price="12"):
    return {
        "service": "x1_ninja_trade_execution_price",
        "version": "1.0",
        "chain": "x1",
        "status": "verified",
        "pool_address": POOL,
        "transaction_signature": signature,
        "transaction_slot": slot,
        "transaction_block_time": 1788696000,
        "onchain_side": "BUY",
        "transaction_pool_membership_verified": True,
        "provider_amounts_match_exact_pool_leg": True,
        "provider_asset_amount_matches_vault_delta": True,
        "provider_quote_amount_matches_vault_delta": True,
        "provider_slot_matches_rpc_slot": True,
        "pool_vault_delta_signs_verified": True,
        "onchain": {
            "asset_amount": "10",
            "quote_amount": "120",
            "effective_execution_price_native": price,
            "post_trade_asset_reserve": "90",
            "post_trade_quote_reserve": "1120",
            "post_trade_reserve_ratio_native": "12.44444444444444444444444444",
        },
        "trade_price_native_execution_semantics_verified": True,
        "execution_authorized": False,
    }


def routing_evidence():
    return {
        "service": "x1_routed_multi_amm_ambiguity",
        "version": "1.0",
        "chain": "x1",
        "status": "verified",
        "signature": TARGET,
        "pool_address": POOL,
        "recognized_amm_instruction_count_normalized": 1,
        "selected_pool_instruction_count_normalized": 1,
        "additional_recognized_instruction_count_normalized": 0,
        "exact_vault_deltas_verified": True,
        "ambiguity_cause": "single_or_no_recognized_amm_instruction",
        "genuine_instruction_multiplicity_observed": False,
        "execution_authorized": False,
    }


def pool_window():
    return {
        "contract_version": "x1_pool_24h_chain_activity/v1",
        "chain": "x1",
        "pool_address": POOL,
        "asset_mint": ASSET,
        "counter_mint": "QuoteMint111",
        "requested_window": {
            "start_epoch": "1788609600",
            "end_epoch": "1788696000",
            "duration_seconds": "86400",
        },
        "history_range_proven": True,
        "history_integrity_verified": True,
        "all_successful_transactions_verified": True,
        "all_pool_relevant_transactions_classified": True,
        "transactions_24h_window_coverage_verified": True,
        "swap_count_semantics_verified": True,
        "usd_valuation_coverage_verified": True,
        "volume_24h_value_verified": True,
        "verified_volume_24h_usd": "1000",
        "transactions": [
            {
                "signature": TARGET,
                "slot": 100,
                "block_time": 1788695000,
                "classification": "EXACT_POOL_SWAP",
                "historical_usd_value_verified": True,
                "usd_value": "120",
            },
            {
                "signature": NEXT,
                "slot": 101,
                "block_time": 1788695010,
                "classification": "EXACT_POOL_SWAP",
                "historical_usd_value_verified": True,
                "usd_value": "50",
            },
        ],
        "execution_authorized": False,
    }


def next_execution_evidence():
    row = execution_evidence(signature=NEXT, slot=101, price="12.5")
    row["onchain"]["asset_amount"] = "4"
    row["onchain"]["quote_amount"] = "50"
    row["onchain"]["post_trade_asset_reserve"] = "86"
    row["onchain"]["post_trade_quote_reserve"] = "1170"
    row["onchain"]["post_trade_reserve_ratio_native"] = (
        "13.60465116279069767441860465"
    )
    return row


class TradePriceImpactIntelligenceTests(unittest.TestCase):
    def build(self, **overrides):
        args = {
            "requested_asset_mint": ASSET,
            "wallet_observation": wallet_observation(),
            "execution_evidence": execution_evidence(),
            "routing_evidence": routing_evidence(),
            "pool_window": pool_window(),
            "next_execution_evidence": next_execution_evidence(),
        }
        args.update(overrides)
        return build_trade_price_impact_intelligence_response(**args)

    def test_builds_verified_pool_local_trade_intelligence(self):
        result = self.build()

        self.assertEqual(result["service"], SERVICE)
        self.assertEqual(result["chain"], "x1")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["contract_version"], CONTRACT_VERSION)
        self.assertTrue(result["data"]["public_service_promoted"])
        self.assertTrue(result["data"]["scout_reliance_promoted"])

        trade = result["data"]["wallet_trade"]
        self.assertEqual(trade["wallet_address"], WALLET)
        self.assertFalse(trade["real_world_identity_verified"])
        self.assertEqual(trade["transaction_signature"], TARGET)
        self.assertEqual(trade["direction"], "BUY")
        self.assertEqual(trade["asset_amount"], "10")
        self.assertEqual(trade["quote_amount"], "120")
        self.assertTrue(trade["wallet_trade_amount_attribution_verified"])

        pool = result["data"]["pool"]
        self.assertEqual(pool["pre_trade_asset_reserve"], "100")
        self.assertEqual(pool["pre_trade_quote_reserve"], "1000")
        self.assertEqual(pool["post_trade_asset_reserve"], "90")
        self.assertEqual(pool["post_trade_quote_reserve"], "1120")
        self.assertEqual(pool["pre_trade_spot_price_native"], "10")
        self.assertEqual(pool["average_execution_price_native"], "12")
        self.assertEqual(
            pool["post_trade_spot_price_native"],
            "12.44444444444444444444444444",
        )
        self.assertEqual(
            pool["execution_price_impact_percent_vs_pre_spot"],
            "20.0",
        )
        self.assertEqual(
            pool["spot_price_change_percent"],
            "24.44444444444444444444444440",
        )
        self.assertTrue(pool["pool_local_state_transition_verified"])

        next_trade = result["data"]["next_verified_trade"]
        self.assertTrue(next_trade["verified"])
        self.assertEqual(next_trade["signature"], NEXT)
        self.assertEqual(next_trade["slot"], 101)
        self.assertEqual(next_trade["execution_price_native"], "12.5")

        window = result["data"]["measured_window"]
        self.assertEqual(window["trade_usd_notional"], "120")
        self.assertEqual(window["verified_window_volume_usd"], "1000")
        self.assertEqual(window["trade_volume_contribution_percent"], "12.00")
        self.assertTrue(
            window["numerator_denominator_same_verified_usd_basis"]
        )

        boundaries = result["data"]["evidence_boundaries"]
        self.assertTrue(boundaries["pool_local_causal_state_transition_authorized"])
        self.assertFalse(boundaries["whole_market_price_impact_claim_authorized"])
        self.assertFalse(boundaries["volume_causality_claim_authorized"])
        self.assertFalse(boundaries["wallet_owner_identity_inference_authorized"])
        self.assertFalse(boundaries["automatic_risk_conclusion_authorized"])
        self.assertFalse(boundaries["trade_recommendation_authorized"])
        self.assertFalse(boundaries["source_independence_verified"])
        self.assertFalse(result["data"]["execution_authorized"])
        self.assertFalse(result["execution_authorized"])

    def test_next_trade_price_can_remain_unavailable_without_blocking_core_trade(self):
        result = self.build(next_execution_evidence=None)

        self.assertEqual(result["status"], "ok")
        next_trade = result["data"]["next_verified_trade"]
        self.assertFalse(next_trade["verified"])
        self.assertEqual(next_trade["signature"], NEXT)
        self.assertIsNone(next_trade["execution_price_native"])
        self.assertTrue(
            any(
                warning.get("code") == "next_trade_price_not_verified"
                for warning in result["warnings"]
            )
        )

    def test_multi_amm_routing_fails_closed(self):
        routing = routing_evidence()
        routing.update(
            {
                "ambiguity_cause": (
                    "selected_pool_plus_additional_recognized_amm_instruction"
                ),
                "recognized_amm_instruction_count_normalized": 2,
                "additional_recognized_instruction_count_normalized": 1,
                "genuine_instruction_multiplicity_observed": True,
            }
        )
        with self.assertRaisesRegex(
            TradePriceImpactIntelligenceError,
            "routed or multi-AMM",
        ):
            self.build(routing_evidence=routing)

    def test_incomplete_window_cannot_claim_volume_contribution(self):
        window = pool_window()
        window["transactions_24h_window_coverage_verified"] = False

        with self.assertRaisesRegex(
            TradePriceImpactIntelligenceError,
            "pool_window.transactions_24h_window_coverage_verified",
        ):
            self.build(pool_window=window)

    def test_wallet_and_pool_direction_must_agree(self):
        wallet = wallet_observation()
        wallet["activity_type"] = "SELL"

        with self.assertRaisesRegex(
            TradePriceImpactIntelligenceError,
            "directions disagree",
        ):
            self.build(wallet_observation=wallet)

    def test_same_slot_activity_keeps_next_trade_ordering_unverified(self):
        window = pool_window()
        window["transactions"][1]["slot"] = 100

        result = self.build(
            pool_window=window,
            next_execution_evidence=None,
        )
        self.assertFalse(result["data"]["next_verified_trade"]["verified"])
        self.assertEqual(
            result["data"]["next_verified_trade"]["reason"],
            "same_slot_ordering_unavailable",
        )

    def test_next_execution_evidence_must_match_deterministic_next_swap(self):
        wrong = next_execution_evidence()
        wrong["transaction_signature"] = "OtherSig"

        with self.assertRaisesRegex(
            TradePriceImpactIntelligenceError,
            "does not match the deterministic next pool swap",
        ):
            self.build(next_execution_evidence=wrong)

    def test_exact_execution_price_is_revalidated_from_pool_leg_amounts(self):
        bad = execution_evidence(price="11.9")
        with self.assertRaisesRegex(
            TradePriceImpactIntelligenceError,
            "execution price does not equal exact quote/asset",
        ):
            self.build(execution_evidence=bad)

    def test_source_evidence_cannot_authorize_execution(self):
        for name, evidence in (
            ("execution", execution_evidence()),
            ("routing", routing_evidence()),
            ("window", pool_window()),
        ):
            with self.subTest(name=name):
                bad = deepcopy(evidence)
                bad["execution_authorized"] = True
                kwargs = {
                    "execution_evidence": bad
                    if name == "execution"
                    else execution_evidence(),
                    "routing_evidence": bad
                    if name == "routing"
                    else routing_evidence(),
                    "pool_window": bad if name == "window" else pool_window(),
                }
                with self.assertRaises(TradePriceImpactIntelligenceError):
                    self.build(**kwargs)


if __name__ == "__main__":
    unittest.main()
