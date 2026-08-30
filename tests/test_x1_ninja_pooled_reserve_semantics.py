import unittest

from liquidity_scout.providers.x1.ninja_pooled_reserve_semantics import (
    DIRECT_MAPPING,
    verify_ninja_pooled_reserve_semantics,
)


def reserve_report(*, reverse=False, mismatch_index=None, equal_index=None):
    samples = []
    for i in range(5):
        vault0 = "100.123456789"
        vault1 = "575617.590655054"
        if equal_index == i:
            vault1 = vault0

        pooled_base = vault0 if reverse else vault1
        pooled_quote = vault1 if reverse else vault0

        if i == 2 and not reverse:
            # Mirrors the small live floating representation delta observed on
            # a large reserve, still comfortably inside the explicit tolerance.
            vault1 = "8618561076.65819085"
            pooled_base = "8618561076.658192"

        if mismatch_index == i:
            pooled_base = str(float(pooled_base) + 0.1)

        samples.append(
            {
                "pool_address": f"Pool{i}",
                "verified": True,
                "vaults": [
                    {
                        "slot_index": 0,
                        "verified": True,
                        "scaled_amount": vault0,
                    },
                    {
                        "slot_index": 1,
                        "verified": True,
                        "scaled_amount": vault1,
                    },
                ],
                "provider_raw_candidates": {
                    "x1_ninja": {
                        "pooledBase": pooled_base,
                        "pooledQuote": pooled_quote,
                        "liquidity": 999,
                    },
                    "xdex": {"tvl": 888},
                },
            }
        )

    return {
        "status": "verified",
        "rpc_vault_reserve_amounts_verified": True,
        "rpc_reserve_unit_scaling_verified": True,
        "position_mapping_verified": True,
        "samples": samples,
    }


def provider_from(report):
    return lambda **kwargs: report


class NinjaPooledReserveSemanticTests(unittest.TestCase):
    def test_verifies_direct_mapping_across_five_rpc_verified_pools(self):
        result = verify_ninja_pooled_reserve_semantics(
            ninja_pools=[],
            xdex_pools=[],
            reserve_unit_provider=provider_from(reserve_report()),
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["stable_mapping"], DIRECT_MAPPING)
        self.assertEqual(result["verified_sample_count"], 5)
        self.assertTrue(result["pooled_reserve_field_roles_verified"])
        self.assertTrue(result["pooled_reserve_units_verified"])
        self.assertTrue(result["pooled_reserve_semantics_verified"])
        self.assertTrue(
            result["x1_ninja_pooled_base_quote_role_mapping_verified"]
        )
        self.assertFalse(result["general_base_quote_semantics_verified"])
        self.assertEqual(
            result["comparison_policy"]["relative_tolerance"],
            "5e-16",
        )
        self.assertEqual(
            result["comparison_policy"]["absolute_tolerance_token_units"],
            "5e-12",
        )
        self.assertTrue(all(v is False for v in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_reports_absolute_and_relative_error(self):
        result = verify_ninja_pooled_reserve_semantics(
            ninja_pools=[],
            xdex_pools=[],
            reserve_unit_provider=provider_from(reserve_report()),
        )

        sample = result["samples"][2]
        direct = sample["candidate_mappings"][DIRECT_MAPPING]
        base = direct["pooledBase_vs_vault1"]
        self.assertEqual(base["absolute_error"], "0.00000115")
        self.assertIsNotNone(base["relative_error"])
        self.assertTrue(base["within_tolerance"])

    def test_material_reserve_mismatch_fails_closed(self):
        result = verify_ninja_pooled_reserve_semantics(
            ninja_pools=[],
            xdex_pools=[],
            reserve_unit_provider=provider_from(
                reserve_report(mismatch_index=1)
            ),
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["pooled_reserve_semantics_verified"])
        self.assertEqual(result["verified_sample_count"], 4)

    def test_ambiguous_equal_reserves_fail_closed(self):
        result = verify_ninja_pooled_reserve_semantics(
            ninja_pools=[],
            xdex_pools=[],
            reserve_unit_provider=provider_from(
                reserve_report(equal_index=0)
            ),
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["samples"][0]["mapping_verified"])
        self.assertEqual(
            result["samples"][0]["matching_mapping_count"],
            2,
        )

    def test_missing_pooled_field_fails_closed(self):
        report = reserve_report()
        del report["samples"][3]["provider_raw_candidates"]["x1_ninja"][
            "pooledQuote"
        ]
        result = verify_ninja_pooled_reserve_semantics(
            ninja_pools=[],
            xdex_pools=[],
            reserve_unit_provider=provider_from(report),
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["pooled_reserve_semantics_verified"])
        self.assertIn(
            "pooledBase/pooledQuote",
            result["samples"][3]["rejection_reasons"][0],
        )

    def test_nonfinite_provider_value_fails_closed(self):
        report = reserve_report()
        report["samples"][4]["provider_raw_candidates"]["x1_ninja"][
            "pooledBase"
        ] = "NaN"
        result = verify_ninja_pooled_reserve_semantics(
            ninja_pools=[],
            xdex_pools=[],
            reserve_unit_provider=provider_from(report),
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["samples"][4]["mapping_verified"])

    def test_requires_five_verified_pools_and_positive_tolerance(self):
        with self.assertRaises(ValueError):
            verify_ninja_pooled_reserve_semantics(
                ninja_pools=[],
                xdex_pools=[],
                min_verified_pools=4,
            )
        with self.assertRaises(ValueError):
            verify_ninja_pooled_reserve_semantics(
                ninja_pools=[],
                xdex_pools=[],
                relative_tolerance=0,
                absolute_tolerance=0,
            )


if __name__ == "__main__":
    unittest.main()
