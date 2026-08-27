"""Deterministic Oracle V2 timestamp-unit and freshness policy.

This module owns no live collection and no production freshness defaults.
Callers must supply explicit policy values with provenance and independently
verified timestamp-unit evidence before any Oracle V2 slot can become eligible.

The accepted timestamp-unit verification method is correlation of a raw Oracle
timestamp against verified X1 transaction/block time. The numerical correlation
tolerance is also explicit policy input; CMIS does not invent one.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping


VERSION = "1.0"
TIMESTAMP_UNIT_UNIX_MS = "unix_ms"
TIMESTAMP_UNIT_METHOD_X1_BLOCK_TIME = "x1_block_time_correlation"

FRESH = "fresh"
STALE = "stale"
FUTURE = "future"
INVALID = "invalid"
MISSING = "missing"
UNIT_UNVERIFIED = "unit_unverified"

CLASSIFICATIONS = frozenset({
    FRESH,
    STALE,
    FUTURE,
    INVALID,
    MISSING,
    UNIT_UNVERIFIED,
})


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _integer(value: Any, *, name: str, minimum: int | None = None) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if str(value).strip() not in {str(parsed), f"+{parsed}"}:
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return parsed


def normalize_oracle_v2_freshness_policy(policy: Mapping[str, Any] | None):
    """Normalize explicit operator-owned Oracle V2 freshness policy.

    No numerical defaults are supplied. Missing values keep the policy
    incomplete and therefore incapable of making a slot CMIS-price-eligible.
    """
    if policy is None:
        policy = {}
    if not isinstance(policy, Mapping):
        raise ValueError("Oracle V2 freshness policy must be a mapping")

    max_age_ms = _integer(
        policy.get("max_age_ms"),
        name="max_age_ms",
        minimum=1,
    )
    max_future_skew_ms = _integer(
        policy.get("max_future_skew_ms"),
        name="max_future_skew_ms",
        minimum=0,
    )
    minimum_eligible_slots = _integer(
        policy.get("minimum_eligible_slots"),
        name="minimum_eligible_slots",
        minimum=1,
    )
    if minimum_eligible_slots is not None and minimum_eligible_slots > 5:
        raise ValueError("minimum_eligible_slots must be <= 5")

    max_age_provenance = _text(policy.get("max_age_provenance"))
    future_skew_provenance = _text(policy.get("future_skew_provenance"))
    minimum_slots_provenance = _text(
        policy.get("minimum_eligible_slots_provenance")
    )

    complete = all([
        max_age_ms is not None,
        max_future_skew_ms is not None,
        minimum_eligible_slots is not None,
        max_age_provenance is not None,
        future_skew_provenance is not None,
        minimum_slots_provenance is not None,
    ])

    return {
        "max_age_ms": max_age_ms,
        "max_age_provenance": max_age_provenance,
        "max_future_skew_ms": max_future_skew_ms,
        "future_skew_provenance": future_skew_provenance,
        "minimum_eligible_slots": minimum_eligible_slots,
        "minimum_eligible_slots_provenance": minimum_slots_provenance,
        "policy_complete": complete,
        "has_hidden_defaults": False,
    }


def assess_unix_ms_block_time_correlation(
    *,
    timestamp_raw: Any,
    block_time_seconds: Any,
    max_difference_ms: Any,
    tolerance_provenance: Any,
):
    """Assess candidate Unix-ms semantics against verified X1 block time.

    This is evidence about timestamp-unit semantics, not freshness and not price
    correctness. The caller must supply the correlation tolerance and its
    provenance explicitly.
    """
    timestamp = _integer(
        timestamp_raw,
        name="timestamp_raw",
        minimum=1,
    )
    if timestamp is None:
        raise ValueError("timestamp_raw is required")

    block_time = _integer(
        block_time_seconds,
        name="block_time_seconds",
        minimum=0,
    )
    if block_time is None:
        raise ValueError("block_time_seconds is required")

    tolerance = _integer(
        max_difference_ms,
        name="max_difference_ms",
        minimum=0,
    )
    if tolerance is None:
        raise ValueError("max_difference_ms is required")

    provenance = _text(tolerance_provenance)
    if provenance is None:
        raise ValueError("tolerance_provenance is required")

    block_time_ms = block_time * 1000
    difference_ms = abs(timestamp - block_time_ms)
    verified = difference_ms <= tolerance

    return {
        "timestamp_unit": TIMESTAMP_UNIT_UNIX_MS,
        "method": TIMESTAMP_UNIT_METHOD_X1_BLOCK_TIME,
        "verified": verified,
        "timestamp_raw": timestamp,
        "block_time_seconds": block_time,
        "block_time_ms": block_time_ms,
        "difference_ms": difference_ms,
        "max_difference_ms": tolerance,
        "tolerance_provenance": provenance,
        "freshness_verified": False,
        "price_correctness_verified": False,
        "source_independence_verified": False,
    }


def normalize_timestamp_unit_evidence(evidence: Mapping[str, Any] | None):
    """Normalize timestamp-unit evidence and fail closed on unsupported methods."""
    if evidence is None:
        evidence = {}
    if not isinstance(evidence, Mapping):
        raise ValueError("timestamp unit evidence must be a mapping")

    timestamp_unit = _text(evidence.get("timestamp_unit"))
    method = _text(evidence.get("method"))
    verified = evidence.get("verified") is True
    provenance = _text(
        evidence.get("provenance")
        or evidence.get("tolerance_provenance")
    )

    accepted = bool(
        verified
        and timestamp_unit == TIMESTAMP_UNIT_UNIX_MS
        and method == TIMESTAMP_UNIT_METHOD_X1_BLOCK_TIME
        and provenance
    )

    return {
        "timestamp_unit": timestamp_unit,
        "method": method,
        "verified": verified,
        "provenance": provenance,
        "accepted_for_policy": accepted,
    }


def classify_oracle_v2_slot(
    *,
    price_raw: Any,
    timestamp_raw: Any,
    observed_at_ms: Any,
    policy: Mapping[str, Any] | None,
    timestamp_unit_evidence: Mapping[str, Any] | None,
):
    """Classify one Oracle V2 slot using only explicit verified inputs."""
    normalized_policy = normalize_oracle_v2_freshness_policy(policy)
    unit_evidence = normalize_timestamp_unit_evidence(timestamp_unit_evidence)

    base = {
        "price_raw": price_raw,
        "timestamp_raw": timestamp_raw,
        "observed_at_ms": observed_at_ms,
        "timestamp_unit": unit_evidence["timestamp_unit"],
        "timestamp_unit_method": unit_evidence["method"],
        "timestamp_unit_verified": unit_evidence["accepted_for_policy"],
        "timestamp_unit_provenance": unit_evidence["provenance"],
        "max_age_ms": normalized_policy["max_age_ms"],
        "max_age_provenance": normalized_policy["max_age_provenance"],
        "max_future_skew_ms": normalized_policy["max_future_skew_ms"],
        "future_skew_provenance": normalized_policy[
            "future_skew_provenance"
        ],
        "policy_complete": normalized_policy["policy_complete"],
        "age_ms": None,
        "future_offset_ms": None,
        "cmis_price_eligible": False,
    }

    if price_raw is None or timestamp_raw is None:
        return {
            **base,
            "classification": MISSING,
            "reason": "price_or_timestamp_missing",
        }

    try:
        price = _integer(price_raw, name="price_raw")
        timestamp = _integer(timestamp_raw, name="timestamp_raw")
        observed = _integer(
            observed_at_ms,
            name="observed_at_ms",
            minimum=0,
        )
    except ValueError:
        return {
            **base,
            "classification": INVALID,
            "reason": "price_timestamp_or_observation_invalid",
        }

    if price is None or timestamp is None or observed is None:
        return {
            **base,
            "classification": MISSING,
            "reason": "price_timestamp_or_observation_missing",
        }

    base["price_raw"] = price
    base["timestamp_raw"] = timestamp
    base["observed_at_ms"] = observed

    if price <= 0 or timestamp <= 0:
        return {
            **base,
            "classification": INVALID,
            "reason": "price_and_timestamp_must_be_positive",
        }

    if not unit_evidence["accepted_for_policy"]:
        return {
            **base,
            "classification": UNIT_UNVERIFIED,
            "reason": "timestamp_unit_not_verified_for_policy",
        }

    if not normalized_policy["policy_complete"]:
        return {
            **base,
            "classification": INVALID,
            "reason": "freshness_policy_incomplete",
        }

    signed_age_ms = observed - timestamp
    base["age_ms"] = signed_age_ms

    if signed_age_ms < 0:
        future_offset_ms = -signed_age_ms
        base["future_offset_ms"] = future_offset_ms
        if future_offset_ms > normalized_policy["max_future_skew_ms"]:
            return {
                **base,
                "classification": FUTURE,
                "reason": "timestamp_exceeds_future_skew_policy",
            }
        # A timestamp inside explicitly accepted clock skew is not treated as
        # negative age for the maximum-age comparison.
        effective_age_ms = 0
    else:
        effective_age_ms = signed_age_ms

    if effective_age_ms > normalized_policy["max_age_ms"]:
        return {
            **base,
            "classification": STALE,
            "reason": "timestamp_exceeds_max_age_policy",
        }

    return {
        **base,
        "classification": FRESH,
        "reason": "timestamp_satisfies_explicit_policy",
        "cmis_price_eligible": True,
    }


def _decimal_price(numerator: int, denominator: int, decimals: int) -> str:
    value = (
        Decimal(numerator)
        / Decimal(denominator)
        / (Decimal(10) ** decimals)
    )
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def aggregate_oracle_v2_slots(
    slots,
    *,
    observed_at_ms: Any,
    policy: Mapping[str, Any] | None,
    timestamp_unit_evidence: Mapping[str, Any] | None,
    decimals: int = 6,
):
    """Classify slots and calculate an exact candidate median when eligible."""
    normalized_policy = normalize_oracle_v2_freshness_policy(policy)

    if isinstance(slots, (str, bytes)) or not isinstance(slots, (list, tuple)):
        raise ValueError("slots must be a list or tuple")

    classifications = []
    for index, slot in enumerate(slots, start=1):
        if not isinstance(slot, Mapping):
            result = {
                "price_raw": None,
                "timestamp_raw": None,
                "observed_at_ms": observed_at_ms,
                "classification": INVALID,
                "reason": "slot_record_invalid",
                "cmis_price_eligible": False,
            }
        else:
            result = classify_oracle_v2_slot(
                price_raw=slot.get("price_raw"),
                timestamp_raw=slot.get("timestamp_raw"),
                observed_at_ms=observed_at_ms,
                policy=normalized_policy,
                timestamp_unit_evidence=timestamp_unit_evidence,
            )
        classifications.append({
            "relay_index": slot.get("relay_index", index)
            if isinstance(slot, Mapping)
            else index,
            **result,
        })

    eligible = [
        item["price_raw"]
        for item in classifications
        if item.get("cmis_price_eligible") is True
    ]
    eligible.sort()

    minimum = normalized_policy["minimum_eligible_slots"]
    if minimum is None:
        status = "unavailable"
        reason = "minimum_eligible_slots_unconfigured"
        enough = False
    elif len(eligible) == 0:
        status = "unavailable"
        reason = "no_eligible_slots"
        enough = False
    elif len(eligible) < minimum:
        status = "partial"
        reason = "insufficient_eligible_slots"
        enough = False
    else:
        status = "ok"
        reason = "minimum_eligible_slots_satisfied"
        enough = True

    median_numerator = None
    median_denominator = None
    median_price = None

    if enough:
        count = len(eligible)
        middle = count // 2
        if count % 2:
            median_numerator = eligible[middle]
            median_denominator = 1
        else:
            median_numerator = eligible[middle - 1] + eligible[middle]
            median_denominator = 2
        median_price = _decimal_price(
            median_numerator,
            median_denominator,
            decimals,
        )

    counts = {classification: 0 for classification in CLASSIFICATIONS}
    for item in classifications:
        classification = item["classification"]
        if classification in counts:
            counts[classification] += 1

    return {
        "status": status,
        "reason": reason,
        "policy": normalized_policy,
        "timestamp_unit_evidence": normalize_timestamp_unit_evidence(
            timestamp_unit_evidence
        ),
        "observed_at_ms": observed_at_ms,
        "slot_classifications": classifications,
        "classification_counts": counts,
        "eligible_slot_count": len(eligible),
        "minimum_eligible_slots": minimum,
        "median_price_raw_numerator": median_numerator,
        "median_price_raw_denominator": median_denominator,
        "median_price": median_price,
        "median_decimals": decimals,
        "current_price_use_authorized": False,
        "cmis_provider_promoted": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "source_independence_verified": False,
        "execution_authorized": False,
        "warnings": [
            (
                "Eligible relay slots are same-system Oracle V2 redundancy and "
                "must not be counted as independent market sources."
            ),
            (
                "A policy-qualified candidate median does not itself authorize "
                "CMIS provider/public-service/Scout promotion."
            ),
        ],
    }


__all__ = [
    "CLASSIFICATIONS",
    "FRESH",
    "FUTURE",
    "INVALID",
    "MISSING",
    "STALE",
    "TIMESTAMP_UNIT_METHOD_X1_BLOCK_TIME",
    "TIMESTAMP_UNIT_UNIX_MS",
    "UNIT_UNVERIFIED",
    "VERSION",
    "aggregate_oracle_v2_slots",
    "assess_unix_ms_block_time_correlation",
    "classify_oracle_v2_slot",
    "normalize_oracle_v2_freshness_policy",
    "normalize_timestamp_unit_evidence",
]
