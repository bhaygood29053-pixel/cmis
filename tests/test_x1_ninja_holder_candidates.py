import unittest

from liquidity_scout.providers.x1.ninja_holder_candidates import (
    extract_x1_ninja_holder_candidates,
)


POOL = "pool111"


def pool_detail():
    return {
        "chain": "x1",
        "source": "X1.Ninja Developer API",
        "pool_address_requested": POOL,
        "observed_at": 100.0,
        "raw_response": {
            "pool": {
                "address": POOL,
                "baseToken": {
                    "address": "base-mint",
                    "symbol": "BASE",
                    "name": "Base Token",
                    "decimals": 6,
                },
                "quoteToken": {
                    "address": "quote-mint",
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "decimals": 9,
                },
                "holders": 115,
                "nested": {"holderCountCandidate": "116"},
            },
            "holderMeta": {"source": "provider"},
        },
        "cmis_promotable": False,
    }


class X1NinjaHolderCandidatesTests(unittest.TestCase):
    def test_extracts_lexical_holder_fields_without_semantic_promotion(self):
        result = extract_x1_ninja_holder_candidates(
            pool_detail(),
            expected_pool_address=POOL,
        )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["pool_identity_transport_consistent"])
        paths = [item["field_path"] for item in result["holder_field_candidates"]]
        self.assertEqual(
            paths,
            [
                "pool.holders",
                "pool.nested.holderCountCandidate",
                "holderMeta",
            ],
        )
        self.assertEqual(result["holder_field_candidates"][0]["raw_value"], 115)
        self.assertEqual(
            result["token_metadata_candidates"]["base_token"]["address"],
            "base-mint",
        )
        self.assertFalse(result["holder_field_semantics_verified"])
        self.assertFalse(result["holder_field_asset_binding_verified"])
        self.assertFalse(result["holder_uniqueness_semantics_verified"])
        self.assertFalse(result["holder_coverage_verified"])
        self.assertFalse(result["beneficial_owner_identity_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_real_schema_shape_surfaces_pool_holders_only_as_candidate(self):
        item = pool_detail()
        item["raw_response"] = {
            "pool": {
                "address": POOL,
                "baseToken": {
                    "address": "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb",
                    "symbol": "XENCAT",
                    "name": "XENCAT",
                    "decimals": 6,
                },
                "quoteToken": {
                    "address": "So11111111111111111111111111111111111111112",
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "decimals": 9,
                },
                "holders": 115,
            },
            "lastUpdated": 1786966355037,
        }

        result = extract_x1_ninja_holder_candidates(item)

        self.assertEqual(
            result["holder_field_candidates"],
            [{"field_path": "pool.holders", "raw_value": 115}],
        )
        self.assertFalse(result["holder_field_asset_binding_verified"])
        self.assertFalse(result["holder_uniqueness_semantics_verified"])

    def test_no_holder_fields_is_partial_not_invented(self):
        item = pool_detail()
        item["raw_response"]["pool"].pop("holders")
        item["raw_response"]["pool"].pop("nested")
        item["raw_response"].pop("holderMeta")

        result = extract_x1_ninja_holder_candidates(item)

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["holder_field_candidates"], [])
        self.assertIn("no_lexical_holder_fields_observed", result["warnings"])
        self.assertFalse(result["cmis_promotable"])

    def test_response_pool_mismatch_fails_closed(self):
        item = pool_detail()
        item["raw_response"]["pool"]["address"] = "other-pool"

        result = extract_x1_ninja_holder_candidates(item)

        self.assertEqual(result["status"], "error")
        self.assertIn("response_pool_identity_mismatch", result["errors"])
        self.assertFalse(result["pool_identity_transport_consistent"])

    def test_expected_pool_scope_mismatch_fails_closed(self):
        result = extract_x1_ninja_holder_candidates(
            pool_detail(),
            expected_pool_address="other-pool",
        )

        self.assertEqual(result["status"], "error")
        self.assertIn("requested_pool_scope_mismatch", result["errors"])

    def test_missing_response_pool_address_is_partial(self):
        item = pool_detail()
        del item["raw_response"]["pool"]["address"]

        result = extract_x1_ninja_holder_candidates(item)

        self.assertEqual(result["status"], "partial")
        self.assertIn("response_pool_address_unavailable", result["warnings"])
        self.assertFalse(result["pool_identity_transport_consistent"])

    def test_wrong_chain_and_missing_raw_response_fail_closed(self):
        item = pool_detail()
        item["chain"] = "solana"
        item["raw_response"] = None

        result = extract_x1_ninja_holder_candidates(item)

        self.assertEqual(result["status"], "error")
        self.assertIn("wrong_chain", result["errors"])
        self.assertIn("raw_response_missing_or_malformed", result["errors"])
        self.assertFalse(result["cmis_promotable"])

    def test_input_must_be_mapping(self):
        with self.assertRaisesRegex(TypeError, "pool_detail must be a mapping"):
            extract_x1_ninja_holder_candidates([])


if __name__ == "__main__":
    unittest.main()
