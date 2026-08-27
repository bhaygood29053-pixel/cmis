import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import cmis_x1_oracle_v2_current_freshness as current
from liquidity_scout.providers.x1.oracle_v2_policy import (
    FRESH,
    FUTURE,
    INVALID,
    STALE,
    normalize_timestamp_unit_evidence,
)
from liquidity_scout.providers.x1.oracle_v2_timestamp_unit_evidence import (
    PROMOTION_ARTIFACT_ID,
    PROMOTION_MERGE_COMMIT,
    PROMOTION_PR,
    accepted_oracle_v2_timestamp_unit_evidence,
)


OBSERVED_AT = datetime(
    2026,
    8,
    27,
    4,
    30,
    0,
    tzinfo=timezone.utc,
)
OBSERVED_AT_MS = int(OBSERVED_AT.timestamp() * 1000)


def _structural_fixture(
    *,
    age_ms=500,
    future_offset_ms=None,
    status="verified_contract_shape",
):
    observations = []
    for asset in ("BTC", "ETH", "SOL", "HYPE", "ZEC", "FARTCOIN"):
        for relay_index in range(1, 6):
            if future_offset_ms is None:
                timestamp_raw = OBSERVED_AT_MS - age_ms
            else:
                timestamp_raw = OBSERVED_AT_MS + future_offset_ms
            observations.append({
                "asset": asset,
                "relay_index": relay_index,
                "price_raw": 100_000_000 + relay_index,
                "price": f"100.00000{relay_index}",
                "timestamp_raw": timestamp_raw,
                "timestamp_unit_live_verified": False,
                "source_contract_timestamp_unit": "unix_ms",
                "zero_price": False,
                "timestamp_positive": True,
                "structurally_valid_before_timestamp_unit_and_freshness": True,
                "cmis_price_eligible": False,
                "freshness_classification": "not_applied",
            })

    return {
        "service": "x1_oracle_v2_probe",
        "version": "0.1.0",
        "chain": "x1",
        "status": status,
        "observed_at": OBSERVED_AT.isoformat(),
        "program": {
            "address": "program",
            "exists": True,
            "executable": True,
        },
        "state": {
            "address": "state",
            "exists": True,
            "executable": False,
        },
        "expected": {
            "decimals": 6,
            "relay_slots_per_asset": 5,
        },
        "checks": {
            "state_decoded": status == "verified_contract_shape",
        },
        "slot_observations": observations,
    }


def _policy(
    *,
    max_age_ms=1_000,
    max_future_skew_ms=100,
    minimum_eligible_slots=3,
):
    return {
        "max_age_ms": max_age_ms,
        "max_age_provenance": "test fixture only",
        "max_future_skew_ms": max_future_skew_ms,
        "future_skew_provenance": "test fixture only",
        "minimum_eligible_slots": minimum_eligible_slots,
        "minimum_eligible_slots_provenance": "test fixture only",
    }


class OracleV2CurrentFreshnessTests(unittest.TestCase):
    def test_accepted_timestamp_unit_evidence_is_policy_eligible(self):
        evidence = accepted_oracle_v2_timestamp_unit_evidence()
        normalized = normalize_timestamp_unit_evidence(evidence)

        self.assertTrue(normalized["accepted_for_policy"])
        self.assertTrue(evidence["verified"])
        self.assertEqual(evidence["promotion_pr"], PROMOTION_PR)
        self.assertEqual(evidence["promotion_pr"], 294)
        self.assertEqual(
            evidence["promotion_merge_commit"],
            PROMOTION_MERGE_COMMIT,
        )
        self.assertEqual(
            evidence["promotion_artifact_id"],
            PROMOTION_ARTIFACT_ID,
        )
        self.assertFalse(evidence["freshness_verified"])
        self.assertFalse(evidence["current_price_use_authorized"])

    def test_incomplete_policy_fails_closed_but_reports_verified_unit_ages(self):
        with patch.object(
            current,
            "probe_oracle_v2",
            return_value=_structural_fixture(age_ms=500),
        ):
            result = current.evaluate_current_oracle_v2_freshness(
                freshness_policy=None,
                observed_at=OBSERVED_AT,
            )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "freshness_policy_incomplete")
        self.assertTrue(result["timestamp_unit_verified"])
        self.assertFalse(result["freshness_policy"]["policy_complete"])
        self.assertFalse(result["freshness_policy_applied"])
        self.assertFalse(result["freshness_verified"])
        self.assertEqual(result["age_summary"]["slot_count"], 30)
        self.assertEqual(
            result["age_summary"]["positive_timestamp_age_count"],
            30,
        )
        self.assertEqual(
            result["age_summary"]["minimum_signed_age_ms"],
            500,
        )
        self.assertEqual(
            result["age_summary"]["maximum_signed_age_ms"],
            500,
        )

        for asset_result in result["assets"].values():
            self.assertEqual(asset_result["status"], "unavailable")
            self.assertEqual(asset_result["eligible_slot_count"], 0)
            self.assertIsNone(asset_result["median_price"])
            for slot in asset_result["slot_classifications"]:
                self.assertEqual(slot["classification"], INVALID)
                self.assertEqual(
                    slot["reason"],
                    "freshness_policy_incomplete",
                )
                self.assertFalse(slot["cmis_price_eligible"])

    def test_complete_policy_classifies_fresh_and_calculates_candidate_median(self):
        with patch.object(
            current,
            "probe_oracle_v2",
            return_value=_structural_fixture(age_ms=1_000),
        ):
            result = current.evaluate_current_oracle_v2_freshness(
                freshness_policy=_policy(max_age_ms=1_000),
                observed_at=OBSERVED_AT,
            )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["timestamp_unit_verified"])
        self.assertTrue(result["freshness_policy_applied"])
        self.assertTrue(result["freshness_verified"])

        for asset_result in result["assets"].values():
            self.assertEqual(asset_result["status"], "ok")
            self.assertEqual(asset_result["eligible_slot_count"], 5)
            self.assertEqual(asset_result["median_price"], "100.000003")
            self.assertTrue(
                all(
                    slot["classification"] == FRESH
                    for slot in asset_result["slot_classifications"]
                )
            )

        self.assertFalse(result["current_price_use_authorized"])
        self.assertFalse(result["cmis_provider_promoted"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_one_millisecond_over_max_age_is_stale(self):
        with patch.object(
            current,
            "probe_oracle_v2",
            return_value=_structural_fixture(age_ms=1_001),
        ):
            result = current.evaluate_current_oracle_v2_freshness(
                freshness_policy=_policy(max_age_ms=1_000),
                observed_at=OBSERVED_AT,
            )

        self.assertEqual(result["status"], "unavailable")
        self.assertTrue(result["freshness_verified"])
        for asset_result in result["assets"].values():
            self.assertEqual(asset_result["eligible_slot_count"], 0)
            self.assertTrue(
                all(
                    slot["classification"] == STALE
                    for slot in asset_result["slot_classifications"]
                )
            )

    def test_future_offset_equal_to_skew_is_fresh(self):
        with patch.object(
            current,
            "probe_oracle_v2",
            return_value=_structural_fixture(future_offset_ms=100),
        ):
            result = current.evaluate_current_oracle_v2_freshness(
                freshness_policy=_policy(max_future_skew_ms=100),
                observed_at=OBSERVED_AT,
            )

        self.assertEqual(result["status"], "ok")
        for asset_result in result["assets"].values():
            self.assertTrue(
                all(
                    slot["classification"] == FRESH
                    for slot in asset_result["slot_classifications"]
                )
            )
            self.assertTrue(
                all(
                    slot["future_offset_ms"] == 100
                    for slot in asset_result["slot_classifications"]
                )
            )

    def test_future_offset_over_skew_is_future_and_ineligible(self):
        with patch.object(
            current,
            "probe_oracle_v2",
            return_value=_structural_fixture(future_offset_ms=101),
        ):
            result = current.evaluate_current_oracle_v2_freshness(
                freshness_policy=_policy(max_future_skew_ms=100),
                observed_at=OBSERVED_AT,
            )

        self.assertEqual(result["status"], "unavailable")
        for asset_result in result["assets"].values():
            self.assertEqual(asset_result["eligible_slot_count"], 0)
            self.assertTrue(
                all(
                    slot["classification"] == FUTURE
                    for slot in asset_result["slot_classifications"]
                )
            )

    def test_minimum_eligible_slots_boundary_is_respected(self):
        fixture = _structural_fixture(age_ms=500)
        # Make three of BTC's five slots stale under the test policy.
        btc = [
            item for item in fixture["slot_observations"]
            if item["asset"] == "BTC"
        ]
        for item in btc[:3]:
            item["timestamp_raw"] = OBSERVED_AT_MS - 2_000

        with patch.object(
            current,
            "probe_oracle_v2",
            return_value=fixture,
        ):
            result = current.evaluate_current_oracle_v2_freshness(
                freshness_policy=_policy(
                    max_age_ms=1_000,
                    minimum_eligible_slots=3,
                ),
                observed_at=OBSERVED_AT,
            )

        btc_result = result["assets"]["BTC"]
        self.assertEqual(btc_result["eligible_slot_count"], 2)
        self.assertEqual(btc_result["status"], "partial")
        self.assertIsNone(btc_result["median_price"])
        self.assertEqual(result["status"], "partial")

    def test_live_observation_clock_is_captured_after_state_read(self):
        call_order = []

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                call_order.append("clock")
                return OBSERVED_AT

        def fake_probe(**kwargs):
            call_order.append("probe")
            self.assertIsNone(kwargs["observed_at"])
            return _structural_fixture(age_ms=500)

        with patch.object(
            current,
            "probe_oracle_v2",
            side_effect=fake_probe,
        ), patch.object(
            current,
            "datetime",
            FakeDateTime,
        ):
            result = current.evaluate_current_oracle_v2_freshness(
                freshness_policy=None,
            )

        self.assertEqual(call_order[:2], ["probe", "clock"])
        self.assertEqual(
            result["observation_clock_source"],
            "post_rpc_runtime",
        )
        self.assertEqual(
            result["age_summary"]["minimum_signed_age_ms"],
            500,
        )

    def test_explicit_observation_clock_remains_deterministic(self):
        with patch.object(
            current,
            "probe_oracle_v2",
            return_value=_structural_fixture(age_ms=500),
        ) as probe:
            result = current.evaluate_current_oracle_v2_freshness(
                freshness_policy=None,
                observed_at=OBSERVED_AT,
            )

        self.assertEqual(
            probe.call_args.kwargs["observed_at"],
            OBSERVED_AT,
        )
        self.assertEqual(
            result["observation_clock_source"],
            "explicit_injected",
        )

    def test_structural_failure_blocks_freshness_evaluation(self):
        with patch.object(
            current,
            "probe_oracle_v2",
            return_value=_structural_fixture(status="mismatch"),
        ):
            result = current.evaluate_current_oracle_v2_freshness(
                freshness_policy=_policy(),
                observed_at=OBSERVED_AT,
            )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(
            result["reason"],
            "oracle_contract_shape_not_verified",
        )
        self.assertTrue(result["timestamp_unit_verified"])
        self.assertFalse(result["freshness_policy_applied"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["price_correctness_verified"])
        self.assertFalse(result["current_price_use_authorized"])
        self.assertEqual(result["assets"], {})

    def test_naive_observation_time_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "timezone-aware",
        ):
            current.evaluate_current_oracle_v2_freshness(
                freshness_policy=None,
                observed_at=datetime(2026, 8, 27, 4, 30, 0),
            )


if __name__ == "__main__":
    unittest.main()
