"""Phase 12 machine-readable Scout reliance contract for verified intelligence.

This module is intentionally separate from the Phase 11 foundation manifest.
The foundation remains non-promoted.  The callable contract below authorizes
Scout reliance only on a result produced by ``verified_intelligence/v1`` for an
exact deterministically revalidated evidence bundle.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.services.cmis_contract import ERROR, build_service_envelope
from liquidity_scout.services.cmis_verified_intelligence import (
    ACCEPTED_CONCLUSION_TYPES,
    CONTRACT_VERSION,
    SERVICE,
    SUPPORTED_CHAIN,
    build_verified_intelligence_response,
)


SCHEMA_VERSION = 1


def build_verified_intelligence_capability(*, chain: str = SUPPORTED_CHAIN) -> dict[str, Any]:
    """Return the exact service-level eligibility record for a Chain Scout."""
    chain_name = str(chain or "").strip().lower()
    promoted = chain_name == SUPPORTED_CHAIN
    return {
        "schema_version": SCHEMA_VERSION,
        "service": SERVICE,
        "service_contract_version": CONTRACT_VERSION,
        "chain": chain_name or "unknown",
        "state": "bounded" if promoted else "unavailable",
        "callable": promoted,
        "read_only": True,
        "public_service_promoted": promoted,
        "scout_reliance_promoted": promoted,
        "promotion_scope": (
            "exact_revalidated_intelligence_evidence_bundle_only" if promoted else None
        ),
        "accepted_conclusion_types": sorted(ACCEPTED_CONCLUSION_TYPES) if promoted else [],
        "requirements": [
            "exact_phase_11_intelligence_evidence_bundle",
            "deterministic_bundle_revalidation",
            "content_addressed_evidence_receipts",
            "exact_recomputed_proof_scores",
            "receipt_chain_source_and_asset_coverage",
        ] if promoted else [],
        "limitations": [
            "phase_11_foundation_objects_remain_unpromoted",
            "proof_strength_remains_separate_from_risk",
            "no_behavioral_or_ownership_labels",
            "no_provider_assertion_promotion",
            "no_execution_authorization",
            "x1_only_initial_scope",
        ] if promoted else ["verified_intelligence_not_promoted_for_chain"],
        "execution_authorized": False,
    }


def dispatch_verified_intelligence_request(request: Any) -> dict[str, Any]:
    """Dispatch the narrow Phase 12 request shape without provider collection."""
    if not isinstance(request, Mapping):
        return build_service_envelope(
            SERVICE,
            "unknown",
            ERROR,
            data={"contract_version": CONTRACT_VERSION, "execution_authorized": False},
            errors=[{"code": "invalid_request", "message": "request must be a mapping."}],
        )

    service = str(request.get("service") or "").strip().lower()
    chain = str(request.get("chain") or "").strip().lower()
    params = request.get("params")
    if service != SERVICE:
        return build_service_envelope(
            service or SERVICE,
            chain or "unknown",
            ERROR,
            data={"contract_version": CONTRACT_VERSION, "execution_authorized": False},
            errors=[{
                "code": "unsupported_service",
                "message": f"This dispatcher accepts only service={SERVICE!r}.",
            }],
        )
    if not isinstance(params, Mapping):
        return build_service_envelope(
            SERVICE,
            chain or "unknown",
            ERROR,
            data={"contract_version": CONTRACT_VERSION, "execution_authorized": False},
            errors=[{"code": "invalid_params", "message": "params must be a mapping."}],
        )
    if "intelligence_evidence" not in params:
        return build_service_envelope(
            SERVICE,
            chain or "unknown",
            ERROR,
            data={"contract_version": CONTRACT_VERSION, "execution_authorized": False},
            errors=[{
                "code": "intelligence_evidence_required",
                "message": "params.intelligence_evidence is required.",
            }],
        )
    return build_verified_intelligence_response(
        params["intelligence_evidence"],
        chain=chain,
    )


__all__ = [
    "SCHEMA_VERSION",
    "build_verified_intelligence_capability",
    "dispatch_verified_intelligence_request",
]
