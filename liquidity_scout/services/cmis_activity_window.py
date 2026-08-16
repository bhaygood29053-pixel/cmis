"""Verified time-window accounting for CMIS asset activity.

v1.2 never assumes that a provider's returned rows are a complete or "latest"
time range. Window membership is based only on X1 RPC block time that already
passed the trade-verification identity check.

A requested window can contain useful verified observations even while its
coverage remains partial. Full window coverage is promoted only when every
selected pool's history transport explicitly says pagination/range semantics
are verified, all returned rows were processed, and the returned verified
chain timestamps reach the requested start boundary (or the verified range is
empty).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from liquidity_scout.services.cmis_activity_transactions import (
    attach_transaction_aggregation,
)

SUPPORTED_WINDOWS = {
    "1h": 60 * 60,
    "6h": 6 * 60 * 60,
    "24h": 24 * 60 * 60,
}


def parse_activity_window_seconds(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("window must be one of: 1h, 6h, 24h")

    if isinstance(value, int):
        for seconds in SUPPORTED_WINDOWS.values():
            if value == seconds:
                return value
        raise ValueError("window must be one of: 1h, 6h, 24h")

    text = str(value or "").strip().lower()
    if text not in SUPPORTED_WINDOWS:
        raise ValueError("window must be one of: 1h, 6h, 24h")
    return SUPPORTED_WINDOWS[text]


def canonical_window_label(seconds: int) -> str:
    for label, value in SUPPORTED_WINDOWS.items():
        if value == seconds:
            return label
    raise ValueError("unsupported window duration")


def _iso_from_epoch(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _parse_chain_epoch(event: Mapping[str, Any]) -> float | None:
    identity = event.get("identity")
    if not isinstance(identity, Mapping):
        return None
    if identity.get("timestamp_verified") is not True:
        return None

    raw = identity.get("chain_block_time")
    text = str(raw or "").strip()
    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).timestamp()


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _window_aggregate(events):
    swap_candidates = sum(
        1
        for event in events
        if (_text(event.get("provider_type")) or "").lower() in {"buy", "sell"}
    )
    synthetic = {
        "data": {
            "events": [dict(event) for event in events],
            "pools": [],
            "swap_candidate_count": swap_candidates,
        },
        "confidence": {},
    }
    aggregated = attach_transaction_aggregation(synthetic)
    data = aggregated.get("data")
    return data if isinstance(data, Mapping) else {}


def apply_activity_window(
    envelope: Any,
    *,
    window_seconds: int,
    window_end_epoch: float,
    pool_records: Sequence[Mapping[str, Any]],
):
    """Attach verified window observations and explicit coverage evidence."""

    if not isinstance(envelope, Mapping):
        return envelope

    result = deepcopy(dict(envelope))
    data = result.get("data")
    if not isinstance(data, Mapping):
        return result

    data = dict(data)
    result["data"] = data

    seconds = parse_activity_window_seconds(window_seconds)
    label = canonical_window_label(seconds)
    end_epoch = float(window_end_epoch)
    start_epoch = end_epoch - seconds

    raw_events = data.get("events")
    events = (
        [dict(event) for event in raw_events if isinstance(event, Mapping)]
        if isinstance(raw_events, Sequence)
        and not isinstance(raw_events, (str, bytes))
        else []
    )

    within = []
    before = 0
    after = 0
    unattributed = 0

    by_pool_times: dict[str, list[float]] = {}

    for event in events:
        chain_epoch = _parse_chain_epoch(event)
        if chain_epoch is None:
            unattributed += 1
            continue

        pool = _text(event.get("pool_address"))
        if pool:
            by_pool_times.setdefault(pool, []).append(chain_epoch)

        if chain_epoch < start_epoch:
            before += 1
        elif chain_epoch > end_epoch:
            after += 1
        else:
            item = dict(event)
            item["window_chain_block_time"] = _iso_from_epoch(chain_epoch)
            within.append(item)

    window_agg = _window_aggregate(within)

    pool_coverage = []
    all_selected_pool_coverage_proven = bool(pool_records)

    for record in pool_records:
        if not isinstance(record, Mapping):
            all_selected_pool_coverage_proven = False
            continue

        address = _text(record.get("pool_address"))
        history_ok = record.get("history_ok") is True
        returned = _int(record.get("provider_event_count"))
        processed = _int(record.get("processed_event_count"))
        all_returned_processed = history_ok and processed >= returned

        semantics = record.get("history_semantics")
        semantics = semantics if isinstance(semantics, Mapping) else {}
        range_semantics_verified = (
            semantics.get("pagination_or_range_verified") is True
        )

        times = by_pool_times.get(address or "", [])
        oldest = min(times) if times else None
        newest = max(times) if times else None

        observed_start_reached = bool(
            oldest is not None and oldest <= start_epoch
        )

        # Empty history can only prove an empty window if range semantics
        # themselves are already independently verified.
        empty_verified_range = bool(
            history_ok
            and returned == 0
            and range_semantics_verified
            and all_returned_processed
        )

        coverage_proven = bool(
            history_ok
            and range_semantics_verified
            and all_returned_processed
            and (observed_start_reached or empty_verified_range)
        )
        if not coverage_proven:
            all_selected_pool_coverage_proven = False

        pool_coverage.append({
            "pool_address": address,
            "history_ok": history_ok,
            "provider_event_count": returned,
            "processed_event_count": processed,
            "all_returned_rows_processed": all_returned_processed,
            "provider_range_semantics_verified": range_semantics_verified,
            "oldest_verified_chain_time_utc": (
                _iso_from_epoch(oldest) if oldest is not None else None
            ),
            "newest_verified_chain_time_utc": (
                _iso_from_epoch(newest) if newest is not None else None
            ),
            "observed_start_boundary_reached": observed_start_reached,
            "window_coverage_proven": coverage_proven,
        })

    confidence = result.get("confidence")
    confidence = dict(confidence) if isinstance(confidence, Mapping) else {}

    pool_selection_complete = confidence.get("pool_selection_complete") is True
    pool_history_complete = confidence.get("pool_history_complete") is True
    timestamp_membership_complete = unattributed == 0

    window_coverage_complete = bool(
        pool_selection_complete
        and pool_history_complete
        and all_selected_pool_coverage_proven
        and timestamp_membership_complete
    )

    base_complete = confidence.get("complete") is True
    confidence["base_complete"] = base_complete
    confidence["window_requested"] = True
    confidence["window_timestamp_membership_complete"] = (
        timestamp_membership_complete
    )
    confidence["window_coverage_complete"] = window_coverage_complete
    confidence["complete"] = bool(base_complete and window_coverage_complete)
    result["confidence"] = confidence

    window_transactions = window_agg.get("transactions")
    if not isinstance(window_transactions, list):
        window_transactions = []

    data["activity_window"] = {
        "label": label,
        "duration_seconds": seconds,
        "start_utc": _iso_from_epoch(start_epoch),
        "end_utc": _iso_from_epoch(end_epoch),
        "membership_basis": "X1_RPC_VERIFIED_CHAIN_BLOCK_TIME",
        "coverage_complete": window_coverage_complete,
        "timestamp_membership_complete": timestamp_membership_complete,
        "processed_event_count_in_window": len(within),
        "processed_event_count_before_window": before,
        "processed_event_count_after_window": after,
        "processed_event_count_without_verified_chain_time": unattributed,
        "pool_coverage": pool_coverage,
    }

    data["window_activity"] = {
        "unique_transaction_count": _int(
            window_agg.get("unique_transaction_count")
        ),
        "verified_transaction_count": _int(
            window_agg.get("verified_transaction_count")
        ),
        "verified_buy_transaction_count": _int(
            window_agg.get("verified_buy_transaction_count")
        ),
        "verified_sell_transaction_count": _int(
            window_agg.get("verified_sell_transaction_count")
        ),
        "verified_mixed_transaction_count": _int(
            window_agg.get("verified_mixed_transaction_count")
        ),
        "multi_pool_transaction_count": _int(
            window_agg.get("multi_pool_transaction_count")
        ),
        "multi_leg_verified_transaction_count": _int(
            window_agg.get("multi_leg_verified_transaction_count")
        ),
        "verified_pool_leg_count": _int(
            window_agg.get("verified_pool_leg_count")
        ),
        "verified_buy_pool_leg_count": _int(
            window_agg.get("verified_buy_pool_leg_count")
        ),
        "verified_sell_pool_leg_count": _int(
            window_agg.get("verified_sell_pool_leg_count")
        ),
        "exact_amount_verified_trade_count": _int(
            window_agg.get("exact_amount_verified_trade_count")
        ),
        "exact_verified_asset_amounts": dict(
            window_agg.get("exact_verified_asset_amounts") or {}
        ),
        "exact_verified_quote_amounts_by_mint": dict(
            window_agg.get("exact_verified_quote_amounts_by_mint") or {}
        ),
        "transactions": window_transactions,
    }

    warnings = result.get("warnings")
    warnings = list(warnings) if isinstance(warnings, list) else []

    if not timestamp_membership_complete:
        warnings.append({
            "code": "activity_window_timestamp_membership_incomplete",
            "message": (
                f"{unattributed} processed event(s) did not have a verified "
                "X1 chain block time and were excluded from window membership."
            ),
        })

    if not window_coverage_complete:
        warnings.append({
            "code": "activity_window_range_not_proven",
            "message": (
                f"Verified observations inside the {label} window are usable, "
                "but complete window coverage is not proven for every selected "
                "pool. Provider pagination/range semantics remain a hard gate."
            ),
        })

    result["warnings"] = warnings

    if result.get("status") == "ok" and not window_coverage_complete:
        result["status"] = "partial"

    return result


__all__ = [
    "SUPPORTED_WINDOWS",
    "apply_activity_window",
    "canonical_window_label",
    "parse_activity_window_seconds",
]
