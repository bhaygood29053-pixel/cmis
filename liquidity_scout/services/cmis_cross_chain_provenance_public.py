"""Public promotion wrapper for accepted cross-chain asset provenance v1.

Issue #491 promotes only canonical CMIS-owned provenance records. The wrapper
revalidates content identity and the accepted structural contract, then exposes
the canonical lineage without reconstructing it from provider calls or labels.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from liquidity_scout.services.cmis_contract import ERROR, OK, build_service_envelope
from liquidity_scout.services.cmis_cross_chain_provenance import (
    PROVENANCE_CONTRACT,
    build_cross_chain_asset_provenance,
)

SERVICE = "cross_chain_asset_provenance"
CONTRACT_VERSION = PROVENANCE_CONTRACT
SUPPORTED_CHAIN = "x1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CrossChainProvenancePublicContractError(ValueError):
    """Canonical provenance failed the accepted #491 promotion contract."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise CrossChainProvenancePublicContractError(
            f"{field} must be normalized text"
        )
    return value


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def content_address_provenance(
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one accepted internal provenance object to a canonical evidence id."""

    if not isinstance(provenance, Mapping):
        raise CrossChainProvenancePublicContractError(
            "provenance must be a mapping"
        )
    material = deepcopy(dict(provenance))
    if "evidence_sha256" in material:
        raise CrossChainProvenancePublicContractError(
            "provenance material must not already contain evidence_sha256"
        )
    return {
        **material,
        "evidence_sha256": _canonical_sha256(material),
    }


def validate_cross_chain_provenance_public_record(
    record: Mapping[str, Any],
    *,
    expected_current_asset_id: Any,
    expected_current_asset_id_kind: Any,
) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise CrossChainProvenancePublicContractError(
            "canonical provenance record must be a mapping"
        )
    safe = deepcopy(dict(record))
    evidence_sha = _text(safe.pop("evidence_sha256", None), "evidence_sha256")
    if not _SHA256_RE.fullmatch(evidence_sha):
        raise CrossChainProvenancePublicContractError(
            "evidence_sha256 must be lowercase SHA-256 hex"
        )
    if evidence_sha != _canonical_sha256(safe):
        raise CrossChainProvenancePublicContractError(
            "canonical provenance evidence hash mismatch"
        )

    if safe.get("contract") != CONTRACT_VERSION:
        raise CrossChainProvenancePublicContractError(
            f"canonical provenance must use {CONTRACT_VERSION}"
        )

    try:
        rebuilt = build_cross_chain_asset_provenance(
            canonical_asset_id=safe.get("canonical_asset_id"),
            origin=safe.get("origin"),
            current=safe.get("current"),
            hops=safe.get("lineage"),
        )
    except (TypeError, ValueError) as exc:
        raise CrossChainProvenancePublicContractError(str(exc)) from exc
    if rebuilt != safe:
        raise CrossChainProvenancePublicContractError(
            "canonical provenance does not exactly match accepted deterministic reconstruction"
        )

    current = safe["current"]
    if current["chain"] != SUPPORTED_CHAIN:
        raise CrossChainProvenancePublicContractError(
            "promoted provenance requires the current representation on X1"
        )
    if current["asset_id"] != _text(
        expected_current_asset_id,
        "expected_current_asset_id",
    ):
        raise CrossChainProvenancePublicContractError(
            "current asset identity mismatch"
        )
    if current["asset_id_kind"] != _text(
        expected_current_asset_id_kind,
        "expected_current_asset_id_kind",
    ).casefold():
        raise CrossChainProvenancePublicContractError(
            "current asset identity kind mismatch"
        )

    verification = safe.get("verification")
    if not isinstance(verification, Mapping):
        raise CrossChainProvenancePublicContractError(
            "canonical provenance verification must be a mapping"
        )
    expected_verification = {
        "structural_continuity_verified": True,
        "exact_chain_scoped_identifiers_required": True,
        "symbol_equivalence_authorized": False,
        "live_bridge_state_verified": False,
        "backing_verified": False,
        "custody_verified": False,
        "source_independence_verified": False,
    }
    if dict(verification) != expected_verification:
        raise CrossChainProvenancePublicContractError(
            "canonical provenance verification boundary drift"
        )
    if safe.get("representation_depth") != len(safe.get("lineage") or []):
        raise CrossChainProvenancePublicContractError(
            "representation depth must equal ordered lineage length"
        )
    if safe.get("read_only") is not True:
        raise CrossChainProvenancePublicContractError(
            "canonical provenance must remain read-only"
        )
    for field in (
        "public_service_promoted",
        "scout_reliance_promoted",
        "execution_authorized",
    ):
        if safe.get(field) is not False:
            raise CrossChainProvenancePublicContractError(
                f"canonical foundation must keep {field}=false"
            )

    return {**safe, "evidence_sha256": evidence_sha}


def build_cross_chain_asset_provenance_response(
    record: Mapping[str, Any],
    *,
    expected_current_asset_id: Any,
    expected_current_asset_id_kind: Any,
) -> dict[str, Any]:
    try:
        safe = validate_cross_chain_provenance_public_record(
            record,
            expected_current_asset_id=expected_current_asset_id,
            expected_current_asset_id_kind=expected_current_asset_id_kind,
        )
    except CrossChainProvenancePublicContractError as exc:
        response = build_service_envelope(
            SERVICE,
            SUPPORTED_CHAIN,
            ERROR,
            data={
                "contract_version": CONTRACT_VERSION,
                "public_service_promoted": True,
                "scout_reliance_promoted": True,
                "execution_authorized": False,
            },
            risk=None,
            errors=[{
                "code": "cross_chain_asset_provenance_contract_violation",
                "message": str(exc),
            }],
        )
        response["execution_authorized"] = False
        return response

    evidence_sha = safe.pop("evidence_sha256")
    canonical = deepcopy(safe)
    verification = deepcopy(canonical["verification"])
    response = build_service_envelope(
        SERVICE,
        SUPPORTED_CHAIN,
        OK,
        asset={
            "canonical_id": canonical["current"]["asset_id"],
            "asset_id": canonical["current"]["asset_id"],
            "asset_id_kind": canonical["current"]["asset_id_kind"],
        },
        data={
            "contract_version": CONTRACT_VERSION,
            "public_service_promoted": True,
            "scout_reliance_promoted": True,
            "read_only": True,
            "canonical_asset_id": canonical["canonical_asset_id"],
            "origin": deepcopy(canonical["origin"]),
            "current": deepcopy(canonical["current"]),
            "representation_depth": canonical["representation_depth"],
            "lineage": deepcopy(canonical["lineage"]),
            "dependencies": deepcopy(canonical["dependencies"]),
            "verification": verification,
            "evidence": {
                "evidence_sha256": evidence_sha,
                "source_independence_verified": verification[
                    "source_independence_verified"
                ],
            },
            "canonical_provenance": canonical,
            "symbol_or_name_identity_inference_authorized": False,
            "bridge_dependency_is_risk": False,
            "custody_dependency_is_risk": False,
            "backing_claim_authorized": False,
            "solvency_claim_authorized": False,
            "safety_claim_authorized": False,
            "adoption_claim_authorized": False,
            "causal_inference_authorized": False,
            "current_bridge_state_claim_authorized": False,
            "risk_promotion_authorized": False,
            "execution_authorized": False,
        },
        risk=None,
        confidence={
            "structural_continuity_verified": True,
            "exact_chain_scoped_identifiers_required": True,
            "source_independence_verified": verification[
                "source_independence_verified"
            ],
        },
        warnings=[{
            "code": "structural_provenance_only",
            "message": (
                "Provenance verifies ordered identity continuity only; it does not "
                "verify live bridge state, backing, solvency, safety, adoption, "
                "causality, custody truth, or risk."
            ),
        }],
    )
    response["execution_authorized"] = False
    return response


__all__ = [
    "CONTRACT_VERSION",
    "CrossChainProvenancePublicContractError",
    "SERVICE",
    "SUPPORTED_CHAIN",
    "build_cross_chain_asset_provenance_response",
    "content_address_provenance",
    "validate_cross_chain_provenance_public_record",
]
