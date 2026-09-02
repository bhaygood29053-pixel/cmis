import json
import os
import unittest
from datetime import datetime, timezone

from liquidity_scout.providers.x1.xdex import fetch_price_history
from liquidity_scout.providers.x1.xdex_archive_start_exhaustion import (
    evaluate_xdex_archive_start_exhaustion,
)
from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)


RUN_LIVE = os.getenv("RUN_XDEX_XNT_ARCHIVE_START_LIVE") == "1"

# Accepted XNT/USDC.X lifetime-start interval from the v4 inception proof.
FIRST_BAR_START = 1767392640
MARKET_OPEN_AT = 1767392668
INTERVAL_SECONDS = 60

# Boundary-local probe geometry: 6h before the first bar and 6h after it.
PRE_SECONDS = 6 * 60 * 60
POST_SECONDS = 6 * 60 * 60


def _iso(value):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _fetch_window(start, end):
    return {
        "time_from": start,
        "time_to": end,
        "rows": fetch_price_history(
            WRAPPED_XNT_MINT,
            USDC_X_MINT,
            time_from=start,
            time_to=end,
        ),
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_XNT_ARCHIVE_START_LIVE=1 to run read-only XNT archive-start evidence",
)
class XDEXXNTArchiveStartExhaustionLiveTests(unittest.TestCase):
    def test_archive_reaches_verified_market_start_without_lifetime_overpromotion(self):
        pre_start = FIRST_BAR_START - PRE_SECONDS
        pre_end = FIRST_BAR_START - 1
        post_start = FIRST_BAR_START
        post_end = FIRST_BAR_START + POST_SECONDS
        crossing_start = pre_start
        crossing_end = post_end

        pre = _fetch_window(pre_start, pre_end)
        crossing = _fetch_window(crossing_start, crossing_end)
        post = _fetch_window(post_start, post_end)
        repeat = _fetch_window(crossing_start, crossing_end)

        anchor = {
            "kind": "first_verified_supported_market_interval",
            "verified": True,
            "observed_at": FIRST_BAR_START,
            "interval_seconds": INTERVAL_SECONDS,
            "market_open_at": MARKET_OPEN_AT,
            "open_time_semantics_verified": True,
        }

        proof = evaluate_xdex_archive_start_exhaustion(
            anchor,
            base_mint=WRAPPED_XNT_MINT,
            quote_mint=USDC_X_MINT,
            pre_window=pre,
            crossing_window=crossing,
            post_window=post,
            repeat_crossing_window=repeat,
        )

        evidence = {
            "schema": "xdex_xnt_archive_start_exhaustion_live.v1",
            "pair": f"{WRAPPED_XNT_MINT}/{USDC_X_MINT}",
            "market_open_at": MARKET_OPEN_AT,
            "market_open_at_utc": _iso(MARKET_OPEN_AT),
            "first_verified_supported_market_interval": FIRST_BAR_START,
            "first_verified_supported_market_interval_utc": _iso(FIRST_BAR_START),
            "archive_start_exhaustion_verified": proof.get(
                "archive_start_exhaustion_verified"
            ),
            "archive_exhaustion_verified": proof.get(
                "archive_exhaustion_verified"
            ),
            "provider_range_complete_verified": proof.get(
                "provider_range_complete_verified"
            ),
            "continuous_coverage_verified": proof.get(
                "continuous_coverage_verified"
            ),
            "full_asset_lifetime_verified": proof.get(
                "full_asset_lifetime_verified"
            ),
            "gates": proof.get("gates"),
            "pre_window": proof.get("pre_window"),
            "crossing_window": proof.get("crossing_window"),
            "post_window": proof.get("post_window"),
            "repeat_crossing_window": proof.get("repeat_crossing_window"),
            "first_provider_observation": proof.get("first_provider_observation"),
            "second_provider_observation": proof.get("second_provider_observation"),
            "limitations": proof.get("limitations"),
        }

        print("XDEX XNT ARCHIVE-START EXHAUSTION EVIDENCE")
        print(json.dumps(evidence, sort_keys=True))

        self.assertTrue(proof["archive_start_exhaustion_verified"])
        self.assertTrue(proof["archive_exhaustion_verified"])
        self.assertFalse(proof["provider_range_complete_verified"])
        self.assertFalse(proof["continuous_coverage_verified"])
        self.assertFalse(proof["full_asset_lifetime_verified"])


if __name__ == "__main__":
    unittest.main()
