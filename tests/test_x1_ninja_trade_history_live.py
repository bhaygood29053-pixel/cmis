import os
import unittest

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw


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


def _shape_summary(body):
    summary = {"type": type(body).__name__}
    if isinstance(body, dict):
        summary["top_level_keys"] = sorted(str(key) for key in body.keys())
        list_fields = []
        for key, value in body.items():
            if isinstance(value, list):
                item_keys = None
                first = next((item for item in value if isinstance(item, dict)), None)
                if first is not None:
                    item_keys = sorted(str(item_key) for item_key in first.keys())
                list_fields.append({
                    "field": str(key),
                    "count": len(value),
                    "first_object_keys": item_keys,
                })
        summary["list_fields"] = list_fields
    elif isinstance(body, list):
        summary["count"] = len(body)
        first = next((item for item in body if isinstance(item, dict)), None)
        summary["first_object_keys"] = (
            sorted(str(key) for key in first.keys()) if first is not None else None
        )
    return summary


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIVE_TESTS=1 to run the read-only X1.Ninja contract probe",
)
class X1NinjaTradeHistoryLiveTests(unittest.TestCase):
    def test_live_trade_history_response_shape_without_semantic_promotion(self):
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

        print("X1.Ninja live trade-history contract probe")
        print(f"Pool address: {address}")
        print(f"Response shape: {result['response_shape']}")
        print(f"Rate limit: {result['rate_limit']}")
        print(f"Shape summary: {_shape_summary(result['raw_response'])}")
        print(f"CMIS promotable: {result['cmis_promotable']}")
        print(f"Semantic gates: {result['semantics']}")

        self.assertEqual(result["pool_address"], address)
        self.assertTrue(result["rate_limit"]["limit"])
        self.assertTrue(result["rate_limit"]["remaining"])
        self.assertTrue(result["rate_limit"]["reset"])
        self.assertFalse(result["cmis_promotable"])
        self.assertTrue(all(value is False for value in result["semantics"].values()))


if __name__ == "__main__":
    unittest.main()
