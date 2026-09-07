"""Deterministic yield provenance for CMIS.

This contract separates organic pool-fee return from externally subsidized
incentives. Missing incentive evidence never becomes zero, and annualized
figures are simple trailing-window extrapolations rather than promises.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

CONTRACT_VERSION = "yield_provenance/v1"
SECONDS_PER_YEAR = Decimal("31536000")
DEFAULT_EXECUTION_AUTHORIZED = False


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _decimal(
    value: Any,
    field: str,
    *,
    nonnegative: bool = True,
    positive: bool = False,
) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field} must be finite")
    if positive and parsed <= 0:
        raise ValueError(f"{field} must be positive")
    if nonnegative and parsed < 0:
        raise ValueError(f"{field} must be non-negative")
    return parsed


def _strict_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be boolean")
    return value


def _fmt(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _annualize(window_return: Decimal, duration_seconds: Decimal) -> Decimal:
    return window_return * (SECONDS_PER_YEAR / duration_seconds)


def build_yield_provenance(
    *,
    chain: Any,
    pool_id: Any,
    window_start: Any,
    window_end: Any,
    value_unit: Any,
    average_liquidity_value: Any,
    liquidity_value_verified: Any,
    base_fee_value: Any,
    base_fee_value_verified: Any,
    base_fee_evidence_id: Any,
    incentive_value: Any = None,
    incentive_value_verified: Any = False,
    incentive_source: Any = None,
    incentive_evidence_id: Any = None,
    reported_apy_percent: Any = None,
    reported_apy_source: Any = None,
) -> dict[str, Any]:
    """Build trailing-window yield provenance with explicit subsidy separation."""

    chain_name = _required_text(chain, "chain").casefold()
    pool = _required_text(pool_id, "pool_id")
    unit = _required_text(value_unit, "value_unit")

    start = _decimal(window_start, "window_start")
    end = _decimal(window_end, "window_end")
    if end <= start:
        raise ValueError("window_end must be greater than window_start")
    duration = end - start

    liquidity = _decimal(
        average_liquidity_value,
        "average_liquidity_value",
        positive=True,
    )
    if _strict_bool(
        liquidity_value_verified,
        "liquidity_value_verified",
    ) is not True:
        raise ValueError("liquidity_value_verified must be true")

    base_fee = _decimal(base_fee_value, "base_fee_value")
    if _strict_bool(
        base_fee_value_verified,
        "base_fee_value_verified",
    ) is not True:
        raise ValueError("base_fee_value_verified must be true")
    base_evidence = _required_text(base_fee_evidence_id, "base_fee_evidence_id")

    incentive_verified = _strict_bool(
        incentive_value_verified,
        "incentive_value_verified",
    )
    incentive: Decimal | None = None
    incentive_source_text: str | None = None
    incentive_evidence: str | None = None

    if incentive_value is None:
        if incentive_verified:
            raise ValueError(
                "incentive_value is required when incentive_value_verified is true"
            )
        if incentive_source is not None or incentive_evidence_id is not None:
            raise ValueError(
                "unverified incentive must not carry source/evidence as verified value"
            )
    else:
        if not incentive_verified:
            raise ValueError(
                "numeric incentive_value requires incentive_value_verified=true"
            )
        incentive = _decimal(incentive_value, "incentive_value")
        incentive_source_text = _required_text(
            incentive_source,
            "incentive_source",
        )
        incentive_evidence = _required_text(
            incentive_evidence_id,
            "incentive_evidence_id",
        )

    reported: Decimal | None = None
    reported_source: str | None = None
    if reported_apy_percent is not None:
        reported = _decimal(
            reported_apy_percent,
            "reported_apy_percent",
        )
        reported_source = _required_text(
            reported_apy_source,
            "reported_apy_source",
        )
    elif reported_apy_source is not None:
        raise ValueError(
            "reported_apy_source requires reported_apy_percent"
        )

    base_return = base_fee / liquidity
    base_annualized = _annualize(base_return, duration)

    incentive_return: Decimal | None = None
    incentive_annualized: Decimal | None = None
    total_return: Decimal | None = None
    total_annualized: Decimal | None = None

    if incentive is not None:
        incentive_return = incentive / liquidity
        incentive_annualized = _annualize(incentive_return, duration)
        total_return = base_return + incentive_return
        total_annualized = _annualize(total_return, duration)

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": chain_name,
        "pool_id": pool,
        "window": {
            "start": _fmt(start),
            "end": _fmt(end),
            "duration_seconds": _fmt(duration),
        },
        "valuation": {
            "unit": unit,
            "average_liquidity_value": _fmt(liquidity),
            "liquidity_value_verified": True,
        },
        "organic_fee_yield": {
            "fee_value": _fmt(base_fee),
            "window_return_ratio": _fmt(base_return),
            "simple_annualized_return_ratio": _fmt(base_annualized),
            "evidence_id": base_evidence,
            "verified": True,
        },
        "subsidized_incentive_yield": {
            "state": "verified" if incentive is not None else "unavailable",
            "incentive_value": _fmt(incentive),
            "window_return_ratio": _fmt(incentive_return),
            "simple_annualized_return_ratio": _fmt(incentive_annualized),
            "source": incentive_source_text,
            "evidence_id": incentive_evidence,
            "verified": incentive is not None,
        },
        "combined_yield": {
            "state": "verified" if incentive is not None else "unavailable_incentive",
            "window_return_ratio": _fmt(total_return),
            "simple_annualized_return_ratio": _fmt(total_annualized),
        },
        "reported_yield": {
            "reported_apy_percent": _fmt(reported),
            "source": reported_source,
            "treated_as_verified_calculation": False,
        },
        "verification": {
            "base_fee_yield_verified": True,
            "incentive_yield_verified": incentive is not None,
            "combined_yield_verified": incentive is not None,
            "future_yield_verified": False,
            "source_independence_verified": False,
        },
        "boundaries": {
            "missing_incentive_is_zero_authorized": False,
            "simple_annualization_is_not_forecast": True,
            "sustainable_yield_claim_authorized": False,
            "future_apy_guarantee_authorized": False,
            "automatic_risk_conclusion_authorized": False,
            "trade_recommendation_authorized": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": DEFAULT_EXECUTION_AUTHORIZED,
    }


__all__ = [
    "CONTRACT_VERSION",
    "DEFAULT_EXECUTION_AUTHORIZED",
    "SECONDS_PER_YEAR",
    "build_yield_provenance",
]
