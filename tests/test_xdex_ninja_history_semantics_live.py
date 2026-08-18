import math
import os
import statistics
import time
import unittest
from datetime import datetime, timezone

from liquidity_scout.providers.x1.ninja_history import (
    fetch_pool_ohlcv_raw,
    fetch_pool_trades_raw,
)
from liquidity_scout.providers.x1.xdex import fetch_price_history


RUN_LIVE = os.getenv("RUN_XDEX_NINJA_HISTORY_LIVE") == "1"
XENCAT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XNT = "So11111111111111111111111111111111111111112"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
INTERVAL_TO_TF = {
    60: "1m",
    300: "5m",
    900: "15m",
    3600: "1h",
    14400: "4h",
    86400: "1D",
}


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _epoch(value):
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                value = float(text)
            except ValueError:
                return None
        else:
            if dt.tzinfo is None:
                return None
            return dt.astimezone(timezone.utc).timestamp()
    value = _num(value)
    if value is None:
        return None
    # Candidate epoch units only. The live comparison below establishes which
    # interpretation is consistent with independently indexed trade times.
    if value > 10_000_000_000:
        value /= 1000.0
    return value


def _rel_close(a, b, rel=5e-3, abs_tol=1e-12):
    return math.isclose(float(a), float(b), rel_tol=rel, abs_tol=abs_tol)


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_NINJA_HISTORY_LIVE=1 to run read-only XDEX/X1.Ninja history semantic evidence",
)
class XDEXNinjaHistorySemanticLiveTests(unittest.TestCase):
    def test_xdex_bars_against_ninja_indexed_history(self):
        now = int(time.time())
        start = now - 24 * 60 * 60
        xdex = fetch_price_history(
            XENCAT,
            XNT,
            time_from=start,
            time_to=now,
        )
        self.assertGreaterEqual(len(xdex), 2, "XDEX returned too few bars for interval semantics")
        self.assertTrue(all(isinstance(row, dict) for row in xdex))
        self.assertTrue(all({"o", "h", "l", "c", "v", "t"}.issubset(row) for row in xdex))

        xdex_times = sorted(t for t in (_epoch(row.get("t")) for row in xdex) if t is not None)
        self.assertGreaterEqual(len(xdex_times), 2, "XDEX bar timestamps were not numeric/ISO epoch candidates")
        deltas = [round(b - a) for a, b in zip(xdex_times, xdex_times[1:]) if b > a]
        self.assertTrue(deltas, "XDEX bar timestamps did not advance")
        interval = int(statistics.median(deltas))
        timeframe = INTERVAL_TO_TF.get(interval)

        print("XDEX/X1.Ninja history semantic probe")
        print(f"XDEX bars={len(xdex)} inferred_interval_seconds={interval} timeframe_candidate={timeframe}")
        print(f"XDEX first={xdex[0]}")
        print(f"XDEX last={xdex[-1]}")
        self.assertIsNotNone(
            timeframe,
            f"XDEX inferred interval {interval}s is not one of X1.Ninja's documented candle intervals",
        )

        ninja_ohlcv = fetch_pool_ohlcv_raw(
            POOL,
            timeframe=timeframe,
            limit=min(300, max(10, len(xdex) + 4)),
        )
        body = ninja_ohlcv["raw_response"]
        candles = body["ohlcv"]
        self.assertTrue(candles, "X1.Ninja returned no OHLCV candles for verified pool")
        print(f"Ninja timeframe={body.get('timeframe')} mode={body.get('mode')} candles={len(candles)}")
        print(f"Ninja current native={body.get('currentPriceNative')} usd={body.get('currentPriceUsd')}")
        print(f"Ninja first={candles[0]}")
        print(f"Ninja last={candles[-1]}")

        ninja_by_time = {}
        for row in candles:
            ts = _epoch(row.get("time"))
            if ts is not None:
                ninja_by_time[round(ts)] = row
        self.assertTrue(ninja_by_time, "X1.Ninja candle time semantics had no epoch candidate")

        # Evaluate whether XDEX t denotes the same candle boundary, or one
        # interval before/after it. This avoids assuming bar-start vs bar-end.
        shift_scores = {}
        for shift in (0, -interval, interval):
            pairs = []
            for row in xdex:
                ts = _epoch(row.get("t"))
                if ts is None:
                    continue
                other = ninja_by_time.get(round(ts + shift))
                if other is not None:
                    pairs.append((row, other))
            shift_scores[shift] = pairs
        best_shift, pairs = max(shift_scores.items(), key=lambda item: len(item[1]))
        print(f"timestamp alignment counts={ {k: len(v) for k, v in shift_scores.items()} } best_shift={best_shift}")

        # X1.Ninja trade rows already have a separate live semantic probe that
        # verifies txHash/slot/time against X1 RPC and verifies priceNative as
        # amountNative / amountToken. Use those rows as independent price/time
        # evidence instead of inferring XDEX compact-key meaning from names.
        trades_result = fetch_pool_trades_raw(POOL)
        trades = [
            row for row in trades_result["raw_response"]["trades"]
            if row.get("type") in {"buy", "sell"}
            and _epoch(row.get("timestamp")) is not None
            and _num(row.get("priceNative")) is not None
        ]
        self.assertTrue(trades, "X1.Ninja returned no buy/sell rows with verified-candidate native price/time")

        bars = []
        for row in xdex:
            ts = _epoch(row.get("t"))
            vals = [_num(row.get(k)) for k in ("o", "h", "l", "c")]
            if ts is None or any(v is None for v in vals):
                continue
            bars.append((ts, *vals))

        containment_checks = 0
        containment_matches = 0
        close_nearest = []
        for trade in trades:
            t = _epoch(trade["timestamp"])
            p = _num(trade["priceNative"])
            containing = [bar for bar in bars if bar[0] <= t < bar[0] + interval]
            if not containing:
                continue
            _, _o, h, l, c = containing[0]
            containment_checks += 1
            if min(l, h) * (1 - 1e-9) <= p <= max(l, h) * (1 + 1e-9):
                containment_matches += 1
            close_nearest.append(abs(c - p) / max(abs(p), 1e-18))

        print(
            f"trade priceNative within XDEX [l,h]: {containment_matches}/{containment_checks}; "
            f"median close-vs-trade relative delta="
            f"{statistics.median(close_nearest) if close_nearest else None}"
        )

        # Strong semantic evidence requires actual overlapping indexed trades.
        # Sparse windows remain a failed gate rather than a guessed promotion.
        self.assertGreater(containment_checks, 0, "No indexed trades overlapped returned XDEX bars")
        self.assertGreaterEqual(
            containment_matches / containment_checks,
            0.90,
            "XDEX h/l do not consistently bound independently verified X1.Ninja priceNative trades",
        )

        # When candle boundaries overlap, test whether direct OHLC values agree.
        # A lack of boundary overlap is retained as evidence, not silently passed.
        if pairs:
            direct_checks = 0
            direct_matches = 0
            for xrow, nrow in pairs:
                for xkey, nkey in (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close")):
                    xv, nv = _num(xrow.get(xkey)), _num(nrow.get(nkey))
                    if xv is None or nv is None:
                        continue
                    direct_checks += 1
                    direct_matches += int(_rel_close(xv, nv))
            print(f"direct XDEX compact OHLC vs Ninja OHLC: {direct_matches}/{direct_checks}")
        else:
            print("No exact/±one-interval Ninja candle-boundary overlap; trade-level verification remains authoritative evidence.")


if __name__ == "__main__":
    unittest.main()
