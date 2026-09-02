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
            rows = fetch_price_history(
                WRAPPED_XNT_MINT,
                USDC_X_MINT,
                time_from=requested - 9 * BAR_INTERVAL_SECONDS,
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
                requested_closed_bar_start=requested,
                provider_rows=rows,
                evaluation_time=evaluated_at,
            )
            break

        self.assertIsNotNone(result, "minute boundary kept moving during bounded retry")

        evidence = {
            "schema": "xdex_xnt_history_current_end_live.v1",
            "pair": f"{WRAPPED_XNT_MINT}/{USDC_X_MINT}",
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
        self.assertTrue(result["latest_expected_closed_bar_verified"])
        self.assertTrue(result["canonical_fact_timestamp_verified"])
        self.assertTrue(result["freshness_verified"])
        self.assertTrue(result["current_end_coverage_verified"])

        self.assertFalse(result["provider_range_complete_verified"])
        self.assertFalse(result["continuous_coverage_verified"])
        self.assertFalse(result["full_asset_lifetime_verified"])


if __name__ == "__main__":
    unittest.main()
