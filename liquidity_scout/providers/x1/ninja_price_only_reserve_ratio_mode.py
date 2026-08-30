"""Verify X1.Ninja price-only gross-reserve-ratio reconciliation events.

This layer consumes the exact-vault evidence from #356. A candidate event is
eligible only when:

- priceNative changes;
- pooledBase and pooledQuote are unchanged;
- both exact vault histories completely cover the safe between-snapshot window;
- no exact vault mutation occurs in that window.

The accepted #341 field mapping is preserved:

    pooledBase  -> vault_1
    pooledQuote -> vault_0

The wrapped-XNT mint slot from exact pool structure determines native-per-asset
gross reserve orientation. Both BEFORE and AFTER priceNative are compared to
that ratio with the already accepted price comparison tolerance.

This is observational evidence only. It does not prove provider-internal
update source, fact-time, freshness, priceUsd, liquidity, TVL, or execution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from liquidity_scout.providers.x1.ninja_execution_price_semantics import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    DEFAULT_RELATIVE_TOLERANCE,
)
from liquidity_scout.providers.x1.ninja_vault_activity_correlation import (
    ACCEPTED_POOLED_RESERVE_MAPPING,
    verify_vault_activity_transition,
)


VERSION = "1.0"

ADOPTION = "gross_reserve_ratio_adoption"
DEPARTURE = "gross_reserve_ratio_departure"
NEITHER = "non_reserve_price_only_update"
ALREADY = "already_at_gross_reserve_ratio"


def _decimal(value: Any, *, name: str, positive: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be finite")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be finite")
    if positive and parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _compare(
    observed: Decimal,
    expected: Decimal,
    *,
    relative: Decimal,
    absolute: Decimal,
) -> dict[str, Any]:
    error = abs(observed - expected)
    scale = abs(expected)
    relative_error = (
        error / scale
        if scale != 0
        else (Decimal(0) if error == 0 else None)
    )
    allowed = max(absolute, scale * relative)
    return {
        "observed": format(observed, "f"),
        "expected": format(expected, "f"),
        "absolute_error": format(error, "f"),
        "relative_error": (
            format(relative_error, "e")
            if relative_error is not None
            else None
        ),
        "allowed_absolute_error": format(allowed, "f"),
        "within_tolerance": error <= allowed,
    }


def _gross_native_per_asset_ratio(
    provider: Mapping[str, Any],
    *,
    xnt_slot: int,
) -> Decimal:
    pooled_base = _decimal(
        provider.get("pooledBase"),
        name="pooledBase",
        positive=True,
    )
    pooled_quote = _decimal(
        provider.get("pooledQuote"),
        name="pooledQuote",
        positive=True,
    )

    if xnt_slot == 0:
        # #341: pooledQuote -> vault_0 (XNT), pooledBase -> vault_1 (asset)
        return pooled_quote / pooled_base
    if xnt_slot == 1:
        # #341: pooledBase -> vault_1 (XNT), pooledQuote -> vault_0 (asset)
        return pooled_base / pooled_quote
    raise ValueError("xnt_slot must be 0 or 1")


def _event_key(
    *,
    pool_address: str,
    base: Mapping[str, Any],
) -> str:
    safe = base.get("safe_slot_window")
    safe = safe if isinstance(safe, Mapping) else {}
    lower = safe.get("exclusive_lower_slot")
    upper = safe.get("inclusive_upper_slot")
    return f"{pool_address}:{lower}:{upper}"


def verify_price_only_reserve_ratio_event(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    pool_address: str,
    vault_activity_verifier: Callable[..., Mapping[str, Any]] = (
        verify_vault_activity_transition
    ),
    relative_tolerance: Any = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance: Any = DEFAULT_ABSOLUTE_TOLERANCE,
    **vault_kwargs: Any,
) -> dict[str, Any]:
    """Classify one verified price-only event against gross reserve ratio."""

    pool_address = str(pool_address or "").strip()
    if not pool_address:
        raise ValueError("pool_address is required")
    if ACCEPTED_POOLED_RESERVE_MAPPING != (
        "pooledBase_to_vault1__pooledQuote_to_vault0"
    ):
        raise ValueError("accepted pooled-reserve mapping changed unexpectedly")

    base_raw = vault_activity_verifier(
        before=before,
        after=after,
        pool_address=pool_address,
        **vault_kwargs,
    )
    if not isinstance(base_raw, Mapping):
        raise ValueError("vault activity verifier returned malformed evidence")
    base = dict(base_raw)

    if base.get("vault_history_complete_for_window") is not True:
        return {
            "service": "x1_ninja_price_only_reserve_ratio_event",
            "version": VERSION,
            "chain": "x1",
            "status": "unavailable",
            "pool_address": pool_address,
            "price_only_update_verified": False,
            "gross_reserve_ratio_adoption_verified": False,
            "gross_reserve_ratio_departure_observed": False,
            "non_reserve_price_only_update_observed": False,
            "already_at_gross_reserve_ratio_observed": False,
            "reconciliation_mode_verified": False,
            "provider_fact_time_verified": False,
            "update_source_semantics_verified": False,
            "freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
            "base_evidence": base,
        }

    if base.get("price_only_update_observed") is not True:
        return {
            "service": "x1_ninja_price_only_reserve_ratio_event",
            "version": VERSION,
            "chain": "x1",
            "status": "not_applicable",
            "pool_address": pool_address,
            "price_only_update_verified": False,
            "gross_reserve_ratio_adoption_verified": False,
            "gross_reserve_ratio_departure_observed": False,
            "non_reserve_price_only_update_observed": False,
            "already_at_gross_reserve_ratio_observed": False,
            "reconciliation_mode_verified": False,
            "provider_fact_time_verified": False,
            "update_source_semantics_verified": False,
            "freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
            "base_evidence": base,
        }

    if base.get("transaction_coverage_complete") is not True:
        raise ValueError("price-only evidence requires complete transaction coverage")
    if base.get("unique_vault_history_signature_count") != 0:
        raise ValueError("price-only evidence must contain zero vault signatures")
    if base.get("verified_vault_transaction_count") != 0:
        raise ValueError("price-only evidence must contain zero vault transactions")
    if base.get("provider_reserve_changed") is not False:
        raise ValueError("price-only evidence requires unchanged provider reserves")
    if base.get("price_changed") is not True:
        raise ValueError("price-only evidence requires changed priceNative")

    identity = base.get("identity")
    identity = identity if isinstance(identity, Mapping) else {}
    xnt_slot = identity.get("xnt_slot")
    if isinstance(xnt_slot, bool) or xnt_slot not in {0, 1}:
        raise ValueError("exact XNT mint slot unavailable")

    before_provider = base.get("before_provider")
    after_provider = base.get("after_provider")
    if not isinstance(before_provider, Mapping) or not isinstance(
        after_provider, Mapping
    ):
        raise ValueError("provider BEFORE/AFTER evidence unavailable")

    before_base = _decimal(before_provider.get("pooledBase"), name="BEFORE pooledBase")
    after_base = _decimal(after_provider.get("pooledBase"), name="AFTER pooledBase")
    before_quote = _decimal(before_provider.get("pooledQuote"), name="BEFORE pooledQuote")
    after_quote = _decimal(after_provider.get("pooledQuote"), name="AFTER pooledQuote")
    if before_base != after_base or before_quote != after_quote:
        raise ValueError("provider reserves must be exactly unchanged")

    before_price = _decimal(
        before_provider.get("priceNative"),
        name="BEFORE priceNative",
        positive=True,
    )
    after_price = _decimal(
        after_provider.get("priceNative"),
        name="AFTER priceNative",
        positive=True,
    )
    if before_price == after_price:
        raise ValueError("priceNative must change")

    before_ratio = _gross_native_per_asset_ratio(
        before_provider,
        xnt_slot=xnt_slot,
    )
    after_ratio = _gross_native_per_asset_ratio(
        after_provider,
        xnt_slot=xnt_slot,
    )
    if before_ratio != after_ratio:
        raise ValueError("unchanged provider reserves must yield unchanged ratio")

    relative = _decimal(relative_tolerance, name="relative_tolerance")
    absolute = _decimal(absolute_tolerance, name="absolute_tolerance")
    if relative < 0 or absolute < 0 or (relative == 0 and absolute == 0):
        raise ValueError("comparison tolerances invalid")

    before_comparison = _compare(
        before_price,
        before_ratio,
        relative=relative,
        absolute=absolute,
    )
    after_comparison = _compare(
        after_price,
        after_ratio,
        relative=relative,
        absolute=absolute,
    )
    before_matches = before_comparison["within_tolerance"] is True
    after_matches = after_comparison["within_tolerance"] is True

    if not before_matches and after_matches:
        classification = ADOPTION
    elif before_matches and not after_matches:
        classification = DEPARTURE
    elif not before_matches and not after_matches:
        classification = NEITHER
    else:
        classification = ALREADY

    return {
        "service": "x1_ninja_price_only_reserve_ratio_event",
        "version": VERSION,
        "chain": "x1",
        "status": "verified",
        "pool_address": pool_address,
        "event_key": _event_key(pool_address=pool_address, base=base),
        "classification": classification,
        "price_only_update_verified": True,
        "gross_reserve_ratio_adoption_verified": classification == ADOPTION,
        "gross_reserve_ratio_departure_observed": classification == DEPARTURE,
        "non_reserve_price_only_update_observed": classification == NEITHER,
        "already_at_gross_reserve_ratio_observed": classification == ALREADY,
        "gross_reserve_ratio_native_per_asset": format(after_ratio, "f"),
        "before_price_comparison": before_comparison,
        "after_price_comparison": after_comparison,
        "accepted_pooled_reserve_mapping": ACCEPTED_POOLED_RESERVE_MAPPING,
        "xnt_slot": xnt_slot,
        "provider_timestamp_candidates": base.get(
            "provider_timestamp_candidates"
        ),
        "before_observed_at_start": before.get("observed_at_start"),
        "before_observed_at_end": before.get("observed_at_end"),
        "after_observed_at_start": after.get("observed_at_start"),
        "after_observed_at_end": after.get("observed_at_end"),
        "rpc_slot_window": base.get("safe_slot_window"),
        "reconciliation_mode_verified": False,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "universal_catalog_price_semantics_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "base_evidence": base,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def aggregate_price_only_reserve_ratio_events(
    events: Sequence[Mapping[str, Any]],
    *,
    minimum_verified_events: int = 5,
) -> dict[str, Any]:
    """Aggregate bounded reconciliation-mode evidence fail-closed."""

    if isinstance(minimum_verified_events, bool) or not isinstance(
        minimum_verified_events, int
    ):
        raise ValueError("minimum_verified_events must be an integer")
    if minimum_verified_events < 5:
        raise ValueError("minimum_verified_events must be at least 5")

    rows = [dict(row) for row in events if isinstance(row, Mapping)]
    verified = [
        row for row in rows if row.get("price_only_update_verified") is True
    ]
    keys = [
        row.get("event_key")
        for row in verified
        if isinstance(row.get("event_key"), str) and row.get("event_key")
    ]
    distinct_keys = set(keys)

    counts = {
        ADOPTION: 0,
        DEPARTURE: 0,
        NEITHER: 0,
        ALREADY: 0,
    }
    for row in verified:
        classification = row.get("classification")
        if classification in counts:
            counts[classification] += 1

    all_rows_verified = bool(rows and len(verified) == len(rows))
    unique_events = bool(len(keys) == len(verified) == len(distinct_keys))
    enough = len(verified) >= minimum_verified_events

    price_only_verified = bool(enough and all_rows_verified and unique_events)
    no_complete_counterexample = bool(
        counts[DEPARTURE] == 0
        and counts[NEITHER] == 0
        and counts[ALREADY] == 0
    )
    reconciliation_mode = bool(
        price_only_verified
        and counts[ADOPTION] == len(verified)
        and no_complete_counterexample
    )

    distinct_pools = {
        row.get("pool_address")
        for row in verified
        if row.get("pool_address")
    }

    return {
        "service": "x1_ninja_price_only_reserve_ratio_reconciliation",
        "version": VERSION,
        "chain": "x1",
        "status": (
            "verified"
            if reconciliation_mode
            else ("partial" if rows else "unavailable")
        ),
        "event_count": len(rows),
        "verified_price_only_event_count": len(verified),
        "minimum_verified_event_count": minimum_verified_events,
        "distinct_event_count": len(distinct_keys),
        "distinct_pool_count": len(distinct_pools),
        "classification_counts": counts,
        "price_only_update_verified": price_only_verified,
        "gross_reserve_ratio_adoption_verified": reconciliation_mode,
        "gross_reserve_ratio_departure_observed": counts[DEPARTURE] > 0,
        "non_reserve_price_only_update_observed": counts[NEITHER] > 0,
        "already_at_gross_reserve_ratio_observed": counts[ALREADY] > 0,
        "no_complete_counterexample": no_complete_counterexample,
        "reconciliation_mode_verified": reconciliation_mode,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "universal_catalog_price_semantics_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "events": rows,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "ADOPTION",
    "ALREADY",
    "DEPARTURE",
    "NEITHER",
    "VERSION",
    "aggregate_price_only_reserve_ratio_events",
    "verify_price_only_reserve_ratio_event",
]
