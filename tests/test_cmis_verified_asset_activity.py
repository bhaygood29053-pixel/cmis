import unittest

from liquidity_scout.services.cmis_verified_asset_activity import (
    build_verified_asset_activity_response,
)


def market(status="ok"):
    return {
        "service": "market_report",
        "chain": "x1",
        "status": status,
        "asset": {"symbol": "AGI", "name": "AGI", "mint": "agi-mint"},
        "data": {
            "price_usd": 1.0,
            "liquidity_usd": 1000.0,
            "volume_24h_usd": 500.0,
            "transactions_24h": 10,
            "lp_count": 1,
            "completeness": {
                "price": True,
                "liquidity": True,
                "volume_24h": True,
                "transactions_24h": True,
                "holders": True,
            },
        },
        "sources": [{"source": "market", "role": "market_report"}],
        "observed_at": 1.0,
    }


def verification(side, *, mint="agi-mint", status="ok", quote_mint="quote"):
    return {
        "service": "trade_verification",
        "chain": "x1",
        "status": status,
        "data": {
            "provider_type": side.lower(),
            "transaction_signature": "sig-" + side.lower(),
            "side": side,
            "side_verified": status == "ok",
            "asset_mint": mint,
            "quote_mint": quote_mint,
            "verification_level": "PROVIDER_SIDE_ONCHAIN_CONFIRMED",
            "verification_basis": "EXACT_POOL_LEG_AMOUNTS",
            "identity": {"identity_verified": True},
            "pool_leg": {
                "side": side,
                "asset_mint": mint,
                "asset_amount": "2",
                "quote_mint": quote_mint,
                "quote_amount": "1",
            },
        },
        "warnings": [],
        "errors": [],
    }


class VerifiedAssetActivityServiceTests(unittest.TestCase):
    def test_holder_only_market_partial_does_not_downgrade_activity(self):
        market_envelope = market(status="partial")
        market_envelope["data"]["completeness"]["holders"] = False
        market_envelope["warnings"] = [{"code": "holders_incomplete"}]

        result = build_verified_asset_activity_response(
            market_envelope=market_envelope,
            pool_records=[{
                "pool_address": "pool-1",
                "pair": "AGI/XNT",
                "history_ok": True,
                "provider_event_count": 1,
                "processed_event_count": 1,
                "verifications": [verification("BUY")],
            }],
            matched_pool_count=1,
            selected_pool_count=1,
        )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["confidence"]["market_complete"])
        self.assertNotIn(
            "market_snapshot_partial",
            {warning["code"] for warning in result["warnings"]},
        )

    def test_counts_only_matching_asset_and_exact_chain_amounts(self):
        result = build_verified_asset_activity_response(
            market_envelope=market(),
            pool_records=[{
                "pool_address": "pool-1",
                "pair": "AGI/XNT",
                "history_ok": True,
                "provider_event_count": 3,
                "processed_event_count": 3,
                "verifications": [
                    verification("BUY"),
                    verification("SELL"),
                    verification("BUY", mint="other-mint"),
                ],
            }],
            matched_pool_count=1,
            selected_pool_count=1,
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["data"]["verified_trade_count"], 2)
        self.assertEqual(result["data"]["verified_buy_count"], 1)
        self.assertEqual(result["data"]["verified_sell_count"], 1)
        self.assertEqual(result["data"]["asset_scope_mismatch_count"], 1)
        self.assertEqual(
            result["data"]["exact_verified_asset_amounts"]["buy_asset_amount"],
            "2",
        )

    def test_empty_full_history_can_be_complete_without_inventing_evidence(self):
        result = build_verified_asset_activity_response(
            market_envelope=market(),
            pool_records=[{
                "pool_address": "pool-1",
                "pair": "AGI/XNT",
                "history_ok": True,
                "provider_event_count": 0,
                "processed_event_count": 0,
                "verifications": [],
            }],
            matched_pool_count=1,
            selected_pool_count=1,
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["confidence"]["complete"])
        self.assertIsNone(result["confidence"]["verification_ratio"])
        self.assertIsNone(
            result["data"]["exact_verified_asset_amounts"]["buy_asset_amount"]
        )
        self.assertIsNone(
            result["data"]["exact_verified_asset_amounts"]["sell_asset_amount"]
        )

    def test_missing_side_amount_stays_null_when_other_side_is_verified(self):
        result = build_verified_asset_activity_response(
            market_envelope=market(),
            pool_records=[{
                "pool_address": "pool-1",
                "pair": "AGI/XNT",
                "history_ok": True,
                "provider_event_count": 1,
                "processed_event_count": 1,
                "verifications": [verification("SELL")],
            }],
            matched_pool_count=1,
            selected_pool_count=1,
        )

        amounts = result["data"]["exact_verified_asset_amounts"]
        self.assertIsNone(amounts["buy_asset_amount"])
        self.assertEqual(amounts["sell_asset_amount"], "2")
        self.assertEqual(result["confidence"]["verification_ratio"], 1.0)

    def test_bounded_event_coverage_is_partial(self):
        result = build_verified_asset_activity_response(
            market_envelope=market(),
            pool_records=[{
                "pool_address": "pool-1",
                "pair": "AGI/XNT",
                "history_ok": True,
                "provider_event_count": 10,
                "processed_event_count": 1,
                "verifications": [verification("BUY")],
            }],
            matched_pool_count=1,
            selected_pool_count=1,
        )
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["confidence"]["event_coverage_complete"])


if __name__ == "__main__":
    unittest.main()