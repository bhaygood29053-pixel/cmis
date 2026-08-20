"""Read-only Phase 12 service wrapper for evidence-bound CMIS intelligence.

The Phase 11 intelligence foundation deliberately remains an internal,
non-promoted evidence primitive.  This module creates the narrow public/Scout
service boundary around one *exact* Phase 11 intelligence-evidence bundle.  It
rebuilds that bundle through the accepted deterministic validator and refuses
any caller-supplied mutation, rather than reinterpreting or upgrading the
underlying conclusion.

This service does not infer behavior, ownership, intent, risk, or execution
advice.  Proof strength remains separate from risk and execution is always
unauthorized.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from liquidity_scout.cmis.intelligence_evidence import (
    CONCLUSION_TYPES,
    build_intelligence_evidence_bundle,
)
from liquidity_scout.services.cmis_contract import (
    ERROR,
    OK,
    UNAVAILABLE,
    build_service_envelope,
)


SERVICE = "verified_intelligence"
CONTRACT_VERSION = "verified_intelligence/v1"
SUPPORTED_CHAIN = "x1"
ACCEPTED_CONCLUSION_TYPES = frozenset(CONCLUSION_TYPES)


def _source_records(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return only traceable source records already present in accepted evidence."""
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for bundle in evidence.get("evidence_bundles", []):
        if not isinstance(bundle, Mapping):
            continue
        receipt = bundle.get("evidence_receipt")
        if not isinstance(receipt, Mapping):
            continue
        for source in receipt.get("sources", []):
            if not isinstance(source, Mapping):
                continue
            copied = deepcopy(dict(source))
            key = (
                copied.get("source"),
                copied.get("evidence_class"),
                copied.get("observed_at"),
            )
            if key not in seen:
                seen.add(key)
                result.append(copied)
    return result


def _proof_records(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for bundle in evidence.get("evidence_bundles", []):
        if not isinstance(bundle, Mapping):
            continue
        receipt = bundle.get("evidence_receipt")
        proof = bundle.get("proof_score")
        if isinstance(receipt, Mapping) and isinstance(proof, Mapping):
            records.append(
                {
                    "receipt_id": receipt.get("receipt_id"),
                    "proof_strength": proof.get("proof_strength"),
                    "proof_percent": proof.get("proof_percent"),
                    "method": proof.get("method"),
                }
            )
    return records


def _error(chain: str, code: str, message: str) -> dict[str, Any]:
    return build_service_envelope(
        SERVICE,
        chain,
        ERROR,
        data={
            "contract_version": CONTRACT_VERSION,
            "read_only": True,
            "execution_authorized": False,
        },
        errors=[{"code": code, "message": message}],
    )


def build_verified_intelligence_response(
    intelligence_evidence: Any,
    *,
    chain: str = SUPPORTED_CHAIN,
) -> dict[str, Any]:
    """Expose one exact, deterministically revalidated intelligence bundle.

    Public/Scout promotion applies only to this wrapper result.  The nested
    Phase 11 evidence bundle intentionally remains byte-for-byte identical to
    its non-promoted foundation representation, including
    ``public_service_promoted=false`` and ``scout_reliance_promoted=false``.
    """
    chain_name = str(chain or "").strip().lower()
    if chain_name != SUPPORTED_CHAIN:
        return build_service_envelope(
            SERVICE,
            chain_name or "unknown",
            UNAVAILABLE,
            data={
                "contract_version": CONTRACT_VERSION,
                "read_only": True,
                "public_service_promoted": False,
                "scout_reliance_promoted": False,
                "execution_authorized": False,
            },
            warnings=[{
                "code": "verified_intelligence_chain_not_promoted",
                "message": (
                    "The Phase 12 verified_intelligence service is currently "
                    "accepted only for X1."
                ),
            }],
        )

    if not isinstance(intelligence_evidence, Mapping):
        return _error(chain_name, "invalid_intelligence_evidence", "intelligence_evidence must be a mapping.")

    conclusion_type = intelligence_evidence.get("conclusion_type")
    if conclusion_type not in ACCEPTED_CONCLUSION_TYPES:
        return _error(
            chain_name,
            "unsupported_intelligence_conclusion",
            "The supplied conclusion type is not accepted by the Phase 12 service contract.",
        )

    try:
        rebuilt = build_intelligence_evidence_bundle(
            conclusion_type=conclusion_type,
            conclusion=intelligence_evidence.get("conclusion"),
            evidence_bundles=intelligence_evidence.get("evidence_bundles"),
        )
    except (TypeError, ValueError, KeyError) as exc:
        return _error(
            chain_name,
            "intelligence_evidence_validation_failed",
            f"The supplied intelligence evidence failed deterministic validation: {exc}",
        )

    supplied = deepcopy(dict(intelligence_evidence))
    if supplied != rebuilt:
        return _error(
            chain_name,
            "intelligence_evidence_exact_match_required",
            "The supplied intelligence evidence is not the exact accepted deterministic bundle.",
        )

    first_receipt = rebuilt["evidence_bundles"][0]["evidence_receipt"]
    if str(first_receipt.get("chain") or "").strip().lower() != chain_name:
        return _error(
            chain_name,
            "intelligence_evidence_chain_mismatch",
            "The evidence bundle chain does not match the requested service chain.",
        )

    proof_records = _proof_records(rebuilt)
    data = {
        "contract_version": CONTRACT_VERSION,
        "read_only": True,
        "public_service_promoted": True,
        "scout_reliance_promoted": True,
        "promotion_scope": "exact_revalidated_intelligence_evidence_bundle_only",
        "conclusion_type": rebuilt["conclusion_type"],
        "intelligence_evidence_id": rebuilt["intelligence_evidence_id"],
        "intelligence_evidence": rebuilt,
        "proof_records": proof_records,
        "proof_strength_separate_from_risk": True,
        "behavioral_interpretation_added": False,
        "provider_assertion_promoted": False,
        "execution_authorized": False,
    }
    return build_service_envelope(
        SERVICE,
        chain_name,
        OK,
        data=data,
        risk=None,
        confidence={
            "deterministic_evidence_revalidated": True,
            "exact_bundle_match_verified": True,
            "proof_records": proof_records,
        },
        sources=_source_records(rebuilt),
        observed_at=None,
        warnings=[],
        errors=[],
    )


__all__ = [
    "ACCEPTED_CONCLUSION_TYPES",
    "CONTRACT_VERSION",
    "SERVICE",
    "SUPPORTED_CHAIN",
    "build_verified_intelligence_response",
]
