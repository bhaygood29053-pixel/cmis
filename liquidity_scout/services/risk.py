"""Deterministic risk assessment over already-verified service facts.

This module deliberately performs no network, RPC, DEX, database, or LLM work.
Callers supply structured market/tokenomics reports that were produced by other
Liquidity Scout / CMIS layers. The risk core evaluates only facts that those
reports mark as verified and preserves uncertainty when data is missing.

The first risk milestone intentionally does not invent a numeric Scout score.
A score remains unavailable until a calibrated, tested scoring policy exists.
"""

from typing import Any, Dict, Mapping, Optional


PASS = "PASS"
WARN = "WARN"
BLOCK = "BLOCK"
_STATUS_ORDER = {PASS: 0, WARN: 1, BLOCK: 2}

DEFAULT_RISK_POLICY = {
    # Monetary/activity thresholds are intentionally unset by default. A caller
    # may supply explicit values, making the resulting decision reproducible
    # without embedding arbitrary market-size assumptions in the core.
    "minimum_liquidity_usd": None,
    "minimum_volume_24h_usd": None,
    "minimum_transactions_24h": None,
    "block_on_zero_liquidity": True,
    "warn_on_zero_activity": True,
    "warn_on_active_mint_authority": True,
    "warn_on_active_freeze_authority": True,
}


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _nonnegative_policy_number(name: str, value: Any) -> Optional[float]:
    if value is None:
        return None
    number = _number(value)
    if number is None or number < 0:
        raise ValueError(f"{name} must be a non-negative number or None")
    return number


def _normalize_policy(policy: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    result = dict(DEFAULT_RISK_POLICY)
    if policy is None:
        return result
    if not isinstance(policy, Mapping):
        raise ValueError("risk policy must be a mapping or None")

    unknown = sorted(set(policy) - set(DEFAULT_RISK_POLICY))
    if unknown:
        raise ValueError(f"unknown risk policy fields: {', '.join(unknown)}")

    result.update(policy)
    for key in (
        "minimum_liquidity_usd",
        "minimum_volume_24h_usd",
        "minimum_transactions_24h",
    ):
        result[key] = _nonnegative_policy_number(key, result.get(key))

    for key in (
        "block_on_zero_liquidity",
        "warn_on_zero_activity",
        "warn_on_active_mint_authority",
        "warn_on_active_freeze_authority",
    ):
        if not isinstance(result.get(key), bool):
            raise ValueError(f"{key} must be a boolean")

    return result


def _merge_status(*statuses: str) -> str:
    if not statuses:
        return PASS
    return max(statuses, key=lambda status: _STATUS_ORDER[status])


def _component(
    status: str,
    *,
    available: bool,
    flags=None,
    reasons=None,
    evidence=None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "available": bool(available),
        "flags": list(flags or []),
        "reasons": list(reasons or []),
        "evidence": dict(evidence or {}),
    }


def _verified_market_metric(
    market_report: Mapping[str, Any],
    report_key: str,
    completeness_key: str,
):
    completeness = market_report.get("completeness")
    complete = (
        isinstance(completeness, Mapping)
        and completeness.get(completeness_key) is True
    )
    value = _number(market_report.get(report_key))
    return value, bool(complete and value is not None and value >= 0)


def _assess_liquidity(
    market_report: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> Dict[str, Any]:
    value, verified = _verified_market_metric(
        market_report,
        "liquidity_usd",
        "liquidity",
    )
    evidence = {
        "liquidity_usd": value,
        "minimum_liquidity_usd": policy["minimum_liquidity_usd"],
    }

    if not verified:
        return _component(
            WARN,
            available=value is not None,
            flags=["liquidity_unverified"],
            reasons=[
                "Asset-wide liquidity is missing, malformed, or incomplete; "
                "partial liquidity is not treated as a verified total."
            ],
            evidence=evidence,
        )

    if value == 0 and policy["block_on_zero_liquidity"]:
        return _component(
            BLOCK,
            available=True,
            flags=["zero_verified_liquidity"],
            reasons=["Verified asset-wide liquidity is zero."],
            evidence=evidence,
        )

    minimum = policy["minimum_liquidity_usd"]
    if minimum is not None and value < minimum:
        return _component(
            WARN,
            available=True,
            flags=["liquidity_below_policy_minimum"],
            reasons=[
                "Verified asset-wide liquidity is below the explicit risk-policy minimum."
            ],
            evidence=evidence,
        )

    return _component(PASS, available=True, evidence=evidence)


def _assess_activity(
    market_report: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> Dict[str, Any]:
    volume, volume_verified = _verified_market_metric(
        market_report,
        "volume_24h_usd",
        "volume_24h",
    )
    transactions, transactions_verified = _verified_market_metric(
        market_report,
        "transactions_24h",
        "transactions_24h",
    )
    evidence = {
        "volume_24h_usd": volume,
        "transactions_24h": transactions,
        "minimum_volume_24h_usd": policy["minimum_volume_24h_usd"],
        "minimum_transactions_24h": policy["minimum_transactions_24h"],
    }
    flags = []
    reasons = []

    if not volume_verified:
        flags.append("volume_24h_unverified")
        reasons.append("24h volume is missing, malformed, or incomplete.")
    if not transactions_verified:
        flags.append("transactions_24h_unverified")
        reasons.append("24h transaction activity is missing, malformed, or incomplete.")

    if volume_verified and policy["warn_on_zero_activity"] and volume == 0:
        flags.append("zero_verified_volume_24h")
        reasons.append("Verified 24h volume is zero.")
    if (
        transactions_verified
        and policy["warn_on_zero_activity"]
        and transactions == 0
    ):
        flags.append("zero_verified_transactions_24h")
        reasons.append("Verified 24h transaction count is zero.")

    minimum_volume = policy["minimum_volume_24h_usd"]
    if volume_verified and minimum_volume is not None and volume < minimum_volume:
        flags.append("volume_24h_below_policy_minimum")
        reasons.append("Verified 24h volume is below the explicit risk-policy minimum.")

    minimum_transactions = policy["minimum_transactions_24h"]
    if (
        transactions_verified
        and minimum_transactions is not None
        and transactions < minimum_transactions
    ):
        flags.append("transactions_24h_below_policy_minimum")
        reasons.append(
            "Verified 24h transaction count is below the explicit risk-policy minimum."
        )

    status = WARN if flags else PASS
    return _component(
        status,
        available=volume is not None or transactions is not None,
        flags=flags,
        reasons=reasons,
        evidence=evidence,
    )


def _assess_tokenomics(
    tokenomics_report: Optional[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> Dict[str, Any]:
    if not isinstance(tokenomics_report, Mapping):
        return _component(
            WARN,
            available=False,
            flags=["tokenomics_unavailable"],
            reasons=["Verified tokenomics facts were not supplied to the risk core."],
        )

    flags = []
    reasons = []
    supply_verified = tokenomics_report.get("supply_verified") is True
    mint_authority_verified = (
        tokenomics_report.get("mint_authority_verified") is True
    )
    freeze_authority_verified = (
        tokenomics_report.get("freeze_authority_verified") is True
    )
    mint_state = _text(tokenomics_report.get("mint_authority_state"))
    freeze_state = _text(tokenomics_report.get("freeze_authority_state"))
    decimals_consistent = tokenomics_report.get("rpc_decimals_consistent")

    if not supply_verified:
        flags.append("supply_unverified")
        reasons.append("Current total supply is not verified.")
    if decimals_consistent is False:
        flags.append("rpc_decimals_conflict")
        reasons.append("RPC sources disagree on token decimals.")

    if not mint_authority_verified or mint_state == "unavailable":
        flags.append("mint_authority_unverified")
        reasons.append("Mint-authority state is not verified.")
    elif mint_state == "active" and policy["warn_on_active_mint_authority"]:
        flags.append("mint_authority_active")
        reasons.append("Verified mint authority is active; future minting remains possible.")

    if not freeze_authority_verified or freeze_state == "unavailable":
        flags.append("freeze_authority_unverified")
        reasons.append("Freeze-authority state is not verified.")
    elif freeze_state == "active" and policy["warn_on_active_freeze_authority"]:
        flags.append("freeze_authority_active")
        reasons.append("Verified freeze authority is active.")

    activity = tokenomics_report.get("token_activity")
    activity_available = isinstance(activity, Mapping) and activity.get("available") is True
    activity_verified = activity_available and activity.get("activity_verified") is True
    if not activity_available:
        flags.append("token_activity_unavailable")
        reasons.append("Verified bounded mint/burn activity was not supplied.")
    elif not activity_verified:
        flags.append("token_activity_unverified")
        reasons.append("Mint/burn activity is present but its selected-window verification failed.")

    evidence = {
        "supply_verified": supply_verified,
        "mint_authority_state": mint_state,
        "freeze_authority_state": freeze_state,
        "rpc_decimals_consistent": decimals_consistent,
        "token_activity_verified": activity_verified,
        "token_activity_coverage_scope": (
            activity.get("coverage_scope") if isinstance(activity, Mapping) else None
        ),
        # Never reinterpret bounded scanner coverage as lifetime coverage.
        "lifetime_coverage_verified": (
            activity.get("lifetime_coverage_verified") is True
            if isinstance(activity, Mapping)
            else False
        ),
    }

    return _component(
        WARN if flags else PASS,
        available=True,
        flags=flags,
        reasons=reasons,
        evidence=evidence,
    )


def _confidence(
    market_report: Mapping[str, Any],
    tokenomics_report: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    _, liquidity_verified = _verified_market_metric(
        market_report, "liquidity_usd", "liquidity"
    )
    _, volume_verified = _verified_market_metric(
        market_report, "volume_24h_usd", "volume_24h"
    )
    _, transactions_verified = _verified_market_metric(
        market_report, "transactions_24h", "transactions_24h"
    )

    tokenomics = tokenomics_report if isinstance(tokenomics_report, Mapping) else {}
    activity = tokenomics.get("token_activity")
    checks = {
        "liquidity_verified": liquidity_verified,
        "volume_24h_verified": volume_verified,
        "transactions_24h_verified": transactions_verified,
        "supply_verified": tokenomics.get("supply_verified") is True,
        "mint_authority_verified": tokenomics.get("mint_authority_verified") is True,
        "freeze_authority_verified": tokenomics.get("freeze_authority_verified") is True,
        "token_activity_verified": (
            isinstance(activity, Mapping)
            and activity.get("available") is True
            and activity.get("activity_verified") is True
        ),
    }
    verified = sum(1 for value in checks.values() if value)
    total = len(checks)
    ratio = verified / total
    if verified == total:
        level = "high"
    elif verified >= 4:
        level = "medium"
    else:
        level = "low"

    return {
        "level": level,
        "verified_checks": verified,
        "total_checks": total,
        "verification_ratio": round(ratio, 6),
        "checks": checks,
    }


def build_risk_check(
    market_report: Mapping[str, Any],
    tokenomics_report: Optional[Mapping[str, Any]] = None,
    *,
    chain: str = "x1",
    policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate deterministic current-fact risk without collecting data.

    ``market_report`` and ``tokenomics_report`` are expected to come from the
    existing deterministic service layers. Missing or incomplete verification
    produces WARN rather than being silently converted to PASS. A verified
    asset-wide liquidity value of zero may produce BLOCK according to policy.

    PASS/WARN/BLOCK applies only to the currently implemented assessment scope:
    liquidity, 24h activity, tokenomics authorities, token activity, and source
    completeness. Holder-distribution, historical-volatility, and trade-impact
    risk remain explicit future layers rather than guessed values.
    """
    if not isinstance(market_report, Mapping):
        raise ValueError("market_report must be a mapping")
    chain_name = (_text(chain) or "").lower()
    if not chain_name:
        raise ValueError("chain is required")

    normalized_policy = _normalize_policy(policy)
    components = {
        "liquidity": _assess_liquidity(market_report, normalized_policy),
        "activity": _assess_activity(market_report, normalized_policy),
        "tokenomics": _assess_tokenomics(tokenomics_report, normalized_policy),
    }
    recommendation = _merge_status(
        *(component["status"] for component in components.values())
    )

    flags = []
    reasons = []
    for name in ("liquidity", "activity", "tokenomics"):
        component = components[name]
        flags.extend(component["flags"])
        reasons.extend(component["reasons"])

    return {
        "chain": chain_name,
        "asset": {
            "symbol": _text(market_report.get("symbol")),
            "mint": _text(market_report.get("mint")),
        },
        "recommendation": recommendation,
        "components": components,
        "confidence": _confidence(market_report, tokenomics_report),
        "flags": flags,
        "reasons": reasons,
        # Deliberately unavailable until a calibrated scoring model is defined.
        "score": None,
        "score_verified": False,
        "score_reason": "risk_score_not_calibrated",
        "policy": normalized_policy,
        "assessment_scope": {
            "included": [
                "liquidity",
                "activity_24h",
                "tokenomics_authorities",
                "bounded_token_activity",
                "source_completeness",
            ],
            "not_yet_included": [
                "holder_distribution",
                "historical_volatility",
                "trade_impact",
            ],
        },
    }


__all__ = [
    "BLOCK",
    "DEFAULT_RISK_POLICY",
    "PASS",
    "WARN",
    "build_risk_check",
]
