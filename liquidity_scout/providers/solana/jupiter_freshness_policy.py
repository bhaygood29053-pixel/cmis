"""Deterministic Solana Jupiter current-price freshness policy.

The numerical production policy is explicit CMIS governance. It is not a
Jupiter SLA and is not derived from the ages observed in live responses.

A policy-qualified Jupiter fact still does not establish DEX Screener
freshness, cross-source time identity, source independence, or current-price
promotion.
"""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

VERSION = "solana_jupiter_freshness_policy/v1"

FRESH = "FRESH"
STALE = "STALE"
FUTURE = "FUTURE"
INVALID = "INVALID"
UNAVAILABLE = "UNAVAILABLE"
POLICY_UNVERIFIED = "POLICY_UNVERIFIED"

CLASSIFICATIONS = frozenset({
    FRESH,
    STALE,
    FUTURE,
    INVALID,
    UNAVAILABLE,
    POLICY_UNVERIFIED,
})

PRODUCTION_POLICY = {
    "policy_id": "cmis.solana.jupiter.current_price_freshness.v1",
    "max_age_seconds": 60,
    "max_age_provenance": (
        "CMIS current-price evidence contract: a candidate market observation "
        "older than one minute at the post-read CMIS collection clock is not "
        "current. This is an operator governance bound selected independently "
        "of observed Jupiter Price V3 ages and matches the accepted cross-chain "
        "CMIS current-price horizon used for X1 Oracle V2."
    ),
    "max_future_skew_seconds": 5,
    "future_skew_provenance": (
        "CMIS clock-reference contract: allow at most five seconds of positive "
        "provider-fact time skew relative to the post-read CMIS UTC collection "
        "clock; larger future offsets fail closed. This is an operator governance "
        "bound, not a Jupiter or Solana SLA and not derived from observed ages."
    ),
}


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


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


def normalize_solana_jupiter_freshness_policy(
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalize explicit policy without numerical defaults."""

    if policy is None:
        policy = {}
    if not isinstance(policy, Mapping):
        raise ValueError("Solana Jupiter freshness policy must be a mapping")

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
    policy_id = _text(policy.get("policy_id"))

    complete = all([
        policy_id is not None,
        max_age_seconds is not None,
        max_future_skew_seconds is not None,
        max_age_provenance is not None,
        future_skew_provenance is not None,
    ])

    return {
        "policy_id": policy_id,
        "max_age_seconds": max_age_seconds,
        "max_age_provenance": max_age_provenance,
        "max_future_skew_seconds": max_future_skew_seconds,
        "future_skew_provenance": future_skew_provenance,
        "policy_complete": complete,
        "has_hidden_defaults": False,
    }


def accepted_solana_jupiter_freshness_policy() -> dict[str, Any]:
    """Return a copy of the accepted production CMIS policy."""

    return dict(PRODUCTION_POLICY)


def classify_solana_jupiter_freshness(
    freshness_evidence: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Classify one Jupiter fact-time against an explicit freshness policy."""

    if not isinstance(freshness_evidence, Mapping):
        raise TypeError("freshness_evidence must be a mapping")

    normalized = normalize_solana_jupiter_freshness_policy(policy)
    base = {
        "policy": normalized,
        "classification": POLICY_UNVERIFIED,
        "classification_verified": False,
        "jupiter_freshness_verified": False,
        "jupiter_current_price_eligible": False,
        "fact_time_unix": None,
        "reference_time_unix": None,
        "signed_age_seconds": None,
        "effective_age_seconds": None,
        "future_offset_seconds": None,
        "dexscreener_freshness_verified": False,
        "cross_source_time_identity_verified": False,
        "current_price_promotable": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }

    if not normalized["policy_complete"]:
        return {
            **base,
            "classification": POLICY_UNVERIFIED,
            "reason": "freshness_policy_incomplete",
        }

    if freshness_evidence.get("chain") != "solana":
        return {
            **base,
            "classification": INVALID,
            "reason": "wrong_chain",
        }

    jupiter = freshness_evidence.get("jupiter")
    if not isinstance(jupiter, Mapping):
        return {
            **base,
            "classification": INVALID,
            "reason": "jupiter_freshness_evidence_invalid",
        }

    if jupiter.get("provider_fact_time_verified") is not True:
        return {
            **base,
            "classification": UNAVAILABLE,
            "reason": "jupiter_provider_fact_time_unavailable",
        }
    if jupiter.get("collection_time_verified") is not True:
        return {
            **base,
            "classification": INVALID,
            "reason": "jupiter_collection_time_unverified",
        }
    if (
        jupiter.get("reference_slot_verified") is True
        and jupiter.get("block_at_or_before_reference_slot") is not True
    ):
        return {
            **base,
            "classification": INVALID,
            "reason": "jupiter_block_after_reference_slot",
        }

    fact_time = _timestamp(jupiter.get("provider_fact_time_unix"))
    reference_time = _timestamp(jupiter.get("collection_completed_at_unix"))
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
                "jupiter_freshness_verified": True,
                "reason": "fact_time_exceeds_future_skew_policy",
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
            "jupiter_freshness_verified": True,
            "reason": "fact_time_exceeds_max_age_policy",
        }

    return {
        **result,
        "classification": FRESH,
        "classification_verified": True,
        "jupiter_freshness_verified": True,
        "jupiter_current_price_eligible": True,
        "reason": "fact_time_satisfies_explicit_policy",
    }


__all__ = [
    "CLASSIFICATIONS",
    "FRESH",
    "FUTURE",
    "INVALID",
    "POLICY_UNVERIFIED",
    "PRODUCTION_POLICY",
    "STALE",
    "UNAVAILABLE",
    "VERSION",
    "accepted_solana_jupiter_freshness_policy",
    "classify_solana_jupiter_freshness",
    "normalize_solana_jupiter_freshness_policy",
]
