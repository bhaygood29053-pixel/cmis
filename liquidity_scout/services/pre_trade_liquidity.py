"""Deterministic trade-size-to-liquidity analysis for CMIS pre-trade checks.

The generic service core intentionally has no calibrated market-size thresholds.
A production runtime may select an explicit named operating profile.  The X1
runtime uses ``CMIS_X1_CONSERVATIVE_PRE_TRADE_POLICY`` when the caller does not
supply a separate policy.

Thresholds are operating policy, not universal market truth.  Every evaluated
result exposes the exact policy identity and configured thresholds used.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Optional

from .pre_trade_capabilities import normalize_required_capabilities
from .risk import BLOCK, PASS, WARN


VERSION = "2.0"

# Generic deterministic core: calculate verified ratios, but do not invent a
# calibrated decision threshold.  This preserves the reusable service contract
# for future chains and for explicit-policy callers.
DEFAULT_PRE_TRADE_POLICY = {
    "policy_name": "cmis_pre_trade_unconfigured",
    "policy_version": "1.0",
    "low_max_notional_to_liquidity_ratio": None,
    "moderate_max_notional_to_liquidity_ratio": None,
    "high_max_notional_to_liquidity_ratio": None,
    "warn_notional_to_liquidity_ratio": None,
    "block_notional_to_liquidity_ratio": None,
    "warn_on_missing_notional": True,
    "block_on_unverified_liquidity_for_sized_trade": True,
    "warn_risk_age_seconds": None,
    "block_risk_age_seconds": None,
    "block_on_unverified_timestamp_when_age_policy_set": True,
    "required_capabilities": [],
}

# Accepted production X1 operating profile for Issue #99.  These are explicit,
# conservative policy bands, not inferred AMM execution physics.
CMIS_X1_CONSERVATIVE_PRE_TRADE_POLICY = {
    **DEFAULT_PRE_TRADE_POLICY,
    "policy_name": "cmis_x1_trade_size_conservative",
    "policy_version": "1.0",
    "low_max_notional_to_liquidity_ratio": 0.02,
    "moderate_max_notional_to_liquidity_ratio": 0.05,
    "high_max_notional_to_liquidity_ratio": 0.10,
    "warn_notional_to_liquidity_ratio": 0.05,
    "block_notional_to_liquidity_ratio": 0.10,
}


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _positive_policy_number(name: str, value: Any) -> Optional[float]:
    if value is None:
        return None
    number = _number(value)
    if number is None or number <= 0:
        raise ValueError(f"{name} must be a positive finite number or None")
    return number


def _policy_text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


def normalize_pre_trade_policy(policy: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Validate one explicit pre-trade policy without adding hidden thresholds."""

    result = dict(DEFAULT_PRE_TRADE_POLICY)
    result["required_capabilities"] = []
    if policy is not None:
        if not isinstance(policy, Mapping):
            raise ValueError("pre_trade policy must be a mapping or None")
        unknown = sorted(set(policy) - set(DEFAULT_PRE_TRADE_POLICY))
        if unknown:
            raise ValueError(f"unknown pre_trade policy fields: {', '.join(unknown)}")
        result.update(policy)

    result["policy_name"] = _policy_text("policy_name", result.get("policy_name"))
    result["policy_version"] = _policy_text("policy_version", result.get("policy_version"))
    result["required_capabilities"] = normalize_required_capabilities(
        result.get("required_capabilities")
    )

    numeric_keys = (
        "low_max_notional_to_liquidity_ratio",
        "moderate_max_notional_to_liquidity_ratio",
        "high_max_notional_to_liquidity_ratio",
        "warn_notional_to_liquidity_ratio",
        "block_notional_to_liquidity_ratio",
        "warn_risk_age_seconds",
        "block_risk_age_seconds",
    )
    for key in numeric_keys:
        result[key] = _positive_policy_number(key, result.get(key))

    classification_values = tuple(
        result[key]
        for key in (
            "low_max_notional_to_liquidity_ratio",
            "moderate_max_notional_to_liquidity_ratio",
            "high_max_notional_to_liquidity_ratio",
        )
    )
    configured_classification_values = [
        value for value in classification_values if value is not None
    ]
    if configured_classification_values and len(configured_classification_values) != 3:
        raise ValueError(
            "low_max_notional_to_liquidity_ratio, "
            "moderate_max_notional_to_liquidity_ratio, and "
            "high_max_notional_to_liquidity_ratio must be configured together"
        )
    if len(configured_classification_values) == 3:
        low, moderate, high = classification_values
        if not (low <= moderate <= high):
            raise ValueError(
                "trade-size classification thresholds must be ordered: "
                "low_max_notional_to_liquidity_ratio <= "
                "moderate_max_notional_to_liquidity_ratio <= "
                "high_max_notional_to_liquidity_ratio"
            )

    warn_ratio = result["warn_notional_to_liquidity_ratio"]
    block_ratio = result["block_notional_to_liquidity_ratio"]
    if warn_ratio is not None and block_ratio is not None and block_ratio < warn_ratio:
        raise ValueError(
            "block_notional_to_liquidity_ratio must be greater than or equal to "
            "warn_notional_to_liquidity_ratio"
        )

    warn_age = result["warn_risk_age_seconds"]
    block_age = result["block_risk_age_seconds"]
    if warn_age is not None and block_age is not None and block_age < warn_age:
        raise ValueError(
            "block_risk_age_seconds must be greater than or equal to "
            "warn_risk_age_seconds"
        )

    for key in (
        "warn_on_missing_notional",
        "block_on_unverified_liquidity_for_sized_trade",
        "block_on_unverified_timestamp_when_age_policy_set",
    ):
        if not isinstance(result.get(key), bool):
            raise ValueError(f"{key} must be a boolean")

    return result


def _risk_liquidity(risk_result: Mapping[str, Any]) -> tuple[Optional[float], bool]:
    components = risk_result.get("components")
    components = components if isinstance(components, Mapping) else {}
    liquidity = components.get("liquidity")
    liquidity = liquidity if isinstance(liquidity, Mapping) else {}
    evidence = liquidity.get("evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    liquidity_usd = _number(evidence.get("liquidity_usd"))

    confidence = risk_result.get("confidence")
    confidence = confidence if isinstance(confidence, Mapping) else {}
    checks = confidence.get("checks")
    checks = checks if isinstance(checks, Mapping) else {}
    verified = (
        checks.get("liquidity_verified") is True
        and liquidity_usd is not None
        and liquidity_usd >= 0
    )
    return liquidity_usd, verified


def _classification(ratio: float, policy: Mapping[str, Any]) -> Optional[str]:
    low = policy.get("low_max_notional_to_liquidity_ratio")
    moderate = policy.get("moderate_max_notional_to_liquidity_ratio")
    high = policy.get("high_max_notional_to_liquidity_ratio")
    if None in (low, moderate, high):
        return None
    if ratio < low:
        return "LOW"
    if ratio < moderate:
        return "MODERATE"
    if ratio < high:
        return "HIGH"
    return "VERY_HIGH"


def _threshold_reason(
    *,
    classification: Optional[str],
    policy: Mapping[str, Any],
    threshold_name: str,
) -> str:
    if classification:
        return (
            f"The proposed notional is {classification} under the explicit "
            f"{policy['policy_name']} v{policy['policy_version']} policy."
        )
    return (
        "The proposed notional meets or exceeds the explicit "
        f"{threshold_name} policy threshold."
    )


def assess_trade_size_liquidity(
    risk_result: Mapping[str, Any],
    trade: Mapping[str, Any],
    *,
    policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Assess proposed USD notional against verified asset-wide liquidity."""
    if not isinstance(risk_result, Mapping):
        raise ValueError("risk_result must be a mapping")
    if not isinstance(trade, Mapping):
        raise ValueError("trade must be a mapping")

    normalized_policy = normalize_pre_trade_policy(policy)
    notional_usd = _number(trade.get("notional_usd"))
    liquidity_usd, liquidity_verified = _risk_liquidity(risk_result)

    warn_ratio = normalized_policy["warn_notional_to_liquidity_ratio"]
    block_ratio = normalized_policy["block_notional_to_liquidity_ratio"]
    classification_configured = all(
        normalized_policy[key] is not None
        for key in (
            "low_max_notional_to_liquidity_ratio",
            "moderate_max_notional_to_liquidity_ratio",
            "high_max_notional_to_liquidity_ratio",
        )
    )
    evidence = {
        "policy_contract_version": VERSION,
        "policy_name": normalized_policy["policy_name"],
        "policy_version": normalized_policy["policy_version"],
        "notional_usd": notional_usd,
        "liquidity_usd": liquidity_usd,
        "liquidity_verified": liquidity_verified,
        "notional_to_liquidity_ratio": None,
        "trade_size_classification": None,
        "evidence_status": "insufficient",
        "classification_thresholds_configured": classification_configured,
        "classification_thresholds": {
            "low_max_ratio": normalized_policy["low_max_notional_to_liquidity_ratio"],
            "moderate_max_ratio": normalized_policy["moderate_max_notional_to_liquidity_ratio"],
            "high_max_ratio": normalized_policy["high_max_notional_to_liquidity_ratio"],
        },
        "warn_notional_to_liquidity_ratio": warn_ratio,
        "block_notional_to_liquidity_ratio": block_ratio,
        "warn_threshold_notional_usd": (
            liquidity_usd * warn_ratio
            if liquidity_verified and liquidity_usd is not None and warn_ratio is not None
            else None
        ),
        "hard_block_notional_usd_threshold": (
            liquidity_usd * block_ratio
            if liquidity_verified and liquidity_usd is not None and block_ratio is not None
            else None
        ),
        "size_assessment_complete": False,
        "slippage_estimate_pct": None,
        "price_impact_estimate_pct": None,
        "route_quality": None,
    }

    if notional_usd is None:
        return {
            "status": WARN if normalized_policy["warn_on_missing_notional"] else PASS,
            "flags": ["trade_notional_unverified"] if normalized_policy["warn_on_missing_notional"] else [],
            "reasons": [
                "Trade notional is required to complete trade-size-to-liquidity analysis."
            ] if normalized_policy["warn_on_missing_notional"] else [],
            "evidence": evidence,
            "policy": normalized_policy,
        }

    if not liquidity_verified:
        blocking = normalized_policy["block_on_unverified_liquidity_for_sized_trade"]
        return {
            "status": BLOCK if blocking else WARN,
            "flags": ["sized_trade_liquidity_unverified"],
            "reasons": [
                "A sized trade cannot be compared with asset-wide liquidity because verified total liquidity is unavailable."
            ],
            "evidence": evidence,
            "policy": normalized_policy,
        }

    if liquidity_usd == 0:
        evidence["size_assessment_complete"] = True
        evidence["trade_size_classification"] = (
            "VERY_HIGH" if classification_configured else None
        )
        evidence["evidence_status"] = "verified"
        return {
            "status": BLOCK,
            "flags": ["zero_verified_liquidity_for_sized_trade"],
            "reasons": ["Verified asset-wide liquidity is zero for the proposed sized trade."],
            "evidence": evidence,
            "policy": normalized_policy,
        }

    ratio = notional_usd / liquidity_usd
    classification = _classification(ratio, normalized_policy)
    evidence["notional_to_liquidity_ratio"] = ratio
    evidence["trade_size_classification"] = classification
    evidence["evidence_status"] = "verified"
    evidence["size_assessment_complete"] = True

    if block_ratio is not None and ratio >= block_ratio:
        return {
            "status": BLOCK,
            "flags": ["trade_size_exceeds_liquidity_block_ratio"],
            "reasons": [
                _threshold_reason(
                    classification=classification,
                    policy=normalized_policy,
                    threshold_name="block_notional_to_liquidity_ratio",
                )
            ],
            "evidence": evidence,
            "policy": normalized_policy,
        }

    if warn_ratio is not None and ratio >= warn_ratio:
        return {
            "status": WARN,
            "flags": ["trade_size_exceeds_liquidity_warn_ratio"],
            "reasons": [
                _threshold_reason(
                    classification=classification,
                    policy=normalized_policy,
                    threshold_name="warn_notional_to_liquidity_ratio",
                )
            ],
            "evidence": evidence,
            "policy": normalized_policy,
        }

    return {
        "status": PASS,
        "flags": [],
        "reasons": [],
        "evidence": evidence,
        "policy": normalized_policy,
    }


__all__ = [
    "CMIS_X1_CONSERVATIVE_PRE_TRADE_POLICY",
    "DEFAULT_PRE_TRADE_POLICY",
    "VERSION",
    "assess_trade_size_liquidity",
    "normalize_pre_trade_policy",
]
