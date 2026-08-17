import os
import unittest

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_history import (
    fetch_pool_ohlcv_raw,
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


def _response_summary(body):
    if isinstance(body, dict):
        return {
            "type": "object",
            "keys": sorted(str(key) for key in body.keys()),
            "size": len(body),
        }

    if isinstance(body, list):
        first = body[0] if body else None
        return {
            "type": "array",
            "length": len(body),
            "first_item_type": type(first).__name__ if first is not None else None,
            "first_item_keys": (
                sorted(str(key) for key in first.keys())
                if isinstance(first, dict)
                else None
            ),
        }

    return {
        "type": type(body).__name__,
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIVE_TESTS=1 to run the read-only X1.Ninja OHLCV probe",
)
class X1NinjaOHLCVLiveTests(unittest.TestCase):
    def test_live_ohlcv_raw_contract_without_semantic_promotion(self):
        pools, _xnt_price = fetch_all_pools(sleep_seconds=0)
        self.assertTrue(
            pools,
            "X1.Ninja pool catalog returned no pools",
        )

        selected = next(
            (
                pool
                for pool in pools
                if isinstance(pool, dict) and _pool_address(pool)
            ),
            None,
        )
        self.assertIsNotNone(
            selected,
            "no pool with a usable address was returned",
        )

        address = _pool_address(selected)

        result = fetch_pool_ohlcv_raw(
            address,
            timeframe="1h",
            limit=5,
        )

        body = result["raw_response"]
        contract = result["contract"]

        print("X1.Ninja live OHLCV contract probe")
        print(f"Pool address: {address}")
        print(f"Timeframe: {result['timeframe']}")
        print(f"Requested limit: {result['requested_limit']}")
        print(f"Observed at: {result['observed_at']}")
        print(f"Rate limit: {result['rate_limit']}")
        print(f"Raw response summary: {_response_summary(body)}")
        print(f"Raw response sample: {body}")
        print(f"Contract gates: {contract}")
        print(f"Semantic gates: {result['semantics']}")
        print(f"CMIS promotable: {result['cmis_promotable']}")

        self.assertEqual(result["pool_address"], address)
        self.assertEqual(result["timeframe"], "1h")
        self.assertEqual(result["requested_limit"], 5)

        self.assertTrue(
            contract["request_contract_verified"]
        )
        self.assertTrue(
            contract["response_json_verified"]
        )
        self.assertTrue(
            contract["candle_schema_verified"]
        )
        self.assertTrue(
            contract["response_contract_verified"]
        )
        self.assertTrue(
            contract["candle_row_shape_verified"]
        )

        self.assertTrue(result["rate_limit"]["limit"])
        self.assertTrue(result["rate_limit"]["remaining"])
        self.assertTrue(result["rate_limit"]["reset"])

        for key, value in result["semantics"].items():
            self.assertFalse(value, key)

        self.assertFalse(result["cmis_promotable"])


if __name__ == "__main__":
    unittest.main()
