import json
import os
import time
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.ninja_pool_detail import (
    X1NinjaPoolDetailError,
    fetch_pool_detail_raw,
)
from liquidity_scout.providers.x1.ninja_liquidity_revaluation import (
    verify_price_only_liquidity_revaluation,
)
from liquidity_scout.providers.x1.candidate_pool_role import extract_pubkey_at
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.rpc import rpc_request
from liquidity_scout.providers.x1.transaction_semantics import (
    account_key_info,
    fetch_transaction,
)
from liquidity_scout.providers.x1.xdex_price_history_import import WRAPPED_XNT_MINT


RUN_LIVE = os.getenv("RUN_X1_NINJA_LIQUIDITY_TRANSITION_LIVE") == "1"
MAX_WAIT_SECONDS = int(os.getenv("X1_NINJA_LIQUIDITY_TRANSITION_MAX_WAIT_SECONDS", "600"))
POLL_SECONDS = float(os.getenv("X1_NINJA_LIQUIDITY_TRANSITION_POLL_SECONDS", "10"))
LOOKBACK_SLOTS = int(os.getenv("X1_NINJA_LIQUIDITY_TRANSITION_LOOKBACK_SLOTS", "2500"))
RATE_LIMIT_BACKOFF_SECONDS = float(
    os.getenv("X1_NINJA_LIQUIDITY_TRANSITION_RATE_LIMIT_BACKOFF_SECONDS", "65")
)
POOL_SPACE = 637
VAULT_0_OFFSET = 72
VAULT_1_OFFSET = 104
MINT_0_OFFSET = 168
MINT_1_OFFSET = 200

POOL_SET = [
    ("GwwCyLS4VEeZXyPWPYRNiVSuVur6ntioxBmjDQHHHv9x", "original_fail_4.07pct"),
    ("GdKcXA1Q78Bquke5jyZUR1C8YMN6VYT9AUheN1RwKLfe", "original_fail_3.46pct_recovered_once"),
    ("Ec3Keyy1yemycLRjh8PgkKiDJaD3w77UBLViwtB5zmSJ", "original_fail_6.57pct"),
    ("7deZorr98nLdZhpmSdUgu8WY4NAjSpeLDGxHzaTAxrUg", "original_control_exact"),
    ("EcmFn1chD6T9rE3XctPUDxjcqEDT3n2YeQJH627rSCD5", "original_control_exact"),

    # High-activity wrapped-XNT pools discovered from the recent XDEX swaps
    # signed by AAoKjyzkykEmaULghjbGRJPzRjYYSaRRpyJTcZroReSs.
    ("Eb9piUoHicVJDBawTMH5rboziwxMc6oENUcwidoWCJSW", "active_signer_12_recent_hits"),
    ("4sn8oCQWPikDxBkyRdd1S6bJ24oYjGF16aR7ZqCSXy4v", "active_signer_8_recent_hits"),
    ("9oNpPyK6z1S2VCNZeAT1NfEXoLi2poMsxsycLbQdYrQe", "active_signer_8_recent_hits"),
    ("CAJeVEoSm1QQZccnCqYu9cnNF7TTD2fcUA3E5HQoxRvR", "active_xnt_usdcx_reference_7_recent_hits"),
    ("8EUkm5ChdmLm9pxKX3Q99APck1URfVqP9m9R3FQcP6Tb", "active_signer_6_recent_hits"),
    ("8hEhKFmb43qkcctdV94VjwQxUubZ7zCTyG7Hsb1BWcsq", "active_signer_3_recent_hits"),
    ("Fq4PGJgsHGu573k2PCujbo6PdYSTz7Ttc5riGHLdjPCC", "active_signer_3_recent_hits"),
    ("42L71tiJR69Y8jDx9jGCivoxMkyS22LVAANeRS7smH5R", "active_signer_2_recent_hits"),
    ("wdLWfF28MtU6Tns7nix5xnfGPZufFKoME4FpFyaf3VW", "active_signer_2_recent_hits"),
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


def _positive(value, *, name):
    parsed = _decimal(value, name=name)
    if parsed <= 0:
        raise AssertionError(f"{name} must be positive")
    return parsed


def _fresh_pool_details(targets):
    """Fetch exact pools with per-request RPC slot brackets.

    Each provider read is bracketed by confirmed X1 slots so any pool
    transaction that could have landed while the request was in flight is
    included in the later zero-intervening-transaction check. A bounded retry
    is allowed only for an explicit provider 429.
    """

    rows = {}
    rate_limits = {}
    for pool in targets:
        last_error = None
        for attempt in range(2):
            slot_before = _current_slot()
            try:
                result = fetch_pool_detail_raw(pool)
            except X1NinjaPoolDetailError as exc:
                last_error = exc
                if "429" in str(exc) and attempt == 0:
                    time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                    continue
                raise
            slot_after = _current_slot()
            break
        else:
            raise last_error or AssertionError(f"{pool} pool-detail unavailable")

        body = result.get("raw_response")
        if not isinstance(body, dict):
            raise AssertionError(f"{pool} pool-detail body is unavailable")
        row = body.get("pool")
        if not isinstance(row, dict):
            raise AssertionError(f"{pool} pool-detail response has no pool object")
        if _address(row) != pool:
            raise AssertionError(
                f"{pool} pool-detail identity mismatch: {_address(row)}"
            )
        xnt_price = body.get("xntPriceUsd")
        rows[pool] = {
            "row": row,
            "xntPriceUsd": xnt_price,
            "lastUpdated": body.get("lastUpdated"),
            "observed_at": result.get("observed_at"),
            "slot_before": slot_before,
            "slot_after": slot_after,
        }
        rate_limits[pool] = result.get("rate_limit") or {}
    return rows, rate_limits


def _current_slot():
    value = rpc_request("getSlot", [{"commitment": "confirmed"}])
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AssertionError("X1 RPC getSlot returned invalid slot")
    return value


def _pool_layout(pool):
    state = fetch_account_state(pool)
    data = state.get("data")
    if not isinstance(data, bytes) or len(data) != POOL_SPACE:
        raise AssertionError(f"{pool} is not an accepted 637-byte XDEX pool")
    return {
        "pool_address": pool,
        "owner": state.get("owner"),
        "vault_0": extract_pubkey_at(data, VAULT_0_OFFSET),
        "vault_1": extract_pubkey_at(data, VAULT_1_OFFSET),
        "mint_0": extract_pubkey_at(data, MINT_0_OFFSET),
        "mint_1": extract_pubkey_at(data, MINT_1_OFFSET),
    }


def _rpc_token_balance(tx, *, account, mint, which):
    keys, _ = account_key_info(tx)
    try:
        index = keys.index(account)
    except ValueError:
        return None
    meta = tx.get("meta") or {}
    rows = meta.get("preTokenBalances") if which == "pre" else meta.get("postTokenBalances")
    for item in rows or []:
        if (
            isinstance(item, dict)
            and item.get("accountIndex") == index
            and _text(item.get("mint")) == mint
        ):
            amount = (item.get("uiTokenAmount") or {}).get("amount")
            decimals = (item.get("uiTokenAmount") or {}).get("decimals")
            if amount is None or decimals is None:
                return None
            return Decimal(int(amount)) / (Decimal(10) ** int(decimals))
    return None


def _orient(layout, reserve_0, reserve_1):
    if layout["mint_0"] == WRAPPED_XNT_MINT and layout["mint_1"] != WRAPPED_XNT_MINT:
        return {
            "asset_mint": layout["mint_1"],
            "xnt_reserve": reserve_0,
            "asset_reserve": reserve_1,
        }
    if layout["mint_1"] == WRAPPED_XNT_MINT and layout["mint_0"] != WRAPPED_XNT_MINT:
        return {
            "asset_mint": layout["mint_0"],
            "xnt_reserve": reserve_1,
            "asset_reserve": reserve_0,
        }
    raise AssertionError("pool must contain exactly one wrapped-XNT mint")


def _provider_snapshot(detail, *, index, rate_limit):
    pool = detail["row"]
    slot_before = detail.get("slot_before")
    slot_after = detail.get("slot_after")
    return {
        "index": index,
        "slot": slot_after,
        "slot_before": slot_before,
        "slot_after": slot_after,
        "observed_at_unix": detail.get("observed_at") or time.time(),
        "liquidity": format(_positive(pool.get("liquidity"), name="liquidity"), "f"),
        "priceUsd": format(_positive(pool.get("priceUsd"), name="priceUsd"), "f"),
        "priceNative": format(_positive(pool.get("priceNative"), name="priceNative"), "f"),
        "pooledBase": format(_positive(pool.get("pooledBase"), name="pooledBase"), "f"),
        "pooledQuote": format(_positive(pool.get("pooledQuote"), name="pooledQuote"), "f"),
        "xntPriceUsd": format(
            _positive(detail.get("xntPriceUsd"), name="xntPriceUsd"),
            "f",
        ),
        "lastSyncedAt": pool.get("lastSyncedAt"),
        "lastUpdated": detail.get("lastUpdated"),
        "rate_limit": rate_limit,
    }


def _relative_error(observed, expected):
    if expected == 0:
        return None
    return abs(observed - expected) / abs(expected)


def _signatures_between(pool, *, before_slot, after_slot):
    rows = rpc_request(
        "getSignaturesForAddress",
        [pool, {"limit": 1000, "commitment": "confirmed"}],
    )
    if not isinstance(rows, list):
        raise AssertionError("getSignaturesForAddress returned invalid history")
    selected = []
    for row in rows:
        if not isinstance(row, dict) or row.get("err") is not None:
            continue
        slot = row.get("slot")
        signature = _text(row.get("signature"))
        if (
            isinstance(slot, int)
            and not isinstance(slot, bool)
            and signature
            and before_slot < slot <= after_slot
        ):
            selected.append({
                "signature": signature,
                "slot": slot,
                "block_time": row.get("blockTime"),
            })
    selected.sort(key=lambda row: row["slot"])
    return selected


def _reconstruct_transition(*, pool, label, layout, samples, before, after):
    capture_start_slot = samples[0]["slot_before"]
    reconstruction_start_slot = max(0, capture_start_slot - LOOKBACK_SLOTS)
    signatures = _signatures_between(
        pool,
        before_slot=reconstruction_start_slot,
        after_slot=after["slot_after"],
    )
    transition_signatures = _signatures_between(
        pool,
        before_slot=before["slot_before"],
        after_slot=after["slot_after"],
    )

    if layout["mint_0"] == WRAPPED_XNT_MINT:
        wrapped_xnt_provider_field = "pooledQuote"
    elif layout["mint_1"] == WRAPPED_XNT_MINT:
        wrapped_xnt_provider_field = "pooledBase"
    else:
        raise AssertionError("transition pool has no wrapped-XNT mint")

    revaluation = verify_price_only_liquidity_revaluation(
        before=before,
        after=after,
        wrapped_xnt_provider_field=wrapped_xnt_provider_field,
        intervening_pool_signature_count=len(transition_signatures),
    )

    candidates = []
    new_liquidity = Decimal(after["liquidity"])
    for item in signatures:
        tx = fetch_transaction(item["signature"])
        if not isinstance(tx, dict):
            continue
        post_0 = _rpc_token_balance(
            tx, account=layout["vault_0"], mint=layout["mint_0"], which="post"
        )
        post_1 = _rpc_token_balance(
            tx, account=layout["vault_1"], mint=layout["mint_1"], which="post"
        )
        if post_0 is None or post_1 is None:
            continue
        oriented = _orient(layout, post_0, post_1)
        formulas = []
        for price_source in samples:
            asset_price = Decimal(price_source["priceUsd"])
            xnt_price = Decimal(price_source["xntPriceUsd"])
            formula = (
                oriented["xnt_reserve"] * xnt_price
                + oriented["asset_reserve"] * asset_price
            )
            error = _relative_error(new_liquidity, formula)
            formulas.append({
                "price_sample_index": price_source["index"],
                "price_sample_slot": price_source["slot"],
                "price_sample_observed_at_unix": price_source["observed_at_unix"],
                "asset_price_usd": format(asset_price, "f"),
                "xnt_price_usd": format(xnt_price, "f"),
                "candidate_liquidity": format(formula, "f"),
                "relative_error": format(error, "e") if error is not None else None,
            })
        candidates.append({
            "signature": item["signature"],
            "slot": item["slot"],
            "block_time": tx.get("blockTime"),
            "asset_mint": oriented["asset_mint"],
            "post_xnt_reserve": format(oriented["xnt_reserve"], "f"),
            "post_asset_reserve": format(oriented["asset_reserve"], "f"),
            "formulas": formulas,
        })

    flattened = []
    for candidate in candidates:
        for formula in candidate["formulas"]:
            if formula["relative_error"] is None:
                continue
            flattened.append({
                "signature": candidate["signature"],
                "slot": candidate["slot"],
                "price_sample_index": formula["price_sample_index"],
                "price_sample_slot": formula["price_sample_slot"],
                "price_sample_observed_at_unix": formula["price_sample_observed_at_unix"],
                "candidate_liquidity": formula["candidate_liquidity"],
                "relative_error": Decimal(formula["relative_error"]),
            })
    flattened.sort(key=lambda row: row["relative_error"])
    best = flattened[0] if flattened else None

    return {
        "pool_address": pool,
        "classification": label,
        "transition": {"before": before, "after": after},
        "capture_start_slot": capture_start_slot,
        "reconstruction_start_slot": reconstruction_start_slot,
        "lookback_slots": LOOKBACK_SLOTS,
        "intervening_signature_count": len(transition_signatures),
        "reconstruction_lookback_signature_count": len(signatures),
        "price_only_revaluation": revaluation,
        "reconstructed_candidate_count": len(candidates),
        "candidates": candidates,
        "best_candidate": ({
            "signature": best["signature"],
            "slot": best["slot"],
            "price_sample_index": best["price_sample_index"],
            "price_sample_slot": best["price_sample_slot"],
            "price_sample_observed_at_unix": best["price_sample_observed_at_unix"],
            "candidate_liquidity": best["candidate_liquidity"],
            "relative_error": format(best["relative_error"], "e"),
        } if best else None),
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIQUIDITY_TRANSITION_LIVE=1 for bounded multi-pool transition evidence",
)
class X1NinjaLiquidityTransitionCaptureLiveTests(unittest.TestCase):
    def test_capture_next_transition_across_selected_461_pools(self):
        self.assertGreaterEqual(MAX_WAIT_SECONDS, 60)
        self.assertGreaterEqual(POLL_SECONDS, 5)
        targets = [pool for pool, _label in POOL_SET]
        labels = dict(POOL_SET)
        layouts = {pool: _pool_layout(pool) for pool in targets}
        series = {pool: [] for pool in targets}
        previous = {}
        transitions = {}
        started = time.time()
        poll_index = 0

        while time.time() - started <= MAX_WAIT_SECONDS:
            details, rate_limits = _fresh_pool_details(targets)

            changed_this_poll = []
            for pool in targets:
                current = _provider_snapshot(
                    details[pool],
                    index=poll_index,
                    rate_limit=rate_limits[pool],
                )
                series[pool].append(current)
                prior = previous.get(pool)
                if prior is not None and current["liquidity"] != prior["liquidity"]:
                    transitions[pool] = {"before": prior, "after": current}
                    changed_this_poll.append(pool)
                previous[pool] = current

            if changed_this_poll:
                break

            poll_index += 1
            elapsed = time.time() - started
            if elapsed + POLL_SECONDS > MAX_WAIT_SECONDS:
                break
            time.sleep(POLL_SECONDS)

        if not transitions:
            evidence = {
                "schema": "x1_liquidity_461_multi_pool_transition_capture.v1",
                "chain": "x1",
                "status": "bounded_timeout_no_transition",
                "watched_pool_count": len(targets),
                "watched_pools": [
                    {
                        "pool_address": pool,
                        "classification": labels[pool],
                        "sample_count": len(series[pool]),
                        "first_sample": series[pool][0] if series[pool] else None,
                        "last_sample": series[pool][-1] if series[pool] else None,
                    }
                    for pool in targets
                ],
                "elapsed_seconds": time.time() - started,
                "poll_seconds": POLL_SECONDS,
                "direct_pool_detail_requests_per_poll": len(targets),
                "provider_rate_limit_policy": "60 requests per 60 seconds observed live",
                "full_catalog_endpoint_used": False,
                "liquidity_transition_observed": False,
                "liquidity_fact_time_verified": False,
                "liquidity_freshness_verified": False,
                "cmis_promotable": False,
                "execution_authorized": False,
            }
            print("X1 #461 MULTI-POOL LIQUIDITY TRANSITION CAPTURE")
            print(json.dumps(evidence, sort_keys=True, default=str))
            self.assertFalse(evidence["liquidity_transition_observed"])
            return

        reconstructions = []
        for pool, transition in transitions.items():
            reconstructions.append(
                _reconstruct_transition(
                    pool=pool,
                    label=labels[pool],
                    layout=layouts[pool],
                    samples=series[pool],
                    before=transition["before"],
                    after=transition["after"],
                )
            )

        evidence = {
            "schema": "x1_liquidity_461_multi_pool_transition_capture.v1",
            "chain": "x1",
            "status": "transition_observed",
            "watched_pool_count": len(targets),
            "transition_pool_count": len(transitions),
            "transition_pools": list(transitions),
            "elapsed_seconds": time.time() - started,
            "poll_seconds": POLL_SECONDS,
            "direct_pool_detail_requests_per_poll": len(targets),
            "provider_rate_limit_policy": "60 requests per 60 seconds observed live",
            "full_catalog_endpoint_used": False,
            "reconstructions": reconstructions,
            "liquidity_transition_observed": True,
            "price_only_revaluation_verified_count": sum(
                1
                for item in reconstructions
                if (item.get("price_only_revaluation") or {}).get(
                    "price_only_liquidity_revaluation_verified"
                )
                is True
            ),
            "provider_internal_liquidity_formula_supported": any(
                (item.get("price_only_revaluation") or {}).get(
                    "provider_internal_liquidity_formula_supported"
                )
                is True
                for item in reconstructions
            ),
            "liquidity_fact_time_candidate_identified": any(
                item.get("best_candidate") is not None
                or (item.get("price_only_revaluation") or {}).get(
                    "price_only_liquidity_revaluation_verified"
                )
                is True
                for item in reconstructions
            ),
            "liquidity_fact_time_verified": False,
            "liquidity_freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        print("X1 #461 MULTI-POOL LIQUIDITY TRANSITION CAPTURE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertTrue(evidence["liquidity_transition_observed"])
        self.assertFalse(evidence["liquidity_fact_time_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["execution_authorized"])


if __name__ == "__main__":
    unittest.main()