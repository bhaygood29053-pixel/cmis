"""Deterministic source-specific freshness policy for Pyth Core on Solana."""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

FRESH = "FRESH"
STALE = "STALE"
FUTURE = "FUTURE"
INVALID = "INVALID"
UNAVAILABLE = "UNAVAILABLE"
POLICY_UNVERIFIED = "POLICY_UNVERIFIED"

PRODUCTION_POLICY = {
    "policy_id": "cmis.solana.pyth_core.current_price_freshness.v1",
    "max_age_seconds": 60,
    "max_age_provenance": (
        "CMIS current-price evidence contract: a verified Pyth publish_time "
        "older than one minute at the post-read CMIS collection clock is not "
        "current. This is a CMIS operator governance bound selected "
        "independently of observed Pyth ages. The accepted sponsored USDC/USD "
        "Solana push feed is documented with a 1-minute heartbeat, which is "
        "source context rather than a freshness SLA."
    ),
    "max_future_skew_seconds": 5,
    "future_skew_provenance": (
        "CMIS clock-reference contract: allow at most five seconds of positive "
        "Pyth publish_time skew relative to the post-read CMIS UTC collection "
        "clock; larger future offsets fail closed. This is an operator "
        "governance bound, not a Pyth or Solana SLA."
    ),
}


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _integer(value: object, *, name: str, minimum: int) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().lstrip("+").isdigit():
        parsed = int(value)
    else:
        raise ValueError(f"{name} must be an integer")
    if parsed < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return parsed


def _timestamp(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        return None
    return parsed


def normalize_pyth_freshness_policy(
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if policy is None:
        policy = {}
    if not isinstance(policy, Mapping):
        raise ValueError("Pyth freshness policy must be a mapping")

    policy_id = _text(policy.get("policy_id"))
    max_age_seconds = _integer(
        policy.get("max_age_seconds"),
        name="max_age_seconds",
        minimum=1,
    )
    max_future_skew_seconds = _integer(
        policy.get("max_future_skew_seconds"),
        name="max_future_skew_seconds",
        minimum=0,
    )
    max_age_provenance = _text(policy.get("max_age_provenance"))
    future_skew_provenance = _text(policy.get("future_skew_provenance"))
    complete = all(
        [
            policy_id is not None,
            max_age_seconds is not None,
            max_future_skew_seconds is not None,
            max_age_provenance is not None,
            future_skew_provenance is not None,
        ]
    )
    return {
        "policy_id": policy_id,
        "max_age_seconds": max_age_seconds,
        "max_age_provenance": max_age_provenance,
        "max_future_skew_seconds": max_future_skew_seconds,
        "future_skew_provenance": future_skew_provenance,
        "policy_complete": complete,
        "has_hidden_defaults": False,
    }


def accepted_pyth_freshness_policy() -> dict[str, Any]:
    return dict(PRODUCTION_POLICY)


def classify_pyth_freshness(
    record: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise TypeError("Pyth record must be a mapping")

    normalized = normalize_pyth_freshness_policy(policy)
    base = {
        "policy": normalized,
        "classification": POLICY_UNVERIFIED,
        "classification_verified": False,
        "pyth_freshness_verified": False,
        "pyth_current_price_eligible": False,
        "fact_time_unix": None,
        "reference_time_unix": None,
        "signed_age_seconds": None,
        "effective_age_seconds": None,
        "future_offset_seconds": None,
        "current_price_promotable": False,
        "cross_source_time_identity_verified": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }

    if not normalized["policy_complete"]:
        return {**base, "reason": "freshness_policy_incomplete"}

    if record.get("chain") != "solana" or record.get("source") != "pyth_core_solana_push":
        return {
            **base,
            "classification": INVALID,
            "reason": "pyth_source_provenance_invalid",
        }
    if record.get("mapping_verified") is not True:
        return {
            **base,
            "classification": UNAVAILABLE,
            "reason": "pyth_exact_mapping_unavailable",
        }
    if record.get("fact_time_verified") is not True:
        return {
            **base,
            "classification": UNAVAILABLE,
            "reason": "pyth_publish_time_unavailable",
        }
    if record.get("collection_time_verified") is not True:
        return {
            **base,
            "classification": INVALID,
            "reason": "pyth_collection_time_unverified",
        }
    if record.get("price_integrity_verified") is not True:
        return {
            **base,
            "classification": INVALID,
            "reason": "pyth_price_integrity_unverified",
        }

    fact_time = _timestamp(record.get("publish_time_unix"))
    reference_time = _timestamp(record.get("collection_completed_at_unix"))
    if fact_time is None or reference_time is None:
        return {
            **base,
            "classification": INVALID,
            "reason": "fact_or_reference_time_invalid",
        }

    signed_age = reference_time - fact_time
    result = {
        **base,
        "fact_time_unix": fact_time,
        "reference_time_unix": reference_time,
        "signed_age_seconds": signed_age,
    }
    if signed_age < 0:
        future_offset = -signed_age
        result["future_offset_seconds"] = future_offset
        if future_offset > normalized["max_future_skew_seconds"]:
            return {
                **result,
                "classification": FUTURE,
                "classification_verified": True,
                "pyth_freshness_verified": True,
                "reason": "publish_time_exceeds_future_skew_policy",
            }
        effective_age = 0.0
    else:
        effective_age = signed_age

    result["effective_age_seconds"] = effective_age
    if effective_age > normalized["max_age_seconds"]:
        return {
            **result,
            "classification": STALE,
            "classification_verified": True,
            "pyth_freshness_verified": True,
            "reason": "publish_time_exceeds_max_age_policy",
        }

    return {
        **result,
        "classification": FRESH,
        "classification_verified": True,
        "pyth_freshness_verified": True,
        "pyth_current_price_eligible": True,
        "reason": "publish_time_satisfies_explicit_policy",
    }


__all__ = [
    "FRESH",
    "FUTURE",
    "INVALID",
    "POLICY_UNVERIFIED",
    "PRODUCTION_POLICY",
    "STALE",
    "UNAVAILABLE",
    "accepted_pyth_freshness_policy",
    "classify_pyth_freshness",
    "normalize_pyth_freshness_policy",
]
