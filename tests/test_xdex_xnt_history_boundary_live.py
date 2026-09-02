import json
import os
import time
import unittest

from liquidity_scout.providers.x1.xdex import fetch_price_history
from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)


RUN_LIVE = os.getenv("RUN_XDEX_XNT_HISTORY_BOUNDARY_LIVE") == "1"
DAY = 86400
MINUTE = 60


def _probe_window(anchor_end, age_days):
    end = anchor_end - int(age_days) * DAY
    start = end - DAY
    rows = fetch_price_history(
        WRAPPED_XNT_MINT,
        USDC_X_MINT,
        time_from=start,
        time_to=end,
    )
    timestamps = []
    for row in rows:
        if not isinstance(row, dict):
            raise AssertionError(f"history row must be a mapping: {row!r}")
        ts = row.get("t")
        if isinstance(ts, bool) or not isinstance(ts, int):
            raise AssertionError(f"history t must be an integer: {row!r}")
        timestamps.append(ts)
    return {
        "age_days": int(age_days),
        "time_from": start,
        "time_to": end,
        "returned_count": len(rows),
        "first_returned_at": min(timestamps) if timestamps else None,
        "last_returned_at": max(timestamps) if timestamps else None,
        "all_rows_within_requested_range": all(
            start <= ts <= end for ts in timestamps
        ),
        "has_history": bool(rows),
    }


def _nearest_transition(observations):
    ordered = sorted(observations, key=lambda item: item["age_days"])
    transitions = []
    for newer, older in zip(ordered, ordered[1:]):
        if newer["has_history"] != older["has_history"]:
            transitions.append((newer, older))
    return transitions


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_XNT_HISTORY_BOUNDARY_LIVE=1 to narrow the read-only XNT history boundary",
)
class XDEXXNTHistoryBoundaryLiveTests(unittest.TestCase):
    def test_narrow_provider_visible_history_transition_without_promotion(self):
        anchor_end = (int(time.time()) // MINUTE) * MINUTE - MINUTE

        coarse_ages = (180, 210, 240, 270, 300, 330, 365)
        observations = [
            _probe_window(anchor_end, age) for age in coarse_ages
        ]

        self.assertTrue(
            all(item["all_rows_within_requested_range"] for item in observations)
        )
        self.assertTrue(observations[0]["has_history"])
        self.assertFalse(observations[-1]["has_history"])

        transitions = _nearest_transition(observations)
        refined_weekly = []
        refined_daily = []

        # Refine only a monotonic-looking non-empty -> empty transition. If the
        # provider shows non-monotonic visibility, preserve that as evidence and
        # do not infer a boundary.
        candidate = next(
            (pair for pair in transitions
             if pair[0]["has_history"] and not pair[1]["has_history"]),
            None,
        )

        if candidate is not None:
            newer, older = candidate
            start_age = newer["age_days"]
            end_age = older["age_days"]
            for age in range(start_age + 7, end_age, 7):
                refined_weekly.append(_probe_window(anchor_end, age))

            weekly_all = [newer, *refined_weekly, older]
            weekly_transitions = _nearest_transition(weekly_all)
            weekly_candidate = next(
                (pair for pair in weekly_transitions
                 if pair[0]["has_history"] and not pair[1]["has_history"]),
                None,
            )
            if weekly_candidate is not None:
                newer_w, older_w = weekly_candidate
                for age in range(
                    newer_w["age_days"] + 1,
                    older_w["age_days"],
                ):
                    refined_daily.append(_probe_window(anchor_end, age))

        all_observations = [
            *observations,
            *refined_weekly,
            *refined_daily,
        ]
        unique = {
            item["age_days"]: item for item in all_observations
        }
        ordered = [unique[age] for age in sorted(unique)]
        final_transitions = _nearest_transition(ordered)

        oldest_nonempty = max(
            (item for item in ordered if item["has_history"]),
            key=lambda item: item["age_days"],
            default=None,
        )
        newest_empty = min(
            (item for item in ordered if not item["has_history"]),
            key=lambda item: item["age_days"],
            default=None,
        )

        evidence = {
            "schema": "xdex_xnt_history_boundary_live.v1",
            "pair": f"{WRAPPED_XNT_MINT}/{USDC_X_MINT}",
            "observations": ordered,
            "oldest_nonempty_age_days": (
                oldest_nonempty["age_days"] if oldest_nonempty else None
            ),
            "oldest_nonempty_first_returned_at": (
                oldest_nonempty["first_returned_at"] if oldest_nonempty else None
            ),
            "newest_empty_age_days": (
                newest_empty["age_days"] if newest_empty else None
            ),
            "transition_count": len(final_transitions),
            "monotonic_single_transition_observed": len(final_transitions) == 1,
            "provider_range_complete_verified": False,
            "archive_exhaustion_verified": False,
            "asset_lifetime_start_verified": False,
            "full_asset_lifetime_verified": False,
            "continuous_coverage_verified": False,
        }

        print("XDEX XNT HISTORY BOUNDARY EVIDENCE")
        print(json.dumps(evidence, sort_keys=True))

        self.assertTrue(
            all(item["all_rows_within_requested_range"] for item in ordered)
        )


if __name__ == "__main__":
    unittest.main()
