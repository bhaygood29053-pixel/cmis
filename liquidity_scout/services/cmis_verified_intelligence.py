"""First bounded Phase 12 CMIS intelligence service contract.

The first service slice is intentionally limited to one deterministic conclusion:
``top_account_concentration_change``. A public/Scout caller supplies only an
exact chain, asset id, and CMIS-owned ``ie_...`` evidence id. The evidence
bundle itself must be resolved through an internal CMIS dependency; caller-
supplied receipts, proof scores, or intelligence bundles are never a trust root.

An optional explicit threshold policy may classify the already-verified numeric
change. That policy output remains separate from the market fact, Proof Score,
and risk. No behavioral, ownership, intent, risk, or execution interpretation
is added.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Callable

from liquidity_scout.cmis.concentration_threshold import evaluate_concentration_threshold
from liquidity_scout.cmis.intelligence_evidence_ledger import (
    ACCEPTED_CONCLUSION_TYPE,
    normalize_intelligence_evidence_id,
    validate_concentration_change_intelligence_evidence,
)
from liquidity_scout.services.cmis_contract import (
    ERROR,
    OK,
    PARTIAL,
    UNAVAILABLE,
    build_service_envelope,
)


SERVICE = "concentration_change_intelligence"
CONTRACT_VERSION = "concentration_change_intelligence/v1"
SUPPORTED_CHAIN = "x1"
PROMOTION_SCOPE = "cmis_owned_top_account_concentration_change_evidence_by_id"
ACCEPTED_CONCLUSION_TYPES = frozenset({ACCEPTED_CONCLUSION_TYPE})
_THRESHOLD_FIELDS = frozenset(
    {"policy_id", "policy_version", "absolute_delta_threshold_bps"}
)


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if text and text == value else None


def _source_records(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
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


def _evidence_summary(evidence: Mapping[str, Any]) -> dict[str, Any]:
    proof_records: list[dict[str, Any]] = []
    receipt_ids: list[str] = []
    freshness_states: list[bool | None] = []
    unresolved_fields: set[str] = set()
    limitations: list[Any] = []

    for bundle in evidence.get("evidence_bundles", []):
        if not isinstance(bundle, Mapping):
            continue
        receipt = bundle.get("evidence_receipt")
        proof = bundle.get("proof_score")
        if not isinstance(receipt, Mapping) or not isinstance(proof, Mapping):
            continue
        receipt_id = receipt.get("receipt_id")
        if isinstance(receipt_id, str):
            receipt_ids.append(receipt_id)
        proof_records.append(
            {
                "receipt_id": receipt_id,
                "proof_strength": proof.get("proof_strength"),
                "proof_percent": proof.get("proof_percent"),
                "method": proof.get("method"),
            }
        )
        freshness = receipt.get("freshness")
        verified = freshness.get("verified") if isinstance(freshness, Mapping) else None
        freshness_states.append(verified if isinstance(verified, bool) else None)
        raw_unresolved = receipt.get("unresolved_fields")
        if isinstance(raw_unresolved, list):
            unresolved_fields.update(str(item) for item in raw_unresolved)
        raw_limitations = receipt.get("limitations")
        if isinstance(raw_limitations, list):
            limitations.extend(deepcopy(raw_limitations))

    if any(value is False for value in freshness_states):
        freshness_verified: bool | None = False
    elif freshness_states and all(value is True for value in freshness_states):
        freshness_verified = True
    else:
        freshness_verified = None

    return {
        "receipt_ids": receipt_ids,
        "proof_records": proof_records,
        "freshness_verified": freshness_verified,
        "unresolved_fields": sorted(unresolved_fields),
        "limitations": limitations,
    }


def _error(chain: str, code: str, message: str) -> dict[str, Any]:
    return build_service_envelope(
        SERVICE,
        chain,
        ERROR,
        data={
            "contract_version": CONTRACT_VERSION,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        },
        errors=[{"code": code, "message": message}],
    )


def _unavailable(chain: str, code: str, message: str) -> dict[str, Any]:
    return build_service_envelope(
        SERVICE,
        chain,
        UNAVAILABLE,
        data={
            "contract_version": CONTRACT_VERSION,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        },
        warnings=[{"code": code, "message": message}],
    )


def _policy_assessment(change: Mapping[str, Any], policy: Any) -> dict[str, Any] | None:
    if policy is None:
        return None
    if not isinstance(policy, Mapping):
        raise ValueError("threshold_policy must be a mapping when supplied")
    if any(not isinstance(key, str) for key in policy):
        raise ValueError("threshold_policy keys must be strings")
    if set(policy) != set(_THRESHOLD_FIELDS):
        raise ValueError(
            "threshold_policy must contain exactly policy_id, policy_version, "
            "and absolute_delta_threshold_bps"
        )
    return evaluate_concentration_threshold(
        change=change,
        policy_id=policy.get("policy_id"),
        policy_version=policy.get("policy_version"),
        absolute_delta_threshold_bps=policy.get("absolute_delta_threshold_bps"),
    )


def build_concentration_change_intelligence_response(
    intelligence_evidence_id: Any,
    *,
    asset_id: Any,
    evidence_resolver: Callable[[str], Any] | None,
    chain: str = SUPPORTED_CHAIN,
    threshold_policy: Any = None,
    promotion_authorized: bool = False,
) -> dict[str, Any]:
    """Resolve and expose one CMIS-owned concentration-change evidence record."""
    chain_name = str(chain or "").strip().lower()
    if chain_name != SUPPORTED_CHAIN:
        return _unavailable(
            chain_name or "unknown",
            "concentration_change_intelligence_chain_not_promoted",
            "The first Phase 12 intelligence contract is scoped to X1 only.",
        )

    asset = _text(asset_id)
    if asset is None:
        return _error(chain_name, "invalid_asset_id", "asset_id must be normalized non-empty text.")
    try:
        evidence_id = normalize_intelligence_evidence_id(intelligence_evidence_id)
    except ValueError as exc:
        return _error(chain_name, "invalid_intelligence_evidence_id", str(exc))

    if not callable(evidence_resolver):
        return _unavailable(
            chain_name,
            "internal_intelligence_evidence_resolver_unavailable",
            "CMIS has no trusted internal intelligence-evidence resolver configured.",
        )

    try:
        resolved = evidence_resolver(evidence_id)
    except Exception as exc:
        return _error(
            chain_name,
            "internal_intelligence_evidence_resolution_failed",
            f"CMIS could not resolve the internal intelligence evidence: {type(exc).__name__}: {exc}",
        )
    if resolved is None:
        return _unavailable(
            chain_name,
            "intelligence_evidence_not_found",
            "The requested CMIS-owned intelligence evidence id was not found.",
        )

    try:
        rebuilt = validate_concentration_change_intelligence_evidence(resolved)
    except (TypeError, ValueError, KeyError) as exc:
        return _error(
            chain_name,
            "stored_intelligence_evidence_validation_failed",
            f"Stored CMIS intelligence evidence failed deterministic validation: {exc}",
        )
    if rebuilt["intelligence_evidence_id"] != evidence_id:
        return _error(
            chain_name,
            "stored_intelligence_evidence_id_mismatch",
            "Resolved CMIS intelligence evidence does not match the requested id.",
        )

    conclusion = rebuilt["conclusion"]
    conclusion_chain = str(conclusion.get("chain") or "").strip().lower()
    conclusion_asset = _text(conclusion.get("asset_id"))
    if conclusion_chain != chain_name:
        return _error(
            chain_name,
            "intelligence_evidence_chain_mismatch",
            "Resolved intelligence evidence chain does not match the request.",
        )
    if conclusion_asset != asset:
        return _error(
            chain_name,
            "intelligence_evidence_asset_mismatch",
            "Resolved intelligence evidence asset does not match the requested asset_id.",
        )

    try:
        policy_assessment = _policy_assessment(conclusion, threshold_policy)
    except (TypeError, ValueError, KeyError) as exc:
        return _error(
            chain_name,
            "invalid_threshold_policy",
            f"The explicit threshold policy is invalid: {exc}",
        )

    summary = _evidence_summary(rebuilt)
    freshness_verified = summary["freshness_verified"]
    unresolved_fields = summary["unresolved_fields"]
    status = (
        OK
        if freshness_verified is True and not unresolved_fields
        else PARTIAL
    )
    warnings: list[dict[str, str]] = []
    if freshness_verified is False:
        warnings.append({
            "code": "intelligence_evidence_not_fresh",
            "message": "At least one authoritative Evidence Receipt explicitly marks freshness unverified.",
        })
    elif freshness_verified is None:
        warnings.append({
            "code": "intelligence_evidence_freshness_unknown",
            "message": "Evidence freshness is not explicitly verified by every authoritative Evidence Receipt.",
        })
    if unresolved_fields:
        warnings.append({
            "code": "intelligence_evidence_unresolved_fields",
            "message": "Authoritative Evidence Receipts retain unresolved evidence fields.",
        })

    promoted = bool(promotion_authorized)
    data = {
        "contract_version": CONTRACT_VERSION,
        "read_only": True,
        "public_service_promoted": promoted,
        "scout_reliance_promoted": promoted,
        "promotion_scope": PROMOTION_SCOPE if promoted else None,
        "accepted_conclusion_type": ACCEPTED_CONCLUSION_TYPE,
        "asset_id": asset,
        "facts": deepcopy(conclusion),
        "policy_assessment": policy_assessment,
        "risk_interpretation": None,
        "evidence": {
            "intelligence_evidence_id": evidence_id,
            "receipt_ids": summary["receipt_ids"],
            "proof_records": summary["proof_records"],
            "freshness_verified": freshness_verified,
            "unresolved_fields": unresolved_fields,
            "limitations": summary["limitations"],
            "intelligence_evidence": rebuilt,
        },
        "proof_strength_separate_from_risk": True,
        "behavioral_interpretation_added": False,
        "provider_assertion_promoted": False,
        "execution_authorized": False,
    }
    return build_service_envelope(
        SERVICE,
        chain_name,
        status,
        asset={"canonical_id": asset},
        data=data,
        risk=None,
        confidence={
            "cmis_owned_evidence_resolved": True,
            "deterministic_evidence_revalidated": True,
            "freshness_verified": freshness_verified,
            "unresolved_fields": unresolved_fields,
            "proof_records": summary["proof_records"],
        },
        sources=_source_records(rebuilt),
        observed_at=conclusion.get("after_observed_at"),
        warnings=warnings,
        errors=[],
    )


__all__ = [
    "ACCEPTED_CONCLUSION_TYPES",
    "CONTRACT_VERSION",
    "PROMOTION_SCOPE",
    "SERVICE",
    "SUPPORTED_CHAIN",
    "build_concentration_change_intelligence_response",
]
