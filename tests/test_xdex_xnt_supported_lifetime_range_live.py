import json
import os
import time
import unittest
from datetime import datetime, timezone

from liquidity_scout.providers.x1.xdex import fetch_price_history
from liquidity_scout.providers.x1.xdex_history_current_end import (
    BAR_INTERVAL_SECONDS,
    evaluate_xdex_history_current_end,
)
from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)
from liquidity_scout.providers.x1.xdex_supported_lifetime_range import (
    evaluate_xdex_supported_lifetime_range,
)
from liquidity_scout.services.x1_quote_price_historical_coverage import (
    evaluate_x1_quote_price_historical_coverage,
)


RUN_LIVE = os.getenv("RUN_XDEX_XNT_SUPPORTED_LIFETIME_LIVE") == "1"

FIRST_BAR_START = 1767392640
MARKET_OPEN_AT = 1767392668

# Accepted full forward-continuity checkpoint from the 243-window live sweep:
# 348,834 / 348,834 expected 60-second bars, zero missing/gaps/conflicts.
FORWARD_SCAN_END = 1788322620
FORWARD_EXPECTED_TIMESTAMP_COUNT = 348834


def _iso(value):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _accepted_archive_start():
    return {
        "base_mint": WRAPPED_XNT_MINT,
        "quote_mint": USDC_X_MINT,
        "archive_start_exhaustion_verified": True,
        "archive_exhaustion_verified": True,
        "first_provider_observation": FIRST_BAR_START,
        "lifetime_start_anchor": {
            "kind": "first_verified_supported_market_interval",
            "verified": True,
            "observed_at": FIRST_BAR_START,
            "interval_seconds": BAR_INTERVAL_SECONDS,
            "market_open_at": MARKET_OPEN_AT,
            "open_time_semantics_verified": True,
        },
    }


def _accepted_forward_continuity():
    return {
        "base_mint": WRAPPED_XNT_MINT,
        "quote_mint": USDC_X_MINT,
        "time_from": FIRST_BAR_START,
        "time_to": FORWARD_SCAN_END,
        "interval_seconds": BAR_INTERVAL_SECONDS,
        "expected_timestamp_count": FORWARD_EXPECTED_TIMESTAMP_COUNT,
        "total_unique_timestamp_count": FORWARD_EXPECTED_TIMESTAMP_COUNT,
        "missing_timestamp_count": 0,
        "unexpected_timestamp_count": 0,
        "conflicting_duplicate_timestamp_count": 0,
        "observed_gap_count": 0,
        "largest_observed_gap_seconds": 0,
        "scan_end_reached": True,
        "all_windows_verified": True,
        "bounded_continuity_verified": True,
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_XNT_SUPPORTED_LIFETIME_LIVE=1 to close the XNT lifetime seam",
)
class XDEXXNTSupportedLifetimeRangeLiveTests(unittest.TestCase):
    def test_forward_checkpoint_to_fresh_end_has_no_seam(self):
        result = None

        # Retry only if the minute boundary moves while the read is in flight.
        for _attempt in range(3):
            before = int(time.time())
            requested = (
                (before // BAR_INTERVAL_SECONDS) * BAR_INTERVAL_SECONDS
                - BAR_INTERVAL_SECONDS
            )
            self.assertGreaterEqual(
                requested,
                FORWARD_SCAN_END,
                "current closed bar unexpectedly predates accepted forward checkpoint",
            )

            rows = fetch_price_history(
                WRAPPED_XNT_MINT,
                USDC_X_MINT,
                time_from=FORWARD_SCAN_END,
                time_to=requested,
            )
            evaluated_at = int(time.time())
            current_closed = (
                (evaluated_at // BAR_INTERVAL_SECONDS) * BAR_INTERVAL_SECONDS
                - BAR_INTERVAL_SECONDS
            )
            if current_closed != requested:
                continue

            current_end = evaluate_xdex_history_current_end(
                base_mint=WRAPPED_XNT_MINT,
                quote_mint=USDC_X_MINT,
                requested_time_from=FORWARD_SCAN_END,
                requested_closed_bar_start=requested,
                provider_rows=rows,
                evaluation_time=evaluated_at,
            )

            supported_range = evaluate_xdex_supported_lifetime_range(
                archive_start=_accepted_archive_start(),
                continuity=_accepted_forward_continuity(),
                current_end=current_end,
            )

            quote_lifetime = evaluate_x1_quote_price_historical_coverage(
                supported_lifetime_range=supported_range,
                exact_pair_quote_identity_verified=True,
                canonical_fact_timestamps_verified=True,
                historical_quote_usd_equivalence_verified=False,
            )

            result = {
                "current_end": current_end,
                "supported_range": supported_range,
                "quote_lifetime": quote_lifetime,
            }
            break

        self.assertIsNotNone(result, "minute boundary kept moving during bounded retry")
        current_end = result["current_end"]
        supported_range = result["supported_range"]
        quote_lifetime = result["quote_lifetime"]

        evidence = {
            "schema": "xdex_xnt_supported_lifetime_range_live.v1",
            "pair": f"{WRAPPED_XNT_MINT}/{USDC_X_MINT}",
            "lifetime_start": FIRST_BAR_START,
            "lifetime_start_utc": _iso(FIRST_BAR_START),
            "forward_checkpoint_end": FORWARD_SCAN_END,
            "forward_checkpoint_end_utc": _iso(FORWARD_SCAN_END),
            "forward_checkpoint_expected_timestamp_count": (
                FORWARD_EXPECTED_TIMESTAMP_COUNT
            ),
            "seam_tail_from": current_end["requested_time_from"],
            "seam_tail_from_utc": _iso(current_end["requested_time_from"]),
            "fresh_current_end": current_end["provider_latest_observed_at"],
            "fresh_current_end_utc": _iso(
                current_end["provider_latest_observed_at"]
            ),
            "seam_expected_timestamp_count": current_end[
                "expected_timestamp_count"
            ],
            "seam_unique_timestamp_count": current_end[
                "unique_timestamp_count"
            ],
            "seam_missing_timestamp_count": current_end[
                "missing_timestamp_count"
            ],
            "seam_unexpected_timestamp_count": current_end[
                "unexpected_timestamp_count"
            ],
            "seam_conflicting_duplicate_timestamp_count": current_end[
                "conflicting_duplicate_timestamp_count"
            ],
            "seam_tail_continuity_verified": current_end[
                "tail_continuity_verified"
            ],
            "current_end_coverage_verified": current_end[
                "current_end_coverage_verified"
            ],
            "supported_lifetime_gates": supported_range["gates"],
            "supported_lifetime_range_complete_verified": supported_range[
                "supported_lifetime_range_complete_verified"
            ],
            "provider_range_complete_verified": supported_range[
                "provider_range_complete_verified"
            ],
            "price_bar_continuity_verified": supported_range[
                "price_bar_continuity_verified"
            ],
            "global_provider_archive_complete_verified": supported_range[
                "global_provider_archive_complete_verified"
            ],
            "full_supported_pair_lifetime_verified": quote_lifetime[
                "full_supported_pair_lifetime_verified"
            ],
            "continuous_pair_price_coverage_verified": quote_lifetime[
                "continuous_pair_price_coverage_verified"
            ],
            "historical_quote_usd_equivalence_verified": quote_lifetime[
                "historical_quote_usd_equivalence_verified"
            ],
            "full_usd_lifetime_verified": quote_lifetime[
                "full_usd_lifetime_verified"
            ],
            "full_asset_lifetime_verified": quote_lifetime[
                "full_asset_lifetime_verified"
            ],
        }

        print("XDEX XNT SUPPORTED-LIFETIME RANGE EVIDENCE")
        print(json.dumps(evidence, sort_keys=True))

        self.assertTrue(current_end["tail_continuity_verified"])
        self.assertEqual(current_end["missing_timestamp_count"], 0)
        self.assertEqual(current_end["unexpected_timestamp_count"], 0)
        self.assertEqual(
            current_end["conflicting_duplicate_timestamp_count"],
            0,
        )
        self.assertTrue(current_end["current_end_coverage_verified"])

        self.assertTrue(
            supported_range["gates"]["forward_to_current_seam_verified"]
        )
        self.assertTrue(
            supported_range["supported_lifetime_range_complete_verified"]
        )
        self.assertTrue(supported_range["provider_range_complete_verified"])
        self.assertTrue(supported_range["price_bar_continuity_verified"])
        self.assertFalse(
            supported_range["global_provider_archive_complete_verified"]
        )

        self.assertTrue(
            quote_lifetime["full_supported_pair_lifetime_verified"]
        )
        self.assertTrue(
            quote_lifetime["continuous_pair_price_coverage_verified"]
        )
        self.assertFalse(
            quote_lifetime["historical_quote_usd_equivalence_verified"]
        )
        self.assertFalse(quote_lifetime["full_usd_lifetime_verified"])
        self.assertFalse(quote_lifetime["full_asset_lifetime_verified"])


if __name__ == "__main__":
    unittest.main()
