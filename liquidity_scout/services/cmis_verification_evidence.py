"""CMIS service wrapper for already-produced deterministic verification results.

This wrapper does not perform provider collection, compare observations, infer
source independence, or strengthen verification. It accepts the output of an
accepted fact-specific CMIS verifier and exposes a sanitized evidence/provenance
view through the standard service envelope.

Fact-specific verification remains authoritative. A caller cannot make a result
stronger by supplying a different service status, data-quality label, or
promotion claim to this wrapper.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
import math
from typing import Any, Dict, Optional

from liquidity_scout.cmis.evidence import (
    AGREEMENT,
    CONFLICT,
    INSUFFICIENT_EVIDENCE,
    VERIFICATION_STATUSES,
)

from .cmis_contract import ERROR, OK, PARTIAL, build_service_envelope


_SERVICE = "verification_evidence"
_QUALITY_LEVELS = frozenset({"HIGH", "MEDIUM", "LOW"})
_TEXT_OBSERVATION_FIELDS = (
    "chain",
    "fact_type",
    "subject_id",
    "source",
    "source_role",
    "raw_identifier",
    "unit",
    "calculation_version",
)
_SCALAR_OBSERVATION_FIELDS = (
    "observed_at",
    "block_slot",
    "raw_value",
    "normalized_value",
)
_BOOLEAN_OBSERVATION_FIELDS = (
    "identity_verified",
    "semantics_verified",
    "freshness_verified",
)


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_scalar(value: Any) -> Any:
    """Expose primitive evidence values only; never nested transport payloads."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return str(value)
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(item)
        for item in value
        if not isinstance(item, (Mapping, list, tuple, set))
    ]


def _safe_observation(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    record: Dict[str, Any] = {
        field: _text(value.get(field)) for field in _TEXT_OBSERVATION_FIELDS
    }
    record.update(
        {
            field: _safe_scalar(value.get(field))
            for field in _SCALAR_OBSERVATION_FIELDS
        }
    )
    record.update(
        {
            field: value.get(field)
            if isinstance(value.get(field), bool)
            else None
            for field in _BOOLEAN_OBSERVATION_FIELDS
        }
    )
    record["warnings"] = _string_list(value.get("warnings"))
    return record


def _safe_quality(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    count = value.get("independent_source_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        count = None
    distinct_count = value.get("distinct_source_label_count")
    if isinstance(distinct_count, bool) or not isinstance(distinct_count, int) or distinct_count < 0:
        distinct_count = None
    independence = value.get("source_independence_verified")
    if independence is not None and not isinstance(independence, bool):
        independence = "INVALID"
    return {
        "quality": _text(value.get("quality")),
        "independent_source_count": count,
        "distinct_source_label_count": distinct_count,
        "source_independence_verified": independence,
        "identity_verified": (
            value.get("identity_verified")
            if isinstance(value.get("identity_verified"), bool)
            else None
        ),
        "semantics_verified": (
            value.get("semantics_verified")
            if isinstance(value.get("semantics_verified"), bool)
            else None
        ),
        "freshness_verified": (
            value.get("freshness_verified")
            if isinstance(value.get("freshness_verified"), bool)
            else None
        ),
        "same_fact_agreement_verified": (
            value.get("same_fact_agreement_verified")
            if isinstance(value.get("same_fact_agreement_verified"), bool)
            else None
        ),
        "independent_agreement_verified": (
            value.get("independent_agreement_verified")
            if isinstance(value.get("independent_agreement_verified"), bool)
            else None
        ),
        "reasons": _string_list(value.get("reasons")),
    }


def _source(observation: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    source = _text(observation.get("source"))
    if source is None:
        return None
    record: Dict[str, Any] = {"source": source}
    role = _text(observation.get("source_role"))
    if role is not None:
        record["role"] = role
    for field in ("observed_at", "block_slot", "calculation_version"):
        scalar = _safe_scalar(observation.get(field))
        if scalar is not None:
            record[field] = scalar
    return record


def _error_response(
    chain: str,
    code: str,
    message: str,
    *,
    asset: Optional[Mapping[str, Any]] = None,
    observed_at: Any = None,
) -> Dict[str, Any]:
    return build_service_envelope(
        _SERVICE,
        chain,
        ERROR,
        asset=asset,
        errors=[{"code": code, "message": message}],
        observed_at=observed_at,
    )


def build_verification_evidence_response(
    verifier_result: Mapping[str, Any],
    *,
    chain: str = "x1",
    asset: Optional[Mapping[str, Any]] = None,
    observed_at: Any = None,
) -> Dict[str, Any]:
    """Expose one accepted verifier result without recalculating it.

    The nested ``verification`` must contain the primary/verifier observations
    retained by the fact-specific verifier. This wrapper sanitizes those records
    to the accepted CMIS evidence fields before exposing them.
    """
    chain_name = _text(chain) or "unknown"
    if not isinstance(verifier_result, Mapping):
        return _error_response(
            chain_name,
            "invalid_verifier_result",
            "verifier_result must be a mapping produced by an accepted CMIS verifier.",
            asset=asset,
            observed_at=observed_at,
        )

    verification = verifier_result.get("verification")
    if not isinstance(verification, Mapping):
        return _error_response(
            chain_name,
            "verification_result_missing",
            "The fact-specific verifier result does not contain verification evidence.",
            asset=asset,
            observed_at=observed_at,
        )

    verification_status = _text(verification.get("status"))
    if verification_status not in VERIFICATION_STATUSES:
        return _error_response(
            chain_name,
            "verification_status_invalid",
            "The fact-specific verifier returned an unsupported verification status.",
            asset=asset,
            observed_at=observed_at,
        )

    primary = _safe_observation(verification.get("primary"))
    verifier = _safe_observation(verification.get("verifier"))
    if primary is None or verifier is None:
        return _error_response(
            chain_name,
            "verification_observations_missing",
            "The fact-specific verifier must preserve both primary and verifier observations.",
            asset=asset,
            observed_at=observed_at,
        )

    primary_chain = _text(primary.get("chain"))
    verifier_chain = _text(verifier.get("chain"))
    if (
        primary_chain is None
        or verifier_chain is None
        or primary_chain != verifier_chain
        or primary_chain.lower() != chain_name.lower()
    ):
        return _error_response(
            chain_name,
            "verification_chain_mismatch",
            "Verification observations must share the requested chain identity.",
            asset=asset,
            observed_at=observed_at,
        )

    primary_fact = (
        _text(primary.get("fact_type")),
        _text(primary.get("subject_id")),
    )
    verifier_fact = (
        _text(verifier.get("fact_type")),
        _text(verifier.get("subject_id")),
    )
    if None in primary_fact or primary_fact != verifier_fact:
        return _error_response(
            chain_name,
            "verification_fact_identity_mismatch",
            "Verification observations must identify the same fact and subject.",
            asset=asset,
            observed_at=observed_at,
        )

    quality = _safe_quality(verifier_result.get("data_quality"))
    if quality is None:
        return _error_response(
            chain_name,
            "data_quality_missing",
            "The fact-specific verifier must provide its deterministic data-quality assessment.",
            asset=asset,
            observed_at=observed_at,
        )
    if (
        quality.get("quality") not in _QUALITY_LEVELS
        or quality.get("independent_source_count") is None
        or quality.get("distinct_source_label_count") is None
        or quality.get("source_independence_verified") == "INVALID"
        or not all(
            isinstance(quality.get(field), bool)
            for field in (
                "identity_verified",
                "semantics_verified",
                "freshness_verified",
                "same_fact_agreement_verified",
                "independent_agreement_verified",
            )
        )
    ):
        return _error_response(
            chain_name,
            "data_quality_invalid",
            "The fact-specific verifier returned an invalid data-quality contract.",
            asset=asset,
            observed_at=observed_at,
        )

    promotable = verifier_result.get("cmis_promotable")
    if not isinstance(promotable, bool):
        return _error_response(
            chain_name,
            "promotion_state_invalid",
            "The fact-specific verifier must provide an explicit boolean CMIS promotion state.",
            asset=asset,
            observed_at=observed_at,
        )

    agreement = verification.get("agreement")
    if verification_status == AGREEMENT and agreement is not True:
        return _error_response(
            chain_name,
            "agreement_state_inconsistent",
            "AGREEMENT verification must carry agreement=true.",
            asset=asset,
            observed_at=observed_at,
        )
    if verification_status == CONFLICT and agreement is not False:
        return _error_response(
            chain_name,
            "conflict_state_inconsistent",
            "CONFLICT verification must carry agreement=false.",
            asset=asset,
            observed_at=observed_at,
        )
    if verification_status == INSUFFICIENT_EVIDENCE and agreement is not None:
        return _error_response(
            chain_name,
            "insufficient_state_inconsistent",
            "INSUFFICIENT_EVIDENCE verification must carry agreement=null.",
            asset=asset,
            observed_at=observed_at,
        )

    same_fact_agreement = quality.get("same_fact_agreement_verified")
    if verification_status == AGREEMENT and same_fact_agreement is not True:
        return _error_response(
            chain_name,
            "data_quality_agreement_inconsistent",
            "AGREEMENT verification must be reflected as same-fact agreement in data quality.",
            asset=asset,
            observed_at=observed_at,
        )
    if verification_status != AGREEMENT and same_fact_agreement is True:
        return _error_response(
            chain_name,
            "data_quality_agreement_inconsistent",
            "Non-agreement verification cannot claim same-fact agreement in data quality.",
            asset=asset,
            observed_at=observed_at,
        )

    independent_agreement = quality.get("independent_agreement_verified")
    independence = quality.get("source_independence_verified")
    expected_independent_agreement = bool(
        same_fact_agreement is True and independence is True
    )
    if independent_agreement is not expected_independent_agreement:
        return _error_response(
            chain_name,
            "data_quality_independence_inconsistent",
            "Independent agreement must equal same-fact agreement AND explicit source-independence proof.",
            asset=asset,
            observed_at=observed_at,
        )

    if promotable and verification_status != AGREEMENT:
        return _error_response(
            chain_name,
            "promotion_state_inconsistent",
            "Only an AGREEMENT result may be marked CMIS-promotable by a fact-specific verifier.",
            asset=asset,
            observed_at=observed_at,
        )
    if promotable and (
        quality.get("quality") != "HIGH"
        or quality.get("distinct_source_label_count", 0) < 2
        or quality.get("source_independence_verified") is not True
        or quality.get("identity_verified") is not True
        or quality.get("semantics_verified") is not True
        or quality.get("freshness_verified") is not True
        or quality.get("same_fact_agreement_verified") is not True
        or quality.get("independent_agreement_verified") is not True
    ):
        return _error_response(
            chain_name,
            "promotion_quality_inconsistent",
            "CMIS-promotable evidence must retain HIGH quality with verified identity, semantics, freshness, same-fact agreement, and explicit source independence.",
            asset=asset,
            observed_at=observed_at,
        )

    sources = [record for record in (_source(primary), _source(verifier)) if record]
    confidence = dict(quality)
    confidence["cmis_promotable"] = promotable

    normalized_fact = None
    normalized_unit = None
    if verification_status == AGREEMENT and promotable:
        primary_value = _safe_scalar(verification.get("primary_value"))
        verifier_value = _safe_scalar(verification.get("verifier_value"))
        unit = _text(verification.get("normalized_unit"))
        if primary_value is not None and primary_value == verifier_value and unit is not None:
            normalized_fact = primary_value
            normalized_unit = unit
        else:
            return _error_response(
                chain_name,
                "promoted_fact_value_invalid",
                "Promotable agreement must preserve one equal normalized value and unit.",
                asset=asset,
                observed_at=observed_at,
            )

    data = {
        "fact": {
            "fact_type": primary_fact[0],
            "subject_id": primary_fact[1],
            "normalized_value": normalized_fact,
            "unit": normalized_unit,
        },
        "verification": {
            "status": verification_status,
            "code": _text(verification.get("code")),
            "agreement": agreement,
        },
        "data_quality": quality,
        "observations": {"primary": primary, "verifier": verifier},
        "cmis_promotable": promotable,
    }

    warnings = []
    if verification_status == CONFLICT:
        warnings.append({
            "code": "source_observation_conflict",
            "message": "Qualifying CMIS observations conflict; no value is promoted or averaged.",
        })
    elif verification_status == INSUFFICIENT_EVIDENCE:
        warnings.append({
            "code": "insufficient_verification_evidence",
            "message": "CMIS cannot prove the requested fact from the qualifying evidence supplied to the fact-specific verifier.",
        })
    elif not promotable:
        warnings.append({
            "code": "agreement_not_promotable",
            "message": "The observations agree, but the fact-specific verifier did not establish all promotion gates such as explicit source independence.",
        })

    envelope_status = OK if verification_status == AGREEMENT and promotable else PARTIAL

    return build_service_envelope(
        _SERVICE,
        chain_name,
        envelope_status,
        asset=asset,
        data=data,
        confidence=confidence,
        sources=sources,
        observed_at=observed_at,
        warnings=warnings,
        errors=[],
    )


__all__ = ["build_verification_evidence_response"]
