import json
import os
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_price_fact_time import (
    collect_ninja_price_fact_time_snapshot,
)
from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)


RUN_LIVE = os.getenv("RUN_X1_NINJA_LIQUIDITY_USD_SEMANTICS_LIVE") == "1"
POOL_SAMPLE_COUNT = 5
REL_TOLERANCE = Decimal("1e-4")
ABS_TOLERANCE = Decimal("0.01")


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


def _token_candidates(row):
    values = []
    for side_name in ("baseToken", "quoteToken"):
        side = row.get(side_name)
        if not isinstance(side, dict):
            continue
        for key in ("mint", "address", "tokenAddress", "mintAddress"):
            value = _text(side.get(key))
            if value and value not in values:
                values.append(value)
    return values


def _positive_decimal(value, *, name):
    parsed = Decimal(str(value))
    if not parsed.is_finite() or parsed <= 0:
        raise AssertionError(f"{name} must be a finite positive value")
    return parsed


def _provider_liquidity(row):
    try:
        return _positive_decimal(row.get("liquidity"), name="provider liquidity")
    except Exception:
        return Decimal("-1")


def _comparison(observed, expected):
    absolute_error = abs(observed - expected)
    allowed = max(ABS_TOLERANCE, abs(expected) * REL_TOLERANCE)
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


def _xnt_asset_reserves(rpc, *, expected_asset=None):
    mint_0 = _text(rpc.get("mint_0"))
    mint_1 = _text(rpc.get("mint_1"))
    reserve_0 = _positive_decimal(rpc.get("gross_reserve_0"), name="RPC reserve 0")
    reserve_1 = _positive_decimal(rpc.get("gross_reserve_1"), name="RPC reserve 1")

    if mint_0 == WRAPPED_XNT_MINT and mint_1 != WRAPPED_XNT_MINT:
        asset = mint_1
        xnt_reserve = reserve_0
        asset_reserve = reserve_1
    elif mint_1 == WRAPPED_XNT_MINT and mint_0 != WRAPPED_XNT_MINT:
        asset = mint_0
        xnt_reserve = reserve_1
        asset_reserve = reserve_0
    else:
        raise AssertionError("RPC pool does not contain exactly one wrapped-XNT mint")

    if expected_asset is not None and asset != expected_asset:
        raise AssertionError(
            f"RPC asset mint mismatch: expected {expected_asset}, observed {asset}"
        )
    return asset, xnt_reserve, asset_reserve


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIQUIDITY_USD_SEMANTICS_LIVE=1 to run read-only evidence",
)
class X1NinjaLiquidityUsdSemanticsLiveTests(unittest.TestCase):
    def test_live_rpc_reserves_bound_same_snapshot_liquidity_diagnostically(self):
        ninja_pools, provider_xnt_price_usd = fetch_all_pools(sleep_seconds=0)
        self.assertTrue(ninja_pools, "X1.Ninja returned no current pools")

        usable = [
            row
            for row in ninja_pools
            if isinstance(row, dict)
            and _address(row)
            and WRAPPED_XNT_MINT in _token_candidates(row)
            and _provider_liquidity(row) > 0
        ]
        self.assertGreaterEqual(
            len(usable),
            POOL_SAMPLE_COUNT + 1,
            "fewer than six positive-liquidity X1.Ninja wrapped-XNT pools are available",
        )

        reference_candidates = [
            row
            for row in usable
            if USDC_X_MINT in _token_candidates(row)
        ]
        self.assertTrue(
            reference_candidates,
            "no current X1.Ninja XNT/USDC.X pool is discoverable",
        )
        reference = max(reference_candidates, key=_provider_liquidity)
        reference_address = _address(reference)

        valuation_candidates = [
            row
            for row in usable
            if _address(row) != reference_address
            and USDC_X_MINT not in _token_candidates(row)
        ]
        valuation_candidates.sort(key=_provider_liquidity, reverse=True)
        selected_valuation = valuation_candidates[:POOL_SAMPLE_COUNT]
        self.assertEqual(
            len(selected_valuation),
            POOL_SAMPLE_COUNT,
            "fewer than five non-USDC.X wrapped-XNT valuation pools are available",
        )

        selected = [reference, *selected_valuation]
        addresses = [_address(row) for row in selected]
        self.assertEqual(len(addresses), len(set(addresses)))

        snapshot = collect_ninja_price_fact_time_snapshot(pool_addresses=addresses)
        observations = {
            row.get("pool_address"): row
            for row in snapshot.get("pools") or []
            if isinstance(row, dict)
        }
        self.assertEqual(set(observations), set(addresses))
        for address in addresses:
            self.assertEqual(
                observations[address].get("status"),
                "ok",
                f"direct RPC pool decoding failed for {address}: {observations[address]}",
            )

        reference_observation = observations[reference_address]
        reference_rpc = reference_observation["rpc"]
        reference_mints = {
            _text(reference_rpc.get("mint_0")),
            _text(reference_rpc.get("mint_1")),
        }
        self.assertEqual(reference_mints, {WRAPPED_XNT_MINT, USDC_X_MINT})
        _, reference_xnt, reference_usdcx = _xnt_asset_reserves(
            reference_rpc,
            expected_asset=USDC_X_MINT,
        )
        xnt_usdcx = reference_usdcx / reference_xnt

        evidence_rows = []
        for pool_row in selected_valuation:
            address = _address(pool_row)
            observation = observations[address]
            rpc = observation["rpc"]
            asset_mint, rpc_xnt, rpc_asset = _xnt_asset_reserves(rpc)
            self.assertNotEqual(asset_mint, USDC_X_MINT)

            provider = observation["provider"]
            provider_liquidity_value = _positive_decimal(
                provider.get("liquidity"),
                name=f"{address} Ninja liquidity",
            )
            pooled_base = _positive_decimal(
                provider.get("pooledBase"),
                name=f"{address} Ninja pooledBase",
            )
            pooled_quote = _positive_decimal(
                provider.get("pooledQuote"),
                name=f"{address} Ninja pooledQuote",
            )

            if _text(rpc.get("mint_0")) == WRAPPED_XNT_MINT:
                provider_xnt = pooled_quote
                provider_asset = pooled_base
            else:
                provider_xnt = pooled_base
                provider_asset = pooled_quote

            native_per_asset = rpc_xnt / rpc_asset
            asset_usdcx = native_per_asset * xnt_usdcx
            asset_side = rpc_asset * asset_usdcx
            xnt_side = rpc_xnt * xnt_usdcx
            two_sided = asset_side + xnt_side
            comparison = _comparison(provider_liquidity_value, two_sided)

            provider_native_per_asset = provider_xnt / provider_asset
            provider_asset_usdcx = provider_native_per_asset * xnt_usdcx
            provider_two_sided = (
                provider_asset * provider_asset_usdcx
                + provider_xnt * xnt_usdcx
            )
            provider_formula_comparison = _comparison(
                provider_liquidity_value,
                provider_two_sided,
            )
            provider_xnt_vs_rpc = _comparison(provider_xnt, rpc_xnt)
            provider_asset_vs_rpc = _comparison(provider_asset, rpc_asset)
            implied_xnt_reserve = provider_liquidity_value / (
                Decimal(2) * xnt_usdcx
            )

            evidence_rows.append(
                {
                    "pool_address": address,
                    "asset_mint": asset_mint,
                    "rpc_xnt_reserve": format(rpc_xnt, "f"),
                    "rpc_asset_reserve": format(rpc_asset, "f"),
                    "ninja_pooled_xnt": format(provider_xnt, "f"),
                    "ninja_pooled_asset": format(provider_asset, "f"),
                    "ninja_pooled_xnt_vs_rpc": provider_xnt_vs_rpc,
                    "ninja_pooled_asset_vs_rpc": provider_asset_vs_rpc,
                    "derived_native_per_asset": format(native_per_asset, "f"),
                    "candidate_xnt_usdcx": format(xnt_usdcx, "f"),
                    "derived_asset_usdcx": format(asset_usdcx, "f"),
                    "derived_two_sided_liquidity_usdcx": format(two_sided, "f"),
                    "ninja_pooled_two_sided_liquidity_usdcx": format(
                        provider_two_sided,
                        "f",
                    ),
                    "implied_xnt_reserve_from_ninja_liquidity": format(
                        implied_xnt_reserve,
                        "f",
                    ),
                    "ninja_reported_liquidity": format(provider_liquidity_value, "f"),
                    "rpc_formula_comparison": comparison,
                    "ninja_pooled_formula_comparison": provider_formula_comparison,
                    "comparison": comparison,
                }
            )

        raw_candidate_formula_match_all = all(
            row["rpc_formula_comparison"]["within_tolerance"]
            for row in evidence_rows
        )
        raw_provider_pooled_formula_match_all = all(
            row["ninja_pooled_formula_comparison"]["within_tolerance"]
            for row in evidence_rows
        )
        same_snapshot_common_scope_verified = (
            snapshot.get("same_fact_temporal_alignment_verified") is True
        )
        candidate_formula_supported = bool(
            same_snapshot_common_scope_verified
            and raw_candidate_formula_match_all
        )
        provider_pooled_formula_supported = bool(
            same_snapshot_common_scope_verified
            and raw_provider_pooled_formula_match_all
        )

        public = {
            "schema": "x1_ninja_liquidity_461_live_candidate.v3",
            "chain": "x1",
            "real_network_calls": True,
            "selection_rule": (
                "highest-liquidity current X1.Ninja XNT/USDC.X reference + "
                "five highest-liquidity non-USDC.X X1.Ninja wrapped-XNT pools; "
                "all exact pool identities/reserves re-decoded by X1 RPC"
            ),
            "reference_pool": reference_address,
            "reference_rpc_xnt_reserve": format(reference_xnt, "f"),
            "reference_rpc_usdcx_reserve": format(reference_usdcx, "f"),
            "candidate_xnt_usdcx": format(xnt_usdcx, "f"),
            "rpc_slot_bracket": snapshot.get("rpc_slot_bracket"),
            "ninja_top_level_xntPriceUsd_observed_for_diagnostic_only": provider_xnt_price_usd,
            "ninja_top_level_xntPriceUsd_used_in_calculation": False,
            "valuation_pool_count": len(evidence_rows),
            "candidate_two_sided_liquidity_formula_supported": candidate_formula_supported,
            "ninja_pooled_two_sided_formula_supported": provider_pooled_formula_supported,
            "raw_candidate_formula_match_all_diagnostic": raw_candidate_formula_match_all,
            "raw_ninja_pooled_formula_match_all_diagnostic": (
                raw_provider_pooled_formula_match_all
            ),
            "same_snapshot_common_scope_verified": (
                same_snapshot_common_scope_verified
            ),
            "same_snapshot_formula_diagnostic_only": True,
            "same_snapshot_formula_required_for_ci": False,
            "reason_same_snapshot_not_promotion_gate": (
                "Live #461 evidence proved Ninja liquidity is not updated atomically "
                "with pooled reserves/prices. Semantic evidence must therefore be "
                "bound to an observed liquidity revaluation epoch, not an arbitrary "
                "same-snapshot catalog comparison."
            ),
            "samples": evidence_rows,
            "usdcx_warp_route_identity_known": True,
            "usdcx_usd_equivalence_verified": False,
            "independent_xnt_usd_fact_verified": False,
            "x1_ninja_liquidity_usd_semantics_verified": False,
            "liquidity_freshness_verified": False,
            "source_independence_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
            "blocker": (
                "Current XNT/USDC.X reserve ratio is proven directly by X1 RPC, "
                "but CMIS has not accepted current USDC.X=USD equivalence/peg; "
                "therefore this can verify the liquidity formula only in USDC.X "
                "scale, not promote USD semantics or freshness."
            ),
        }
        print("X1.NINJA #461 LIVE LIQUIDITY EVIDENCE")
        print(json.dumps(public, sort_keys=True, default=str))

        self.assertTrue(
            all(
                row["ninja_pooled_xnt_vs_rpc"]["within_tolerance"]
                and row["ninja_pooled_asset_vs_rpc"]["within_tolerance"]
                for row in evidence_rows
            ),
            "Ninja pooled reserves must remain corroborated by exact RPC reserves",
        )
        self.assertTrue(public["same_snapshot_formula_diagnostic_only"])
        self.assertFalse(public["same_snapshot_formula_required_for_ci"])
        self.assertFalse(public["same_snapshot_common_scope_verified"])
        self.assertFalse(public["candidate_two_sided_liquidity_formula_supported"])
        self.assertFalse(public["ninja_pooled_two_sided_formula_supported"])
        self.assertFalse(public["usdcx_usd_equivalence_verified"])
        self.assertFalse(public["x1_ninja_liquidity_usd_semantics_verified"])
        self.assertFalse(public["liquidity_freshness_verified"])
        self.assertFalse(public["execution_authorized"])


if __name__ == "__main__":
    unittest.main()