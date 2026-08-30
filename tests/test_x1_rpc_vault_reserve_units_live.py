import json
import os
import unittest

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.rpc_vault_reserve_units import (
    verify_rpc_vault_reserve_units,
)
from liquidity_scout.providers.x1.xdex import fetch_pool_list


RUN_LIVE = os.getenv("RUN_X1_RPC_VAULT_RESERVE_UNITS_LIVE") == "1"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_RPC_VAULT_RESERVE_UNITS_LIVE=1 to run read-only evidence",
)
class RPCVaultReserveUnitsLiveTests(unittest.TestCase):
    def test_live_rpc_vault_balances_and_units_verify_across_current_pools(self):
        ninja_pools, _ = fetch_all_pools(sleep_seconds=0)
        xdex_pools = fetch_pool_list(network="X1 Mainnet")

        self.assertTrue(ninja_pools, "X1.Ninja returned no current pools")
        self.assertTrue(xdex_pools, "XDEX returned no X1 Mainnet pools")

        result = verify_rpc_vault_reserve_units(
            ninja_pools=ninja_pools,
            xdex_pools=xdex_pools,
            min_verified_pools=3,
            max_samples=5,
            signature_limit=1,
        )

        public = {
            "status": result["status"],
            "common_pool_count_observed": result["common_pool_count_observed"],
            "selected_sample_count": result["selected_sample_count"],
            "verified_sample_count": result["verified_sample_count"],
            "minimum_verified_pool_count": result["minimum_verified_pool_count"],
            "all_selected_samples_verified": result[
                "all_selected_samples_verified"
            ],
            "position_mapping_verified": result["position_mapping_verified"],
            "rpc_vault_balance_fields_verified": result[
                "rpc_vault_balance_fields_verified"
            ],
            "rpc_vault_decimals_verified": result[
                "rpc_vault_decimals_verified"
            ],
            "rpc_reserve_unit_scaling_verified": result[
                "rpc_reserve_unit_scaling_verified"
            ],
            "rpc_vault_reserve_amounts_verified": result[
                "rpc_vault_reserve_amounts_verified"
            ],
            "base_quote_semantics_verified": result[
                "base_quote_semantics_verified"
            ],
            "provider_candidate_semantics_verified": result[
                "provider_candidate_semantics_verified"
            ],
            "samples": result["samples"],
            "semantics": result["semantics"],
            "cmis_promotable": result["cmis_promotable"],
            "execution_authorized": result["execution_authorized"],
        }
        print(
            "[X1 RPC vault reserve-unit evidence] "
            + json.dumps(public, sort_keys=True, default=str)
        )

        self.assertEqual(result["status"], "verified")
        self.assertGreaterEqual(result["verified_sample_count"], 3)
        self.assertTrue(result["all_selected_samples_verified"])
        self.assertTrue(result["position_mapping_verified"])
        self.assertTrue(result["rpc_vault_balance_fields_verified"])
        self.assertTrue(result["rpc_vault_decimals_verified"])
        self.assertTrue(result["rpc_reserve_unit_scaling_verified"])
        self.assertTrue(result["rpc_vault_reserve_amounts_verified"])
        self.assertFalse(result["base_quote_semantics_verified"])
        self.assertFalse(result["provider_candidate_semantics_verified"])
        self.assertTrue(all(v is False for v in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
