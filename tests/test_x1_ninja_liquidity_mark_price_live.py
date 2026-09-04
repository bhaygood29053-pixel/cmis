import json
import os
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_price_fact_time import (
    collect_ninja_price_fact_time_snapshot,
)
from liquidity_scout.providers.x1.xdex_price_history_import import (
    WRAPPED_XNT_MINT,
)


RUN_LIVE = os.getenv("RUN_X1_NINJA_LIQUIDITY_MARK_PRICE_LIVE") == "1"
REL_TOLERANCE = Decimal("1e-4")
ABS_TOLERANCE = Decimal("0.01")
PRICE_ABS_TOLERANCE = Decimal("1e-18")

POOLS = [
    ("GwwCyLS4VEeZXyPWPYRNiVSuVur6ntioxBmjDQHHHv9x", "original_fail_4.07pct"),
    ("GdKcXA1Q78Bquke5jyZUR1C8YMN6VYT9AUheN1RwKLfe", "original_fail_3.46pct"),
    ("Ec3Keyy1yemycLRjh8PgkKiDJaD3w77UBLViwtB5zmSJ", "original_fail_6.57pct"),
    ("7deZorr98nLdZhpmSdUgu8WY4NAjSpeLDGxHzaTAxrUg", "original_control_exact"),
    ("EcmFn1chD6T9rE3XctPUDxjcqEDT3n2YeQJH627rSCD5", "original_control_exact"),
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


def _positive_decimal(value, *, name):
    parsed = Decimal(str(value))
    if not parsed.is_finite() or parsed <= 0:
        raise AssertionError(f"{name} must be finite and positive")
    return parsed


def _comparison(observed, expected, *, absolute_tolerance=ABS_TOLERANCE):
    absolute_error = abs(observed - expected)
    allowed = max(absolute_tolerance, abs(expected) * REL_TOLERANCE)
    relative_error = absolute_error / abs(expected) if expected else None
    return {
        "observed": format(observed, "f"),
        "expected": format(expected, "f"),
        "absolute_error": format(absolute_error, "f"),
        "relative_error": (
            format(relative_error, "e") if relative_error is not None else None
        ),
        "allowed_absolute_error": format(allowed, "f"),
        "within_tolerance": absolute_error <= allowed,
    }


def _orient_rpc(rpc):
    mint_0 = _text(rpc.get("mint_0"))
    mint_1 = _text(rpc.get("mint_1"))
    reserve_0 = _positive_decimal(rpc.get("gross_reserve_0"), name="RPC reserve 0")
    reserve_1 = _positive_decimal(rpc.get("gross_reserve_1"), name="RPC reserve 1")
    if mint_0 == WRAPPED_XNT_MINT and mint_1 != WRAPPED_XNT_MINT:
        return mint_1, reserve_0, reserve_1
    if mint_1 == WRAPPED_XNT_MINT and mint_0 != WRAPPED_XNT_MINT:
        return mint_0, reserve_1, reserve_0
    raise AssertionError("pool does not contain exactly one wrapped-XNT mint")


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIQUIDITY_MARK_PRICE_LIVE=1 for read-only provider-formula diagnostics",
)
class X1NinjaLiquidityMarkPriceLiveTests(unittest.TestCase):
    def test_exact_461_pools_against_ninja_mark_price_formula(self):
        ninja_pools, xnt_price_usd_raw = fetch_all_pools(sleep_seconds=0)
        self.assertTrue(ninja_pools)
        xnt_price_usd = _positive_decimal(
            xnt_price_usd_raw,
            name="Ninja top-level XNT/USD diagnostic mark",
        )
        by_address = {
            _address(row): row
            for row in ninja_pools
            if isinstance(row, dict) and _address(row)
        }
        addresses = [address for address, _label in POOLS]
        missing = [address for address in addresses if address not in by_address]
        self.assertFalse(missing, f"exact #461 pools missing from Ninja catalog: {missing}")

        snapshot = collect_ninja_price_fact_time_snapshot(pool_addresses=addresses)
        observations = {
            row.get("pool_address"): row
            for row in snapshot.get("pools") or []
            if isinstance(row, dict)
        }
        self.assertEqual(set(observations), set(addresses))

        rows = []
        for address, original_class in POOLS:
            pool = by_address[address]
            observation = observations[address]
            self.assertEqual(observation.get("status"), "ok")
            rpc = observation["rpc"]
            asset_mint, rpc_xnt, rpc_asset = _orient_rpc(rpc)

            base_mint = _token_mint(pool, "baseToken")
            quote_mint = _token_mint(pool, "quoteToken")
            if base_mint != asset_mint or quote_mint != WRAPPED_XNT_MINT:
                raise AssertionError(
                    f"{address} provider orientation is not asset/XNT: "
                    f"base={base_mint} quote={quote_mint} rpc_asset={asset_mint}"
                )

            ninja_liquidity = _positive_decimal(
                pool.get("liquidity"),
                name=f"{address} Ninja liquidity",
            )
            ninja_asset_price_usd = _positive_decimal(
                pool.get("priceUsd"),
                name=f"{address} Ninja asset priceUsd",
            )

            xnt_side_usd = rpc_xnt * xnt_price_usd
            asset_side_usd = rpc_asset * ninja_asset_price_usd
            mark_price_liquidity = xnt_side_usd + asset_side_usd
            formula_cmp = _comparison(ninja_liquidity, mark_price_liquidity)

            implied_asset_price_usd = (
                ninja_liquidity - xnt_side_usd
            ) / rpc_asset
            implied_cmp = _comparison(
                implied_asset_price_usd,
                ninja_asset_price_usd,
                absolute_tolerance=PRICE_ABS_TOLERANCE,
            )
            amm_asset_price_usd = (rpc_xnt / rpc_asset) * xnt_price_usd
            mark_vs_amm = (
                (ninja_asset_price_usd - amm_asset_price_usd)
                / amm_asset_price_usd
                * Decimal(100)
            )

            rows.append({
                "pool_address": address,
                "original_461_class": original_class,
                "asset_mint": asset_mint,
                "rpc_xnt_reserve": format(rpc_xnt, "f"),
                "rpc_asset_reserve": format(rpc_asset, "f"),
                "ninja_xnt_price_usd_mark": format(xnt_price_usd, "f"),
                "ninja_asset_price_usd_mark": format(ninja_asset_price_usd, "f"),
                "amm_spot_asset_price_usd_using_same_xnt_mark": format(
                    amm_asset_price_usd,
                    "f",
                ),
                "ninja_mark_vs_amm_spot_pct": format(mark_vs_amm, "f"),
                "ninja_reported_liquidity": format(ninja_liquidity, "f"),
                "mark_price_liquidity": format(mark_price_liquidity, "f"),
                "mark_price_formula_comparison": formula_cmp,
                "implied_asset_price_usd_from_liquidity": format(
                    implied_asset_price_usd,
                    "f",
                ),
                "implied_asset_price_vs_ninja_priceUsd": implied_cmp,
                "lastSyncedAt": pool.get("lastSyncedAt"),
                "lastUpdated": pool.get("lastUpdated"),
            })

        formula_match_count = sum(
            row["mark_price_formula_comparison"]["within_tolerance"] is True
            for row in rows
        )
        implied_mark_match_count = sum(
            row["implied_asset_price_vs_ninja_priceUsd"]["within_tolerance"] is True
            for row in rows
        )
        evidence = {
            "schema": "x1_liquidity_461_mark_price_diagnostic.v1",
            "chain": "x1",
            "real_network_calls": True,
            "exact_original_pool_set": True,
            "pool_count": len(rows),
            "mark_price_formula_match_count": formula_match_count,
            "implied_mark_match_count": implied_mark_match_count,
            "mark_price_formula_supported_5_of_5": formula_match_count == len(rows),
            "implied_asset_mark_matches_priceUsd_5_of_5": (
                implied_mark_match_count == len(rows)
            ),
            "samples": rows,
            "provider_price_usd_used_for_diagnostic_only": True,
            "provider_formula_identified": formula_match_count == len(rows),
            "provider_price_usd_independently_verified": False,
            "x1_ninja_liquidity_usd_semantics_verified": False,
            "liquidity_freshness_verified": False,
            "source_independence_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        print("X1 #461 NINJA MARK-PRICE LIQUIDITY DIAGNOSTIC")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertEqual(len(rows), 5)
        self.assertFalse(evidence["provider_price_usd_independently_verified"])
        self.assertFalse(evidence["x1_ninja_liquidity_usd_semantics_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["execution_authorized"])


if __name__ == "__main__":
    unittest.main()