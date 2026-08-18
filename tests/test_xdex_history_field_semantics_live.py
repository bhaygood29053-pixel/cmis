import math
import os
import time
import unittest

from liquidity_scout.providers.x1.ninja_history import fetch_pool_ohlcv_raw
from liquidity_scout.providers.x1.xdex import fetch_price_history


RUN_LIVE = os.getenv("RUN_XDEX_NINJA_HISTORY_LIVE") == "1"
XENCAT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XNT = "So11111111111111111111111111111111111111112"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
EXPECTED_INTERVAL_SECONDS = 60


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_NINJA_HISTORY_LIVE=1 to run read-only XDEX history field semantic evidence",
)
class XDEXHistoryFieldSemanticLiveTests(unittest.TestCase):
    def test_timestamp_interval_and_native_close_semantics(self):
        now = int(time.time())
        start = now - 24 * 60 * 60
        bars = fetch_price_history(
            XENCAT,
            XNT,
            time_from=start,
            time_to=now,
        )
        self.assertGreaterEqual(len(bars), 2)
        self.assertTrue(all(isinstance(row, dict) for row in bars))
        self.assertTrue(all({"o", "h", "l", "c", "v", "t"}.issubset(row) for row in bars))

        times = []
        for row in bars:
            t = row.get("t")
            self.assertIsInstance(t, int, f"XDEX t must remain an integer Unix-second candidate: {row}")
            times.append(t)
            o = _num(row.get("o"))
            h = _num(row.get("h"))
            l = _num(row.get("l"))
            c = _num(row.get("c"))
            self.assertTrue(all(value is not None for value in (o, h, l, c)))
            self.assertLessEqual(l, h)
            self.assertGreaterEqual(o, l)
            self.assertLessEqual(o, h)
            self.assertGreaterEqual(c, l)
            self.assertLessEqual(c, h)

        self.assertEqual(times, sorted(times), "XDEX bars must remain oldest-to-newest for this verified contract")
        deltas = [b - a for a, b in zip(times, times[1:])]
        self.assertTrue(deltas)
        self.assertTrue(
            all(delta == EXPECTED_INTERVAL_SECONDS for delta in deltas),
            f"XDEX history no longer presents a continuous 60-second bar timeline: observed deltas={sorted(set(deltas))}",
        )

        # Unix-second scope: the requested range is seconds, and returned bars
        # remain in a nearby seconds-scale window rather than ms/us/ns units.
        self.assertGreaterEqual(times[0], start - EXPECTED_INTERVAL_SECONDS)
        self.assertLessEqual(times[-1], now + EXPECTED_INTERVAL_SECONDS)

        ninja = fetch_pool_ohlcv_raw(POOL, timeframe="1m", limit=10)["raw_response"]
        current_native = _num(ninja.get("currentPriceNative"))
        self.assertIsNotNone(current_native)
        latest_close = _num(bars[-1].get("c"))
        self.assertIsNotNone(latest_close)
        self.assertTrue(
            math.isclose(latest_close, current_native, rel_tol=1e-9, abs_tol=1e-15),
            f"Latest XDEX c must remain the same native-XNT price as X1.Ninja currentPriceNative: xdex={latest_close} ninja={current_native}",
        )

        print("XDEX history field semantic evidence")
        print(f"bars={len(bars)} first_t={times[0]} last_t={times[-1]} interval={EXPECTED_INTERVAL_SECONDS}")
        print(f"latest_xdex_close_native={latest_close}")
        print(f"ninja_current_price_native={current_native}")
        print(f"xdex_v_latest_uninterpreted={bars[-1].get('v')!r}")

        # Deliberately no assertion assigning meaning to `v`. The provider field
        # remains raw/unverified until an independent relationship is proven.


if __name__ == "__main__":
    unittest.main()
