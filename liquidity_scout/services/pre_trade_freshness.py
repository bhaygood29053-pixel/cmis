"""Deterministic freshness assessment for CMIS pre-trade analysis.

This module performs no collection and owns no default freshness threshold. It
compares an already-observed risk timestamp with the pre-trade evaluation time
and applies only explicit caller policy thresholds.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .pre_trade_liquidity import normalize_pre_trade_policy
from .risk import BLOCK, PASS, WARN


VERSION = "1.0"


def _epoch(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")) or number < 0:
            return None
        return number

    text = str(value).strip()
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    epoch = parsed.timestamp()
    if epoch < 0:
        return None
    return epoch


def assess_risk_freshness(
    *,
    risk_observed_at: Any,
    evaluated_at: Any,
    policy=None,
) -> Dict[str, Any]:
    """Assess risk-evidence age without inventing a freshness window."""
    normalized_policy = normalize_pre_trade_policy(policy)
    warn_age = normalized_policy["warn_risk_age_seconds"]
    block_age = normalized_policy["block_risk_age_seconds"]
    policy_active = warn_age is not None or block_age is not None

    risk_epoch = _epoch(risk_observed_at)
    evaluated_epoch = _epoch(evaluated_at)
    age_seconds = None
    complete = False
    if risk_epoch is not None and evaluated_epoch is not None and risk_epoch <= evaluated_epoch:
        age_seconds = evaluated_epoch - risk_epoch
        complete = True

    evidence = {
        "risk_observed_at": risk_observed_at,
        "evaluated_at": evaluated_at,
        "risk_observed_at_epoch": risk_epoch,
        "evaluated_at_epoch": evaluated_epoch,
        "risk_age_seconds": age_seconds,
        "warn_risk_age_seconds": warn_age,
        "block_risk_age_seconds": block_age,
        "freshness_policy_active": policy_active,
        "freshness_assessment_complete": complete if policy_active else True,
    }

    if not policy_active:
        return {
            "status": PASS,
            "flags": [],
            "reasons": [],
            "evidence": evidence,
            "policy": normalized_policy,
        }

    flags = []
    reasons = []
    if risk_epoch is None:
        flags.append("risk_timestamp_unverified_for_freshness")
        reasons.append(
            "The risk evidence timestamp is missing or invalid while an explicit freshness policy is active."
        )
    if evaluated_epoch is None:
        flags.append("evaluation_timestamp_unverified_for_freshness")
        reasons.append(
            "The pre-trade evaluation timestamp is missing or invalid while an explicit freshness policy is active."
        )
    if risk_epoch is not None and evaluated_epoch is not None and risk_epoch > evaluated_epoch:
        flags.append("risk_timestamp_after_evaluation")
        reasons.append(
            "The risk evidence timestamp occurs after the pre-trade evaluation timestamp."
        )

    if flags:
        blocking = normalized_policy[
            "block_on_unverified_timestamp_when_age_policy_set"
        ]
        return {
            "status": BLOCK if blocking else WARN,
            "flags": flags,
            "reasons": reasons,
            "evidence": evidence,
            "policy": normalized_policy,
        }

    evidence["freshness_assessment_complete"] = True

    if block_age is not None and age_seconds >= block_age:
        return {
            "status": BLOCK,
            "flags": ["risk_evidence_stale_block"],
            "reasons": [
                "Risk evidence age meets or exceeds the explicit pre-trade block threshold."
            ],
            "evidence": evidence,
            "policy": normalized_policy,
        }

    if warn_age is not None and age_seconds >= warn_age:
        return {
            "status": WARN,
            "flags": ["risk_evidence_stale_warn"],
            "reasons": [
                "Risk evidence age meets or exceeds the explicit pre-trade warning threshold."
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


__all__ = ["VERSION", "assess_risk_freshness"]
