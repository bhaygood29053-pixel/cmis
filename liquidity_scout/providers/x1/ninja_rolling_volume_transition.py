"""Exact X1.Ninja rolling-volume transition semantics for CMIS #504.

This contract compares two retained provider snapshots around one exact XDEX
swap.  It can prove the arithmetic relationship between the provider's rolling
aggregate delta and the post-update pool USD price.  It deliberately does not
treat the provider price as an independent valuation source and does not infer
the provider's internal storage/query implementation.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any


CONTRACT = "x1_ninja_rolling_volume_transition/v1"
DEFAULT_RELATIVE_TOLERANCE = Decimal("1e-12")
DEFAULT_ABSOLUTE_TOLERANCE_USD = Decimal("1e-12")


class X1NinjaRollingVolumeTransitionError(ValueError):
    pass


def _decimal(value: Any, *, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise X1NinjaRollingVolumeTransitionError(f"{name} must be numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise X1NinjaRollingVolumeTransitionError(
            f"{name} must be numeric"
        ) from exc
    if not parsed.is_finite():
        raise X1NinjaRollingVolumeTransitionError(f"{name} must be finite")
    return parsed


def _nonnegative(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name)
    if parsed < 0:
        raise X1NinjaRollingVolumeTransitionError(
            f"{name} must be non-negative"
        )
    return parsed


def _nonnegative_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool):
        raise X1NinjaRollingVolumeTransitionError(
            f"{name} must be an integer"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise X1NinjaRollingVolumeTransitionError(
            f"{name} must be an integer"
        ) from exc
    if parsed < 0 or Decimal(str(value)) != Decimal(parsed):
        raise X1NinjaRollingVolumeTransitionError(
            f"{name} must be a non-negative integer"
        )
    return parsed


def evaluate_x1_ninja_rolling_volume_transition(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    new_swap: Mapping[str, Any],
    relative_tolerance: Any = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance_usd: Any = DEFAULT_ABSOLUTE_TOLERANCE_USD,
) -> dict[str, Any]:
    """Evaluate one exact 1->2 style rolling-volume transition."""

    if not all(isinstance(value, Mapping) for value in (before, after, new_swap)):
        raise TypeError("before, after, and new_swap must be mappings")

    before_volume = _nonnegative(before.get("volume24h"), name="before volume24h")
    after_volume = _nonnegative(after.get("volume24h"), name="after volume24h")
    before_txns = _nonnegative_int(before.get("transactions24h"), name="before txns")
    after_txns = _nonnegative_int(after.get("transactions24h"), name="after txns")
    asset_amount = _nonnegative(new_swap.get("asset_amount"), name="asset amount")
    quote_amount = _nonnegative(new_swap.get("quote_amount"), name="quote amount")
    post_price_usd = _nonnegative(after.get("priceUsd"), name="after priceUsd")
    price_native = _nonnegative(new_swap.get("price_native"), name="price native")
    rel = _nonnegative(relative_tolerance, name="relative tolerance")
    abs_usd = _nonnegative(
        absolute_tolerance_usd, name="absolute tolerance USD"
    )

    if asset_amount <= 0 or quote_amount <= 0 or post_price_usd <= 0 or price_native <= 0:
        raise X1NinjaRollingVolumeTransitionError(
            "swap amounts and prices must be positive"
        )
    if after_volume < before_volume:
        raise X1NinjaRollingVolumeTransitionError(
            "after volume24h must not be below before volume24h"
        )

    volume_delta = after_volume - before_volume
    provider_candidate = asset_amount * post_price_usd
    error = abs(volume_delta - provider_candidate)
    allowed = max(abs_usd, abs(provider_candidate) * rel)
    matches_post_update_price = error <= allowed

    transaction_count_delta = after_txns - before_txns
    one_new_transaction = transaction_count_delta == 1

    implied_asset_usd = volume_delta / asset_amount
    implied_xnt_usd = volume_delta / (asset_amount * price_native)

    return {
        "contract": CONTRACT,
        "before_volume24h": format(before_volume, "f"),
        "after_volume24h": format(after_volume, "f"),
        "volume24h_delta_usd": format(volume_delta, "f"),
        "before_transactions24h": before_txns,
        "after_transactions24h": after_txns,
        "transactions24h_delta": transaction_count_delta,
        "one_new_provider_transaction_observed": one_new_transaction,
        "new_swap_signature": str(new_swap.get("signature") or "").strip() or None,
        "new_swap_slot": new_swap.get("slot"),
        "new_swap_block_time": new_swap.get("block_time"),
        "new_swap_asset_amount": format(asset_amount, "f"),
        "new_swap_quote_amount": format(quote_amount, "f"),
        "new_swap_price_native": format(price_native, "f"),
        "after_pool_price_usd": format(post_price_usd, "f"),
        "asset_amount_times_after_price_usd": format(provider_candidate, "f"),
        "absolute_error_usd": format(error, "f"),
        "allowed_error_usd": format(allowed, "f"),
        "volume_delta_matches_asset_amount_times_after_price_usd": (
            matches_post_update_price
        ),
        "implied_stored_asset_usd_price": format(implied_asset_usd, "f"),
        "implied_stored_xnt_usd_price": format(implied_xnt_usd, "f"),
        "rolling_volume_transition_observed": bool(
            one_new_transaction and volume_delta > 0
        ),
        "post_update_pool_usd_price_relationship_verified": bool(
            one_new_transaction and matches_post_update_price
        ),
        "provider_price_used_as_independent_valuation": False,
        "provider_internal_formula_verified": False,
        "provider_fact_time_verified": False,
        "independent_usd_valuation_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT",
    "DEFAULT_ABSOLUTE_TOLERANCE_USD",
    "DEFAULT_RELATIVE_TOLERANCE",
    "X1NinjaRollingVolumeTransitionError",
    "evaluate_x1_ninja_rolling_volume_transition",
]
