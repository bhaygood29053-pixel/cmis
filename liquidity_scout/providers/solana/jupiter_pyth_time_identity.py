"""Deterministic Jupiter-Pyth Solana cross-source time-identity policy.

This policy is a CMIS operator comparison contract, not a Jupiter, Pyth, or
Solana SLA. It applies only after both source-specific freshness gates are
independently FRESH and exact mint/subject/unit semantics have already passed.

SAME_TIME is still analysis evidence only. It does not establish market-source
independence, equivalent price-construction methodology, current-price
promotion, Scout authority, risk authority, or execution authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.cmis.evidence import AGREEMENT, CONFLICT, INSUFFICIENT_EVIDENCE

VERSION = "solana_jupiter_pyth_time_identity/v1"

SAME_TIME = "SAME_TIME"
TIME_MISMATCH = "TIME_MISMATCH"
SOURCE_STALE = "SOURCE_STALE"
SOURCE_FUTURE = "SOURCE_FUTURE"
INVALID = "INVALID"
UNAVAILABLE = "UNAVAILABLE"
POLICY_UNVERIFIED = "POLICY_UNVERIFIED"

PRODUCTION_POLICY = {
    "policy_id": "cmis.solana.jupiter_pyth.same_time.v1",
    "max_fact_time_delta_seconds": 5,
    "max_fact_time_delta_provenance": (
        "CMIS cross-source synchronization contract for the exact "
        "Jupiter/Pyth Solana comparison path. Both provider fact times are "
        "Unix-second observations; Jupiter documents popular-token prices as "
        "updating every few seconds, while Pyth USDC/USD may remain valid "
        "until its one-minute heartbeat. CMIS therefore defines same-time "
        "much more strictly than source freshness: observations must be no "
        "more than five seconds apart. Five seconds is an operator comparison "
        "window, not a Jupiter, Pyth, or Solana SLA, and was selected "
        "independently of observed passing samples."
    ),
    "scope": "exact_verified_solana_mint_usd_price_pairs",
    "scope_provenance": (
        "Initial accepted implementation is exercised on the exact USDC mint "
        "/ Pyth USDC-USD fixture from issue #313. The policy is only applicable "
        "when exact mint, subject, USD unit, provider fact time, and both "
        "source-specific FRESH gates are verified."
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


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0:
        return None
    return parsed


def _canonical_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def normalize_jupiter_pyth_time_identity_policy(
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalize explicit policy without any numerical default."""

    if policy is None:
        policy = {}
    if not isinstance(policy, Mapping):
        raise ValueError("Jupiter-Pyth time-identity policy must be a mapping")

    policy_id = _text(policy.get("policy_id"))
    max_delta = _integer(
        policy.get("max_fact_time_delta_seconds"),
        name="max_fact_time_delta_seconds",
        minimum=0,
    )
    provenance = _text(policy.get("max_fact_time_delta_provenance"))
    scope = _text(policy.get("scope"))
    scope_provenance = _text(policy.get("scope_provenance"))

    complete = all(
        [
            policy_id is not None,
            max_delta is not None,
            provenance is not None,
            scope is not None,
            scope_provenance is not None,
        ]
    )
    return {
        "policy_id": policy_id,
        "max_fact_time_delta_seconds": max_delta,
        "max_fact_time_delta_provenance": provenance,
        "scope": scope,
        "scope_provenance": scope_provenance,
        "policy_complete": complete,
        "has_hidden_defaults": False,
    }


def accepted_jupiter_pyth_time_identity_policy() -> dict[str, Any]:
    return dict(PRODUCTION_POLICY)


def classify_jupiter_pyth_time_identity(
    crosscheck: Mapping[str, Any],
    jupiter_freshness: Mapping[str, Any],
    pyth_freshness: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Classify exact Jupiter/Pyth fact-time compatibility."""

    if not all(
        isinstance(record, Mapping)
        for record in (crosscheck, jupiter_freshness, pyth_freshness)
    ):
        raise TypeError("time-identity inputs must be mappings")

    normalized = normalize_jupiter_pyth_time_identity_policy(policy)
    base = {
        "version": VERSION,
        "policy": normalized,
        "classification": POLICY_UNVERIFIED,
        "classification_verified": False,
        "cross_source_time_identity_verified": False,
        "same_time_candidate": False,
        "numerical_price_agreement": (
            crosscheck.get("status") == AGREEMENT
            and crosscheck.get("within_tolerance") is True
        ),
        "fact_time_delta_seconds": None,
        "source_independence_verified": False,
        "price_construction_equivalence_verified": False,
        "current_price_promotable": False,
        "execution_authorized": False,
    }

    if not normalized["policy_complete"]:
        return {**base, "reason": "time_identity_policy_incomplete"}

    if crosscheck.get("service") != "solana_jupiter_pyth_price_crosscheck":
        return {
            **base,
            "classification": INVALID,
            "reason": "crosscheck_contract_invalid",
        }
    if crosscheck.get("chain") != "solana":
        return {
            **base,
            "classification": INVALID,
            "reason": "crosscheck_chain_invalid",
        }
    crosscheck_status = crosscheck.get("status")
    if crosscheck_status == INSUFFICIENT_EVIDENCE:
        return {
            **base,
            "classification": UNAVAILABLE,
            "reason": "crosscheck_evidence_unavailable",
        }
    if crosscheck_status not in {AGREEMENT, CONFLICT}:
        return {
            **base,
            "classification": INVALID,
            "reason": "crosscheck_status_invalid",
        }
    if (
        crosscheck.get("identity_verified") is not True
        or crosscheck.get("semantics_verified") is not True
    ):
        return {
            **base,
            "classification": INVALID,
            "reason": "crosscheck_identity_or_semantics_unverified",
        }

    jupiter_class = _text(jupiter_freshness.get("classification"))
    pyth_class = _text(pyth_freshness.get("classification"))

    if jupiter_class == "INVALID" or pyth_class == "INVALID":
        return {
            **base,
            "classification": INVALID,
            "reason": "source_freshness_invalid",
        }
    if jupiter_class == "FUTURE" or pyth_class == "FUTURE":
        return {
            **base,
            "classification": SOURCE_FUTURE,
            "classification_verified": True,
            "reason": "one_or_more_sources_future",
        }
    if jupiter_class == "STALE" or pyth_class == "STALE":
        return {
            **base,
            "classification": SOURCE_STALE,
            "classification_verified": True,
            "reason": "one_or_more_sources_stale",
        }
    if jupiter_class == "POLICY_UNVERIFIED" or pyth_class == "POLICY_UNVERIFIED":
        return {
            **base,
            "classification": POLICY_UNVERIFIED,
            "reason": "one_or_more_source_freshness_policies_unverified",
        }
    if (
        jupiter_class in {"UNAVAILABLE", None}
        or pyth_class in {"UNAVAILABLE", None}
    ):
        return {
            **base,
            "classification": UNAVAILABLE,
            "reason": "one_or_more_source_freshness_gates_unavailable",
        }

    if (
        jupiter_class != "FRESH"
        or pyth_class != "FRESH"
        or jupiter_freshness.get("jupiter_current_price_eligible") is not True
        or pyth_freshness.get("pyth_current_price_eligible") is not True
    ):
        return {
            **base,
            "classification": INVALID,
            "reason": "source_freshness_contract_inconsistent",
        }

    jupiter_time = _decimal(crosscheck.get("jupiter_fact_time_unix"))
    pyth_time = _decimal(crosscheck.get("pyth_fact_time_unix"))
    reported_delta = _decimal(crosscheck.get("fact_time_delta_seconds"))
    if jupiter_time is None or pyth_time is None or reported_delta is None:
        return {
            **base,
            "classification": UNAVAILABLE,
            "reason": "cross_source_fact_time_unavailable",
        }

    computed_delta = abs(jupiter_time - pyth_time)
    if computed_delta != reported_delta:
        return {
            **base,
            "classification": INVALID,
            "reason": "cross_source_fact_time_delta_mismatch",
        }

    result = {
        **base,
        "classification_verified": True,
        "fact_time_delta_seconds": _canonical_decimal(computed_delta),
        "jupiter_fact_time_unix": _canonical_decimal(jupiter_time),
        "pyth_fact_time_unix": _canonical_decimal(pyth_time),
    }

    if computed_delta > Decimal(normalized["max_fact_time_delta_seconds"]):
        return {
            **result,
            "classification": TIME_MISMATCH,
            "reason": "fact_time_delta_exceeds_policy",
        }

    return {
        **result,
        "classification": SAME_TIME,
        "cross_source_time_identity_verified": True,
        "same_time_candidate": True,
        "reason": "fact_time_delta_satisfies_explicit_policy",
    }


__all__ = [
    "INVALID",
    "POLICY_UNVERIFIED",
    "PRODUCTION_POLICY",
    "SAME_TIME",
    "SOURCE_FUTURE",
    "SOURCE_STALE",
    "TIME_MISMATCH",
    "UNAVAILABLE",
    "VERSION",
    "accepted_jupiter_pyth_time_identity_policy",
    "classify_jupiter_pyth_time_identity",
    "normalize_jupiter_pyth_time_identity_policy",
]
