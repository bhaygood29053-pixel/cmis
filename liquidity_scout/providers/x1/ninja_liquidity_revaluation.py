"""Verify bounded X1.Ninja price-only liquidity revaluation events.

This contract is intentionally narrower than USD-liquidity semantics. It accepts
only an observed provider liquidity transition where the provider's exact pooled
reserves remain unchanged and the new liquidity value is reproduced by:

    2 * wrapped-XNT reserve * revaluation reference price

The reference price may be a provider-internal diagnostic input unless a
separate caller proves its independent USD semantics and same-time fact scope.
Therefore this verifier never promotes USD semantics, freshness, source
independence, or execution authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

VERSION = "x1_ninja_liquidity_revaluation/v1"
DEFAULT_RELATIVE_TOLERANCE = Decimal("1e-10")
DEFAULT_ABSOLUTE_TOLERANCE = Decimal("1e-9")


def _decimal(value: Any, *, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be a finite number")
    return parsed


def _positive(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _compare(observed: Decimal, expected: Decimal, *, rel: Decimal, abs_: Decimal):
    error = abs(observed - expected)
    allowed = max(abs_, abs(expected) * rel)
    return {
        "observed": format(observed, "f"),
        "expected": format(expected, "f"),
        "absolute_error": format(error, "f"),
        "allowed_absolute_error": format(allowed, "f"),
        "relative_error": format(error / abs(expected), "e") if expected else None,
        "within_tolerance": error <= allowed,
    }


def verify_price_only_liquidity_revaluation(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    wrapped_xnt_provider_field: str,
    reference_price_field: str = "xntPriceUsd",
    intervening_pool_signature_count: int,
    relative_tolerance: Any = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance: Any = DEFAULT_ABSOLUTE_TOLERANCE,
) -> dict[str, Any]:
    """Verify one provider-internal price-only liquidity revaluation event."""

    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise ValueError("before and after must be mappings")
    if wrapped_xnt_provider_field not in {"pooledBase", "pooledQuote"}:
        raise ValueError("wrapped_xnt_provider_field must be pooledBase or pooledQuote")
    if isinstance(intervening_pool_signature_count, bool) or not isinstance(
        intervening_pool_signature_count, int
    ):
        raise ValueError("intervening_pool_signature_count must be an integer")
    if intervening_pool_signature_count < 0:
        raise ValueError("intervening_pool_signature_count must be non-negative")

    rel = _decimal(relative_tolerance, name="relative_tolerance")
    abs_ = _decimal(absolute_tolerance, name="absolute_tolerance")
    if rel < 0 or abs_ < 0 or (rel == 0 and abs_ == 0):
        raise ValueError("comparison tolerance must be non-negative and non-zero")

    before_liquidity = _positive(before.get("liquidity"), name="before liquidity")
    after_liquidity = _positive(after.get("liquidity"), name="after liquidity")
    before_base = _positive(before.get("pooledBase"), name="before pooledBase")
    after_base = _positive(after.get("pooledBase"), name="after pooledBase")
    before_quote = _positive(before.get("pooledQuote"), name="before pooledQuote")
    after_quote = _positive(after.get("pooledQuote"), name="after pooledQuote")
    after_reference = _positive(
        after.get(reference_price_field),
        name=f"after {reference_price_field}",
    )

    before_xnt = before_base if wrapped_xnt_provider_field == "pooledBase" else before_quote
    after_xnt = after_base if wrapped_xnt_provider_field == "pooledBase" else after_quote

    expected_after = Decimal(2) * after_xnt * after_reference
    comparison = _compare(after_liquidity, expected_after, rel=rel, abs_=abs_)

    reserves_unchanged = before_base == after_base and before_quote == after_quote
    liquidity_changed = before_liquidity != after_liquidity
    xnt_reserve_unchanged = before_xnt == after_xnt
    zero_intervening = intervening_pool_signature_count == 0

    verified = bool(
        reserves_unchanged
        and xnt_reserve_unchanged
        and liquidity_changed
        and zero_intervening
        and comparison["within_tolerance"] is True
    )

    reasons = []
    if not liquidity_changed:
        reasons.append("liquidity_did_not_change")
    if not reserves_unchanged:
        reasons.append("provider_reserves_changed")
    if not zero_intervening:
        reasons.append("intervening_pool_transactions_present")
    if comparison["within_tolerance"] is not True:
        reasons.append("new_liquidity_not_reproduced_by_revaluation_formula")

    return {
        "service": "x1_ninja_liquidity_revaluation",
        "version": VERSION,
        "chain": "x1",
        "status": "verified" if verified else "unavailable",
        "wrapped_xnt_provider_field": wrapped_xnt_provider_field,
        "reference_price_field": reference_price_field,
        "before_liquidity": format(before_liquidity, "f"),
        "after_liquidity": format(after_liquidity, "f"),
        "before_xnt_reserve": format(before_xnt, "f"),
        "after_xnt_reserve": format(after_xnt, "f"),
        "after_reference_price": format(after_reference, "f"),
        "expected_after_liquidity": format(expected_after, "f"),
        "comparison": comparison,
        "provider_reserves_unchanged": reserves_unchanged,
        "intervening_pool_signature_count": intervening_pool_signature_count,
        "zero_intervening_pool_transactions": zero_intervening,
        "price_only_liquidity_revaluation_verified": verified,
        "provider_internal_liquidity_formula_supported": verified,
        "provider_fact_time_verified": False,
        "reference_price_usd_semantics_verified": False,
        "liquidity_usd_semantics_verified": False,
        "liquidity_freshness_verified": False,
        "source_independence_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
        "rejection_reasons": reasons,
    }


__all__ = [
    "DEFAULT_ABSOLUTE_TOLERANCE",
    "DEFAULT_RELATIVE_TOLERANCE",
    "VERSION",
    "verify_price_only_liquidity_revaluation",
]
