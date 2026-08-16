import math
import os
import unittest
from collections import Counter, defaultdict
from datetime import datetime, timezone

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw
from liquidity_scout.providers.x1.rpc import rpc_request


RUN_LIVE = os.getenv("RUN_X1_NINJA_LIVE_TESTS") == "1"
SWAP_TYPE_CANDIDATES = frozenset({"buy", "sell"})


def _text(value):
    text = str(value or "").strip()
    return text or None


def _pool_address(pool):
    if not isinstance(pool, dict):
        return None
    return _text(
        pool.get("address")
        or pool.get("poolAddress")
        or pool.get("pool_address")
        or pool.get("id")
    )


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _parse_iso_utc(value):
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _close(left, right):
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIVE_TESTS=1 to run the read-only X1.Ninja semantic probe",
)
class X1NinjaTradeSemanticLiveTests(unittest.TestCase):
    def test_live_trade_relationships_and_rpc_identity_crosscheck(self):
        pools, _xnt_price = fetch_all_pools(sleep_seconds=0)
        self.assertTrue(pools, "X1.Ninja pool catalog returned no pools")

        selected = next(
            (
                pool
                for pool in pools
                if isinstance(pool, dict) and _pool_address(pool)
            ),
            None,
        )
        self.assertIsNotNone(selected, "no pool with a usable address was returned")
        address = _pool_address(selected)

        result = fetch_pool_trades_raw(address)
        body = result["raw_response"]
        trades = body["trades"]
        self.assertTrue(trades, "selected pool returned no trade rows for semantic probing")

        pool_matches = 0
        iso_timestamps = 0
        integer_slots = 0
        nonempty_tx_hashes = 0
        observed_types = Counter()
        arithmetic = defaultdict(
            lambda: {
                "native_checks": 0,
                "native_matches": 0,
                "usd_checks": 0,
                "usd_matches": 0,
            }
        )

        for row in trades:
            row_type = str(row.get("type")) if row.get("type") is not None else "<missing>"
            observed_types[row_type] += 1

            if row.get("poolAddress") == address:
                pool_matches += 1

            if _parse_iso_utc(row.get("timestamp")) is not None:
                iso_timestamps += 1

            slot = row.get("slot")
            if isinstance(slot, int) and not isinstance(slot, bool) and slot >= 0:
                integer_slots += 1

            if _text(row.get("txHash")):
                nonempty_tx_hashes += 1

            amount_native = _number(row.get("amountNative"))
            amount_token = _number(row.get("amountToken"))
            price_native = _number(row.get("priceNative"))
            if (
                amount_native is not None
                and amount_token not in (None, 0.0)
                and price_native is not None
            ):
                arithmetic[row_type]["native_checks"] += 1
                if _close(amount_native / amount_token, price_native):
                    arithmetic[row_type]["native_matches"] += 1

            amount_usd = _number(row.get("amountUsd"))
            price_usd = _number(row.get("priceUsd"))
            if (
                amount_token is not None
                and amount_usd is not None
                and price_usd is not None
            ):
                arithmetic[row_type]["usd_checks"] += 1
                if _close(amount_token * price_usd, amount_usd):
                    arithmetic[row_type]["usd_matches"] += 1

        last_updated = body.get("lastUpdated")
        last_updated_iso = None
        if isinstance(last_updated, int) and not isinstance(last_updated, bool):
            try:
                last_updated_iso = datetime.fromtimestamp(
                    last_updated / 1000.0,
                    tz=timezone.utc,
                ).isoformat()
            except (OverflowError, OSError, ValueError):
                last_updated_iso = None

        print("X1.Ninja live trade semantic-candidate probe")
        print(f"Pool address: {address}")
        print(f"Returned rows: {len(trades)}")
        print(f"Observed type counts: {dict(sorted(observed_types.items()))}")
        print(f"poolAddress matches requested pool: {pool_matches}/{len(trades)}")
        print(f"ISO-8601 timezone-aware timestamps: {iso_timestamps}/{len(trades)}")
        print(f"Non-negative integer slots: {integer_slots}/{len(trades)}")
        print(f"Non-empty txHash values: {nonempty_tx_hashes}/{len(trades)}")
        for row_type in sorted(arithmetic):
            stats = arithmetic[row_type]
            print(
                f"{row_type} priceNative relation: "
                f"{stats['native_matches']}/{stats['native_checks']}"
            )
            print(
                f"{row_type} amountUsd relation: "
                f"{stats['usd_matches']}/{stats['usd_checks']}"
            )
        print(
            f"lastUpdated raw: {last_updated!r}; "
            f"milliseconds-as-UTC candidate: {last_updated_iso}"
        )

        self.assertEqual(pool_matches, len(trades))
        self.assertEqual(iso_timestamps, len(trades))
        self.assertEqual(integer_slots, len(trades))
        self.assertEqual(nonempty_tx_hashes, len(trades))

        # The live provider vocabulary includes both swap-looking labels and LP
        # events.  Only buy/sell rows are candidates for swap arithmetic here;
        # LP-event financial semantics stay explicitly unverified.
        swap_rows_checked = 0
        for row_type in SWAP_TYPE_CANDIDATES:
            stats = arithmetic[row_type]
            if observed_types[row_type] == 0:
                continue
            self.assertGreater(stats["native_checks"], 0, row_type)
            self.assertEqual(
                stats["native_matches"],
                stats["native_checks"],
                f"{row_type} native-price relationship",
            )
            self.assertGreater(stats["usd_checks"], 0, row_type)
            self.assertEqual(
                stats["usd_matches"],
                stats["usd_checks"],
                f"{row_type} USD-value relationship",
            )
            swap_rows_checked += observed_types[row_type]
        self.assertGreater(swap_rows_checked, 0)

        non_swap_types = sorted(set(observed_types) - SWAP_TYPE_CANDIDATES)
        print(f"Non-swap provider types left semantically gated: {non_swap_types}")

        candidate = next(
            (
                row
                for row in trades
                if _text(row.get("txHash"))
                and isinstance(row.get("slot"), int)
                and _parse_iso_utc(row.get("timestamp")) is not None
                and row.get("type") in SWAP_TYPE_CANDIDATES
            ),
            None,
        )
        self.assertIsNotNone(candidate, "no buy/sell row available for RPC identity cross-check")

        tx_hash = _text(candidate.get("txHash"))
        provider_slot = candidate.get("slot")
        provider_time = _parse_iso_utc(candidate.get("timestamp"))

        status_result = rpc_request(
            "getSignatureStatuses",
            [[tx_hash], {"searchTransactionHistory": True}],
        )
        status_values = (
            status_result.get("value")
            if isinstance(status_result, dict)
            else None
        )
        status = status_values[0] if isinstance(status_values, list) and status_values else None

        if not isinstance(status, dict):
            print("RPC signature-status cross-check: unavailable from current RPC history")
            print("RPC identity cross-check verified: False")
            return

        rpc_slot = status.get("slot")
        print(
            "RPC signature status: "
            f"slot={rpc_slot!r}, confirmations={status.get('confirmations')!r}, "
            f"confirmationStatus={status.get('confirmationStatus')!r}, "
            f"err={status.get('err')!r}"
        )
        print(f"Provider slot == RPC signature slot: {provider_slot == rpc_slot}")
        self.assertEqual(provider_slot, rpc_slot)

        block_time = rpc_request("getBlockTime", [provider_slot])
        if not isinstance(block_time, (int, float)) or isinstance(block_time, bool):
            print("RPC block-time cross-check: unavailable for provider slot")
            print("RPC identity cross-check verified: partial (signature slot only)")
            return

        rpc_time = datetime.fromtimestamp(float(block_time), tz=timezone.utc)
        delta_seconds = abs((provider_time - rpc_time).total_seconds())
        print(f"Provider timestamp UTC: {provider_time.isoformat()}")
        print(f"RPC block time UTC: {rpc_time.isoformat()}")
        print(f"Timestamp delta seconds: {delta_seconds}")
        print(f"RPC identity cross-check verified: {delta_seconds <= 1.0}")
        self.assertLessEqual(delta_seconds, 1.0)


if __name__ == "__main__":
    unittest.main()
