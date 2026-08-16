"""Transaction-aware post-processing for CMIS Verified Asset Activity v1.1.

The v1 service verifies provider rows pool-by-pool. This helper adds a second,
asset-level accounting pass so one blockchain transaction is not mistaken for
multiple independent transactions merely because it appears in multiple pool
histories.

It preserves every evidence event, deduplicates repeated verified pool-leg
representations, and exposes transaction counts separately from pool-leg counts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

EXACT_POOL_LEG = "EXACT_POOL_LEG_AMOUNTS"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _verified_leg_key(event: Mapping[str, Any]) -> tuple | None:
    if event.get("asset_scope_verified") is not True:
        return None

    signature = _text(event.get("transaction_signature"))
    pool = _text(event.get("pool_address"))
    side = _text(event.get("side"))
    if not signature or not pool or side not in {"BUY", "SELL"}:
        return None

    exact = event.get("exact_pool_leg")
    if isinstance(exact, Mapping):
        return (
            signature,
            pool,
            side,
            _text(exact.get("asset_mint")),
            _text(exact.get("asset_account")),
            _text(exact.get("asset_amount")),
            _text(exact.get("quote_mint")),
            _text(exact.get("quote_account")),
            _text(exact.get("quote_amount")),
        )

    return (signature, pool, side, None, None, None, None, None, None)


def _transaction_summary(signature, events, verified_leg_keys):
    observed_pools = sorted({
        pool
        for pool in (_text(event.get("pool_address")) for event in events)
        if pool
    })

    seen = set()
    verified_sides = set()
    exact_count = 0
    verified_leg_count = 0
    conflict_count = 0
    mismatch_count = 0
    unresolved_count = 0

    for event in events:
        if event.get("status") == "ambiguous":
            conflict_count += 1

        if (
            event.get("side_verified") is True
            and event.get("asset_scope_verified") is not True
        ):
            mismatch_count += 1

        if (
            event.get("status") != "ambiguous"
            and event.get("verification_level") != "PROVIDER_EVENT_SEMANTICS_GATED"
            and event.get("asset_scope_verified") is not True
        ):
            unresolved_count += 1

        key = _verified_leg_key(event)
        if key is None or key not in verified_leg_keys or key in seen:
            continue

        seen.add(key)
        verified_leg_count += 1
        verified_sides.add(event.get("side"))
        if isinstance(event.get("exact_pool_leg"), Mapping):
            exact_count += 1

    if verified_sides == {"BUY"}:
        activity_side = "BUY"
    elif verified_sides == {"SELL"}:
        activity_side = "SELL"
    elif verified_sides == {"BUY", "SELL"}:
        activity_side = "MIXED"
    else:
        activity_side = "NONE"

    return {
        "transaction_signature": signature,
        "observed_pool_count": len(observed_pools),
        "observed_pools": observed_pools,
        "provider_event_count": len(events),
        "verified_asset_pool_leg_count": verified_leg_count,
        "verified_sides": sorted(verified_sides),
        "activity_side": activity_side,
        "exact_pool_leg_count": exact_count,
        "conflict_event_count": conflict_count,
        "unresolved_event_count": unresolved_count,
        "asset_scope_mismatch_event_count": mismatch_count,
    }


def attach_transaction_aggregation(envelope: Any):
    """Return the v1 envelope enriched with transaction-aware accounting."""

    if not isinstance(envelope, Mapping):
        return envelope

    result = deepcopy(dict(envelope))
    data = result.get("data")
    if not isinstance(data, Mapping):
        return result

    data = dict(data)
    result["data"] = data

    raw_events = data.get("events")
    events = (
        [dict(event) for event in raw_events if isinstance(event, Mapping)]
        if isinstance(raw_events, Sequence) and not isinstance(raw_events, (str, bytes))
        else []
    )

    unique_verified_events = []
    verified_leg_keys = set()

    for event in events:
        key = _verified_leg_key(event)
        if key is None or key in verified_leg_keys:
            continue
        verified_leg_keys.add(key)
        unique_verified_events.append(event)

    verified_pool_leg_count = len(unique_verified_events)
    buy_pool_legs = sum(
        1 for event in unique_verified_events if event.get("side") == "BUY"
    )
    sell_pool_legs = sum(
        1 for event in unique_verified_events if event.get("side") == "SELL"
    )

    exact_count = 0
    exact_buy_asset = Decimal(0)
    exact_sell_asset = Decimal(0)
    quote_totals = {}

    for event in unique_verified_events:
        leg = event.get("exact_pool_leg")
        if not isinstance(leg, Mapping):
            continue

        asset_amount = _decimal(leg.get("asset_amount"))
        quote_amount = _decimal(leg.get("quote_amount"))
        quote_mint = _text(leg.get("quote_mint"))
        if asset_amount is None or quote_amount is None or not quote_mint:
            continue

        exact_count += 1
        side = event.get("side")
        if side == "BUY":
            exact_buy_asset += asset_amount
        elif side == "SELL":
            exact_sell_asset += asset_amount

        bucket = quote_totals.setdefault(
            quote_mint,
            {"buy": Decimal(0), "sell": Decimal(0)},
        )
        if side == "BUY":
            bucket["buy"] += quote_amount
        elif side == "SELL":
            bucket["sell"] += quote_amount

    by_signature = {}
    missing_signature_count = 0

    for event in events:
        signature = _text(event.get("transaction_signature"))
        if not signature:
            missing_signature_count += 1
            continue
        by_signature.setdefault(signature, []).append(event)

    transactions = [
        _transaction_summary(signature, grouped, verified_leg_keys)
        for signature, grouped in sorted(by_signature.items())
    ]

    verified_transactions = [
        tx for tx in transactions if tx["verified_asset_pool_leg_count"] > 0
    ]

    data.update({
        "aggregation_version": "1.1",
        "unique_transaction_count": len(transactions),
        "verified_transaction_count": len(verified_transactions),
        "verified_buy_transaction_count": sum(
            1 for tx in verified_transactions if tx["activity_side"] == "BUY"
        ),
        "verified_sell_transaction_count": sum(
            1 for tx in verified_transactions if tx["activity_side"] == "SELL"
        ),
        "verified_mixed_transaction_count": sum(
            1 for tx in verified_transactions if tx["activity_side"] == "MIXED"
        ),
        "multi_pool_transaction_count": sum(
            1 for tx in transactions if tx["observed_pool_count"] > 1
        ),
        "multi_leg_verified_transaction_count": sum(
            1 for tx in verified_transactions if tx["verified_asset_pool_leg_count"] > 1
        ),
        "verified_pool_leg_count": verified_pool_leg_count,
        "verified_buy_pool_leg_count": buy_pool_legs,
        "verified_sell_pool_leg_count": sell_pool_legs,
        "verified_trade_count": verified_pool_leg_count,
        "verified_buy_count": buy_pool_legs,
        "verified_sell_count": sell_pool_legs,
        "exact_amount_verified_trade_count": exact_count,
        "missing_signature_event_count": missing_signature_count,
        "exact_verified_asset_amounts": {
            "buy_asset_amount": _decimal_text(exact_buy_asset),
            "sell_asset_amount": _decimal_text(exact_sell_asset),
        },
        "exact_verified_quote_amounts_by_mint": {
            mint: {
                "buy_quote_amount": _decimal_text(values["buy"]),
                "sell_quote_amount": _decimal_text(values["sell"]),
            }
            for mint, values in sorted(quote_totals.items())
        },
        "transactions": transactions,
    })

    pool_keys = {}
    for event in unique_verified_events:
        pool = _text(event.get("pool_address"))
        key = _verified_leg_key(event)
        if not pool or key is None:
            continue
        pool_keys.setdefault(pool, []).append((key, event.get("side")))

    pools = data.get("pools")
    if isinstance(pools, Sequence) and not isinstance(pools, (str, bytes)):
        updated_pools = []
        for pool_record in pools:
            if not isinstance(pool_record, Mapping):
                updated_pools.append(pool_record)
                continue
            item = dict(pool_record)
            pool = _text(item.get("pool_address"))
            rows = pool_keys.get(pool, [])
            item["verified_pool_leg_count"] = len(rows)
            item["verified_trade_count"] = len(rows)
            item["verified_buy_count"] = sum(1 for _key, side in rows if side == "BUY")
            item["verified_sell_count"] = sum(1 for _key, side in rows if side == "SELL")
            updated_pools.append(item)
        data["pools"] = updated_pools

    confidence = result.get("confidence")
    if isinstance(confidence, Mapping):
        confidence = dict(confidence)
        swap_candidates = data.get("swap_candidate_count")
        if (
            isinstance(swap_candidates, int)
            and not isinstance(swap_candidates, bool)
            and swap_candidates > 0
        ):
            confidence["verification_ratio"] = round(
                verified_pool_leg_count / swap_candidates,
                6,
            )
        confidence["transaction_aggregation_applied"] = True
        result["confidence"] = confidence

    return result


__all__ = ["attach_transaction_aggregation"]
