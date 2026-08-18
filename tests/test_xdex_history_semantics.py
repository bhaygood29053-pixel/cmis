import unittest

from liquidity_scout.providers.x1.xdex_history_semantics import classify_xdex_history_semantics


class XDEXHistorySemanticTests(unittest.TestCase):
    def test_verified_timestamp_interval_and_independent_close(self):
        bars = [
            {"t": 1000, "c": "0.25", "v": "999"},
            {"t": 1060, "c": "0.26", "v": "888"},
            {"t": 1120, "c": "0.27", "v": "777"},
        ]
        result = classify_xdex_history_semantics(
            bars,
            requested_time_from=1000,
            requested_time_to=1120,
            corroborated_close_native="0.2700",
        )
        self.assertTrue(result.timestamp_unix_seconds_verified)
        self.assertTrue(result.interval_seconds_verified)
        self.assertEqual(result.interval_seconds, 60)
        self.assertTrue(result.close_native_verified)
        self.assertFalse(result.volume_semantics_verified)
        self.assertFalse(result.coverage_complete_verified)
        self.assertFalse(result.cmis_promotable)

    def test_close_does_not_promote_on_mismatch(self):
        result = classify_xdex_history_semantics(
            [{"t": 1000, "c": "0.25"}, {"t": 1060, "c": "0.26"}],
            requested_time_from=1000,
            requested_time_to=1060,
            corroborated_close_native="0.261",
        )
        self.assertFalse(result.close_native_verified)
        self.assertTrue(result.timestamp_unix_seconds_verified)

    def test_irregular_spacing_keeps_timestamp_semantics_unverified(self):
        result = classify_xdex_history_semantics(
            [{"t": 1000, "c": "1"}, {"t": 1061, "c": "1"}],
            requested_time_from=1000,
            requested_time_to=1100,
        )
        self.assertFalse(result.timestamp_unix_seconds_verified)
        self.assertFalse(result.interval_seconds_verified)
        self.assertIsNone(result.interval_seconds)

    def test_out_of_window_timestamp_is_not_verified(self):
        result = classify_xdex_history_semantics(
            [{"t": 940, "c": "1"}, {"t": 1000, "c": "1"}],
            requested_time_from=1000,
            requested_time_to=1100,
        )
        self.assertFalse(result.timestamp_unix_seconds_verified)

    def test_empty_sample_proves_nothing(self):
        result = classify_xdex_history_semantics(
            [], requested_time_from=1000, requested_time_to=1100
        )
        self.assertFalse(result.close_native_verified)
        self.assertFalse(result.timestamp_unix_seconds_verified)
        self.assertFalse(result.volume_semantics_verified)

    def test_requires_raw_t_and_c(self):
        with self.assertRaises(ValueError):
            classify_xdex_history_semantics(
                [{"t": 1000}], requested_time_from=1000, requested_time_to=1100
            )

    def test_rejects_boolean_timestamp(self):
        with self.assertRaises(ValueError):
            classify_xdex_history_semantics(
                [{"t": True, "c": "1"}], requested_time_from=1, requested_time_to=2
            )

    def test_rejects_nonfinite_close(self):
        with self.assertRaises(ValueError):
            classify_xdex_history_semantics(
                [{"t": 1000, "c": "NaN"}], requested_time_from=1000, requested_time_to=1100
            )


if __name__ == "__main__":
    unittest.main()
