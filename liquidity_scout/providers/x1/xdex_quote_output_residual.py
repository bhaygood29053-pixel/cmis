"""Deterministic residual observation for XDEX read-only quote outputs.

This module does not explain a residual. It only measures the difference between an
observed provider output and an independently supplied reference output. Transfer
fees, rounding, curve rules, slippage, fill quality, and execution quality remain
unverified unless separate evidence proves them.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

SCHEMA = "xdex_quote_output_residual.v1"


@dataclass(frozen=True)
class XDEXQuoteOutputResidual:
    schema: str
    observed_output_amount: Decimal
    reference_output_amount: Decimal
    residual_amount: Decimal
    residual_ratio: Decimal | None
    exact_match: bool
    residual_present: bool
    residual_cause_verified: bool
    transfer_fee_semantics_verified: bool
    rounding_semantics_verified: bool
    curve_semantics_verified: bool
    slippage_semantics_verified: bool
    fill_quality_verified: bool
    execution_quality_verified: bool
    cmis_promotable: bool


def _amount(value: Any, *, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must not be boolean")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise ValueError(f"{field} must be finite non-negative numeric") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{field} must be finite non-negative numeric")
    return parsed


def observe_xdex_quote_output_residual(
    *,
    observed_output_amount: Any,
    independently_derived_reference_output_amount: Any,
) -> XDEXQuoteOutputResidual:
    """Measure, but never explain, an output residual.

    ``reference_output_amount`` is intentionally described as independently derived:
    this function does not decide whether the caller's model is correct. The result is
    therefore an observation boundary, not semantic verification of either amount.
    """

    observed = _amount(observed_output_amount, field="observed_output_amount")
    reference = _amount(
        independently_derived_reference_output_amount,
        field="independently_derived_reference_output_amount",
    )
    residual = observed - reference
    ratio = None if reference == 0 else residual / reference
    exact = residual == 0

    return XDEXQuoteOutputResidual(
        schema=SCHEMA,
        observed_output_amount=observed,
        reference_output_amount=reference,
        residual_amount=residual,
        residual_ratio=ratio,
        exact_match=exact,
        residual_present=not exact,
        residual_cause_verified=False,
        transfer_fee_semantics_verified=False,
        rounding_semantics_verified=False,
        curve_semantics_verified=False,
        slippage_semantics_verified=False,
        fill_quality_verified=False,
        execution_quality_verified=False,
        cmis_promotable=False,
    )


__all__ = ["SCHEMA", "XDEXQuoteOutputResidual", "observe_xdex_quote_output_residual"]
