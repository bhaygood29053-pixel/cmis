import json
import os
import unittest

from liquidity_scout.providers.x1.exact_pool_triangulation import (
    triangulate_exact_pool_identity,
)
from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.xdex import fetch_pool_list


RUN_LIVE = os.getenv("RUN_X1_EXACT_POOL_TRIANGULATION_LIVE") == "1"


def _public_result(result):
    return {
        "status": result.get("status"),
        "pool_address": result.get("pool_address"),
        "program_id": result.get("program_id"),
        "rpc_mints": result.get("rpc_mints"),
        "rpc_vaults": result.get("rpc_vaults"),
        "provider_identity": result.get("provider_identity"),
        "identity": result.get("identity"),
        "semantics": result.get("semantics"),
        "common_pool_count_observed": result.get("common_pool_count_observed"),
        "attempt_count": result.get("attempt_count"),
        "cmis_promotable": result.get("cmis_promotable"),
        "execution_authorized": result.get("execution_authorized"),
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_EXACT_POOL_TRIANGULATION_LIVE=1 to run read-only evidence",
)
class X1ExactPoolTriangulationLiveTests(unittest.TestCase):
    def test_one_exact_pool_is_bound_across_ninja_xdex_and_rpc(self):
        ninja_pools, _xnt_price = fetch_all_pools(sleep_seconds=0)
        xdex_pools = fetch_pool_list()

        self.assertTrue(ninja_pools, "X1.Ninja returned no current pools")
        self.assertTrue(xdex_pools, "XDEX public API returned no current pools")

        result = triangulate_exact_pool_identity(
            ninja_pools=ninja_pools,
            xdex_pools=xdex_pools,
            signature_limit=1,
        )

        print(
            "[X1 exact pool triangulation evidence] "
            + json.dumps(_public_result(result), sort_keys=True, default=str)
        )

        self.assertEqual(
            result["status"],
            "verified",
            "No exact current pool reached full Ninja/XDEX/RPC identity proof.",
        )
        self.assertTrue(result["identity"]["pool_identity_verified"])
        self.assertTrue(result["identity"]["token_set_identity_verified"])
        self.assertTrue(result["identity"]["base_quote_orientation_verified"])
        self.assertTrue(result["identity"]["rpc_mint_identity_verified"])
        self.assertFalse(
            result["identity"]["onchain_mint_slot_base_quote_semantics_verified"]
        )
        self.assertTrue(all(v is False for v in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
