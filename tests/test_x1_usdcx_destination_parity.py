import unittest

from liquidity_scout.providers.x1.usdcx_destination_parity import (
    EXPECTED_DECIMALS,
    SOLANA_USDC_MINT,
    WARP_USDC_ROUTE_ID,
    X1_USDC_X_MINT,
    evaluate_usdcx_destination_parity,
)


def backing(*, source_amount=24_007_049, destination_amount=24_007_049, current=True, authority=True):
    equal = source_amount == destination_amount
    return {
        "route_id": WARP_USDC_ROUTE_ID,
        "source": {
            "chain": "solana",
            "mint": SOLANA_USDC_MINT,
            "amount_raw": source_amount,
            "decimals": EXPECTED_DECIMALS,
            "identity_verified": True,
        },
        "destination": {
            "chain": "x1",
            "mint": X1_USDC_X_MINT,
            "raw_supply": destination_amount,
            "decimals": EXPECTED_DECIMALS,
            "identity_verified": authority,
        },
        "decimals": EXPECTED_DECIMALS,
        "decimals_verified": True,
        "observation_time_compatible": current,
        "source_vault_balance_equals_destination_supply": equal,
        "current_backing_closure_verified": bool(current and authority and equal),
        "bridged_supply_verified": bool(current and authority and equal),
        "amount_raw": destination_amount if current and authority and equal else None,
    }


class X1UsdcxDestinationParityTests(unittest.TestCase):
    def test_current_exact_backing_closure_verifies_destination_parity(self):
        result = evaluate_usdcx_destination_parity(backing())
        self.assertTrue(result["current_reserve_backing_verified"])
        self.assertTrue(result["exact_backing_closure_verified"])
        self.assertEqual(result["reserve_surplus_raw"], 0)

    def test_current_overcollateralized_reserve_verifies_sufficiency_without_exact_closure(self):
        result = evaluate_usdcx_destination_parity(
            backing(source_amount=24_107_049, destination_amount=24_007_049)
        )
        self.assertTrue(result["source_reserve_gte_destination_supply"])
        self.assertTrue(result["current_reserve_backing_verified"])
        self.assertTrue(result["reserve_or_redemption_semantics_verified"])
        self.assertTrue(result["destination_representation_value_equivalence_verified"])
        self.assertFalse(result["exact_backing_closure_verified"])
        self.assertEqual(result["reserve_surplus_raw"], 100_000)
        self.assertFalse(result["future_redemption_guaranteed"])
        self.assertFalse(result["historical_value_equivalence_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_undercollateralized_reserve_fails_closed(self):
        result = evaluate_usdcx_destination_parity(
            backing(source_amount=24_007_048, destination_amount=24_007_049)
        )
        self.assertFalse(result["source_reserve_gte_destination_supply"])
        self.assertFalse(result["current_reserve_backing_verified"])
        self.assertFalse(result["destination_representation_value_equivalence_verified"])

    def test_stale_or_incompatible_observation_fails_closed(self):
        result = evaluate_usdcx_destination_parity(backing(current=False))
        self.assertFalse(result["current_reserve_backing_verified"])

    def test_unverified_destination_identity_fails_closed(self):
        result = evaluate_usdcx_destination_parity(backing(authority=False))
        self.assertFalse(result["source_destination_identity_verified"])
        self.assertFalse(result["current_reserve_backing_verified"])

    def test_wrong_route_fails_closed(self):
        evidence = backing()
        evidence["route_id"] = "wrong-route"
        result = evaluate_usdcx_destination_parity(evidence)
        self.assertFalse(result["exact_route_identity_verified"])
        self.assertFalse(result["current_reserve_backing_verified"])


if __name__ == "__main__":
    unittest.main()
