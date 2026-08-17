"""Deterministic trade-size analysis over verified USD liquidity.

This module performs no provider collection, routing, simulation, signing, or
transaction work. It evaluates only an explicit proposed USD notional against
an explicitly verified USD-liquidity fact. Classification thresholds are
caller-supplied and versioned; CMIS does not invent default market thresholds.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional


POLICY_SCHEMA_VERSION = "pre_trade_size_policy.v1"


def _decimal(name: str, value: Any, *, positive: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not number.is_finite():
        raise ValueError(f"{name} must be a finite number")
    if positive and number <= 0:
        raise ValueError(f"{name} must be greater than zero")
    if not positive and number < 0:
        raise ValueError(f"{name} must be non-negative")
    return number


def normalize_trade_size_policy(policy: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Validate an explicit, versioned notional/liquidity-ratio policy.

    No thresholds are supplied by default. With ``policy=None`` CMIS may still
    calculate the ratio, but classification remains unavailable.
    """
    if policy is None:
        return {
            "schema_version": POLICY_SCHEMA_VERSION,
            "warn_ratio": None,
            "block_ratio": None,
        }
    if not isinstance(policy, Mapping):
        raise ValueError("trade_size_policy must be a mapping or None")

    allowed = {"schema_version", "warn_ratio", "block_ratio"}
    unknown = sorted(set(policy) - allowed)
    if unknown:
        raise ValueError("unknown trade_size_policy fields: " + ", ".join(unknown))

    version = str(policy.get("schema_version") or "").strip()
    if version != POLICY_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {POLICY_SCHEMA_VERSION}")

    warn_raw = policy.get("warn_ratio")
    block_raw = policy.get("block_ratio")
    warn = None if warn_raw is None else _decimal("warn_ratio", warn_raw)
    block = None if block_raw is None else _decimal("block_ratio", block_raw)
    if warn is not None and block is not None and block < warn:
        raise ValueError("block_ratio must be greater than or equal to warn_ratio")

    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "warn_ratio": str(warn) if warn is not None else None,
        "block_ratio": str(block) if block is not None else None,
    }


def assess_trade_size(
    notional_usd: Any,
    liquidity_usd: Any,
    *,
    liquidity_verified: bool,
    policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Calculate and optionally classify notional as a share of liquidity.

    ``liquidity_verified`` must be exactly ``True``. Missing/unverified/zero
    liquidity fails closed and never produces a fabricated ratio. Thresholds
    are ratios (for example 0.05 means 5%) and must be explicitly supplied to
    produce PASS/WARN/BLOCK classification.
    """
    notional = _decimal("notional_usd", notional_usd, positive=True)
    normalized_policy = normalize_trade_size_policy(policy)

    result = {
        "available": False,
        "status": "UNAVAILABLE",
        "notional_usd": str(notional),
        "liquidity_usd": None,
        "notional_to_liquidity_ratio": None,
        "notional_to_liquidity_pct": None,
        "policy": normalized_policy,
        "flags": [],
        "reasons": [],
    }

    if liquidity_verified is not True:
        result["flags"].append("verified_liquidity_required")
        result["reasons"].append(
            "Trade-size analysis requires verified total USD liquidity; partial or unverified liquidity is not used."
        )
        return result

    try:
        liquidity = _decimal("liquidity_usd", liquidity_usd)
    except ValueError:
        result["flags"].append("verified_liquidity_invalid")
        result["reasons"].append("Verified liquidity is missing or malformed.")
        return result

    result["liquidity_usd"] = str(liquidity)
    if liquidity == 0:
        result["status"] = "BLOCK"
        result["flags"].append("zero_verified_liquidity")
        result["reasons"].append("Verified total USD liquidity is zero.")
        return result

    ratio = notional / liquidity
    result["available"] = True
    result["notional_to_liquidity_ratio"] = str(ratio)
    result["notional_to_liquidity_pct"] = str(ratio * Decimal("100"))

    warn = normalized_policy["warn_ratio"]
    block = normalized_policy["block_ratio"]
    if warn is None and block is None:
        result["status"] = "UNCLASSIFIED"
        result["flags"].append("trade_size_policy_thresholds_unset")
        result["reasons"].append(
            "The verified notional-to-liquidity ratio was calculated, but no explicit classification thresholds were supplied."
        )
        return result

    warn_value = Decimal(warn) if warn is not None else None
    block_value = Decimal(block) if block is not None else None
    if block_value is not None and ratio >= block_value:
        result["status"] = "BLOCK"
        result["flags"].append("trade_size_at_or_above_block_ratio")
    elif warn_value is not None and ratio >= warn_value:
        result["status"] = "WARN"
        result["flags"].append("trade_size_at_or_above_warn_ratio")
    else:
        result["status"] = "PASS"
    return result


__all__ = ["POLICY_SCHEMA_VERSION", "normalize_trade_size_policy", "assess_trade_size"]
