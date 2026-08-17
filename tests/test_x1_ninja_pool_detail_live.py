import os
import unittest

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_pool_detail import fetch_pool_detail_raw


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


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIVE_TESTS=1 to run the read-only pool-detail probe",
)
class X1NinjaPoolDetailLiveTests(unittest.TestCase):
    def test_live_pool_detail_contract_without_reserve_semantic_promotion(self):
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
        result = fetch_pool_detail_raw(address)

        print("X1.Ninja live pool-detail contract probe")
        print(f"Requested pool: {address}")
        print(f"Observed at: {result['observed_at']}")
        print(f"Top-level keys: {result['contract']['top_level_keys']}")
        print(
            "Lexical reserve fields: "
            f"{result['contract']['lexical_reserve_field_paths']}"
        )
        print(
            "Raw identifier candidates: "
            f"{result['identity']['raw_identifier_candidates']}"
        )
        print(f"Raw pool detail: {result['raw_response']}")
        print(f"Semantic gates: {result['semantics']}")
        print(f"CMIS promotable: {result['cmis_promotable']}")

        self.assertEqual(result["pool_address_requested"], address)
        self.assertTrue(result["contract"]["request_contract_verified"])
        self.assertTrue(result["contract"]["response_json_verified"])
        self.assertTrue(result["contract"]["rate_limit_headers_verified"])
        self.assertFalse(result["identity"]["pool_identity_verified"])
        for name, verified in result["semantics"].items():
            self.assertFalse(verified, name)
        self.assertFalse(result["cmis_promotable"])


if __name__ == "__main__":
    unittest.main()
