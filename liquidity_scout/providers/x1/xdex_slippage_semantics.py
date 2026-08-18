"""Deterministic XDEX quote-side slippage semantics.

This module classifies already-observed quote values. It performs no network I/O and
must not be used to infer transaction-construction or execution semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Any


@dataclass(frozen=True)
class XdexSlippageSemanticResult:
    schema: str
    slippage_percent: Decimal
    slippage_bps: Decimal
    zero_slippage_output_raw: int
    observed_output_raw: int
    expected_output_raw: int
    output_transform_verified: bool
    price_impact_independent_of_slippage_verified: bool
    default_slippage_verified: bool
    quote_to_onchain_minimum_out_binding_verified: bool
    fill_quality_verified: bool
    execution_quality_verified: bool
    cmis_promotable: bool


def _decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric, not boolean")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def _raw_amount(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer raw-token amount")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def classify_xdex_slippage_semantics(
    *,
    zero_slippage_output_raw: int,
    observed_output_raw: int,
    slippage_percent: Any,
    price_impact_without_slippage: Any | None = None,
    price_impact_with_slippage: Any | None = None,
    omitted_slippage_output_raw: int | None = None,
    explicit_default_output_raw: int | None = None,
) -> XdexSlippageSemanticResult:
    """Classify only the deterministic quote-side semantics already proven.

    ``slippage_percent`` is interpreted as the verified XDEX quote request unit:
    percent, not a fraction. The expected raw output is::

        floor(zero_slippage_output_raw * (1 - slippage_percent / 100))

    The helper intentionally does not promote the stronger historical/program-family
    evidence about transaction-specific ``minimum_amount_out`` into a quote→prepare
    binding. That server-side mapping remains unavailable.
    """

    zero_raw = _raw_amount(zero_slippage_output_raw, "zero_slippage_output_raw")
    observed_raw = _raw_amount(observed_output_raw, "observed_output_raw")
    slippage = _decimal(slippage_percent, "slippage_percent")
    if slippage < 0 or slippage >= 100:
        raise ValueError("slippage_percent must be >= 0 and < 100")

    expected = int(
        (Decimal(zero_raw) * (Decimal(1) - slippage / Decimal(100))).to_integral_value(
            rounding=ROUND_FLOOR
        )
    )

    impact_independent = False
    if price_impact_without_slippage is not None or price_impact_with_slippage is not None:
        if price_impact_without_slippage is None or price_impact_with_slippage is None:
            raise ValueError("both price-impact observations are required")
        impact_independent = _decimal(
            price_impact_without_slippage, "price_impact_without_slippage"
        ) == _decimal(price_impact_with_slippage, "price_impact_with_slippage")

    default_verified = False
    if omitted_slippage_output_raw is not None or explicit_default_output_raw is not None:
        if omitted_slippage_output_raw is None or explicit_default_output_raw is None:
            raise ValueError("both default-slippage output observations are required")
        default_verified = _raw_amount(
            omitted_slippage_output_raw, "omitted_slippage_output_raw"
        ) == _raw_amount(explicit_default_output_raw, "explicit_default_output_raw")

    return XdexSlippageSemanticResult(
        schema="xdex_quote_slippage_semantics.v1",
        slippage_percent=slippage,
        slippage_bps=slippage * Decimal(100),
        zero_slippage_output_raw=zero_raw,
        observed_output_raw=observed_raw,
        expected_output_raw=expected,
        output_transform_verified=observed_raw == expected,
        price_impact_independent_of_slippage_verified=impact_independent,
        default_slippage_verified=default_verified,
        quote_to_onchain_minimum_out_binding_verified=False,
        fill_quality_verified=False,
        execution_quality_verified=False,
        cmis_promotable=False,
    )
