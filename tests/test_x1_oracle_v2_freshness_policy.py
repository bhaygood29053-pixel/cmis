import unittest

from liquidity_scout.providers.x1.oracle_v2_policy import (
    FRESH,
    FUTURE,
    INVALID,
    MISSING,
    STALE,
    UNIT_UNVERIFIED,
    aggregate_oracle_v2_slots,
    assess_unix_ms_block_time_correlation,
    classify_oracle_v2_slot,
    normalize_oracle_v2_freshness_policy,
)


def policy(**overrides):
    value = {
        "max_age_ms": 60_000,
        "max_age_provenance": "test fixture only",
        "max_future_skew_ms": 2_000,
        "future_skew_provenance": "test fixture only",
        "minimum_eligible_slots": 3,
        "minimum_eligible_slots_provenance": "test fixture only",
    }
    value.update(overrides)
    return value


def unit_evidence(*, verified=True):
    return {
        "timestamp_unit": "unix_ms",
        "method": "x1_block_time_correlation",
        "verified": verified,
        "provenance": "test correlation evidence only",
    }


class OracleV2FreshnessPolicyTests(unittest.TestCase):
    def test_no_policy_defaults_are_invented(self):
        normalized = normalize_oracle_v2_freshness_policy(None)

        self.assertIsNone(normalized["max_age_ms"])
        self.assertIsNone(normalized["max_future_skew_ms"])
        self.assertIsNone(normalized["minimum_eligible_slots"])
        self.assertFalse(normalized["policy_complete"])
        self.assertFalse(normalized["has_hidden_defaults"])

    def test_policy_requires_provenance_for_every_threshold(self):
        normalized = normalize_oracle_v2_freshness_policy({
            "max_age_ms": 60_000,
            "max_future_skew_ms": 2_000,
            "minimum_eligible_slots": 3,
        })

        self.assertFalse(normalized["policy_complete"])

    def test_policy_rejects_invalid_minimum_slot_count(self):
        with self.assertRaisesRegex(ValueError, "minimum_eligible_slots"):
            normalize_oracle_v2_freshness_policy(policy(
                minimum_eligible_slots=6
            ))

    def test_timestamp_unit_correlation_has_no_hidden_tolerance(self):
        with self.assertRaisesRegex(ValueError, "max_difference_ms"):
            assess_unix_ms_block_time_correlation(
                timestamp_raw=1_780_000_000_250,
                block_time_seconds=1_780_000_000,
                max_difference_ms=None,
                tolerance_provenance="test",
            )

    def test_timestamp_unit_correlation_is_exact_and_provenance_preserving(self):
        result = assess_unix_ms_block_time_correlation(
            timestamp_raw=1_780_000_000_250,
            block_time_seconds=1_780_000_000,
            max_difference_ms=500,
            tolerance_provenance="test fixture tolerance",
        )

        self.assertTrue(result["verified"])
        self.assertEqual(result["difference_ms"], 250)
        self.assertEqual(result["max_difference_ms"], 500)
        self.assertEqual(
            result["tolerance_provenance"],
            "test fixture tolerance",
        )
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["price_correctness_verified"])
        self.assertFalse(result["source_independence_verified"])

    def test_unverified_timestamp_unit_fails_closed(self):
        result = classify_oracle_v2_slot(
            price_raw=1_000_000,
            timestamp_raw=1_780_000_000_000,
            observed_at_ms=1_780_000_001_000,
            policy=policy(),
            timestamp_unit_evidence=unit_evidence(verified=False),
        )

        self.assertEqual(result["classification"], UNIT_UNVERIFIED)
        self.assertFalse(result["cmis_price_eligible"])

    def test_missing_slot_value_is_missing(self):
        result = classify_oracle_v2_slot(
            price_raw=None,
            timestamp_raw=1_780_000_000_000,
            observed_at_ms=1_780_000_001_000,
            policy=policy(),
            timestamp_unit_evidence=unit_evidence(),
        )

        self.assertEqual(result["classification"], MISSING)
        self.assertFalse(result["cmis_price_eligible"])

    def test_zero_price_is_invalid_even_with_verified_unit(self):
        result = classify_oracle_v2_slot(
            price_raw=0,
            timestamp_raw=1_780_000_000_000,
            observed_at_ms=1_780_000_001_000,
            policy=policy(),
            timestamp_unit_evidence=unit_evidence(),
        )

        self.assertEqual(result["classification"], INVALID)
        self.assertFalse(result["cmis_price_eligible"])

    def test_incomplete_freshness_policy_is_invalid(self):
        result = classify_oracle_v2_slot(
            price_raw=1_000_000,
            timestamp_raw=1_780_000_000_000,
            observed_at_ms=1_780_000_001_000,
            policy={},
            timestamp_unit_evidence=unit_evidence(),
        )

        self.assertEqual(result["classification"], INVALID)
        self.assertEqual(result["reason"], "freshness_policy_incomplete")
        self.assertFalse(result["cmis_price_eligible"])

    def test_timestamp_beyond_future_skew_is_future(self):
        result = classify_oracle_v2_slot(
            price_raw=1_000_000,
            timestamp_raw=1_780_000_003_001,
            observed_at_ms=1_780_000_001_000,
            policy=policy(),
            timestamp_unit_evidence=unit_evidence(),
        )

        self.assertEqual(result["classification"], FUTURE)
        self.assertEqual(result["future_offset_ms"], 2_001)
        self.assertFalse(result["cmis_price_eligible"])

    def test_timestamp_inside_explicit_future_skew_can_be_fresh(self):
        result = classify_oracle_v2_slot(
            price_raw=1_000_000,
            timestamp_raw=1_780_000_002_000,
            observed_at_ms=1_780_000_001_000,
            policy=policy(),
            timestamp_unit_evidence=unit_evidence(),
        )

        self.assertEqual(result["classification"], FRESH)
        self.assertEqual(result["age_ms"], -1_000)
        self.assertEqual(result["future_offset_ms"], 1_000)
        self.assertTrue(result["cmis_price_eligible"])

    def test_age_equal_to_max_age_is_fresh(self):
        result = classify_oracle_v2_slot(
            price_raw=1_000_000,
            timestamp_raw=1_780_000_000_000,
            observed_at_ms=1_780_000_060_000,
            policy=policy(),
            timestamp_unit_evidence=unit_evidence(),
        )

        self.assertEqual(result["classification"], FRESH)
        self.assertEqual(result["age_ms"], 60_000)
        self.assertTrue(result["cmis_price_eligible"])

    def test_age_above_max_age_is_stale(self):
        result = classify_oracle_v2_slot(
            price_raw=1_000_000,
            timestamp_raw=1_780_000_000_000,
            observed_at_ms=1_780_000_060_001,
            policy=policy(),
            timestamp_unit_evidence=unit_evidence(),
        )

        self.assertEqual(result["classification"], STALE)
        self.assertEqual(result["age_ms"], 60_001)
        self.assertFalse(result["cmis_price_eligible"])

    def test_insufficient_eligible_slots_returns_partial_without_median(self):
        slots = [
            {
                "relay_index": 1,
                "price_raw": 1_000_000,
                "timestamp_raw": 1_780_000_000_000,
            },
            {
                "relay_index": 2,
                "price_raw": 1_100_000,
                "timestamp_raw": 1_780_000_000_000,
            },
            {
                "relay_index": 3,
                "price_raw": 1_200_000,
                "timestamp_raw": 1_779_999_000_000,
            },
        ]

        result = aggregate_oracle_v2_slots(
            slots,
            observed_at_ms=1_780_000_001_000,
            policy=policy(),
            timestamp_unit_evidence=unit_evidence(),
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["eligible_slot_count"], 2)
        self.assertIsNone(result["median_price"])
        self.assertEqual(result["classification_counts"][FRESH], 2)
        self.assertEqual(result["classification_counts"][STALE], 1)

    def test_zero_eligible_slots_returns_unavailable(self):
        slots = [
            {
                "relay_index": 1,
                "price_raw": 0,
                "timestamp_raw": 1_780_000_000_000,
            },
            {
                "relay_index": 2,
                "price_raw": 1_100_000,
                "timestamp_raw": 1_779_999_000_000,
            },
        ]

        result = aggregate_oracle_v2_slots(
            slots,
            observed_at_ms=1_780_000_001_000,
            policy=policy(),
            timestamp_unit_evidence=unit_evidence(),
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["eligible_slot_count"], 0)
        self.assertIsNone(result["median_price"])

    def test_minimum_slots_met_produces_exact_odd_median(self):
        slots = [
            {
                "relay_index": 1,
                "price_raw": 1_100_000,
                "timestamp_raw": 1_780_000_000_000,
            },
            {
                "relay_index": 2,
                "price_raw": 1_000_000,
                "timestamp_raw": 1_780_000_000_000,
            },
            {
                "relay_index": 3,
                "price_raw": 1_200_000,
                "timestamp_raw": 1_780_000_000_000,
            },
        ]

        result = aggregate_oracle_v2_slots(
            slots,
            observed_at_ms=1_780_000_001_000,
            policy=policy(),
            timestamp_unit_evidence=unit_evidence(),
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["eligible_slot_count"], 3)
        self.assertEqual(result["median_price_raw_numerator"], 1_100_000)
        self.assertEqual(result["median_price_raw_denominator"], 1)
        self.assertEqual(result["median_price"], "1.1")
        self.assertFalse(result["current_price_use_authorized"])
        self.assertFalse(result["cmis_provider_promoted"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_even_median_is_exact_without_float_rounding(self):
        result = aggregate_oracle_v2_slots(
            [
                {
                    "relay_index": 1,
                    "price_raw": 1_000_000,
                    "timestamp_raw": 1_780_000_000_000,
                },
                {
                    "relay_index": 2,
                    "price_raw": 1_000_001,
                    "timestamp_raw": 1_780_000_000_000,
                },
            ],
            observed_at_ms=1_780_000_001_000,
            policy=policy(
                minimum_eligible_slots=2,
                minimum_eligible_slots_provenance="test fixture only",
            ),
            timestamp_unit_evidence=unit_evidence(),
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["median_price_raw_numerator"], 2_000_001)
        self.assertEqual(result["median_price_raw_denominator"], 2)
        self.assertEqual(result["median_price"], "1.0000005")


if __name__ == "__main__":
    unittest.main()
