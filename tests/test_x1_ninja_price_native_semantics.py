import unittest

from liquidity_scout.providers.x1.ninja_pooled_reserve_semantics import DIRECT_MAPPING
from liquidity_scout.providers.x1.ninja_price_native_semantics import (
    BASE_PER_QUOTE,
    QUOTE_PER_BASE,
    verify_ninja_price_native_semantics,
)


def fixtures(*, inverse_index=None, mismatch_index=None, zero_index=None):
    ninja = []
    samples = []
    for i in range(5):
        base = "200"
        quote = str(1 + i)
        ratio = (1 + i) / 200
        price = ratio
        if inverse_index == i:
            price = 200 / (1 + i)
        if mismatch_index == i:
            price = ratio + 0.01
        if zero_index == i:
            base = "0"

        ninja.append(
            {
                "address": f"Pool{i}",
                "priceNative": str(price),
            }
        )
        samples.append(
            {
                "pool_address": f"Pool{i}",
                "mapping_verified": True,
                "rpc_vault_0_reserve": quote,
                "rpc_vault_1_reserve": base,
            }
        )

    upstream = {
        "status": "verified",
        "pooled_reserve_semantics_verified": True,
        "stable_mapping": DIRECT_MAPPING,
        "samples": samples,
    }
    return ninja, upstream


def provider_from(report):
    return lambda **kwargs: report


class NinjaPriceNativeSemanticTests(unittest.TestCase):
    def test_verifies_quote_per_base_direction_across_five_pools(self):
        ninja, upstream = fixtures()
        result = verify_ninja_price_native_semantics(
            ninja_pools=ninja,
            xdex_pools=[],
            pooled_reserve_provider=provider_from(upstream),
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["stable_direction"], QUOTE_PER_BASE)
        self.assertEqual(result["verified_sample_count"], 5)
        self.assertTrue(result["price_native_pair_direction_verified"])
        self.assertTrue(result["price_native_reserve_ratio_verified"])
        self.assertTrue(result["price_native_semantics_verified"])
        self.assertTrue(result["price_native_unit_verified"])
        self.assertFalse(result["price_native_is_usd_verified"])
        self.assertEqual(
            result["comparison_policy"]["relative_tolerance"],
            "5e-9",
        )
        self.assertEqual(
            result["comparison_policy"]["absolute_tolerance_price_units"],
            "5e-12",
        )
        self.assertTrue(all(v is False for v in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_reports_absolute_and_relative_error(self):
        ninja, upstream = fixtures()
        result = verify_ninja_price_native_semantics(
            ninja_pools=ninja,
            xdex_pools=[],
            pooled_reserve_provider=provider_from(upstream),
        )

        comparison = result["samples"][0]["candidate_ratios"][
            QUOTE_PER_BASE
        ]["comparison"]
        self.assertIn("absolute_error", comparison)
        self.assertIn("relative_error", comparison)
        self.assertTrue(comparison["within_tolerance"])

    def test_mixed_direction_fails_closed(self):
        ninja, upstream = fixtures(inverse_index=4)
        result = verify_ninja_price_native_semantics(
            ninja_pools=ninja,
            xdex_pools=[],
            pooled_reserve_provider=provider_from(upstream),
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["price_native_semantics_verified"])
        self.assertEqual(result["verified_sample_count"], 5)
        self.assertIsNone(result["stable_direction"])
        self.assertEqual(
            result["samples"][4]["unique_matching_direction"],
            BASE_PER_QUOTE,
        )

    def test_material_price_mismatch_fails_closed(self):
        ninja, upstream = fixtures(mismatch_index=2)
        result = verify_ninja_price_native_semantics(
            ninja_pools=ninja,
            xdex_pools=[],
            pooled_reserve_provider=provider_from(upstream),
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["verified_sample_count"], 4)
        self.assertFalse(result["samples"][2]["price_native_sample_verified"])

    def test_zero_reserve_fails_closed(self):
        ninja, upstream = fixtures(zero_index=1)
        result = verify_ninja_price_native_semantics(
            ninja_pools=ninja,
            xdex_pools=[],
            pooled_reserve_provider=provider_from(upstream),
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["samples"][1]["price_native_sample_verified"])
        self.assertIn(
            "must be positive",
            result["samples"][1]["rejection_reasons"][-1],
        )

    def test_missing_or_nonfinite_price_fails_closed(self):
        ninja, upstream = fixtures()
        del ninja[2]["priceNative"]
        ninja[3]["priceNative"] = "NaN"

        result = verify_ninja_price_native_semantics(
            ninja_pools=ninja,
            xdex_pools=[],
            pooled_reserve_provider=provider_from(upstream),
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["verified_sample_count"], 3)

    def test_upstream_reserve_semantics_must_be_verified(self):
        ninja, upstream = fixtures()
        upstream["pooled_reserve_semantics_verified"] = False
        result = verify_ninja_price_native_semantics(
            ninja_pools=ninja,
            xdex_pools=[],
            pooled_reserve_provider=provider_from(upstream),
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["price_native_semantics_verified"])

    def test_requires_five_pools_and_positive_tolerance(self):
        with self.assertRaises(ValueError):
            verify_ninja_price_native_semantics(
                ninja_pools=[],
                xdex_pools=[],
                min_verified_pools=4,
            )
        with self.assertRaises(ValueError):
            verify_ninja_price_native_semantics(
                ninja_pools=[],
                xdex_pools=[],
                relative_tolerance=0,
                absolute_tolerance=0,
            )


if __name__ == "__main__":
    unittest.main()
