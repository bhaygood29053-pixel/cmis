import os
import unittest

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_history import (
    OBSERVED_TRADE_HISTORY_TOP_LEVEL_KEYS,
    OBSERVED_TRADE_ROW_KEYS,
    fetch_pool_trades_raw,
)


RUN_LIVE = os.getenv("RUN_X1_NINJA_LIVE_TESTS") == "1"


def _text(value):
    text = str(value or "").strip()
    return text or None


def _pool_address(pool):
    if not isinstance(pool, dict):
        return None
    return _text(
        pool.get("address")
        or pool.get("poolAddress")
        or pool.get("pool_address")
        or pool.get("id")
    )


def _sample_without_maker(row):
    if not isinstance(row, dict):
        return None
    fields = (
        "amountNative",
        "amountToken",
        "amountUsd",
        "poolAddress",
        "priceNative",
        "priceUsd",
        "slot",
        "timestamp",
        "txHash",
        "type",
    )
    return {field: row.get(field) for field in fields}


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIVE_TESTS=1 to run the read-only X1.Ninja contract probe",
)
class X1NinjaTradeHistoryLiveTests(unittest.TestCase):
    def test_live_trade_history_structure_and_semantic_candidates(self):
        pools, _xnt_price = fetch_all_pools(sleep_seconds=0)
        self.assertTrue(pools, "X1.Ninja pool catalog returned no pools")

        selected = next(
            (
                pool
                for pool in pools
                if isinstance(pool, dict) and _pool_address(pool)
            ),
            None,
        )
        self.assertIsNotNone(selected, "no pool with a usable address was returned")
        address = _pool_address(selected)

        result = fetch_pool_trades_raw(address)
        body = result["raw_response"]
        trades = body["trades"]
        contract = result["contract"]

        print("X1.Ninja live trade-history contract probe")
        print(f"Pool address: {address}")
        print(f"Response contract verified: {contract['response_contract_verified']}")
        print(f"Trade row shape verified: {contract['trade_row_shape_verified']}")
        print(f"Top-level keys: {contract['top_level_keys']}")
        print(f"Trade row keys: {contract['trade_row_keys']}")
        print(
            "Provider metadata: "
            f"total={contract['provider_total_raw']!r} "
            f"({type(contract['provider_total_raw']).__name__}), "
            f"lastUpdated={contract['provider_last_updated_raw']!r} "
            f"({type(contract['provider_last_updated_raw']).__name__})"
        )
        print(f"Returned trade rows: {contract['returned_trade_count']}")
        print(f"Rate limit: {result['rate_limit']}")

        types = sorted(
            {
                str(row.get("type"))
                for row in trades
                if isinstance(row, dict) and row.get("type") is not None
            }
        )
        print(f"Observed type values: {types}")
        sample = next((row for row in trades if isinstance(row, dict)), None)
        print(f"First trade sample (maker omitted): {_sample_without_maker(sample)}")
        print(f"CMIS promotable: {result['cmis_promotable']}")
        print(f"Semantic gates: {result['semantics']}")

        self.assertEqual(result["pool_address"], address)
        self.assertEqual(result["response_shape"], "object")
        self.assertTrue(OBSERVED_TRADE_HISTORY_TOP_LEVEL_KEYS.issubset(body.keys()))
        self.assertIsInstance(trades, list)
        for row in trades:
            self.assertIsInstance(row, dict)
            self.assertTrue(OBSERVED_TRADE_ROW_KEYS.issubset(row.keys()))

        self.assertTrue(contract["response_contract_verified"])
        self.assertTrue(contract["trade_row_shape_verified"])
        self.assertEqual(contract["returned_trade_count"], len(trades))
        self.assertTrue(result["rate_limit"]["limit"])
        self.assertTrue(result["rate_limit"]["remaining"])
        self.assertTrue(result["rate_limit"]["reset"])
        self.assertTrue(result["semantics"]["trade_rows_verified"])
        for key, value in result["semantics"].items():
            if key != "trade_rows_verified":
                self.assertFalse(value, key)
        self.assertFalse(result["cmis_promotable"])


if __name__ == "__main__":
    unittest.main()
