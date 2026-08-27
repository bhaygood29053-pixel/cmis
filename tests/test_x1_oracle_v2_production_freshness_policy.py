import json
import pathlib
import unittest

from liquidity_scout.providers.x1.oracle_v2_policy import (
    FRESH,
    FUTURE,
    STALE,
    aggregate_oracle_v2_slots,
    classify_oracle_v2_slot,
    normalize_oracle_v2_freshness_policy,
)
from liquidity_scout.providers.x1.oracle_v2_timestamp_unit_evidence import (
    accepted_oracle_v2_timestamp_unit_evidence,
)


POLICY_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "liquidity_scout"
    / "providers"
    / "x1"
    / "oracle_v2_freshness_policy.json"
)


def production_policy():
    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class OracleV2ProductionFreshnessPolicyTests(unittest.TestCase):
    def test_accepted_policy_is_complete_and_exact(self):
        raw = production_policy()
        normalized = normalize_oracle_v2_freshness_policy(raw)

        self.assertEqual(
            raw["policy_id"],
            "cmis.x1.oracle_v2.current_price_freshness.v1",
        )
        self.assertEqual(normalized["max_age_ms"], 60_000)
        self.assertEqual(normalized["max_future_skew_ms"], 5_000)
        self.assertEqual(normalized["minimum_eligible_slots"], 3)
        self.assertTrue(normalized["policy_complete"])
        self.assertFalse(normalized["has_hidden_defaults"])
        self.assertIn("independently", normalized["max_age_provenance"])
        self.assertIn("operator governance", normalized["future_skew_provenance"])
        self.assertIn("strict majority", normalized["minimum_eligible_slots_provenance"])

    def test_max_age_boundary_is_inclusive(self):
        observed_at_ms = 2_000_000_000_000
        result = classify_oracle_v2_slot(
            price_raw=100_000_000,
            timestamp_raw=observed_at_ms - 60_000,
            observed_at_ms=observed_at_ms,
            policy=production_policy(),
            timestamp_unit_evidence=accepted_oracle_v2_timestamp_unit_evidence(),
        )

        self.assertEqual(result["classification"], FRESH)
        self.assertTrue(result["cmis_price_eligible"])

        stale = classify_oracle_v2_slot(
            price_raw=100_000_000,
            timestamp_raw=observed_at_ms - 60_001,
            observed_at_ms=observed_at_ms,
            policy=production_policy(),
            timestamp_unit_evidence=accepted_oracle_v2_timestamp_unit_evidence(),
        )

        self.assertEqual(stale["classification"], STALE)
        self.assertFalse(stale["cmis_price_eligible"])

    def test_future_skew_boundary_is_inclusive(self):
        observed_at_ms = 2_000_000_000_000
        accepted = classify_oracle_v2_slot(
            price_raw=100_000_000,
            timestamp_raw=observed_at_ms + 5_000,
            observed_at_ms=observed_at_ms,
            policy=production_policy(),
            timestamp_unit_evidence=accepted_oracle_v2_timestamp_unit_evidence(),
        )
        rejected = classify_oracle_v2_slot(
            price_raw=100_000_000,
            timestamp_raw=observed_at_ms + 5_001,
            observed_at_ms=observed_at_ms,
            policy=production_policy(),
            timestamp_unit_evidence=accepted_oracle_v2_timestamp_unit_evidence(),
        )

        self.assertEqual(accepted["classification"], FRESH)
        self.assertTrue(accepted["cmis_price_eligible"])
        self.assertEqual(rejected["classification"], FUTURE)
        self.assertFalse(rejected["cmis_price_eligible"])

    def test_three_of_five_is_minimum_quorum(self):
        observed_at_ms = 2_000_000_000_000
        slots = [
            {
                "relay_index": 1,
                "price_raw": 100_000_000,
                "timestamp_raw": observed_at_ms - 1_000,
            },
            {
                "relay_index": 2,
                "price_raw": 101_000_000,
                "timestamp_raw": observed_at_ms - 2_000,
            },
            {
                "relay_index": 3,
                "price_raw": 102_000_000,
                "timestamp_raw": observed_at_ms - 3_000,
            },
            {
                "relay_index": 4,
                "price_raw": 1,
                "timestamp_raw": observed_at_ms - 60_001,
            },
            {
                "relay_index": 5,
                "price_raw": 999_000_000,
                "timestamp_raw": observed_at_ms - 60_001,
            },
        ]

        result = aggregate_oracle_v2_slots(
            slots,
            observed_at_ms=observed_at_ms,
            policy=production_policy(),
            timestamp_unit_evidence=accepted_oracle_v2_timestamp_unit_evidence(),
            decimals=6,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["eligible_slot_count"], 3)
        self.assertEqual(result["median_price_raw_numerator"], 101_000_000)
        self.assertEqual(result["median_price_raw_denominator"], 1)
        self.assertEqual(result["median_price"], "101")
        self.assertEqual(result["classification_counts"][FRESH], 3)
        self.assertEqual(result["classification_counts"][STALE], 2)
        self.assertFalse(result["current_price_use_authorized"])
        self.assertFalse(result["cmis_provider_promoted"])
        self.assertFalse(result["source_independence_verified"])

    def test_two_of_five_never_constructs_candidate_median(self):
        observed_at_ms = 2_000_000_000_000
        slots = [
            {
                "relay_index": relay_index,
                "price_raw": 100_000_000 + relay_index,
                "timestamp_raw": (
                    observed_at_ms - 1_000
                    if relay_index <= 2
                    else observed_at_ms - 60_001
                ),
            }
            for relay_index in range(1, 6)
        ]

        result = aggregate_oracle_v2_slots(
            slots,
            observed_at_ms=observed_at_ms,
            policy=production_policy(),
            timestamp_unit_evidence=accepted_oracle_v2_timestamp_unit_evidence(),
            decimals=6,
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["eligible_slot_count"], 2)
        self.assertIsNone(result["median_price_raw_numerator"])
        self.assertIsNone(result["median_price_raw_denominator"])
        self.assertIsNone(result["median_price"])


if __name__ == "__main__":
    unittest.main()
