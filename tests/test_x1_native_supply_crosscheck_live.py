import os
import unittest

from liquidity_scout.providers.x1.rpc_supply import get_network_supply_rpc
from liquidity_scout.providers.x1.supply import X1SupplyProvider


RUN_LIVE = os.getenv("RUN_X1_SUPPLY_LIVE_TESTS") == "1"


def _integer_ratio(raw_base_units, provider_units):
    raw = int(raw_base_units)
    provider = int(provider_units)
    if provider == 0:
        return 1 if raw == 0 else None
    quotient, remainder = divmod(raw, provider)
    return quotient if remainder == 0 else None


def _is_power_of_ten(value):
    if not isinstance(value, int) or value <= 0:
        return False
    while value % 10 == 0:
        value //= 10
    return value == 1


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

        total_ratio = _integer_ratio(rpc_total, api_total)
        circulating_ratio = _integer_ratio(rpc_circulating, api_circulating)
        shared_ratio = (
            total_ratio
            if total_ratio is not None and total_ratio == circulating_ratio
            else None
        )

        rpc_components_match = (
            int(rpc_total) == int(rpc_circulating) + int(rpc_non_circulating)
        )
        scaled_values_match = False
        if shared_ratio is not None:
            scaled_values_match = (
                int(api_total) * shared_ratio == int(rpc_total)
                and int(api_circulating) * shared_ratio == int(rpc_circulating)
            )

        print("Native XNT supply cross-check")
        print(f"api.x1.xyz total: {api_total}")
        print(f"api.x1.xyz circulating: {api_circulating}")
        print(f"X1 RPC total raw: {rpc_total}")
        print(f"X1 RPC circulating raw: {rpc_circulating}")
        print(f"X1 RPC non-circulating raw: {rpc_non_circulating}")
        print(f"X1 RPC context slot: {rpc['context_slot']}")
        print(f"RPC total == circulating + non-circulating: {rpc_components_match}")
        print(f"Exact integer scale candidate (total): {total_ratio}")
        print(f"Exact integer scale candidate (circulating): {circulating_ratio}")
        print(f"Shared scale candidate: {shared_ratio}")
        print(f"Shared scale is power of ten: {_is_power_of_ten(shared_ratio)}")
        print(f"Both API values map exactly through shared scale: {scaled_values_match}")
        print("CMIS cross-source supply promotion: False (live semantic review required)")

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
        self.assertFalse(rpc["units_verified_against_network_supply_api"])


if __name__ == "__main__":
    unittest.main()
