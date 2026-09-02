"""Deterministic freshness classification for live CMIS X1 market observations.

This verifies the age of the CMIS observation itself. It does NOT claim that
X1.Ninja's internal provider fact-time semantics are verified.
"""

from __future__ import annotations

import math
import time
from typing import Any


POLICY_ID = "cmis.x1.market.observation_freshness.v1"

# X1Provider keeps the XDEX catalog for up to 300 seconds.
# Observation freshness must cover that accepted cache lifetime plus a
# small deterministic processing margin. This verifies CMIS observation
# age only; it does not verify X1.Ninja provider fact-time semantics.
MAX_AGE_SECONDS = 60
MAX_FUTURE_SKEW_SECONDS = 5


def _timestamp(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def evaluate_market_observation_freshness(
    observed_at: Any,
    *,
    evaluated_at: Any = None,
) -> dict[str, Any]:
    observed = _timestamp(observed_at)
    evaluated = _timestamp(
        time.time() if evaluated_at is None else evaluated_at
    )

    if observed is None or evaluated is None:
        return {
            "policy_id": POLICY_ID,
            "scope": "cmis_observation_time",
            "classification": "unknown",
            "observed_at": observed,
            "evaluated_at": evaluated,
            "age_seconds": None,
            "max_age_seconds": MAX_AGE_SECONDS,
            "max_future_skew_seconds": MAX_FUTURE_SKEW_SECONDS,
            "freshness_policy_complete": True,
            "freshness_policy_applied": False,
            "observation_freshness_verified": False,
            "provider_fact_time_verified": False,
        }

    age = evaluated - observed

    if age < -MAX_FUTURE_SKEW_SECONDS:
        classification = "future"
        verified = False
    elif age <= MAX_AGE_SECONDS:
        classification = "fresh"
        verified = True
    else:
        classification = "stale"
        verified = False

    return {
        "policy_id": POLICY_ID,
        "scope": "cmis_observation_time",
        "classification": classification,
        "observed_at": observed,
        "evaluated_at": evaluated,
        "age_seconds": round(age, 6),
        "max_age_seconds": MAX_AGE_SECONDS,
        "max_future_skew_seconds": MAX_FUTURE_SKEW_SECONDS,
        "freshness_policy_complete": True,
        "freshness_policy_applied": True,
        "observation_freshness_verified": verified,

        # Important boundary:
        # a fresh CMIS observation does not prove X1.Ninja's internal
        # provider fact-time semantics.
        "provider_fact_time_verified": False,
    }


__all__ = [
    "POLICY_ID",
    "MAX_AGE_SECONDS",
    "MAX_FUTURE_SKEW_SECONDS",
    "evaluate_market_observation_freshness",
]
