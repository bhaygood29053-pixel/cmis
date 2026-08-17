import copy
import unittest

from liquidity_scout.providers.x1.reserve_scope_samples import (
    summarize_x1_reserve_scope_artifacts,
)


def artifact(
    *,
    duration="4",
    provider_age="20",
    slot_span="2",
    asset_delta="0",
    counter_delta="1",
    scope_status="ok",
):
    return {
        "evidence_type": "x1_reserve_scope_evidence",
        "evidence_version": "1.0",
        "chain": "x1",
        "pool_address": "pool111",
        "identity": {
            "shared_authority": "owner111",
            "shared_authority_consistent": True,
        },
        "roles": {
            "asset": {
                "expected_identity": {
                    "vault": "asset-vault",
                    "mint": "asset-mint",
                    "decimals": 6,
                    "shared_authority": "owner111",
                    "provider_field_path": "pool.pooledBase",
                }
            },
            "counter": {
                "expected_identity": {
                    "vault": "counter-vault",
                    "mint": "counter-mint",
                    "decimals": 9,
                    "shared_authority": "owner111",
                    "provider_field_path": "pool.pooledQuote",
                }
            },
        },
        "scope": {
            "status": scope_status,
            "metrics": {
                "collection_duration_seconds": duration,
                "provider_reported_last_synced_age_at_collection_end_seconds": provider_age,
                "rpc_slot_span": slot_span,
                "provider_observed_within_collection": True,
                "roles": {
                    "asset": {"balance_identity_slot_delta": asset_delta},
                    "counter": {"balance_identity_slot_delta": counter_delta},
                },
            },
            "warnings": [],
            "errors": [],
        },
        "verification_state": {
            "rpc_identity_verified": True,
            "rpc_decimals_match": True,
            "freshness_verified": False,
            "observation_scope_verified": False,
        },
        "artifact_sanitized": True,
        "cmis_promotable": False,
        "warnings": [],
        "errors": [],
    }


class X1ReserveScopeSampleSummaryTests(unittest.TestCase):
    def test_summarizes_identity_consistent_samples_without_thresholds(self):
        samples = [
            artifact(duration="2", provider_age="10", slot_span="1", asset_delta="0", counter_delta="1"),
            artifact(duration="4", provider_age="20", slot_span="2", asset_delta="1", counter_delta="1"),
            artifact(duration="6", provider_age="30", slot_span="3", asset_delta="2", counter_delta="3"),
        ]
        result = summarize_x1_reserve_scope_artifacts(samples)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(result["scope_status_counts"], {"ok": 3})
        self.assertEqual(
            result["metrics"]["collection_duration_seconds"],
            {"available": 3, "min": "2", "median": "4", "max": "6"},
        )
        self.assertEqual(
            result["metrics"]["provider_sync_age_seconds"],
            {"available": 3, "min": "10", "median": "20", "max": "30"},
        )
        self.assertEqual(
            result["metrics"]["rpc_slot_span"],
            {"available": 3, "min": "1", "median": "2", "max": "3"},
        )
        self.assertEqual(result["evidence_counts"]["rpc_identity_verified"], 3)
        self.assertEqual(result["evidence_counts"]["rpc_decimals_match"], 3)
        self.assertIsNone(result["threshold_recommendation"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["observation_scope_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(result["warnings"], [])

    def test_even_sample_median_is_exact_decimal(self):
        result = summarize_x1_reserve_scope_artifacts(
            [artifact(duration="2"), artifact(duration="5")]
        )
        self.assertEqual(
            result["metrics"]["collection_duration_seconds"]["median"], "3.5"
        )

    def test_missing_metric_is_partial_with_explicit_coverage(self):
        first = artifact(provider_age="10")
        second = artifact(provider_age=None)
        result = summarize_x1_reserve_scope_artifacts([first, second])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(
            result["coverage"]["provider_sync_age_seconds"],
            {"available": 1, "total": 2},
        )
        self.assertIn(
            "partial_metric_coverage:provider_sync_age_seconds", result["warnings"]
        )
        self.assertFalse(result["freshness_verified"])

    def test_identity_mismatch_is_ambiguous_and_not_aggregated(self):
        first = artifact()
        second = copy.deepcopy(first)
        second["roles"]["asset"]["expected_identity"]["mint"] = "other-mint"
        result = summarize_x1_reserve_scope_artifacts([first, second])
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["metrics"], {})
        self.assertIn("artifact_identity_mismatch", result["errors"])
        self.assertFalse(result["cmis_promotable"])

    def test_invalid_or_unsanitized_artifact_fails_closed(self):
        bad = artifact()
        bad["artifact_sanitized"] = False
        bad["evidence_type"] = "other"
        result = summarize_x1_reserve_scope_artifacts([bad])
        self.assertEqual(result["status"], "error")
        self.assertIn("artifact_0:artifact_not_sanitized", result["errors"])
        self.assertIn("artifact_0:unexpected_evidence_type", result["errors"])
        self.assertFalse(result["cmis_promotable"])

    def test_negative_provider_sync_age_is_measured_and_flagged(self):
        result = summarize_x1_reserve_scope_artifacts([artifact(provider_age="-2")])
        self.assertEqual(result["metrics"]["provider_sync_age_seconds"]["min"], "-2")
        self.assertIn("negative_provider_sync_age_observed", result["warnings"])
        self.assertFalse(result["freshness_verified"])

    def test_source_artifact_errors_make_summary_partial(self):
        item = artifact()
        item["errors"] = ["source-probe-error"]
        result = summarize_x1_reserve_scope_artifacts([item])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["evidence_counts"]["artifacts_with_errors"], 1)
        self.assertIn("source_artifacts_contain_errors", result["warnings"])

    def test_upstream_promotion_claim_does_not_promote_summary(self):
        item = artifact()
        item["cmis_promotable"] = True
        item["verification_state"]["freshness_verified"] = True
        item["verification_state"]["observation_scope_verified"] = True
        result = summarize_x1_reserve_scope_artifacts([item])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["observation_scope_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_empty_sample_set_is_unavailable(self):
        result = summarize_x1_reserve_scope_artifacts([])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["sample_count"], 0)
        self.assertIn("no_scope_artifacts", result["warnings"])

    def test_input_must_be_list(self):
        with self.assertRaisesRegex(TypeError, "artifacts must be a list"):
            summarize_x1_reserve_scope_artifacts({})


if __name__ == "__main__":
    unittest.main()
