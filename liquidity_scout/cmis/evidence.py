"""Deterministic CMIS evidence and same-fact verification primitives.

This module does not fetch provider data and does not decide financial
semantics. It records already-observed facts with explicit provenance and
compares only facts whose identity and units are compatible.

Conflicting observations are never averaged. Missing, malformed, differently
scoped, or differently-unitized observations fail closed. Distinct provider
labels are observable provenance but are not proof of upstream independence.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional


AGREEMENT = "AGREEMENT"
CONFLICT = "CONFLICT"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
UNIT_MISMATCH = "UNIT_MISMATCH"
VALUE_MISSING = "VALUE_MISSING"
VALUE_INVALID = "VALUE_INVALID"
SINGLE_SOURCE_ONLY = "SINGLE_SOURCE_ONLY"
SOURCE_INDEPENDENCE_UNPROVEN = "SOURCE_INDEPENDENCE_UNPROVEN"
SOURCE_INDEPENDENCE_FAILED = "SOURCE_INDEPENDENCE_FAILED"
VALUES_AGREE = "VALUES_AGREE"
VALUES_DISAGREE = "VALUES_DISAGREE"

VERIFICATION_STATUSES = frozenset({
    AGREEMENT,
    CONFLICT,
    INSUFFICIENT_EVIDENCE,
})


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal_text(value: Any) -> Optional[str]:
    """Return a canonical decimal string without float coercion."""
    if value is None or isinstance(value, bool):
        return None

    text = _text(value)
    if text is None:
        return None

    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        return None

    if not parsed.is_finite():
        return None

    normalized = format(parsed, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")

    if normalized in {"", "-0"}:
        normalized = "0"

    return normalized


def build_evidence_observation(
    *,
    chain: Any,
    fact_type: Any,
    subject_id: Any,
    source: Any,
    source_role: Any,
    observed_at: Any,
    raw_value: Any,
    normalized_value: Any = None,
    unit: Any = None,
    block_slot: Any = None,
    raw_identifier: Any = None,
    calculation_version: Any = None,
    semantics_verified: bool = False,
    identity_verified: bool = False,
    freshness_verified: bool = False,
    warnings: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """Build one auditable provider/RPC evidence record.

    ``normalized_value`` is intentionally caller-supplied because CMIS must not
    infer provider units or semantics. When omitted, the observation remains
    valid provenance but cannot participate in exact numeric agreement.
    """
    required = {
        "chain": _text(chain),
        "fact_type": _text(fact_type),
        "subject_id": _text(subject_id),
        "source": _text(source),
        "source_role": _text(source_role),
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError(
            "CMIS evidence observation requires: " + ", ".join(missing)
        )

    return {
        **required,
        "observed_at": observed_at,
        "block_slot": block_slot,
        "raw_identifier": _text(raw_identifier),
        "raw_value": raw_value,
        "normalized_value": (
            _decimal_text(normalized_value)
            if normalized_value is not None
            else None
        ),
        "unit": _text(unit),
        "calculation_version": _text(calculation_version),
        "identity_verified": bool(identity_verified),
        "semantics_verified": bool(semantics_verified),
        "freshness_verified": bool(freshness_verified),
        "warnings": [str(item) for item in (warnings or [])],
    }


def _identity_tuple(observation: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        _text(observation.get("chain")),
        _text(observation.get("fact_type")),
        _text(observation.get("subject_id")),
    )


def compare_same_fact_exact(
    primary: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two normalized observations of the same fact exactly.

    This primitive proves same-fact numeric agreement or conflict. It does not
    infer that the two observations are independently sourced merely because
    their ``source`` labels differ. Independence is a separate evidence gate.

    The function deliberately has no tolerance parameter. Reserve/supply style
    facts should first be normalized to the same proven unit and observation
    scope. A future fact-specific verifier may define a time/market tolerance,
    but the generic trust primitive must not silently weaken exact agreement.
    """
    if not isinstance(primary, Mapping) or not isinstance(verifier, Mapping):
        raise TypeError("CMIS evidence comparisons require mapping observations.")

    primary_identity = _identity_tuple(primary)
    verifier_identity = _identity_tuple(verifier)
    if primary_identity != verifier_identity or None in primary_identity:
        return {
            "status": CONFLICT,
            "code": IDENTITY_MISMATCH,
            "agreement": False,
            "primary": dict(primary),
            "verifier": dict(verifier),
        }

    primary_unit = _text(primary.get("unit"))
    verifier_unit = _text(verifier.get("unit"))
    if primary_unit != verifier_unit or primary_unit is None:
        return {
            "status": CONFLICT,
            "code": UNIT_MISMATCH,
            "agreement": False,
            "primary": dict(primary),
            "verifier": dict(verifier),
        }

    primary_value = primary.get("normalized_value")
    verifier_value = verifier.get("normalized_value")
    if primary_value is None or verifier_value is None:
        return {
            "status": INSUFFICIENT_EVIDENCE,
            "code": VALUE_MISSING,
            "agreement": None,
            "primary": dict(primary),
            "verifier": dict(verifier),
        }

    primary_decimal = _decimal_text(primary_value)
    verifier_decimal = _decimal_text(verifier_value)
    if primary_decimal is None or verifier_decimal is None:
        return {
            "status": INSUFFICIENT_EVIDENCE,
            "code": VALUE_INVALID,
            "agreement": None,
            "primary": dict(primary),
            "verifier": dict(verifier),
        }

    agreement = Decimal(primary_decimal) == Decimal(verifier_decimal)
    return {
        "status": AGREEMENT if agreement else CONFLICT,
        "code": VALUES_AGREE if agreement else VALUES_DISAGREE,
        "agreement": agreement,
        "normalized_unit": primary_unit,
        "primary_value": primary_decimal,
        "verifier_value": verifier_decimal,
        "primary": dict(primary),
        "verifier": dict(verifier),
    }


def build_data_quality_assessment(
    *,
    observations: list[Mapping[str, Any]],
    verification: Optional[Mapping[str, Any]] = None,
    source_independence_verified: Optional[bool] = None,
) -> dict[str, Any]:
    """Return transparent quality dimensions without a pseudo-precise score.

    ``source_independence_verified`` is intentionally tri-state. ``True`` means
    an accepted fact-specific evidence contract has separately proven upstream
    independence for the exact observations. ``False`` means independence was
    explicitly disproven. ``None`` means independence remains unknown. Distinct
    source labels alone never upgrade this field.
    """
    if source_independence_verified is not None and not isinstance(
        source_independence_verified, bool
    ):
        raise TypeError("source_independence_verified must be true, false, or null")

    records = [item for item in observations if isinstance(item, Mapping)]

    distinct_source_labels = {
        _text(item.get("source"))
        for item in records
        if _text(item.get("source"))
    }

    identity_verified = bool(records) and all(
        item.get("identity_verified") is True for item in records
    )
    semantics_verified = bool(records) and all(
        item.get("semantics_verified") is True for item in records
    )
    freshness_verified = bool(records) and all(
        item.get("freshness_verified") is True for item in records
    )

    verification_status = (
        _text((verification or {}).get("status")) if verification else None
    )
    same_fact_agreement_verified = verification_status == AGREEMENT
    independent_agreement_verified = bool(
        same_fact_agreement_verified and source_independence_verified is True
    )

    if verification_status == CONFLICT:
        quality = "LOW"
    elif (
        len(distinct_source_labels) >= 2
        and source_independence_verified is True
        and identity_verified
        and semantics_verified
        and freshness_verified
        and same_fact_agreement_verified
    ):
        quality = "HIGH"
    elif records and identity_verified and semantics_verified and freshness_verified:
        quality = "MEDIUM"
    else:
        quality = "LOW"

    reasons = []
    if len(distinct_source_labels) < 2:
        reasons.append(SINGLE_SOURCE_ONLY)
    if source_independence_verified is None:
        reasons.append(SOURCE_INDEPENDENCE_UNPROVEN)
    elif source_independence_verified is False:
        reasons.append(SOURCE_INDEPENDENCE_FAILED)
    if not identity_verified:
        reasons.append("IDENTITY_UNVERIFIED")
    if not semantics_verified:
        reasons.append("SEMANTICS_UNVERIFIED")
    if not freshness_verified:
        reasons.append("FRESHNESS_UNVERIFIED")
    if verification_status == CONFLICT:
        reasons.append("SOURCE_OBSERVATION_CONFLICT")
    elif verification and not same_fact_agreement_verified:
        reasons.append("SAME_FACT_AGREEMENT_UNPROVEN")

    return {
        "quality": quality,
        # Compatibility field: this counts distinct source labels only. It is
        # not an independence proof and must never be used as one by itself.
        "independent_source_count": len(distinct_source_labels),
        "distinct_source_label_count": len(distinct_source_labels),
        "source_independence_verified": source_independence_verified,
        "identity_verified": identity_verified,
        "semantics_verified": semantics_verified,
        "freshness_verified": freshness_verified,
        "same_fact_agreement_verified": same_fact_agreement_verified,
        "independent_agreement_verified": independent_agreement_verified,
        "reasons": reasons,
    }


__all__ = [
    "AGREEMENT",
    "CONFLICT",
    "IDENTITY_MISMATCH",
    "INSUFFICIENT_EVIDENCE",
    "SINGLE_SOURCE_ONLY",
    "SOURCE_INDEPENDENCE_FAILED",
    "SOURCE_INDEPENDENCE_UNPROVEN",
    "UNIT_MISMATCH",
    "VALUE_INVALID",
    "VALUE_MISSING",
    "VALUES_AGREE",
    "VALUES_DISAGREE",
    "VERIFICATION_STATUSES",
    "build_data_quality_assessment",
    "build_evidence_observation",
    "compare_same_fact_exact",
]