import os
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.rpc_supply import (
    X1_NATIVE_BASE_UNITS_PER_XNT,
    get_network_supply_rpc,
)
from liquidity_scout.providers.x1.supply import X1SupplyProvider


RUN_LIVE = os.getenv("RUN_X1_SUPPLY_LIVE_TESTS") == "1"


def _absolute_delta(left, right):
    return abs(Decimal(str(left)) - Decimal(str(right)))


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_SUPPLY_LIVE_TESTS=1 to run the read-only native XNT supply cross-check",
)
class X1NativeSupplyCrossCheckLiveTests(unittest.TestCase):
    def test_api_x1_xyz_against_finalized_x1_rpc_get_supply(self):
        api = X1SupplyProvider().get_supply()
        rpc = get_network_supply_rpc()

        api_total = api["total"]["supply"]
        api_circulating = api["circulating"]["supply"]
        rpc_total = rpc["total_raw"]
        rpc_circulating = rpc["circulating_raw"]
        rpc_non_circulating = rpc["non_circulating_raw"]

        rpc_components_match = (
            int(rpc_total) == int(rpc_circulating) + int(rpc_non_circulating)
        )

        total_delta_xnt = _absolute_delta(rpc["total_xnt"], api_total)
        circulating_delta_xnt = _absolute_delta(
            rpc["circulating_xnt"],
            api_circulating,
        )
        total_whole_token_compatible = total_delta_xnt < Decimal("1")
        circulating_whole_token_compatible = circulating_delta_xnt < Decimal("1")

        print("Native XNT supply cross-check")
        print(f"Verified X1 SDK base units per native token: {X1_NATIVE_BASE_UNITS_PER_XNT}")
        print(f"Unit provenance: {rpc['unit_source']}")
        print(f"api.x1.xyz total whole-XNT observation: {api_total}")
        print(f"api.x1.xyz circulating whole-XNT observation: {api_circulating}")
        print(f"X1 RPC total raw base units: {rpc_total}")
        print(f"X1 RPC circulating raw base units: {rpc_circulating}")
        print(f"X1 RPC non-circulating raw base units: {rpc_non_circulating}")
        print(f"X1 RPC total exact XNT: {rpc['total_xnt']}")
        print(f"X1 RPC circulating exact XNT: {rpc['circulating_xnt']}")
        print(f"X1 RPC non-circulating exact XNT: {rpc['non_circulating_xnt']}")
        print(f"X1 RPC context slot: {rpc['context_slot']}")
        print(f"RPC total == circulating + non-circulating: {rpc_components_match}")
        print(f"Total source delta XNT: {total_delta_xnt}")
        print(f"Circulating source delta XNT: {circulating_delta_xnt}")
        print(
            "api.x1.xyz total compatible with precise RPC within <1 XNT: "
            f"{total_whole_token_compatible}"
        )
        print(
            "api.x1.xyz circulating compatible with precise RPC within <1 XNT: "
            f"{circulating_whole_token_compatible}"
        )
        print(f"api.x1.xyz exact rounding rule verified: {rpc['api_x1_xyz_rounding_verified']}")
        print(
            "CMIS cross-source supply promotion: PARTIAL candidate — precise RPC unit "
            "conversion verified; API whole-token rounding rule still unverified"
        )

        self.assertEqual(api["chain"], "x1")
        self.assertEqual(api["asset"], "XNT")
        self.assertEqual(rpc["chain"], "x1")
        self.assertEqual(rpc["asset"], "XNT")
        self.assertTrue(api_total.isdigit())
        self.assertTrue(api_circulating.isdigit())
        self.assertTrue(rpc_total.isdigit())
        self.assertTrue(rpc_circulating.isdigit())
        self.assertTrue(rpc_non_circulating.isdigit())
        self.assertTrue(rpc_components_match)
        self.assertTrue(rpc["units_verified_by_x1_sdk"])
        self.assertEqual(rpc["base_units_per_xnt"], 1_000_000_000)
        self.assertTrue(total_whole_token_compatible)
        self.assertTrue(circulating_whole_token_compatible)
        self.assertFalse(rpc["api_x1_xyz_rounding_verified"])


if __name__ == "__main__":
    unittest.main()
