"""Classify and capture live X1.Ninja price/reserve update events.

This module consumes the accepted slot-bracketed snapshot shape from #345 and
detects real provider-side market-data changes for one exact pool.

A meaningful update event requires priceNative and/or pooled reserve changes.
Timestamp-only changes are preserved but do not satisfy the market-fact event
gate. No timestamp field names, units, source names, or causal ordering are
inferred from observation alone.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.rpc import get_signatures_for_address


VERSION = "1.0"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _provider_row(snapshot: Mapping[str, Any], pool_address: str) -> Mapping[str, Any] | None:
    rows = snapshot.get("pools")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return None
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if _text(row.get("pool_address")) == pool_address:
            return row
    return None


def _field(provider: Mapping[str, Any], name: str) -> Any:
    return provider.get(name) if name in provider else None


def classify_ninja_price_reserve_transition(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    pool_address: str,
) -> dict[str, Any]:
    """Classify one exact-pool transition between two accepted snapshots."""

    pool_address = _text(pool_address)
    if not pool_address:
        raise ValueError("pool_address is required")

    before_row = _provider_row(before, pool_address)
    after_row = _provider_row(after, pool_address)
    if not isinstance(before_row, Mapping) or not isinstance(after_row, Mapping):
        return {
            "service": "x1_ninja_price_reserve_transition",
            "version": VERSION,
            "chain": "x1",
            "status": "unavailable",
            "pool_address": pool_address,
            "update_event_observed": False,
            "market_fact_change_observed": False,
            "event_type": None,
            "timing_classification_authorized": False,
            "errors": ["pool_missing_from_before_or_after_snapshot"],
        }

    before_provider = before_row.get("provider")
    after_provider = after_row.get("provider")
    if not isinstance(before_provider, Mapping) or not isinstance(after_provider, Mapping):
        return {
            "service": "x1_ninja_price_reserve_transition",
            "version": VERSION,
            "chain": "x1",
            "status": "unavailable",
            "pool_address": pool_address,
            "update_event_observed": False,
            "market_fact_change_observed": False,
            "event_type": None,
            "timing_classification_authorized": False,
            "errors": ["provider_fields_missing_from_before_or_after_snapshot"],
        }

    fields = ("priceNative", "pooledBase", "pooledQuote", "lastSyncedAt_raw")
    changed = {
        name: _field(before_provider, name) != _field(after_provider, name)
        for name in fields
    }
    global_before = (
        before.get("provider_timestamp_candidates", {}).get("global_lastUpdated_raw")
        if isinstance(before.get("provider_timestamp_candidates"), Mapping)
        else None
    )
    global_after = (
        after.get("provider_timestamp_candidates", {}).get("global_lastUpdated_raw")
        if isinstance(after.get("provider_timestamp_candidates"), Mapping)
        else None
    )
    global_changed = global_before != global_after

    price_changed = changed["priceNative"]
    reserve_changed = changed["pooledBase"] or changed["pooledQuote"]
    timestamp_changed = changed["lastSyncedAt_raw"] or global_changed
    market_fact_change = price_changed or reserve_changed
    update_event = market_fact_change or timestamp_changed

    if price_changed and reserve_changed:
        event_type = "joint_price_and_reserve"
    elif price_changed:
        event_type = "price_only"
    elif reserve_changed:
        event_type = "reserve_only"
    elif timestamp_changed:
        event_type = "timestamp_only"
    else:
        event_type = None

    before_ratio = (
        before_row.get("price_vs_rpc_ratio")
        if isinstance(before_row.get("price_vs_rpc_ratio"), Mapping)
        else {}
    )
    after_ratio = (
        after_row.get("price_vs_rpc_ratio")
        if isinstance(after_row.get("price_vs_rpc_ratio"), Mapping)
        else {}
    )

    return {
        "service": "x1_ninja_price_reserve_transition",
        "version": VERSION,
        "chain": "x1",
        "status": "observed" if update_event else "no_change",
        "pool_address": pool_address,
        "update_event_observed": update_event,
        "market_fact_change_observed": market_fact_change,
        "event_type": event_type,
        "changed_fields": {
            **changed,
            "global_lastUpdated_raw": global_changed,
        },
        "before": {
            "provider": {
                name: _field(before_provider, name)
                for name in fields
            },
            "global_lastUpdated_raw": global_before,
            "relative_price_vs_rpc_ratio_error": before_ratio.get("relative_error"),
            "rpc_slot_bracket": before.get("rpc_slot_bracket"),
            "observed_at_start": before.get("observed_at_start"),
            "observed_at_end": before.get("observed_at_end"),
        },
        "after": {
            "provider": {
                name: _field(after_provider, name)
                for name in fields
            },
            "global_lastUpdated_raw": global_after,
            "relative_price_vs_rpc_ratio_error": after_ratio.get("relative_error"),
            "rpc_slot_bracket": after.get("rpc_slot_bracket"),
            "observed_at_start": after.get("observed_at_start"),
            "observed_at_end": after.get("observed_at_end"),
        },
        "provider_timestamp_units_verified": False,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "event_ordering_verified": False,
        "same_fact_temporal_alignment_verified": False,
        "timing_classification_authorized": market_fact_change,
        "price_native_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
        "errors": [],
    }


def collect_recent_exact_pool_activity(
    pool_address: str,
    *,
    limit: int = 5,
    activity_fetcher: Callable[..., Sequence[Mapping[str, Any]]] = (
        get_signatures_for_address
    ),
) -> dict[str, Any]:
    """Preserve bounded recent exact-pool chain activity when available."""

    pool_address = _text(pool_address)
    if not pool_address:
        raise ValueError("pool_address is required")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("limit must be an integer from 1 to 20")

    try:
        raw = activity_fetcher(pool_address, limit=limit)
    except Exception as exc:
        return {
            "pool_address": pool_address,
            "available": False,
            "transactions": [],
            "error": f"{type(exc).__name__}: {exc}",
        }

    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return {
            "pool_address": pool_address,
            "available": False,
            "transactions": [],
            "error": "activity_fetcher_returned_non_sequence",
        }

    rows = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "signature": item.get("signature"),
                "slot": item.get("slot"),
                "block_time": item.get("block_time"),
                "err": item.get("err"),
                "confirmation_status": item.get("confirmation_status"),
            }
        )

    return {
        "pool_address": pool_address,
        "available": True,
        "transactions": rows,
        "error": None,
    }


def select_first_meaningful_transition(
    snapshots: Sequence[Mapping[str, Any]],
    *,
    pool_addresses: Sequence[str],
    activity_fetcher: Callable[..., Sequence[Mapping[str, Any]]] = (
        get_signatures_for_address
    ),
) -> dict[str, Any]:
    """Select the first price/reserve change and attach recent pool activity."""

    if not isinstance(snapshots, Sequence) or isinstance(snapshots, (str, bytes)):
        raise ValueError("snapshots must be a sequence")
    if len(snapshots) < 2:
        raise ValueError("at least two snapshots are required")

    addresses = []
    seen = set()
    for raw in pool_addresses:
        address = _text(raw)
        if address and address not in seen:
            seen.add(address)
            addresses.append(address)
    if not addresses:
        raise ValueError("at least one pool address is required")

    timestamp_only_events = []
    for index in range(1, len(snapshots)):
        before = snapshots[index - 1]
        after = snapshots[index]
        if not isinstance(before, Mapping) or not isinstance(after, Mapping):
            continue
        for address in addresses:
            event = classify_ninja_price_reserve_transition(
                before,
                after,
                pool_address=address,
            )
            if event.get("market_fact_change_observed") is True:
                return {
                    "service": "x1_ninja_live_update_event",
                    "version": VERSION,
                    "chain": "x1",
                    "status": "observed",
                    "transition_index": index,
                    "event": event,
                    "recent_exact_pool_activity": collect_recent_exact_pool_activity(
                        address,
                        activity_fetcher=activity_fetcher,
                    ),
                    "provider_timestamp_units_verified": False,
                    "provider_fact_time_verified": False,
                    "update_source_semantics_verified": False,
                    "event_ordering_verified": False,
                    "same_fact_temporal_alignment_verified": False,
                    "price_native_semantics_verified": False,
                    "cmis_promotable": False,
                    "execution_authorized": False,
                }
            if event.get("event_type") == "timestamp_only":
                timestamp_only_events.append(event)

    return {
        "service": "x1_ninja_live_update_event",
        "version": VERSION,
        "chain": "x1",
        "status": "unavailable",
        "transition_index": None,
        "event": None,
        "timestamp_only_events": timestamp_only_events,
        "recent_exact_pool_activity": None,
        "provider_timestamp_units_verified": False,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "event_ordering_verified": False,
        "same_fact_temporal_alignment_verified": False,
        "price_native_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
        "warnings": [
            "no_price_or_reserve_change_observed",
            "timestamp_only_change_does_not_satisfy_event_gate",
        ],
    }


__all__ = [
    "VERSION",
    "classify_ninja_price_reserve_transition",
    "collect_recent_exact_pool_activity",
    "select_first_meaningful_transition",
]
