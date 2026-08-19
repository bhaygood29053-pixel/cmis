import unittest

from liquidity_scout.services.cmis_activity_transactions import (
    attach_transaction_aggregation,
)


def event(signature, pool, side, *, exact=True, asset_amount="10", quote_amount="1"):
    exact_leg = None
    basis = "SIGNER_OR_ROUTED_BALANCE_DIRECTION"
    if exact:
        basis = "EXACT_POOL_LEG_AMOUNTS"
        exact_leg = {
            "side": side,
            "asset_mint": "agi-mint",
            "asset_account": "asset-" + pool,
            "asset_amount": asset_amount,
            "quote_mint": "quote",
            "quote_account": "quote-" + pool,
            "quote_amount": quote_amount,
        }

    return {
        "status": "ok",
        "pool_address": pool,
        "transaction_signature": signature,
        "provider_type": side.lower(),
        "side": side,
        "side_verified": True,
        "asset_scope_verified": True,
        "asset_mint": "agi-mint",
        "quote_mint": "quote",
        "verification_level": "PROVIDER_SIDE_ONCHAIN_CONFIRMED",
        "verification_basis": basis,
        "identity": {"identity_verified": True},
        "exact_pool_leg": exact_leg,
        "warnings": [],
        "errors": [],
    }


def envelope(events, pools):
    return {
        "service": "verified_asset_activity",
        "chain": "x1",
        "status": "ok",
        "asset": {"symbol": "AGI", "mint": "agi-mint"},
        "data": {
            "swap_candidate_count": len(events),
            "verified_trade_count": len(events),
            "verified_buy_count": sum(1 for e in events if e["side"] == "BUY"),
            "verified_sell_count": sum(1 for e in events if e["side"] == "SELL"),
            "exact_amount_verified_trade_count": len(events),
            "exact_verified_asset_amounts": {
                "buy_asset_amount": "999",
                "sell_asset_amount": "999",
            },
            "exact_verified_quote_amounts_by_mint": {},
            "pools": pools,
            "events": events,
        },
        "confidence": {"verification_ratio": 1.0 if events else None},
        "sources": [],
        "warnings": [],
        "errors": [],
    }


class TransactionAggregationTests(unittest.TestCase):
    def test_same_signature_across_two_pools_is_one_transaction_two_legs(self):
        result = attach_transaction_aggregation(
            envelope(
                [
                    event("sig-1", "pool-a", "BUY"),
                    event("sig-1", "pool-b", "BUY"),
                ],
                [
                    {"pool_address": "pool-a"},
                    {"pool_address": "pool-b"},
                ],
            )
        )

        data = result["data"]
        self.assertEqual(data["aggregation_version"], "1.1")
        self.assertEqual(data["unique_transaction_count"], 1)
        self.assertEqual(data["verified_transaction_count"], 1)
        self.assertEqual(data["verified_buy_transaction_count"], 1)
        self.assertEqual(data["verified_pool_leg_count"], 2)
        self.assertEqual(data["multi_pool_transaction_count"], 1)
        self.assertEqual(data["multi_leg_verified_transaction_count"], 1)
        self.assertEqual(data["transactions"][0]["activity_side"], "BUY")
        self.assertEqual(
            data["exact_verified_asset_amounts"]["buy_asset_amount"],
            "20",
        )
        self.assertIsNone(
            data["exact_verified_asset_amounts"]["sell_asset_amount"]
        )
        self.assertEqual(
            data["exact_verified_quote_amounts_by_mint"]["quote"]["buy_quote_amount"],
            "2",
        )
        self.assertIsNone(
            data["exact_verified_quote_amounts_by_mint"]["quote"]["sell_quote_amount"]
        )

    def test_duplicate_same_pool_leg_does_not_double_count_amounts(self):
        duplicate = event("sig-2", "pool-a", "SELL")
        result = attach_transaction_aggregation(
            envelope(
                [duplicate, duplicate],
                [{"pool_address": "pool-a"}],
            )
        )

        data = result["data"]
        self.assertEqual(data["unique_transaction_count"], 1)
        self.assertEqual(data["verified_transaction_count"], 1)
        self.assertEqual(data["verified_pool_leg_count"], 1)
        self.assertEqual(data["verified_sell_pool_leg_count"], 1)
        self.assertEqual(data["exact_amount_verified_trade_count"], 1)
        self.assertIsNone(
            data["exact_verified_asset_amounts"]["buy_asset_amount"]
        )
        self.assertEqual(
            data["exact_verified_asset_amounts"]["sell_asset_amount"],
            "10",
        )
        self.assertIsNone(
            data["exact_verified_quote_amounts_by_mint"]["quote"]["buy_quote_amount"]
        )
        self.assertEqual(
            data["exact_verified_quote_amounts_by_mint"]["quote"][
                "sell_quote_amount"
            ],
            "1",
        )

    def test_empty_events_do_not_invent_zero_amounts(self):
        result = attach_transaction_aggregation(envelope([], []))
        data = result["data"]
        self.assertEqual(data["exact_amount_verified_trade_count"], 0)
        self.assertIsNone(data["exact_verified_asset_amounts"]["buy_asset_amount"])
        self.assertIsNone(data["exact_verified_asset_amounts"]["sell_asset_amount"])
        self.assertEqual(data["exact_verified_quote_amounts_by_mint"], {})
        self.assertIsNone(result["confidence"]["verification_ratio"])

    def test_verified_numeric_zero_remains_zero(self):
        result = attach_transaction_aggregation(
            envelope(
                [event("sig-zero", "pool-a", "BUY", asset_amount="0", quote_amount="0")],
                [{"pool_address": "pool-a"}],
            )
        )
        data = result["data"]
        self.assertEqual(data["exact_amount_verified_trade_count"], 1)
        self.assertEqual(data["exact_verified_asset_amounts"]["buy_asset_amount"], "0")
        self.assertIsNone(data["exact_verified_asset_amounts"]["sell_asset_amount"])
        self.assertEqual(
            data["exact_verified_quote_amounts_by_mint"]["quote"]["buy_quote_amount"],
            "0",
        )
        self.assertIsNone(
            data["exact_verified_quote_amounts_by_mint"]["quote"]["sell_quote_amount"]
        )

    def test_buy_and_sell_legs_in_same_signature_are_mixed_transaction(self):
        result = attach_transaction_aggregation(
            envelope(
                [
                    event("sig-3", "pool-a", "BUY", exact=False),
                    event("sig-3", "pool-b", "SELL", exact=False),
                ],
                [
                    {"pool_address": "pool-a"},
                    {"pool_address": "pool-b"},
                ],
            )
        )

        data = result["data"]
        self.assertEqual(data["verified_transaction_count"], 1)
        self.assertEqual(data["verified_mixed_transaction_count"], 1)
        self.assertEqual(data["verified_buy_transaction_count"], 0)
        self.assertEqual(data["verified_sell_transaction_count"], 0)
        self.assertEqual(data["verified_pool_leg_count"], 2)
        self.assertEqual(data["transactions"][0]["activity_side"], "MIXED")
        self.assertIsNone(data["exact_verified_asset_amounts"]["buy_asset_amount"])
        self.assertIsNone(data["exact_verified_asset_amounts"]["sell_asset_amount"])


if __name__ == "__main__":
    unittest.main()