import json
import os
import time
import unittest
from datetime import datetime, timezone

from liquidity_scout.providers.x1.xdex import fetch_price_history
from liquidity_scout.providers.x1.xdex_forward_bar_continuity import (
    scan_xdex_forward_bar_continuity,
)
from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)


RUN_LIVE = os.getenv("RUN_XDEX_XNT_FORWARD_CONTINUITY_LIVE") == "1"
FIRST_BAR_START = 1767392640
INTERVAL_SECONDS = 60


def _positive_int_env(name, default):
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _nonnegative_float_env(name, default):
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return float(default)
    value = float(raw)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _positive_float_env(name, default):
    value = _nonnegative_float_env(name, default)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _iso(value):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _rate_limit_aware_fetcher(*, request_delay_seconds, max_retries, retry_base_seconds):
    state = {
        "request_count": 0,
        "rate_limit_retry_count": 0,
        "last_request_monotonic": None,
        "total_retry_sleep_seconds": 0.0,
    }

    def fetcher(base, quote, *, time_from, time_to):
        last = state["last_request_monotonic"]
        if last is not None and request_delay_seconds > 0:
            elapsed = time.monotonic() - last
            remaining = request_delay_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)

        for attempt in range(max_retries + 1):
            state["request_count"] += 1
            state["last_request_monotonic"] = time.monotonic()
            try:
                return fetch_price_history(
                    base,
                    quote,
                    time_from=time_from,
                    time_to=time_to,
                )
            except Exception as exc:
                message = str(exc)
                rate_limited = (
                    "429" in message
                    or "Rate limit exceeded" in message
                    or "Too Many Requests" in message
                )
                if not rate_limited or attempt >= max_retries:
                    raise

                state["rate_limit_retry_count"] += 1
                backoff = min(
                    60.0,
                    retry_base_seconds * (2 ** attempt),
                )
                state["total_retry_sleep_seconds"] += backoff
                time.sleep(backoff)
                state["last_request_monotonic"] = time.monotonic()

        raise AssertionError("unreachable")

    return fetcher, state


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_XNT_FORWARD_CONTINUITY_LIVE=1 to scan read-only XNT continuity",
)
class XDEXXNTForwardContinuityLiveTests(unittest.TestCase):
    def test_verified_start_to_recent_closed_bar_continuity(self):
        # Avoid the moving/current bar. End at the last fully closed minute.
        end = (int(time.time()) // INTERVAL_SECONDS) * INTERVAL_SECONDS - INTERVAL_SECONDS

        window_minutes = _positive_int_env(
            "XDEX_XNT_CONTINUITY_WINDOW_MINUTES",
            1440,
        )
        max_windows = _positive_int_env(
            "XDEX_XNT_CONTINUITY_MAX_WINDOWS",
            400,
        )
        request_delay_seconds = _nonnegative_float_env(
            "XDEX_XNT_CONTINUITY_REQUEST_DELAY_SECONDS",
            1.10,
        )
        max_retries = _positive_int_env(
            "XDEX_XNT_CONTINUITY_MAX_RETRIES",
            6,
        )
        retry_base_seconds = _positive_float_env(
            "XDEX_XNT_CONTINUITY_RETRY_BASE_SECONDS",
            5.0,
        )

        fetcher, transport = _rate_limit_aware_fetcher(
            request_delay_seconds=request_delay_seconds,
            max_retries=max_retries,
            retry_base_seconds=retry_base_seconds,
        )

        result = scan_xdex_forward_bar_continuity(
            WRAPPED_XNT_MINT,
            USDC_X_MINT,
            time_from=FIRST_BAR_START,
            time_to=end,
            interval_seconds=INTERVAL_SECONDS,
            window_intervals=window_minutes,
            max_windows=max_windows,
            fetcher=fetcher,
        )

        evidence = {
            "schema": "xdex_xnt_forward_continuity_live.v2",
            "pair": f"{WRAPPED_XNT_MINT}/{USDC_X_MINT}",
            "time_from": result["time_from"],
            "time_from_utc": _iso(result["time_from"]),
            "time_to": result["time_to"],
            "time_to_utc": _iso(result["time_to"]),
            "interval_seconds": result["interval_seconds"],
            "window_intervals": result["window_intervals"],
            "expected_timestamp_count": result["expected_timestamp_count"],
            "expected_window_count": result["expected_window_count"],
            "requested_window_count": result["requested_window_count"],
            "total_returned_rows": result["total_returned_rows"],
            "total_unique_timestamp_count": result[
                "total_unique_timestamp_count"
            ],
            "missing_timestamp_count": result["missing_timestamp_count"],
            "missing_timestamp_sample": result["missing_timestamp_sample"],
            "unexpected_timestamp_count": result["unexpected_timestamp_count"],
            "duplicate_timestamp_count": result["duplicate_timestamp_count"],
            "conflicting_duplicate_timestamp_count": result[
                "conflicting_duplicate_timestamp_count"
            ],
            "observed_gap_count": result["observed_gap_count"],
            "largest_observed_gap_seconds": result[
                "largest_observed_gap_seconds"
            ],
            "scan_end_reached": result["scan_end_reached"],
            "all_windows_verified": result["all_windows_verified"],
            "bounded_continuity_verified": result[
                "bounded_continuity_verified"
            ],
            "continuous_coverage_verified": result[
                "continuous_coverage_verified"
            ],
            "provider_range_complete_verified": result[
                "provider_range_complete_verified"
            ],
            "full_asset_lifetime_verified": result[
                "full_asset_lifetime_verified"
            ],
            "failure_reason": result["failure_reason"],
            "request_delay_seconds": request_delay_seconds,
            "transport_request_count": transport["request_count"],
            "rate_limit_retry_count": transport["rate_limit_retry_count"],
            "total_retry_sleep_seconds": round(
                transport["total_retry_sleep_seconds"],
                3,
            ),
            "first_window": result["windows"][0] if result["windows"] else None,
            "last_window": result["windows"][-1] if result["windows"] else None,
            "limitations": result["limitations"],
        }

        print("XDEX XNT FORWARD CONTINUITY EVIDENCE")
        print(json.dumps(evidence, sort_keys=True))

        self.assertTrue(result["scan_end_reached"])
        self.assertTrue(result["all_windows_verified"])
        self.assertTrue(result["bounded_continuity_verified"])
        self.assertEqual(result["missing_timestamp_count"], 0)
        self.assertEqual(result["unexpected_timestamp_count"], 0)
        self.assertEqual(result["conflicting_duplicate_timestamp_count"], 0)

        # This proof is intentionally not the final lifetime promotion gate.
        self.assertFalse(result["continuous_coverage_verified"])
        self.assertFalse(result["provider_range_complete_verified"])
        self.assertFalse(result["full_asset_lifetime_verified"])


if __name__ == "__main__":
    unittest.main()
