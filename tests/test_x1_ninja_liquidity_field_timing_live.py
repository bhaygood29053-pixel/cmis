import json
import os
import time
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1 import market as market_provider
from liquidity_scout.providers.x1.ninja_price_fact_time import (
    collect_ninja_price_fact_time_snapshot,
)
from liquidity_scout.providers.x1.xdex_price_history_import import WRAPPED_XNT_MINT


RUN_LIVE = os.getenv("RUN_X1_NINJA_LIQUIDITY_FIELD_TIMING_LIVE") == "1"
SNAPSHOT_COUNT = int(os.getenv("X1_NINJA_LIQUIDITY_TIMING_SNAPSHOTS", "8"))
INTERVAL_SECONDS = float(os.getenv("X1_NINJA_LIQUIDITY_TIMING_INTERVAL_SECONDS", "15"))

POOLS = [
    ("GwwCyLS4VEeZXyPWPYRNiVSuVur6ntioxBmjDQHHHv9x", "persistent_mismatch"),
    ("Ec3Keyy1yemycLRjh8PgkKiDJaD3w77UBLViwtB5zmSJ", "persistent_mismatch"),
    ("GdKcXA1Q78Bquke5jyZUR1C8YMN6VYT9AUheN1RwKLfe", "recovered_to_exact"),
]


def _text(value):
    text = str(value or "").strip()
    return text or None


def _address(row):
    return _text(
        row.get("address")
        or row.get("poolAddress")
        or row.get("pool_address")
        or row.get("id")
    )


def _decimal(value, *, name):
    parsed = Decimal(str(value))
    if not parsed.is_finite():
        raise AssertionError(f"{name} must be finite")
    return parsed


def _positive_decimal(value, *, name):
    parsed = _decimal(value, name=name)
    if parsed <= 0:
        raise AssertionError(f"{name} must be positive")
    return parsed


def _token_mint(row, side):
    token = row.get(side)
    if not isinstance(token, dict):
        return None
    return _text(
        token.get("mint")
        or token.get("address")
        or token.get("tokenAddress")
        or token.get("mintAddress")
    )


def _orient_rpc(rpc):
    mint_0 = _text(rpc.get("mint_0"))
    mint_1 = _text(rpc.get("mint_1"))
    reserve_0 = _positive_decimal(rpc.get("gross_reserve_0"), name="RPC reserve 0")
    reserve_1 = _positive_decimal(rpc.get("gross_reserve_1"), name="RPC reserve 1")
    if mint_0 == WRAPPED_XNT_MINT and mint_1 != WRAPPED_XNT_MINT:
        return mint_1, reserve_0, reserve_1
    if mint_1 == WRAPPED_XNT_MINT and mint_0 != WRAPPED_XNT_MINT:
        return mint_0, reserve_1, reserve_0
    raise AssertionError("pool must contain exactly one wrapped-XNT mint")


def _fresh_catalog():
    # This is an evidence-only bypass of the provider cache so every timing
    # sample performs a real X1.Ninja catalog request.
    market_provider._CACHE = None
    market_provider._CACHE_AT = 0.0
    return market_provider.fetch_all_pools(sleep_seconds=0)


def _relative_error(observed, expected):
    if expected == 0:
        return None
    return abs(observed - expected) / abs(expected)


def _changed(left, right):
    return left != right


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIQUIDITY_FIELD_TIMING_LIVE=1 for repeated live timing evidence",
)
class X1NinjaLiquidityFieldTimingLiveTests(unittest.TestCase):
    def test_repeated_catalog_and_rpc_snapshots_localize_field_timing(self):
        self.assertGreaterEqual(SNAPSHOT_COUNT, 4)
        self.assertGreaterEqual(INTERVAL_SECONDS, 1)
        addresses = [address for address, _label in POOLS]
        labels = dict(POOLS)
        series = {address: [] for address in addresses}

        started = time.time()
        for index in range(SNAPSHOT_COUNT):
            observed_at = time.time()
            pools, xnt_price_raw = _fresh_catalog()
            xnt_price = _positive_decimal(
                xnt_price_raw,
                name="Ninja top-level XNT/USD diagnostic mark",
            )
            by_address = {
                _address(row): row
                for row in pools
                if isinstance(row, dict) and _address(row)
            }
            missing = [address for address in addresses if address not in by_address]
            self.assertFalse(missing, f"timing pools missing from Ninja catalog: {missing}")

            snapshot = collect_ninja_price_fact_time_snapshot(
                pool_addresses=addresses,
                pool_fetcher=lambda **_kwargs: (pools, float(xnt_price)),
            )
            observations = {
                row.get("pool_address"): row
                for row in snapshot.get("pools") or []
                if isinstance(row, dict)
            }
            self.assertEqual(set(observations), set(addresses))

            for address in addresses:
                pool = by_address[address]
                observation = observations[address]
                self.assertEqual(observation.get("status"), "ok")
                rpc = observation["rpc"]
                asset_mint, rpc_xnt, rpc_asset = _orient_rpc(rpc)
                base_mint = _token_mint(pool, "baseToken")
                quote_mint = _token_mint(pool, "quoteToken")
                self.assertEqual(base_mint, asset_mint)
                self.assertEqual(quote_mint, WRAPPED_XNT_MINT)

                liquidity = _positive_decimal(
                    pool.get("liquidity"),
                    name=f"{address} liquidity",
                )
                price_usd = _positive_decimal(
                    pool.get("priceUsd"),
                    name=f"{address} priceUsd",
                )
                price_native = _positive_decimal(
                    pool.get("priceNative"),
                    name=f"{address} priceNative",
                )
                pooled_base = _positive_decimal(
                    pool.get("pooledBase"),
                    name=f"{address} pooledBase",
                )
                pooled_quote = _positive_decimal(
                    pool.get("pooledQuote"),
                    name=f"{address} pooledQuote",
                )
                formula = rpc_xnt * xnt_price + rpc_asset * price_usd
                error = _relative_error(liquidity, formula)

                series[address].append({
                    "index": index,
                    "observed_at_unix": observed_at,
                    "lastSyncedAt": pool.get("lastSyncedAt"),
                    "lastUpdated": pool.get("lastUpdated"),
                    "liquidity": format(liquidity, "f"),
                    "priceUsd": format(price_usd, "f"),
                    "priceNative": format(price_native, "f"),
                    "pooledBase": format(pooled_base, "f"),
                    "pooledQuote": format(pooled_quote, "f"),
                    "xntPriceUsd": format(xnt_price, "f"),
                    "rpc_xnt_reserve": format(rpc_xnt, "f"),
                    "rpc_asset_reserve": format(rpc_asset, "f"),
                    "mark_formula_liquidity": format(formula, "f"),
                    "mark_formula_relative_error": (
                        format(error, "e") if error is not None else None
                    ),
                    "rpc_before_slot": (
                        (snapshot.get("rpc_slot_bracket") or {}).get("before") or {}
                    ).get("slot"),
                    "rpc_after_slot": (
                        (snapshot.get("rpc_slot_bracket") or {}).get("after") or {}
                    ).get("slot"),
                })

            if index + 1 < SNAPSHOT_COUNT:
                elapsed = time.time() - observed_at
                delay = max(0.0, INTERVAL_SECONDS - elapsed)
                if delay:
                    time.sleep(delay)

        pool_results = []
        async_observed_any = False
        for address in addresses:
            rows = series[address]
            transitions = []
            counts = {
                "liquidity": 0,
                "priceUsd": 0,
                "priceNative": 0,
                "pooledBase": 0,
                "pooledQuote": 0,
                "xntPriceUsd": 0,
                "rpc_xnt_reserve": 0,
                "rpc_asset_reserve": 0,
                "lastSyncedAt": 0,
            }
            async_transitions = []
            for previous, current in zip(rows, rows[1:]):
                changed = {
                    field: _changed(previous[field], current[field])
                    for field in counts
                }
                for field, flag in changed.items():
                    counts[field] += int(flag)
                provider_inputs_changed = any(
                    changed[field]
                    for field in (
                        "priceUsd",
                        "priceNative",
                        "pooledBase",
                        "pooledQuote",
                        "xntPriceUsd",
                    )
                )
                rpc_inputs_changed = any(
                    changed[field]
                    for field in ("rpc_xnt_reserve", "rpc_asset_reserve")
                )
                liquidity_changed = changed["liquidity"]
                asynchronous = bool(
                    (liquidity_changed and not provider_inputs_changed and not rpc_inputs_changed)
                    or (not liquidity_changed and (provider_inputs_changed or rpc_inputs_changed))
                )
                if asynchronous:
                    async_observed_any = True
                    async_transitions.append({
                        "from_index": previous["index"],
                        "to_index": current["index"],
                        "changed": changed,
                    })
                transitions.append({
                    "from_index": previous["index"],
                    "to_index": current["index"],
                    "changed": changed,
                    "asynchronous_field_change": asynchronous,
                })

            alignments = []
            for row in rows:
                liquidity = Decimal(row["liquidity"])
                best = None
                for candidate in rows:
                    formula = Decimal(candidate["mark_formula_liquidity"])
                    error = _relative_error(liquidity, formula)
                    if error is None:
                        continue
                    record = {
                        "formula_snapshot_index": candidate["index"],
                        "relative_error": error,
                        "offset_snapshots": candidate["index"] - row["index"],
                        "offset_seconds": (
                            candidate["observed_at_unix"] - row["observed_at_unix"]
                        ),
                    }
                    if best is None or record["relative_error"] < best["relative_error"]:
                        best = record
                alignments.append({
                    "liquidity_snapshot_index": row["index"],
                    "same_snapshot_relative_error": row["mark_formula_relative_error"],
                    "best_formula_snapshot_index": best["formula_snapshot_index"] if best else None,
                    "best_formula_relative_error": (
                        format(best["relative_error"], "e") if best else None
                    ),
                    "best_formula_offset_snapshots": best["offset_snapshots"] if best else None,
                    "best_formula_offset_seconds": best["offset_seconds"] if best else None,
                })

            pool_results.append({
                "pool_address": address,
                "classification": labels[address],
                "field_change_counts": counts,
                "asynchronous_transition_count": len(async_transitions),
                "asynchronous_transitions": async_transitions,
                "alignments": alignments,
                "snapshots": rows,
            })

        evidence = {
            "schema": "x1_liquidity_461_field_timing.v1",
            "chain": "x1",
            "real_network_calls": True,
            "snapshot_count": SNAPSHOT_COUNT,
            "target_interval_seconds": INTERVAL_SECONDS,
            "elapsed_seconds": time.time() - started,
            "provider_cache_bypassed_each_snapshot": True,
            "pools": pool_results,
            "asynchronous_field_update_observed": async_observed_any,
            "provider_field_fact_time_semantics_verified": False,
            "x1_ninja_liquidity_usd_semantics_verified": False,
            "liquidity_freshness_verified": False,
            "source_independence_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        print("X1 #461 NINJA LIQUIDITY FIELD-TIMING EVIDENCE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertEqual(len(pool_results), len(POOLS))
        self.assertFalse(evidence["provider_field_fact_time_semantics_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
