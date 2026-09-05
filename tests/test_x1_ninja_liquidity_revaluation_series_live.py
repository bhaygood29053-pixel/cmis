import json
import os
import time
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.ninja_liquidity_revaluation_series import (
    REFERENCE_SOURCE,
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
    evaluate_ninja_liquidity_revaluation_series,
)
from liquidity_scout.providers.x1.rpc import rpc_request
from tests.test_x1_ninja_liquidity_transition_capture_live import (
    POOL_SET,
    _fresh_pool_details,
    _pool_layout,
    _provider_snapshot,
    _reconstruct_transition,
    _signatures_between,
)

RUN_LIVE = os.getenv("RUN_X1_NINJA_LIQUIDITY_REVALUATION_SERIES_LIVE") == "1"
MAX_WAIT_SECONDS = int(os.getenv("X1_NINJA_LIQUIDITY_REVALUATION_SERIES_MAX_WAIT_SECONDS", "900"))
POLL_SECONDS = float(os.getenv("X1_NINJA_LIQUIDITY_REVALUATION_SERIES_POLL_SECONDS", "20"))
MIN_EVENTS = int(os.getenv("X1_NINJA_LIQUIDITY_REVALUATION_SERIES_MIN_EVENTS", "3"))
MIN_POOLS = int(os.getenv("X1_NINJA_LIQUIDITY_REVALUATION_SERIES_MIN_POOLS", "2"))
REFERENCE_POOL = "CAJeVEoSm1QQZccnCqYu9cnNF7TTD2fcUA3E5HQoxRvR"
REFERENCE_REL_TOL = Decimal(os.getenv("X1_NINJA_LIQUIDITY_REFERENCE_REL_TOL", "0.000001"))


def _token_balance(account):
    result = rpc_request("getTokenAccountBalance", [account, {"commitment": "confirmed"}])
    if not isinstance(result, dict):
        raise AssertionError(f"invalid token balance response for {account}")
    value = result.get("value") or {}
    amount = value.get("amount")
    decimals = value.get("decimals")
    if amount is None or decimals is None:
        raise AssertionError(f"missing token amount/decimals for {account}")
    return Decimal(int(amount)) / (Decimal(10) ** int(decimals))


def _reference_alignment(event_after):
    layout = _pool_layout(REFERENCE_POOL)
    if {layout["mint_0"], layout["mint_1"]} != {WRAPPED_XNT_MINT, USDC_X_MINT}:
        raise AssertionError("reference pool mint identity mismatch")

    detail_rows, _rate_limits = _fresh_pool_details([REFERENCE_POOL])
    detail = detail_rows[REFERENCE_POOL]
    row = detail["row"]

    slot_before_rpc = rpc_request("getSlot", [{"commitment": "confirmed"}])
    reserve_0 = _token_balance(layout["vault_0"])
    reserve_1 = _token_balance(layout["vault_1"])
    slot_after_rpc = rpc_request("getSlot", [{"commitment": "confirmed"}])
    if not isinstance(slot_before_rpc, int) or not isinstance(slot_after_rpc, int):
        raise AssertionError("invalid reference slot bracket")

    if layout["mint_0"] == WRAPPED_XNT_MINT:
        xnt_reserve, usdcx_reserve = reserve_0, reserve_1
    else:
        xnt_reserve, usdcx_reserve = reserve_1, reserve_0
    if xnt_reserve <= 0 or usdcx_reserve <= 0:
        raise AssertionError("reference reserves must be positive")

    rpc_price = usdcx_reserve / xnt_reserve
    provider_reference_price = Decimal(str(detail.get("xntPriceUsd")))
    event_reference_price = Decimal(str(event_after.get("xntPriceUsd")))
    rel_error = abs(provider_reference_price - rpc_price) / rpc_price

    combined_before = min(int(detail["slot_before"]), slot_before_rpc)
    combined_after = max(int(detail["slot_after"]), slot_after_rpc)
    signatures = _signatures_between(
        REFERENCE_POOL,
        before_slot=combined_before,
        after_slot=combined_after,
    )

    provider_matches_rpc = rel_error <= REFERENCE_REL_TOL
    event_matches_reference = event_reference_price == provider_reference_price
    same_fact = provider_matches_rpc and event_matches_reference and len(signatures) == 0

    return {
        "source": REFERENCE_SOURCE,
        "reference_pool": REFERENCE_POOL,
        "base_mint": WRAPPED_XNT_MINT,
        "quote_mint": USDC_X_MINT,
        "exact_pool_identity_verified": True,
        "rpc_reserves_verified": True,
        "rpc_xnt_reserve": format(xnt_reserve, "f"),
        "rpc_usdcx_reserve": format(usdcx_reserve, "f"),
        "rpc_reserve_ratio_usdcx_per_xnt": format(rpc_price, "f"),
        "provider_reference_price": format(provider_reference_price, "f"),
        "event_reference_price": format(event_reference_price, "f"),
        "relative_error": format(rel_error, "e"),
        "reference_fact_time_verified": same_fact,
        "same_fact_temporal_alignment_verified": same_fact,
        "provider_reference_price_matches_rpc": provider_matches_rpc,
        "event_reference_price_matches_fresh_reference": event_matches_reference,
        "intervening_reference_pool_signature_count": len(signatures),
        "slot_before": combined_before,
        "slot_after": combined_after,
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIQUIDITY_REVALUATION_SERIES_LIVE=1 for repeated live evidence",
)
class X1NinjaLiquidityRevaluationSeriesLiveTests(unittest.TestCase):
    def test_capture_repeated_same_fact_revaluation_series(self):
        self.assertGreaterEqual(MAX_WAIT_SECONDS, 60)
        self.assertGreaterEqual(POLL_SECONDS, 5)
        self.assertGreaterEqual(MIN_EVENTS, 3)
        self.assertGreaterEqual(MIN_POOLS, 2)

        targets = [pool for pool, _label in POOL_SET]
        labels = dict(POOL_SET)
        layouts = {pool: _pool_layout(pool) for pool in targets}
        series = {pool: [] for pool in targets}
        previous = {}
        events = []
        seen_transitions = set()
        started = time.time()
        poll_index = 0

        while time.time() - started <= MAX_WAIT_SECONDS:
            details, rate_limits = _fresh_pool_details(targets)
            changed = []
            for pool in targets:
                current = _provider_snapshot(
                    details[pool], index=poll_index, rate_limit=rate_limits[pool]
                )
                series[pool].append(current)
                prior = previous.get(pool)
                if prior is not None and current["liquidity"] != prior["liquidity"]:
                    transition_key = (
                        pool,
                        prior["liquidity"],
                        current["liquidity"],
                        prior.get("lastSyncedAt"),
                        current.get("lastSyncedAt"),
                    )
                    if transition_key not in seen_transitions:
                        seen_transitions.add(transition_key)
                        changed.append((pool, prior, current))
                previous[pool] = current

            for pool, before, after in changed:
                reconstruction = _reconstruct_transition(
                    pool=pool,
                    label=labels[pool],
                    layout=layouts[pool],
                    samples=series[pool],
                    before=before,
                    after=after,
                )
                revaluation = reconstruction.get("price_only_revaluation") or {}
                if revaluation.get("price_only_liquidity_revaluation_verified") is not True:
                    continue
                reference = _reference_alignment(after)
                events.append(
                    {
                        "event_key": f"{pool}:{after.get('lastSyncedAt')}:{after['liquidity']}",
                        "pool_address": pool,
                        "revaluation": revaluation,
                        "reference_alignment": reference,
                        "transition": {"before": before, "after": after},
                    }
                )

            evaluation = evaluate_ninja_liquidity_revaluation_series(
                events,
                current_usdcx_usd_equivalence_verified=False,
                minimum_repeated_events=MIN_EVENTS,
                minimum_repeated_pools=MIN_POOLS,
                minimum_usd_semantic_pools=5,
            )
            if evaluation["liquidity_fact_time_verified"] is True:
                break

            poll_index += 1
            elapsed = time.time() - started
            if elapsed + POLL_SECONDS > MAX_WAIT_SECONDS:
                break
            time.sleep(POLL_SECONDS)

        evaluation = evaluate_ninja_liquidity_revaluation_series(
            events,
            current_usdcx_usd_equivalence_verified=False,
            minimum_repeated_events=MIN_EVENTS,
            minimum_repeated_pools=MIN_POOLS,
            minimum_usd_semantic_pools=5,
        )
        evidence = {
            "schema": "x1_liquidity_461_repeated_revaluation_live.v1",
            "chain": "x1",
            "elapsed_seconds": time.time() - started,
            "watched_pool_count": len(targets),
            "events": events,
            "evaluation": evaluation,
            "current_usdcx_usd_equivalence_verified": False,
            "x1_ninja_liquidity_usd_semantics_verified": False,
            "liquidity_freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        print("X1 #461 REPEATED LIQUIDITY REVALUATION EVIDENCE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertFalse(evidence["current_usdcx_usd_equivalence_verified"])
        self.assertFalse(evidence["x1_ninja_liquidity_usd_semantics_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["cmis_promotable"])
        self.assertFalse(evidence["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
