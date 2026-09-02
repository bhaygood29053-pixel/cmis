import json
import os
import time
import unittest

from liquidity_scout.providers.x1.xdex import fetch_price_history
from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)


RUN_LIVE = os.getenv("RUN_XDEX_XNT_HISTORY_RANGE_LIVE") == "1"
INTERVAL_SECONDS = 60
DAY = 86400


def _rows_by_timestamp(rows):
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise AssertionError(f"history row must be a mapping: {row!r}")
        ts = row.get("t")
        if isinstance(ts, bool) or not isinstance(ts, int):
            raise AssertionError(f"history t must be an integer: {row!r}")
        if ts in result and result[ts] != row:
            raise AssertionError(f"conflicting duplicate timestamp: {ts}")
        result[ts] = dict(row)
    return result


def _summary(label, start, end, rows):
    timestamps = sorted(_rows_by_timestamp(rows))
    return {
        "label": label,
        "time_from": start,
        "time_to": end,
        "returned_count": len(rows),
        "first_returned_at": timestamps[0] if timestamps else None,
        "last_returned_at": timestamps[-1] if timestamps else None,
        "all_rows_within_requested_range": all(
            start <= ts <= end for ts in timestamps
        ),
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_XNT_HISTORY_RANGE_LIVE=1 to run read-only XNT range evidence",
)
class XDEXXNTHistoryRangeSemanticLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Avoid the moving current minute so repeated/split requests observe a
        # stable closed-bar range.
        cls.end = (int(time.time()) // INTERVAL_SECONDS) * INTERVAL_SECONDS - INTERVAL_SECONDS

    def test_split_window_union_matches_single_window_for_closed_recent_range(self):
        end = self.end
        start = end - DAY
        midpoint = start + DAY // 2

        full = fetch_price_history(
            WRAPPED_XNT_MINT,
            USDC_X_MINT,
            time_from=start,
            time_to=end,
        )
        left = fetch_price_history(
            WRAPPED_XNT_MINT,
            USDC_X_MINT,
            time_from=start,
            time_to=midpoint,
        )
        right = fetch_price_history(
            WRAPPED_XNT_MINT,
            USDC_X_MINT,
            time_from=midpoint,
            time_to=end,
        )

        full_by_t = _rows_by_timestamp(full)
        union_by_t = _rows_by_timestamp([*left, *right])
        overlap = sorted(set(full_by_t) & set(union_by_t))
        mismatches = [
            ts for ts in overlap if full_by_t[ts] != union_by_t[ts]
        ]

        evidence = {
            "schema": "xdex_xnt_history_range_semantics_live.v1",
            "pair": f"{WRAPPED_XNT_MINT}/{USDC_X_MINT}",
            "full": _summary("full_24h", start, end, full),
            "left": _summary("left_12h", start, midpoint, left),
            "right": _summary("right_12h", midpoint, end, right),
            "full_unique_timestamps": len(full_by_t),
            "split_union_unique_timestamps": len(union_by_t),
            "timestamp_sets_equal": set(full_by_t) == set(union_by_t),
            "overlap_row_mismatch_count": len(mismatches),
            "split_union_exact_match": full_by_t == union_by_t,
            "provider_range_complete_verified": False,
        }
        print("XDEX XNT SPLIT-RANGE EVIDENCE")
        print(json.dumps(evidence, sort_keys=True))

        self.assertTrue(full, "XDEX returned no recent XNT/USDC.X history")
        self.assertTrue(left, "XDEX returned no left-half history")
        self.assertTrue(right, "XDEX returned no right-half history")
        self.assertTrue(evidence["full"]["all_rows_within_requested_range"])
        self.assertTrue(evidence["left"]["all_rows_within_requested_range"])
        self.assertTrue(evidence["right"]["all_rows_within_requested_range"])
        # Exact split/full equality is evidence for deterministic requested-range
        # behavior. It is still not, by itself, archive/lifetime completeness.
        self.assertTrue(evidence["timestamp_sets_equal"])
        self.assertEqual(evidence["overlap_row_mismatch_count"], 0)

    def test_bounded_retention_map_records_old_windows_without_promotion(self):
        observations = []
        for age_days in (0, 7, 30, 90, 180, 365):
            end = self.end - age_days * DAY
            start = end - DAY
            rows = fetch_price_history(
                WRAPPED_XNT_MINT,
                USDC_X_MINT,
                time_from=start,
                time_to=end,
            )
            observations.append(
                _summary(f"age_{age_days}d", start, end, rows)
            )

        evidence = {
            "schema": "xdex_xnt_history_retention_map_live.v1",
            "pair": f"{WRAPPED_XNT_MINT}/{USDC_X_MINT}",
            "windows": observations,
            "provider_range_complete_verified": False,
            "archive_exhaustion_verified": False,
            "full_asset_lifetime_verified": False,
        }
        print("XDEX XNT RETENTION MAP EVIDENCE")
        print(json.dumps(evidence, sort_keys=True))

        self.assertTrue(
            observations[0]["returned_count"] > 0,
            "XDEX returned no recent XNT/USDC.X history",
        )
        self.assertTrue(
            all(item["all_rows_within_requested_range"] for item in observations),
            "at least one historical window returned a row outside its request scope",
        )


if __name__ == "__main__":
    unittest.main()
