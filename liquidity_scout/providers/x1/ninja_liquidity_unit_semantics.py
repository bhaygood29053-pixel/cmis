"""Explicit X1.Ninja liquidity unit semantics for CMIS #515.

This contract separates two values that earlier evidence had partially conflated:

1. the provider's own USD-labelled liquidity basis, which is numerically tied to
   XNT/USDC.X reference pricing; and
2. an independently valued current USD amount, which additionally applies an
   externally qualified current USDC/USD value.

The contract is deterministic and read-only. It does not establish provider
fact time, source independence, global XDEX completeness, or execution
authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any


VERSION = "x1_ninja_liquidity_unit_semantics/v1"
DEFAULT_RELATIVE_TOLERANCE = Decimal("1e-4")
DEFAULT_ABSOLUTE_TOLERANCE = Decimal("0.01")
DEFAULT_REFERENCE_RELATIVE_TOLERANCE = Decimal("1e-6")


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


def _nonnegative(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name)
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def _comparison(
    observed: Decimal,
    expected: Decimal,
    *,
    relative_tolerance: Decimal,
    absolute_tolerance: Decimal,
) -> dict[str, Any]:
    error = abs(observed - expected)
    allowed = max(absolute_tolerance, abs(expected) * relative_tolerance)
    relative = (
        error / abs(expected)
        if expected != 0
        else (Decimal(0) if error == 0 else None)
    )
    return {
        "observed": format(observed, "f"),
        "expected": format(expected, "f"),
        "absolute_error": format(error, "f"),
        "relative_error": format(relative, "e") if relative is not None else None,
        "allowed_absolute_error": format(allowed, "f"),
        "within_tolerance": error <= allowed,
    }


def evaluate_x1_ninja_liquidity_unit_semantics(
    *,
    provider_liquidity: Any,
    provider_xnt_price_usd: Any,
    rpc_xnt_reserve: Any,
    rpc_asset_reserve: Any,
    reference_usdcx_per_xnt: Any,
    source_usdc_usd_price: Any,
    exact_pool_identity_verified: bool,
    wrapped_xnt_position_verified: bool,
    reference_pool_identity_verified: bool,
    current_usdcx_usd_equivalence_verified: bool,
    relative_tolerance: Any = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance: Any = DEFAULT_ABSOLUTE_TOLERANCE,
    reference_relative_tolerance: Any = DEFAULT_REFERENCE_RELATIVE_TOLERANCE,
) -> dict[str, Any]:
    """Separate provider nominal liquidity from independently valued USD."""

    rel = _nonnegative(relative_tolerance, name="relative_tolerance")
    abs_tol = _nonnegative(absolute_tolerance, name="absolute_tolerance")
    ref_rel = _nonnegative(
        reference_relative_tolerance,
        name="reference_relative_tolerance",
    )

    provider_value = _positive(provider_liquidity, name="provider_liquidity")
    provider_xnt_basis = _positive(
        provider_xnt_price_usd,
        name="provider_xnt_price_usd",
    )
    xnt_reserve = _positive(rpc_xnt_reserve, name="rpc_xnt_reserve")
    asset_reserve = _positive(rpc_asset_reserve, name="rpc_asset_reserve")
    reference_ratio = _positive(
        reference_usdcx_per_xnt,
        name="reference_usdcx_per_xnt",
    )
    usdc_usd = _positive(source_usdc_usd_price, name="source_usdc_usd_price")

    identity_verified = bool(
        exact_pool_identity_verified is True
        and wrapped_xnt_position_verified is True
        and reference_pool_identity_verified is True
    )

    native_per_asset = xnt_reserve / asset_reserve

    # Provider basis. The provider names this input xntPriceUsd, but accepted
    # live evidence established that its numerical value tracks the exact
    # XNT/USDC.X reference reserve ratio.
    provider_asset_nominal = native_per_asset * provider_xnt_basis
    provider_nominal_liquidity = (
        asset_reserve * provider_asset_nominal
        + xnt_reserve * provider_xnt_basis
    )
    provider_liquidity_comparison = _comparison(
        provider_value,
        provider_nominal_liquidity,
        relative_tolerance=rel,
        absolute_tolerance=abs_tol,
    )

    reference_comparison = _comparison(
        provider_xnt_basis,
        reference_ratio,
        relative_tolerance=ref_rel,
        absolute_tolerance=Decimal(0),
    )

    provider_nominal_semantics_verified = bool(
        identity_verified
        and reference_comparison["within_tolerance"] is True
        and provider_liquidity_comparison["within_tolerance"] is True
    )

    # Independent current USD basis. This is distinct from the provider's
    # nominal quote basis whenever USDC/USD != 1.
    independent_xnt_usd = reference_ratio * usdc_usd
    independent_asset_usd = native_per_asset * independent_xnt_usd
    independent_liquidity_usd = (
        asset_reserve * independent_asset_usd
        + xnt_reserve * independent_xnt_usd
    )
    provider_vs_independent = _comparison(
        provider_value,
        independent_liquidity_usd,
        relative_tolerance=rel,
        absolute_tolerance=abs_tol,
    )

    independent_usd_valuation_verified = bool(
        identity_verified
        and current_usdcx_usd_equivalence_verified is True
    )

    return {
        "contract_version": VERSION,
        "chain": "x1",
        "status": (
            "verified"
            if provider_nominal_semantics_verified
            and independent_usd_valuation_verified
            else "partial"
        ),
        "provider_field_name": "liquidity",
        "provider_field_label": "USD",
        "provider_numerical_unit": "USDC.X_nominal_quote_basis",
        "provider_nominal_basis": {
            "provider_xnt_price_usd": format(provider_xnt_basis, "f"),
            "reference_usdcx_per_xnt": format(reference_ratio, "f"),
            "provider_reference_basis_matches_rpc": (
                reference_comparison["within_tolerance"] is True
            ),
            "reference_comparison": reference_comparison,
            "provider_nominal_asset_unit_value": format(
                provider_asset_nominal,
                "f",
            ),
            "derived_provider_nominal_liquidity": format(
                provider_nominal_liquidity,
                "f",
            ),
            "provider_liquidity_comparison": provider_liquidity_comparison,
            "provider_nominal_liquidity_semantics_verified": (
                provider_nominal_semantics_verified
            ),
            "independently_verified_external_usd": False,
        },
        "independent_current_usd": {
            "source_usdc_usd_price": format(usdc_usd, "f"),
            "current_usdcx_usd_equivalence_verified": (
                current_usdcx_usd_equivalence_verified is True
            ),
            "independent_xnt_usd": format(independent_xnt_usd, "f"),
            "independent_asset_usd": format(independent_asset_usd, "f"),
            "independent_liquidity_usd": format(
                independent_liquidity_usd,
                "f",
            ),
            "independent_usd_valuation_verified": (
                independent_usd_valuation_verified
            ),
            "provider_vs_independent_usd": provider_vs_independent,
        },
        "exact_pool_identity_verified": exact_pool_identity_verified is True,
        "wrapped_xnt_position_verified": wrapped_xnt_position_verified is True,
        "reference_pool_identity_verified": reference_pool_identity_verified is True,
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "stable_name_implies_one_usd": False,
        "provider_price_reused_as_independent_usd_proof": False,
        "execution_authorized": False,
    }


__all__ = [
    "DEFAULT_ABSOLUTE_TOLERANCE",
    "DEFAULT_REFERENCE_RELATIVE_TOLERANCE",
    "DEFAULT_RELATIVE_TOLERANCE",
    "VERSION",
    "evaluate_x1_ninja_liquidity_unit_semantics",
]
