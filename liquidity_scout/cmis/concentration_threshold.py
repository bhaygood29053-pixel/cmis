"""Deterministic threshold evaluation for verified concentration changes.

This module classifies only whether an already-validated numeric concentration
change crosses an explicit versioned threshold. It never interprets the change
as whale behavior, accumulation, distribution, insider activity, manipulation,
or any other behavioral claim.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from typing import Any, Mapping


_DISPLAY_PRECISION = 50


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()


def _nonnegative_decimal(name: str, value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite non-negative decimal.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a finite non-negative decimal.") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{name} must be a finite non-negative decimal.")
    return result


def _canonical_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _exact_fraction(value: Any, *, name: str, signed: bool = False) -> Fraction:
    if not isinstance(value, Mapping) or set(value) != {"numerator", "denominator"}:
        raise ValueError(f"{name} must be an exact ratio object.")
    numerator = value.get("numerator")
    denominator = value.get("denominator")
    if isinstance(numerator, bool) or isinstance(denominator, bool):
        raise ValueError(f"{name} must contain canonical integer strings.")
    if not isinstance(numerator, str) or not isinstance(denominator, str):
        raise ValueError(f"{name} must contain canonical integer strings.")
    try:
        numerator_int = int(numerator)
        denominator_int = int(denominator)
    except ValueError as exc:
        raise ValueError(f"{name} must contain canonical integer strings.") from exc
    if str(numerator_int) != numerator or str(denominator_int) != denominator:
        raise ValueError(f"{name} must contain canonical integer strings.")
    if denominator_int <= 0 or (not signed and numerator_int < 0):
        raise ValueError(f"{name} is outside the accepted ratio domain.")
    return Fraction(numerator_int, denominator_int)


def _fraction_decimal(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = _DISPLAY_PRECISION
        return format(Decimal(value.numerator) / Decimal(value.denominator), "f")


def _validate_change(change: Mapping[str, Any]) -> Fraction:
    if not isinstance(change, Mapping):
        raise ValueError("change must be a concentration change object.")
    if change.get("schema") != "cmis_top_account_concentration_change.v1":
        raise ValueError("change must use cmis_top_account_concentration_change.v1.")
    for field in ("chain", "asset_id", "source", "scope"):
        _text(f"change.{field}", change.get(field))
    if change.get("scope") != "observed_top_token_accounts":
        raise ValueError("unsupported concentration scope.")
    if change.get("identity_verified") is not True:
        raise ValueError("concentration change requires verified identity.")
    for field in (
        "scope_complete",
        "holder_semantics_verified",
        "beneficial_owner_identity_verified",
        "behavioral_interpretation_verified",
        "cmis_promotable",
    ):
        if change.get(field) is not False:
            raise ValueError(f"change.{field} must remain false.")

    before = _exact_fraction(change.get("before_share_exact"), name="before_share_exact")
    after = _exact_fraction(change.get("after_share_exact"), name="after_share_exact")
    delta = _exact_fraction(
        change.get("delta_share_exact"), name="delta_share_exact", signed=True
    )
    if before > 1 or after > 1 or delta != after - before:
        raise ValueError("concentration change exact ratios are inconsistent.")
    expected_direction = "INCREASE" if delta > 0 else "DECREASE" if delta < 0 else "NO_CHANGE"
    if change.get("direction") != expected_direction:
        raise ValueError("concentration change direction is inconsistent.")
    if change.get("delta_share") != _fraction_decimal(delta):
        raise ValueError("concentration change decimal delta is inconsistent.")
    if change.get("delta_bps") != _fraction_decimal(delta * 10000):
        raise ValueError("concentration change basis-point delta is inconsistent.")
    return delta


def evaluate_concentration_threshold(
    *,
    change: Mapping[str, Any],
    policy_id: str,
    policy_version: str,
    absolute_delta_threshold_bps: Any,
) -> dict[str, Any]:
    """Evaluate an explicit threshold against a verified numeric change.

    The threshold is caller supplied and versioned; CMIS provides no hidden or
    default anomaly threshold. The result is a threshold observation only and
    is deliberately non-promotable as a behavioral or risk conclusion.
    """
    delta = _validate_change(change)
    policy = _text("policy_id", policy_id)
    version = _text("policy_version", policy_version)
    threshold = _nonnegative_decimal(
        "absolute_delta_threshold_bps", absolute_delta_threshold_bps
    )

    absolute_delta_bps = abs(delta * 10000)
    threshold_fraction = Fraction(threshold)
    exceeded = absolute_delta_bps > threshold_fraction
    matched = absolute_delta_bps == threshold_fraction
    if exceeded:
        status = "EXCEEDS_THRESHOLD"
    elif matched:
        status = "AT_THRESHOLD"
    else:
        status = "WITHIN_THRESHOLD"

    return {
        "schema": "cmis_concentration_threshold_evaluation.v1",
        "chain": change["chain"],
        "asset_id": change["asset_id"],
        "source": change["source"],
        "scope": change["scope"],
        "policy": {
            "policy_id": policy,
            "policy_version": version,
            "absolute_delta_threshold_bps": _canonical_decimal(threshold),
            "comparison": "absolute_delta_bps",
        },
        "direction": change["direction"],
        "delta_share_exact": dict(change["delta_share_exact"]),
        "delta_bps": change["delta_bps"],
        "absolute_delta_bps": _fraction_decimal(absolute_delta_bps),
        "status": status,
        "threshold_exceeded": exceeded,
        "threshold_matched": matched,
        "identity_verified": True,
        "scope_complete": False,
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "behavioral_interpretation_verified": False,
        "risk_interpretation_verified": False,
        "cmis_promotable": False,
        "limitations": [
            "threshold_is_explicit_policy_not_a_market_fact",
            "threshold_crossing_does_not_establish_whale_or_insider_behavior",
            "threshold_crossing_does_not_establish_accumulation_or_distribution",
            "threshold_crossing_does_not_establish_manipulation_or_risk",
            "token_accounts_are_not_unique_holder_identities",
            "observed_top_account_scope_is_incomplete",
        ],
    }


__all__ = ["evaluate_concentration_threshold"]
