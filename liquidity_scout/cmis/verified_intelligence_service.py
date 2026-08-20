"""Machine-readable contract boundary for the first Phase 12 intelligence slice.

This module does not register the service into the canonical CMIS gateway or
capability manifest.  It defines the narrow request/capability contract that a
later accepted integration may promote.  Until that integration explicitly
passes ``promotion_authorized=True``, the dispatcher is unavailable to Scouts.

The request never accepts an Evidence Receipt, Proof Score, conclusion, or full
intelligence bundle from the caller.  Those objects must be resolved internally
from a CMIS-owned ``intelligence_evidence_id``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from liquidity_scout.services.cmis_contract import ERROR, UNAVAILABLE, build_service_envelope
from liquidity_scout.services.cmis_verified_intelligence import (
    ACCEPTED_CONCLUSION_TYPES,
    CONTRACT_VERSION,
    PROMOTION_SCOPE,
    SERVICE,
    SUPPORTED_CHAIN,
    build_concentration_change_intelligence_response,
)


SCHEMA_VERSION = 1
_REQUEST_PARAM_FIELDS = frozenset(
    {"intelligence_evidence_id", "asset_id", "threshold_policy"}
)


def build_verified_intelligence_capability(
    *,
    chain: str = SUPPORTED_CHAIN,
    promotion_authorized: bool = False,
) -> dict[str, Any]:
    """Return the exact candidate/public eligibility record for a Chain Scout."""
    chain_name = str(chain or "").strip().lower()
    x1_scope = chain_name == SUPPORTED_CHAIN
    promoted = bool(x1_scope and promotion_authorized)
    return {
        "schema_version": SCHEMA_VERSION,
        "service": SERVICE,
        "service_contract_version": CONTRACT_VERSION,
        "chain": chain_name or "unknown",
        "state": "bounded" if x1_scope else "unavailable",
        "callable": promoted,
        "read_only": True,
        "public_service_promoted": promoted,
        "scout_reliance_promoted": promoted,
        "promotion_scope": PROMOTION_SCOPE if x1_scope else None,
        "accepted_conclusion_types": sorted(ACCEPTED_CONCLUSION_TYPES) if x1_scope else [],
        "requirements": [
            "exact_x1_asset_id",
            "cmis_owned_intelligence_evidence_id",
            "trusted_internal_evidence_resolver",
            "deterministic_bundle_revalidation",
            "top_account_concentration_change_only",
            "content_addressed_evidence_receipts",
            "exact_recomputed_proof_scores",
            "receipt_chain_source_and_asset_coverage",
        ] if x1_scope else [],
        "limitations": [
            "caller_supplied_intelligence_evidence_not_accepted",
            "phase_11_foundation_objects_remain_unpromoted",
            "observed_top_token_account_scope_is_incomplete",
            "token_accounts_are_not_unique_holders",
            "beneficial_owner_identity_unverified",
            "proof_strength_remains_separate_from_risk",
            "threshold_policy_is_not_a_market_fact",
            "no_behavioral_or_ownership_labels",
            "no_provider_assertion_promotion",
            "no_execution_authorization",
            "x1_only_initial_scope",
        ] if x1_scope else ["concentration_change_intelligence_not_available_for_chain"],
        "promotion_blocker": None if promoted else (
            "canonical_runtime_and_capability_manifest_integration_required"
            if x1_scope
            else "unsupported_chain"
        ),
        "execution_authorized": False,
    }


def _error(chain: str, code: str, message: str) -> dict[str, Any]:
    return build_service_envelope(
        SERVICE,
        chain,
        ERROR,
        data={"contract_version": CONTRACT_VERSION, "execution_authorized": False},
        errors=[{"code": code, "message": message}],
    )


def dispatch_verified_intelligence_request(
    request: Any,
    *,
    evidence_resolver: Callable[[str], Any] | None = None,
    promotion_authorized: bool = False,
) -> dict[str, Any]:
    """Dispatch the narrow contract without allowing caller self-attestation."""
    if not isinstance(request, Mapping):
        return _error("unknown", "invalid_request", "request must be a mapping.")

    service = str(request.get("service") or "").strip().lower()
    chain = str(request.get("chain") or "").strip().lower()
    params = request.get("params")
    if service != SERVICE:
        return _error(
            chain or "unknown",
            "unsupported_service",
            f"This dispatcher accepts only service={SERVICE!r}.",
        )
    if not isinstance(params, Mapping):
        return _error(chain or "unknown", "invalid_params", "params must be a mapping.")
    if any(not isinstance(key, str) for key in params):
        return _error(chain or "unknown", "invalid_params", "params keys must be strings.")

    if "intelligence_evidence" in params or "evidence_receipt" in params or "proof_score" in params:
        return _error(
            chain or "unknown",
            "caller_intelligence_evidence_not_accepted",
            "Caller-supplied intelligence evidence, receipts, and proof scores are not trusted inputs.",
        )
    unknown = sorted(set(params) - set(_REQUEST_PARAM_FIELDS))
    if unknown:
        return _error(
            chain or "unknown",
            "unknown_params",
            "Unsupported params: " + ", ".join(unknown),
        )

    evidence_id = params.get("intelligence_evidence_id")
    asset_id = params.get("asset_id")
    if evidence_id is None:
        return _error(
            chain or "unknown",
            "intelligence_evidence_id_required",
            "params.intelligence_evidence_id is required.",
        )
    if asset_id is None:
        return _error(
            chain or "unknown",
            "asset_id_required",
            "params.asset_id is required.",
        )

    if not promotion_authorized:
        return build_service_envelope(
            SERVICE,
            chain or "unknown",
            UNAVAILABLE,
            data={
                "contract_version": CONTRACT_VERSION,
                "public_service_promoted": False,
                "scout_reliance_promoted": False,
                "execution_authorized": False,
            },
            warnings=[{
                "code": "concentration_change_intelligence_not_promoted",
                "message": (
                    "The contract exists, but canonical CMIS runtime/capability "
                    "integration has not yet authorized public or Scout reliance."
                ),
            }],
        )

    return build_concentration_change_intelligence_response(
        evidence_id,
        asset_id=asset_id,
        evidence_resolver=evidence_resolver,
        chain=chain,
        threshold_policy=params.get("threshold_policy"),
        promotion_authorized=True,
    )


__all__ = [
    "SCHEMA_VERSION",
    "build_verified_intelligence_capability",
    "dispatch_verified_intelligence_request",
]
