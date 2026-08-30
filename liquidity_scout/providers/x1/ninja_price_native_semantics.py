"""Verify X1.Ninja priceNative semantics from exact RPC reserve ratios.

This gate builds on the accepted X1.Ninja pooled-reserve proof from CMIS #341.
For each verified pool, it computes both possible pair-price ratios from exact
RPC-scaled reserves:

    quote_per_base = vault_0 / vault_1
    base_per_quote = vault_1 / vault_0

The provider field priceNative is accepted only when exactly one ratio matches
within an explicit Decimal tolerance and the same direction holds across at
least five verified pools.

This proves the provider field's pair-price construction and direction for the
tested XDEX pool family. It does not verify priceUsd, freshness/fact-time, USD
liquidity, XDEX TVL, volume, market cap/FDV, source independence, public service
promotion, or execution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from liquidity_scout.providers.x1.ninja_pooled_reserve_semantics import (
    DIRECT_MAPPING,
    verify_ninja_pooled_reserve_semantics,
)


VERSION = "1.0"
DEFAULT_RELATIVE_TOLERANCE = Decimal("5e-9")
DEFAULT_ABSOLUTE_TOLERANCE = Decimal("5e-12")

QUOTE_PER_BASE = "priceNative_equals_pooledQuote_div_pooledBase"
BASE_PER_QUOTE = "priceNative_equals_pooledBase_div_pooledQuote"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _pool_address(row: Mapping[str, Any]) -> str | None:
    return _text(
        row.get("address")
        or row.get("poolAddress")
        or row.get("pool_address")
        or row.get("id")
    )


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


def _positive_decimal(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _nonnegative_decimal(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name)
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def _compare(
    observed: Decimal,
    expected: Decimal,
    *,
    relative_tolerance: Decimal,
    absolute_tolerance: Decimal,
) -> dict[str, Any]:
    absolute_error = abs(observed - expected)
    scale = abs(expected)
    relative_error = (
        absolute_error / scale
        if scale != 0
        else (Decimal(0) if absolute_error == 0 else None)
    )
    allowed_error = max(
        absolute_tolerance,
        scale * relative_tolerance,
    )
    return {
        "observed": format(observed, "f"),
        "expected": format(expected, "f"),
        "absolute_error": format(absolute_error, "f"),
        "relative_error": (
            format(relative_error, "e") if relative_error is not None else None
        ),
        "allowed_absolute_error": format(allowed_error, "f"),
        "within_tolerance": absolute_error <= allowed_error,
    }


def _price_native_index(
    ninja_pools: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in ninja_pools:
        if not isinstance(row, Mapping):
            continue
        address = _pool_address(row)
        if not address or address in result:
            continue
        if "priceNative" in row:
            result[address] = row.get("priceNative")
    return result


def verify_ninja_price_native_semantics(
    *,
    ninja_pools: Sequence[Mapping[str, Any]],
    xdex_pools: Sequence[Mapping[str, Any]],
    min_verified_pools: int = 5,
    max_samples: int = 5,
    relative_tolerance: Any = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance: Any = DEFAULT_ABSOLUTE_TOLERANCE,
    pooled_reserve_provider: Callable[..., Mapping[str, Any]] = (
        verify_ninja_pooled_reserve_semantics
    ),
    rpc_url: str | None = None,
    signature_limit: int = 1,
) -> dict[str, Any]:
    """Verify priceNative against both exact reserve-ratio directions."""

    if isinstance(min_verified_pools, bool) or not isinstance(min_verified_pools, int):
        raise ValueError("min_verified_pools must be an integer")
    if min_verified_pools < 5:
        raise ValueError("min_verified_pools must be at least 5")
    if isinstance(max_samples, bool) or not isinstance(max_samples, int):
        raise ValueError("max_samples must be an integer")
    if max_samples < min_verified_pools:
        raise ValueError("max_samples must be >= min_verified_pools")

    relative = _nonnegative_decimal(
        relative_tolerance,
        name="relative_tolerance",
    )
    absolute = _nonnegative_decimal(
        absolute_tolerance,
        name="absolute_tolerance",
    )
    if relative == 0 and absolute == 0:
        raise ValueError("at least one comparison tolerance must be positive")

    kwargs: dict[str, Any] = {
        "ninja_pools": ninja_pools,
        "xdex_pools": xdex_pools,
        "min_verified_pools": min_verified_pools,
        "max_samples": max_samples,
        "signature_limit": signature_limit,
    }
    if rpc_url is not None:
        kwargs["rpc_url"] = rpc_url

    try:
        raw = pooled_reserve_provider(**kwargs)
        upstream = dict(raw) if isinstance(raw, Mapping) else {}
    except Exception as exc:
        return {
            "service": "x1_ninja_price_native_semantics",
            "version": VERSION,
            "chain": "x1",
            "status": "unavailable",
            "price_native_semantics_verified": False,
            "stable_direction": None,
            "samples": [],
            "errors": [
                {
                    "stage": "pooled_reserve_provider",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            ],
            "cmis_promotable": False,
            "execution_authorized": False,
        }

    upstream_verified = bool(
        upstream.get("status") == "verified"
        and upstream.get("pooled_reserve_semantics_verified") is True
        and upstream.get("stable_mapping") == DIRECT_MAPPING
    )

    raw_samples = upstream.get("samples")
    raw_samples = (
        list(raw_samples)
        if isinstance(raw_samples, Sequence)
        and not isinstance(raw_samples, (str, bytes))
        else []
    )
    prices = _price_native_index(ninja_pools)

    samples: list[dict[str, Any]] = []
    for raw_sample in raw_samples:
        if not isinstance(raw_sample, Mapping):
            continue

        address = _text(raw_sample.get("pool_address"))
        rejection_reasons: list[str] = []

        if raw_sample.get("mapping_verified") is not True:
            rejection_reasons.append("pooled_reserve_sample_unverified")

        try:
            pooled_base = _positive_decimal(
                raw_sample.get("rpc_vault_1_reserve"),
                name="rpc_vault_1_reserve",
            )
            pooled_quote = _positive_decimal(
                raw_sample.get("rpc_vault_0_reserve"),
                name="rpc_vault_0_reserve",
            )
            provider_price = _positive_decimal(
                prices.get(address),
                name="priceNative",
            )

            quote_per_base = pooled_quote / pooled_base
            base_per_quote = pooled_base / pooled_quote

            qpb = _compare(
                provider_price,
                quote_per_base,
                relative_tolerance=relative,
                absolute_tolerance=absolute,
            )
            bpq = _compare(
                provider_price,
                base_per_quote,
                relative_tolerance=relative,
                absolute_tolerance=absolute,
            )

            matches = []
            if qpb["within_tolerance"]:
                matches.append(QUOTE_PER_BASE)
            if bpq["within_tolerance"]:
                matches.append(BASE_PER_QUOTE)

            if len(matches) != 1:
                rejection_reasons.append(
                    "price_native_ratio_direction_ambiguous"
                    if len(matches) > 1
                    else "price_native_does_not_match_verified_reserve_ratio"
                )

            samples.append(
                {
                    "pool_address": address,
                    "rpc_pooledBase_reserve": format(pooled_base, "f"),
                    "rpc_pooledQuote_reserve": format(pooled_quote, "f"),
                    "provider_priceNative": format(provider_price, "f"),
                    "candidate_ratios": {
                        QUOTE_PER_BASE: {
                            "ratio": format(quote_per_base, "f"),
                            "comparison": qpb,
                        },
                        BASE_PER_QUOTE: {
                            "ratio": format(base_per_quote, "f"),
                            "comparison": bpq,
                        },
                    },
                    "matching_direction_count": len(matches),
                    "unique_matching_direction": (
                        matches[0] if len(matches) == 1 else None
                    ),
                    "price_native_sample_verified": (
                        not rejection_reasons and len(matches) == 1
                    ),
                    "rejection_reasons": rejection_reasons,
                }
            )
        except Exception as exc:
            rejection_reasons.append(f"{type(exc).__name__}: {exc}")
            samples.append(
                {
                    "pool_address": address,
                    "price_native_sample_verified": False,
                    "unique_matching_direction": None,
                    "rejection_reasons": rejection_reasons,
                }
            )

    verified_samples = [
        row for row in samples
        if row.get("price_native_sample_verified") is True
    ]
    directions = {
        row.get("unique_matching_direction")
        for row in verified_samples
        if row.get("unique_matching_direction")
    }

    stable = bool(
        upstream_verified
        and len(verified_samples) >= min_verified_pools
        and len(verified_samples) == len(samples)
        and len(directions) == 1
    )
    stable_direction = next(iter(directions)) if stable else None

    status = "verified" if stable else ("partial" if samples else "unavailable")

    return {
        "service": "x1_ninja_price_native_semantics",
        "version": VERSION,
        "chain": "x1",
        "status": status,
        "upstream_pooled_reserve_semantics_verified": upstream_verified,
        "sample_count": len(samples),
        "verified_sample_count": len(verified_samples),
        "minimum_verified_pool_count": min_verified_pools,
        "stable_direction": stable_direction,
        "price_native_pair_direction_verified": stable,
        "price_native_reserve_ratio_verified": stable,
        "price_native_semantics_verified": stable,
        "price_native_unit_verified": stable,
        "price_native_is_usd_verified": False,
        "comparison_policy": {
            "arithmetic": "Decimal(str(value))",
            "relative_tolerance": format(relative, "e"),
            "absolute_tolerance_price_units": format(absolute, "e"),
            "rule": (
                "absolute_error <= max(absolute_tolerance, "
                "abs(verified_ratio) * relative_tolerance)"
            ),
            "purpose": (
                "Permit only parts-per-billion-scale provider decimal "
                "serialization differences; meaningful price disagreement "
                "fails closed."
            ),
        },
        "samples": samples,
        "semantics": {
            "price_usd_semantics_verified": False,
            "provider_fact_time_verified": False,
            "freshness_verified": False,
            "x1_ninja_liquidity_semantics_verified": False,
            "xdex_tvl_semantics_verified": False,
            "volume_semantics_verified": False,
            "market_cap_semantics_verified": False,
            "source_independence_verified": False,
        },
        "cmis_promotable": False,
        "execution_authorized": False,
        "errors": [],
    }


__all__ = [
    "BASE_PER_QUOTE",
    "DEFAULT_ABSOLUTE_TOLERANCE",
    "DEFAULT_RELATIVE_TOLERANCE",
    "QUOTE_PER_BASE",
    "VERSION",
    "verify_ninja_price_native_semantics",
]
