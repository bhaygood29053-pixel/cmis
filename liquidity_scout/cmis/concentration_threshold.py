"""Deterministic threshold evaluation for verified concentration changes.

This module classifies only whether a canonical, already-verified numeric
concentration change crosses an explicit versioned threshold. It never
interprets the change as whale behavior, accumulation, distribution, insider
activity, manipulation, or any other behavioral/risk claim.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from typing import Any, Mapping


_DISPLAY_PRECISION = 50
_CHANGE_SCHEMA = "cmis_top_account_concentration_change.v1"
_RESULT_SCHEMA = "cmis_concentration_threshold_evaluation.v1"
_SCOPE = "observed_top_token_accounts"
_REQUIRED_LIMITATIONS = frozenset(
    {
        "numeric_change_does_not_establish_accumulation_or_distribution",
        "token_accounts_are_not_unique_holder_identities",
        "observed_top_account_scope_is_incomplete",
        "comparison_requires_same_source_top_n_and_observed_account_count",
        "decimal_share_is_presentation_only_exact_ratio_drives_comparison",
    }
)


def _normalized_text(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a normalized non-empty string.")
    text = value.strip()
    if not text or text != value:
        raise ValueError(f"{name} must be a normalized non-empty string.")
    return text


def _nonnegative_int(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative integer.")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isdigit() and str(int(value)) == value:
        result = int(value)
    else:
        raise ValueError(f"{name} must be a non-negative integer.")
    if result < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return result


def _positive_int(name: str, value: Any) -> int:
    result = _nonnegative_int(name, value)
    if result <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return result


def _nonnegative_decimal(name: str, value: Any) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be a finite non-negative decimal.")
    if not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{name} must be a finite non-negative decimal.")
    if isinstance(value, str) and (not value or value.strip() != value):
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


def _fraction_decimal(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = _DISPLAY_PRECISION
        return format(Decimal(value.numerator) / Decimal(value.denominator), "f")


def _exact_fraction(value: Any, *, name: str, signed: bool = False) -> Fraction:
    if not isinstance(value, Mapping) or set(value) != {"numerator", "denominator"}:
        raise ValueError(f"{name} must be an exact ratio object.")
    numerator = value.get("numerator")
    denominator = value.get("denominator")
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


def _canonical_utc_timestamp(name: str, value: Any) -> datetime:
    text = _normalized_text(name, value)
    if not text.endswith("Z"):
        raise ValueError(f"{name} must be canonical UTC ending in Z.")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{name} must be canonical UTC ending in Z.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != text:
        raise ValueError(f"{name} must be canonical UTC ending in Z.")
    return parsed


def _validate_limitations(value: Any) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("change.limitations must be a list of strings.")
    if len(value) != len(set(value)):
        raise ValueError("change.limitations must not contain duplicates.")
    if set(value) != set(_REQUIRED_LIMITATIONS):
        raise ValueError("change.limitations do not match the canonical v1 boundary.")


def _validate_change(change: Mapping[str, Any]) -> Fraction:
    if not isinstance(change, Mapping):
        raise ValueError("change must be a concentration change object.")
    if change.get("schema") != _CHANGE_SCHEMA:
        raise ValueError(f"change must use {_CHANGE_SCHEMA}.")

    for field in ("chain", "asset_id", "source"):
        _normalized_text(f"change.{field}", change.get(field))
    if change.get("scope") != _SCOPE:
        raise ValueError("unsupported concentration scope.")

    requested_limit = _positive_int(
        "change.requested_account_limit", change.get("requested_account_limit")
    )
    observed_count = _positive_int(
        "change.observed_account_count", change.get("observed_account_count")
    )
    if observed_count > requested_limit:
        raise ValueError("change.observed_account_count exceeds requested_account_limit.")

    before_time = _canonical_utc_timestamp(
        "change.before_observed_at", change.get("before_observed_at")
    )
    after_time = _canonical_utc_timestamp(
        "change.after_observed_at", change.get("after_observed_at")
    )
    if after_time <= before_time:
        raise ValueError("change.after_observed_at must be later than before_observed_at.")

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
    if before > 1 or after > 1:
        raise ValueError("concentration shares cannot exceed total supply.")
    if delta != after - before:
        raise ValueError("concentration change exact ratios are inconsistent.")

    presentations = {
        "before_share": _fraction_decimal(before),
        "after_share": _fraction_decimal(after),
        "delta_share": _fraction_decimal(delta),
        "delta_bps": _fraction_decimal(delta * 10000),
    }
    for field, expected in presentations.items():
        if change.get(field) != expected:
            raise ValueError(f"concentration change {field} is inconsistent.")

    expected_direction = "INCREASE" if delta > 0 else "DECREASE" if delta < 0 else "NO_CHANGE"
    if change.get("direction") != expected_direction:
        raise ValueError("concentration change direction is inconsistent.")

    _validate_limitations(change.get("limitations"))
    return delta


def evaluate_concentration_threshold(
    *,
    change: Mapping[str, Any],
    policy_id: str,
    policy_version: str,
    absolute_delta_threshold_bps: Any,
) -> dict[str, Any]:
    """Evaluate an explicit threshold against one canonical concentration change.

    The threshold is caller supplied and versioned; CMIS provides no hidden or
    default anomaly threshold. The result is a threshold observation only and
    is deliberately non-promotable as a behavioral or risk conclusion.
    """
    delta = _validate_change(change)
    policy = _normalized_text("policy_id", policy_id)
    version = _normalized_text("policy_version", policy_version)
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
        "schema": _RESULT_SCHEMA,
        "chain": change["chain"],
        "asset_id": change["asset_id"],
        "source": change["source"],
        "scope": change["scope"],
        "requested_account_limit": change["requested_account_limit"],
        "observed_account_count": change["observed_account_count"],
        "before_observed_at": change["before_observed_at"],
        "after_observed_at": change["after_observed_at"],
        "policy": {
            "policy_id": policy,
            "policy_version": version,
            "absolute_delta_threshold_bps": _canonical_decimal(threshold),
            "comparison": "absolute_delta_bps",
            "hidden_default_threshold": False,
        },
        "direction": change["direction"],
        "before_share_exact": dict(change["before_share_exact"]),
        "after_share_exact": dict(change["after_share_exact"]),
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
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "limitations": [
            "threshold_is_explicit_policy_not_a_market_fact",
            "threshold_crossing_does_not_establish_whale_or_insider_behavior",
            "threshold_crossing_does_not_establish_accumulation_or_distribution",
            "threshold_crossing_does_not_establish_manipulation_or_risk",
            "token_accounts_are_not_unique_holder_identities",
            "observed_top_account_scope_is_incomplete",
            "threshold_result_is_not_a_public_service_or_scout_reliance_contract",
        ],
    }


__all__ = ["evaluate_concentration_threshold"]
