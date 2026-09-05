import json
import os
import time
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_liquidity_revaluation_series import (
    REFERENCE_SOURCE,
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
    evaluate_ninja_liquidity_revaluation_series,
)
from liquidity_scout.providers.x1.ninja_revaluation_watch import (
    select_wrapped_xnt_watch_candidates,
)
from liquidity_scout.providers.x1.rpc import rpc_request
from tests.test_x1_current_usdcx_usd_equivalence_live import (
    capture_current_usdcx_usd_equivalence_live_evidence,
)
from tests.test_x1_ninja_liquidity_transition_capture_live import (
    POOL_SET,
    _current_slot,
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
MAX_WATCH_POOLS = int(os.getenv("X1_NINJA_LIQUIDITY_REVALUATION_SERIES_MAX_WATCH_POOLS", "150"))
REFERENCE_POOL = "CAJeVEoSm1QQZccnCqYu9cnNF7TTD2fcUA3E5HQoxRvR"
REFERENCE_REL_TOL = Decimal(os.getenv("X1_NINJA_LIQUIDITY_REFERENCE_REL_TOL", "0.000001"))


def _address(row):
    if not isinstance(row, dict):
        return None
    value = (
        row.get("address")
        or row.get("poolAddress")
        or row.get("pool_address")
        or row.get("id")
    )
    text = str(value or "").strip()
    return text or None


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


def _bulk_catalog_details(targets):
    """Fetch the full catalog once and bracket the whole read with X1 slots."""
    slot_before = _current_slot()
    pools, xnt_price_usd = fetch_all_pools(sleep_seconds=0)
    slot_after = _current_slot()
    observed_at = time.time()
    by_address = {
        address: row
        for row in pools
        if isinstance(row, dict)
        and (address := _address(row)) is not None
    }
    details = {}
    for pool in targets:
        row = by_address.get(pool)
        if row is None:
            continue
        details[pool] = {
            "row": row,
            "xntPriceUsd": xnt_price_usd,
            "lastUpdated": None,
            "observed_at": observed_at,
            "slot_before": slot_before,
            "slot_after": slot_after,
        }
    return details, {
        "catalog_row_count": len(pools),
        "returned_target_count": len(details),
        "slot_before": slot_before,
        "slot_after": slot_after,
        "observed_at": observed_at,
    }


def _discover_verified_watch_set():
    pools, _xnt_price_usd = fetch_all_pools(sleep_seconds=0)
    priority = [pool for pool, _label in POOL_SET]
    selection = select_wrapped_xnt_watch_candidates(
        pools,
        wrapped_xnt_mint=WRAPPED_XNT_MINT,
        max_pools=MAX_WATCH_POOLS,
        priority_addresses=priority,
        excluded_addresses=[REFERENCE_POOL],
    )

    layouts = {}
    rejected = []
    for pool in selection["selected_candidate_addresses"]:
        try:
            layout = _pool_layout(pool)
        except Exception as exc:
            rejected.append({
                "pool_address": pool,
                "reason": f"{type(exc).__name__}: {exc}",
            })
            continue
        mints = {layout.get("mint_0"), layout.get("mint_1")}
        if WRAPPED_XNT_MINT not in mints or len(mints) != 2:
            rejected.append({
                "pool_address": pool,
                "reason": "onchain_layout_does_not_contain_exactly_one_wrapped_xnt_side",
            })
            continue
        layouts[pool] = layout

    targets = list(layouts)
    return targets, layouts, {
        **selection,
        "onchain_verified_watch_pool_count": len(targets),
        "onchain_rejected_candidate_count": len(rejected),
        "onchain_rejected_candidates": rejected,
        "pool_identity_verified_for_watched_set": bool(targets),
        "wrapped_xnt_position_verified_for_watched_set": bool(targets),
        "liquidity_semantics_verified_by_selection": False,
        "execution_authorized": False,
    }


def _reference_alignment(event_after):
    layout = _pool_layout(REFERENCE_POOL)
    if {layout["mint_0"], layout["mint_1"]} != {WRAPPED_XNT_MINT, USDC_X_MINT}:
        raise AssertionError("reference pool mint identity mismatch")

    detail_rows, _rate_limits = _fresh_pool_details([REFERENCE_POOL])
    detail = detail_rows[REFERENCE_POOL]

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
        self.assertGreaterEqual(MIN_EVENTS, 5)
        self.assertGreaterEqual(MIN_POOLS, 5)
        self.assertGreaterEqual(MAX_WATCH_POOLS, 5)
        self.assertLessEqual(MAX_WATCH_POOLS, 500)

        usdcx_evidence = capture_current_usdcx_usd_equivalence_live_evidence()
        current_usdcx_usd_equivalence_verified = bool(
            (usdcx_evidence.get("equivalence") or {}).get(
                "current_usdcx_usd_equivalence_verified"
            )
            is True
        )
        self.assertTrue(current_usdcx_usd_equivalence_verified)

        targets, layouts, watch_discovery = _discover_verified_watch_set()
        self.assertGreaterEqual(
            len(targets),
            5,
            f"fewer than five on-chain verified wrapped-XNT watch pools: {watch_discovery}",
        )
        labels = {
            pool: (
                "priority_wrapped_xnt_pool"
                if pool in {address for address, _label in POOL_SET}
                else "catalog_wrapped_xnt_pool"
            )
            for pool in targets
        }
        series = {pool: [] for pool in targets}
        previous = {}
        events = []
        evidenced_pools = set()
        seen_transitions = set()
        catalog_polls = []
        missing_target_observations = 0
        started = time.time()
        poll_index = 0

        while time.time() - started <= MAX_WAIT_SECONDS:
            details, poll_meta = _bulk_catalog_details(targets)
            catalog_polls.append(poll_meta)
            changed = []
            for pool in targets:
                detail = details.get(pool)
                if detail is None:
                    previous.pop(pool, None)
                    missing_target_observations += 1
                    continue
                current = _provider_snapshot(
                    detail,
                    index=poll_index,
                    rate_limit={},
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

            # Distinct pools are the scarce acceptance resource. Process unseen
            # pools first, then already-evidenced pools only if needed.
            changed.sort(key=lambda item: (item[0] in evidenced_pools, item[0]))
            for pool, before, after in changed:
                if pool in evidenced_pools:
                    continue
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
                event = {
                    "event_key": f"{pool}:{after.get('lastSyncedAt')}:{after['liquidity']}",
                    "pool_address": pool,
                    "revaluation": revaluation,
                    "reference_alignment": reference,
                    "transition": {"before": before, "after": after},
                }
                events.append(event)
                if reference.get("same_fact_temporal_alignment_verified") is True:
                    evidenced_pools.add(pool)

            evaluation = evaluate_ninja_liquidity_revaluation_series(
                events,
                current_usdcx_usd_equivalence_verified=(
                    current_usdcx_usd_equivalence_verified
                ),
                minimum_repeated_events=MIN_EVENTS,
                minimum_repeated_pools=MIN_POOLS,
                minimum_usd_semantic_pools=5,
            )
            if evaluation["x1_ninja_liquidity_usd_semantics_verified"] is True:
                break

            poll_index += 1
            elapsed = time.time() - started
            if elapsed + POLL_SECONDS > MAX_WAIT_SECONDS:
                break
            time.sleep(POLL_SECONDS)

        evaluation = evaluate_ninja_liquidity_revaluation_series(
            events,
            current_usdcx_usd_equivalence_verified=(
                current_usdcx_usd_equivalence_verified
            ),
            minimum_repeated_events=MIN_EVENTS,
            minimum_repeated_pools=MIN_POOLS,
            minimum_usd_semantic_pools=5,
        )
        evidence = {
            "schema": "x1_liquidity_461_repeated_revaluation_live.v3",
            "chain": "x1",
            "collector": "bulk_catalog_watch_onchain_verified_wrapped_xnt_v1",
            "elapsed_seconds": time.time() - started,
            "watch_discovery": watch_discovery,
            "watched_pool_count": len(targets),
            "catalog_poll_count": len(catalog_polls),
            "catalog_polls": catalog_polls,
            "missing_target_observation_count": missing_target_observations,
            "events": events,
            "current_usdcx_usd_equivalence_evidence": usdcx_evidence,
            "evaluation": evaluation,
            "current_usdcx_usd_equivalence_verified": (
                current_usdcx_usd_equivalence_verified
            ),
            "x1_ninja_liquidity_usd_semantics_verified": evaluation[
                "x1_ninja_liquidity_usd_semantics_verified"
            ],
            "liquidity_freshness_verified": False,
            "source_independence_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        print("X1 #461 FIVE-POOL USD LIQUIDITY SEMANTICS EVIDENCE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertTrue(evidence["current_usdcx_usd_equivalence_verified"])
        self.assertGreaterEqual(evidence["watched_pool_count"], 5)
        self.assertTrue(evidence["watch_discovery"]["pool_identity_verified_for_watched_set"])
        self.assertTrue(evidence["watch_discovery"]["wrapped_xnt_position_verified_for_watched_set"])
        self.assertTrue(evidence["x1_ninja_liquidity_usd_semantics_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["source_independence_verified"])
        self.assertFalse(evidence["cmis_promotable"])
        self.assertFalse(evidence["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
