import os
import unittest

from liquidity_scout.providers.x1.ninja_pool_catalog import (
    fetch_pool_catalog_raw,
)


RUN_LIVE = os.getenv("RUN_X1_NINJA_CATALOG_LIVE") == "1"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_CATALOG_LIVE=1 to run the read-only catalog probe",
)
class X1NinjaPoolCatalogLiveTests(unittest.TestCase):
    def test_current_developer_api_catalog_transport_and_shape(self):
        result = fetch_pool_catalog_raw(limit=5)
        contract = result["contract"]

        print("X1.Ninja Developer API pool-catalog evidence")
        print(f"Observed at: {result['observed_at']}")
        print(f"Endpoint: {result['endpoint']}")
        print(f"Requested limit: {result['requested_limit']}")
        print(f"Returned pools: {contract['returned_pool_count']}")
        print(f"Top-level keys: {contract['top_level_keys']}")
        print(f"Pool-row keys: {contract['pool_row_keys']}")
        print(
            "Pagination candidate values (raw): "
            f"{contract['pagination_candidate_values_raw']}"
        )
        print(f"Rate-limit headers: {sorted(result['rate_limit'].keys())}")
        print(f"Semantic gates: {result['semantics']}")
        print(f"CMIS promotable: {result['cmis_promotable']}")
        print(f"Execution authorized: {result['execution_authorized']}")

        self.assertTrue(contract["request_contract_verified"])
        self.assertTrue(contract["response_json_verified"])
        self.assertTrue(contract["pool_array_verified"])
        self.assertTrue(contract["pool_row_object_shape_verified"])
        self.assertGreaterEqual(contract["returned_pool_count"], 0)
        self.assertTrue(result["rate_limit"]["limit"])
        self.assertTrue(result["rate_limit"]["remaining"])
        self.assertTrue(result["rate_limit"]["reset"])
        self.assertTrue(all(value is False for value in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
