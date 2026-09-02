import json
import os
import time
import unittest
from datetime import datetime, timezone

from liquidity_scout.providers.x1.xdex import fetch_price_history
from liquidity_scout.providers.x1.xdex_history_current_end import (
    BAR_INTERVAL_SECONDS,
    FRESHNESS_BOUND_SECONDS,
    evaluate_xdex_history_current_end,
)
from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)


RUN_LIVE = os.getenv("RUN_XDEX_XNT_CURRENT_END_LIVE") == "1"
TAIL_INTERVAL_COUNT = 10


def _iso(value):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_XNT_CURRENT_END_LIVE=1 to verify fresh closed XDEX history end",
)
class XDEXXNTCurrentEndLiveTests(unittest.TestCase):
    def test_recent_closed_bar_reaches_current_end_policy(self):
        result = None

        # If a minute boundary rolls during the request, retry against the newly
        # closed minute so a transport race cannot masquerade as stale history.
        for _attempt in range(3):
            before = int(time.time())
            requested = (
                (before // BAR_INTERVAL_SECONDS) * BAR_INTERVAL_SECONDS
                - BAR_INTERVAL_SECONDS
            )
            start = requested - (TAIL_INTERVAL_COUNT - 1) * BAR_INTERVAL_SECONDS
            rows = fetch_price_history(
                WRAPPED_XNT_MINT,
                USDC_X_MINT,
                time_from=start,
                time_to=requested,
            )
            evaluated_at = int(time.time())

            current_closed = (
                (evaluated_at // BAR_INTERVAL_SECONDS) * BAR_INTERVAL_SECONDS
                - BAR_INTERVAL_SECONDS
            )
            if current_closed != requested:
                continue

            result = evaluate_xdex_history_current_end(
                base_mint=WRAPPED_XNT_MINT,
                quote_mint=USDC_X_MINT,
                requested_time_from=start,
                requested_closed_bar_start=requested,
                provider_rows=rows,
                evaluation_time=evaluated_at,
            )
            break

        self.assertIsNotNone(result, "minute boundary kept moving during bounded retry")

        evidence = {
            "schema": "xdex_xnt_history_current_end_live.v2",
            "pair": f"{WRAPPED_XNT_MINT}/{USDC_X_MINT}",
            "requested_time_from": result["requested_time_from"],
            "requested_time_from_utc": _iso(result["requested_time_from"]),
            "requested_closed_bar_start": result[
                "requested_closed_bar_start"
            ],
            "requested_closed_bar_start_utc": _iso(
                result["requested_closed_bar_start"]
            ),
            "provider_latest_observed_at": result[
                "provider_latest_observed_at"
            ],
            "provider_latest_observed_at_utc": _iso(
                result["provider_latest_observed_at"]
            ),
            "evaluation_time": result["evaluation_time"],
            "evaluation_time_utc": _iso(result["evaluation_time"]),
            "interval_seconds": result["interval_seconds"],
            "freshness_bound_seconds": result["freshness_bound_seconds"],
            "age_seconds": result["age_seconds"],
            "expected_timestamp_count": result["expected_timestamp_count"],
            "unique_timestamp_count": result["unique_timestamp_count"],
            "missing_timestamp_count": result["missing_timestamp_count"],
            "unexpected_timestamp_count": result["unexpected_timestamp_count"],
            "conflicting_duplicate_timestamp_count": result[
                "conflicting_duplicate_timestamp_count"
            ],
            "exact_pair_identity_bound": result["exact_pair_identity_bound"],
            "tail_continuity_verified": result["tail_continuity_verified"],
            "latest_expected_closed_bar_verified": result[
                "latest_expected_closed_bar_verified"
            ],
            "canonical_fact_timestamp_verified": result[
                "canonical_fact_timestamp_verified"
            ],
            "freshness_verified": result["freshness_verified"],
            "current_end_coverage_verified": result[
                "current_end_coverage_verified"
            ],
            "provider_range_complete_verified": result[
                "provider_range_complete_verified"
            ],
            "continuous_coverage_verified": result[
                "continuous_coverage_verified"
            ],
            "full_asset_lifetime_verified": result[
                "full_asset_lifetime_verified"
            ],
            "limitations": result["limitations"],
        }

        print("XDEX XNT CURRENT-END COVERAGE EVIDENCE")
        print(json.dumps(evidence, sort_keys=True))

        self.assertEqual(
            result["freshness_bound_seconds"],
            FRESHNESS_BOUND_SECONDS,
        )
        self.assertTrue(result["exact_pair_identity_bound"])
        self.assertTrue(result["tail_continuity_verified"])
        self.assertEqual(result["missing_timestamp_count"], 0)
        self.assertEqual(result["unexpected_timestamp_count"], 0)
        self.assertEqual(result["conflicting_duplicate_timestamp_count"], 0)
        self.assertTrue(result["latest_expected_closed_bar_verified"])
        self.assertTrue(result["canonical_fact_timestamp_verified"])
        self.assertTrue(result["freshness_verified"])
        self.assertTrue(result["current_end_coverage_verified"])

        self.assertFalse(result["provider_range_complete_verified"])
        self.assertFalse(result["continuous_coverage_verified"])
        self.assertFalse(result["full_asset_lifetime_verified"])


if __name__ == "__main__":
    unittest.main()
