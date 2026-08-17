import json
import unittest

from liquidity_scout.services.cmis_history_range_artifact import (
    sanitize_history_range_probe_result,
)


def probe_result():
    return {
        "service": "history_range_probe",
        "version": "1.3.1",
        "chain": "x1",
        "asset": {"symbol": "XENCAT", "mint": "mint-1", "secret": "drop"},
        "status": "observed_chain_range_proven",
        "requested_window": {
            "label": "1h",
            "duration_seconds": 3600,
            "start_epoch": 100.0,
            "start_utc": "1970-01-01T00:01:40+00:00",
            "end_epoch": 3700.0,
            "end_utc": "1970-01-01T01:01:40+00:00",
            "membership_basis": "X1_RPC_BLOCK_TIME",
        },
        "market_snapshot_status": "ok",
        "matched_pool_count": 1,
        "selected_pool_count": 1,
        "pools": [
            {
                "pool_address": "pool-1",
                "pair": "XENCAT/XNT",
                "provider_history": {
                    "returned_row_count": 50,
                    "provider_total_raw": 123,
                    "provider_last_updated_raw": 999,
                    "transport_pagination_or_range_verified": False,
                    "raw_response": {"apiKey": "secret"},
                },
                "requested_window_chain": {
                    "start_epoch": 100.0,
                    "start_utc": "start",
                    "end_epoch": 3700.0,
                    "end_utc": "end",
                    "membership_basis": "X1_RPC_BLOCK_TIME",
                    "signature_count": 12,
                    "successful_signature_count": 11,
                    "failed_signature_count": 1,
                    "scanned_entries_without_block_time": 0,
                    "oldest_signature_time_utc": "old",
                    "newest_signature_time_utc": "new",
                },
                "proof_scan": {
                    "chain": "x1",
                    "source": "X1 RPC getSignaturesForAddress",
                    "address": "pool-1",
                    "scan_start_epoch": 90.0,
                    "scan_start_utc": "scan-start",
                    "scan_end_epoch": 3700.0,
                    "scan_end_utc": "scan-end",
                    "page_size": 1000,
                    "max_signatures": 5000,
                    "pages_fetched": 2,
                    "signature_count": 60,
                    "successful_signature_count": 59,
                    "failed_signature_count": 1,
                    "scan_interval_signature_count": 12,
                    "rpc_errors": 0,
                    "malformed_entries": 0,
                    "duplicate_signatures": 0,
                    "cursor_stalls": 0,
                    "history_exhausted": False,
                    "start_boundary_reached": True,
                    "bound_reached": False,
                    "slot_order_verified": True,
                    "block_time_complete": True,
                    "block_time_order_verified": True,
                    "integrity_verified": True,
                    "range_proven": True,
                    "coverage_scope": "scan_boundary_reached",
                    "newest_signature": "SECRET_SIG_NEW",
                    "newest_slot": 30,
                    "newest_block_time_utc": "new-time",
                    "oldest_signature": "SECRET_SIG_OLD",
                    "oldest_slot": 10,
                    "oldest_block_time_utc": "old-time",
                    "entries": [{"signature": "SECRET_SIG_ENTRY"}],
                },
                "provider_chain_comparison": {
                    "provider_row_count": 50,
                    "provider_valid_identity_row_count": 50,
                    "provider_malformed_row_count": 0,
                    "provider_duplicate_signature_count": 0,
                    "provider_slot_order_newest_to_oldest_observed": True,
                    "provider_time_order_newest_to_oldest_observed": True,
                    "provider_ordering_observed_consistent": True,
                    "provider_oldest_timestamp_utc": "provider-old",
                    "provider_newest_timestamp_utc": "provider-new",
                    "provider_signatures_found_in_chain_scan": 50,
                    "provider_chain_slot_match_count": 50,
                    "provider_chain_timestamp_match_count": 50,
                    "provider_chain_timestamp_comparable_count": 50,
                    "overlapping_identity_verified": True,
                    "provider_range_contract_verified": False,
                    "provider_range_contract_reason": "sample overlap is not exhaustiveness",
                    "api_key": "secret",
                },
                "chain_signature_sample": {
                    "first": ["SECRET_FIRST"],
                    "last": ["SECRET_LAST"],
                },
            }
        ],
        "summary": {
            "all_selected_pool_proof_ranges_proven": True,
            "all_selected_pool_chain_ranges_proven": True,
            "all_provider_ordering_observed_consistent": True,
            "all_overlapping_provider_chain_identity_verified": True,
            "provider_range_contract_verified": False,
            "cmis_window_completion_promoted": False,
            "interpretation": "sample proof only",
        },
        "errors": [],
        "token": "secret",
    }


class HistoryRangeArtifactTests(unittest.TestCase):
    def test_sanitizes_raw_signatures_and_payloads(self):
        artifact = sanitize_history_range_probe_result(probe_result())
        encoded = json.dumps(artifact, sort_keys=True)

        self.assertEqual(artifact["service"], "x1_history_range_evidence")
        self.assertFalse(artifact["raw_signatures_retained"])
        self.assertFalse(artifact["raw_provider_payloads_retained"])
        self.assertFalse(artifact["provider_range_contract_verified"])
        self.assertFalse(artifact["cmis_promotable"])
        self.assertTrue(artifact["pools"][0]["proof_scan"]["range_proven"])
        self.assertEqual(
            artifact["pools"][0]["provider_chain_comparison"][
                "provider_signatures_found_in_chain_scan"
            ],
            50,
        )
        for secret in (
            "SECRET_SIG_NEW",
            "SECRET_SIG_OLD",
            "SECRET_SIG_ENTRY",
            "SECRET_FIRST",
            "SECRET_LAST",
            "apiKey",
            "api_key",
            "secret",
        ):
            self.assertNotIn(secret, encoded)

    def test_incomplete_range_remains_nonpromotable_and_warns(self):
        raw = probe_result()
        raw["pools"][0]["proof_scan"]["range_proven"] = False
        raw["pools"][0]["provider_chain_comparison"][
            "overlapping_identity_verified"
        ] = False

        artifact = sanitize_history_range_probe_result(raw)

        self.assertFalse(artifact["cmis_promotable"])
        self.assertIn(
            "one_or_more_rpc_proof_ranges_incomplete",
            artifact["warnings"],
        )
        self.assertIn(
            "provider_chain_overlap_identity_incomplete",
            artifact["warnings"],
        )

    def test_empty_pool_set_is_explicit(self):
        raw = probe_result()
        raw["pools"] = []
        raw["selected_pool_count"] = 0

        artifact = sanitize_history_range_probe_result(raw)

        self.assertEqual(artifact["pools"], [])
        self.assertIn("no_selected_pool_history_evidence", artifact["warnings"])
        self.assertFalse(artifact["cmis_promotable"])

    def test_rejects_provider_range_promotion(self):
        raw = probe_result()
        raw["summary"]["provider_range_contract_verified"] = True
        with self.assertRaisesRegex(ValueError, "provider range promotion"):
            sanitize_history_range_probe_result(raw)

        raw = probe_result()
        raw["pools"][0]["provider_chain_comparison"][
            "provider_range_contract_verified"
        ] = True
        with self.assertRaisesRegex(ValueError, "provider range promotion"):
            sanitize_history_range_probe_result(raw)

    def test_rejects_cmis_window_promotion(self):
        raw = probe_result()
        raw["summary"]["cmis_window_completion_promoted"] = True
        with self.assertRaisesRegex(ValueError, "CMIS window promotion"):
            sanitize_history_range_probe_result(raw)

    def test_rejects_wrong_service_or_chain(self):
        raw = probe_result()
        raw["service"] = "market_report"
        with self.assertRaisesRegex(ValueError, "history_range_probe"):
            sanitize_history_range_probe_result(raw)

        raw = probe_result()
        raw["chain"] = "solana"
        with self.assertRaisesRegex(ValueError, "history_range_probe"):
            sanitize_history_range_probe_result(raw)


if __name__ == "__main__":
    unittest.main()
