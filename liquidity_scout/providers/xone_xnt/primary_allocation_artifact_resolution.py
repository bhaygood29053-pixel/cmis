"""Lead-driven XONE -> XNT primary allocation artifact resolution.

This provider consumes one explicit artifact lead that a bounded caller already
retrieved. It performs no network discovery and does not enumerate chain
accounts. The goal is to decide whether the artifact is reproducible and exact
enough to hand to a stronger verifier.

Resolution is not allocation truth:
- exact XONE source binding is not snapshot eligibility;
- a Merkle root is not a verified allocation formula;
- an X1 program/IDL is not issuance proof;
- a structured holder file is not an authoritative registry merely because it
  contains addresses or amounts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Any, Optional
from urllib.parse import urlparse

from .allocation_source_provenance import (
    CONTRACT_VERSION as SOURCE_PROVENANCE_CONTRACT_VERSION,
    SOURCE_CLASS_API,
    SOURCE_CLASS_CONTENT_ADDRESSED,
    SOURCE_CLASS_MERKLE,
    SOURCE_CLASS_REGISTRY_EXPORT,
    SOURCE_CLASS_RELEASE_ASSET,
    SOURCE_CLASS_STRUCTURED_FILE,
    SOURCE_CLASS_X1_PROGRAM_SCHEMA,
    XONE_CONTRACT,
    XoneXntAllocationSourceProvenanceError,
    extract_allocation_source_provenance,
)


CONTRACT_VERSION = "xone_xnt_primary_allocation_artifact_resolution/v1"

NO_LEAD = "NO_LEAD"
REJECTED = "REJECTED"
CANDIDATE = "CANDIDATE"
RESOLVED_FOR_HANDOFF = "RESOLVED_FOR_HANDOFF"

HANDOFF_ALLOCATION_RECORDS = "xone_xnt_x1_allocation_record_discovery/v1"
HANDOFF_SNAPSHOT_REGISTRY = "ethereum_xone_snapshot_registry/v1"
HANDOFF_MERKLE_BINDING = "xone_xnt_snapshot_allocation_binding_verification/future"
HANDOFF_X1_PROGRAM_RPC = "xone_xnt_x1_program_account_qualification/future"
HANDOFF_API_VERIFICATION = "xone_xnt_allocation_api_source_verification/future"
HANDOFF_CONTENT_RETRIEVAL = "xone_xnt_content_addressed_artifact_verification/future"
HANDOFF_RELEASE_RESOLUTION = "xone_xnt_release_asset_resolution/future"

SNAPSHOT_BLOCK_RE = re.compile(
    r"\b(?:snapshot\s+(?:block|at\s+block)|block\s+number)\s*"
    r"[:=#-]?\s*(?P<block>[1-9][0-9]{4,11})\b",
    re.IGNORECASE,
)

GENERIC_CONFIG_BASENAMES = {
    "package.json",
    "tsconfig.json",
    "tsconfig.test.json",
    "pyproject.toml",
    "cargo.toml",
}

MOONPARTY_TERMS = ("moonparty", "moon party")


class XoneXntPrimaryAllocationArtifactResolutionError(RuntimeError):
    """Raised when one explicit artifact lead fails integrity/shape checks."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_https_url(value: Any) -> str:
    text = _text(value)
    parsed = urlparse(text)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise XoneXntPrimaryAllocationArtifactResolutionError(
            "lead url must be absolute HTTPS"
        )
    if parsed.username is not None or parsed.password is not None:
        raise XoneXntPrimaryAllocationArtifactResolutionError(
            "lead url must not embed credentials"
        )
    return text


def _sha256_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _normalize_expected_sha256(value: Any) -> Optional[str]:
    text = _text(value).casefold()
    if not text:
        return None
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise XoneXntPrimaryAllocationArtifactResolutionError(
            "expected_sha256 must be exactly 64 hexadecimal characters"
        )
    return text


def _snapshot_blocks(text: str) -> list[int]:
    rows: list[int] = []
    for match in SNAPSHOT_BLOCK_RE.finditer(text):
        block = int(match.group("block"))
        if block not in rows:
            rows.append(block)
    return rows


def _generic_config_path(path: Optional[str]) -> bool:
    normalized = _text(path).replace("\\", "/").casefold()
    if not normalized:
        return False
    return normalized.rsplit("/", 1)[-1] in GENERIC_CONFIG_BASENAMES


def _locator_pinned(
    *,
    revision: Optional[str],
    release_name: Optional[str],
    source_classes: Sequence[str],
    candidate: Mapping[str, Any],
) -> bool:
    if _text(revision) or _text(release_name):
        return True
    if SOURCE_CLASS_CONTENT_ADDRESSED in source_classes:
        return bool(candidate.get("ipfs_cids") or candidate.get("arweave_ids"))
    return False


def _handoffs(
    candidate: Mapping[str, Any],
    *,
    snapshot_blocks: Sequence[int],
) -> list[dict[str, Any]]:
    source_classes = set(candidate.get("source_classes") or [])
    rows: list[dict[str, Any]] = []

    def add(contract: str, reason: str) -> None:
        if contract not in {row["contract"] for row in rows}:
            rows.append(
                {
                    "contract": contract,
                    "reason": reason,
                    "authorized": False,
                }
            )

    if (
        SOURCE_CLASS_STRUCTURED_FILE in source_classes
        or SOURCE_CLASS_REGISTRY_EXPORT in source_classes
    ):
        add(
            HANDOFF_ALLOCATION_RECORDS,
            "structured/export artifact may contain holder or allocation rows",
        )

    if snapshot_blocks:
        add(
            HANDOFF_SNAPSHOT_REGISTRY,
            "artifact contains an explicit candidate snapshot block",
        )

    if SOURCE_CLASS_MERKLE in source_classes:
        add(
            HANDOFF_MERKLE_BINDING,
            "artifact contains Merkle allocation provenance",
        )

    if SOURCE_CLASS_X1_PROGRAM_SCHEMA in source_classes:
        add(
            HANDOFF_X1_PROGRAM_RPC,
            "artifact contains an X1 program/account-schema source",
        )

    if SOURCE_CLASS_API in source_classes:
        add(
            HANDOFF_API_VERIFICATION,
            "artifact identifies an allocation/claim API source",
        )

    if SOURCE_CLASS_CONTENT_ADDRESSED in source_classes:
        add(
            HANDOFF_CONTENT_RETRIEVAL,
            "artifact identifies an immutable content-addressed source",
        )

    if SOURCE_CLASS_RELEASE_ASSET in source_classes:
        add(
            HANDOFF_RELEASE_RESOLUTION,
            "artifact is tied to a release asset/manifest",
        )

    return rows


def no_lead_resolution(*, observed_at: float) -> dict[str, Any]:
    """Return the intended idle state without performing any discovery."""

    return {
        "status": "PASS",
        "contract_version": CONTRACT_VERSION,
        "resolution_state": NO_LEAD,
        "observed_at": observed_at,
        "network_discovery_performed": False,
        "network_request_count": 0,
        "lead_supplied": False,
        "primary_artifact_candidate_discovered": False,
        "primary_artifact_resolved_for_handoff": False,
        "handoffs": [],
        "private_or_unpublished_allocation_source_absence_proven": False,
        "allocation_source_provenance_verified": False,
        "authoritative_allocation_source_verified": False,
        "official_xone_snapshot_verified": False,
        "official_registry_artifact_verified": False,
        "xone_snapshot_eligibility_verified": False,
        "xone_snapshot_xnt_allocation_binding_verified": False,
        "allocation_semantics_verified": False,
        "claim_state_verified": False,
        "vesting_or_unlock_state_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "october_6_unlock_applies_to_xone_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


def resolve_primary_allocation_artifact(
    lead: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve one caller-supplied primary allocation artifact lead.

    The caller supplies already-retrieved text. This function makes zero
    network calls.
    """

    if not isinstance(lead, Mapping):
        raise ValueError("lead must be a mapping")

    source_id = _text(lead.get("source_id"))
    source_role = _text(lead.get("source_role"))
    url = _normalize_https_url(lead.get("url"))
    text = lead.get("text")
    observed_at = lead.get("observed_at")

    if not source_id:
        raise ValueError("lead source_id is required")
    if not source_role:
        raise ValueError("lead source_role is required")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("lead text must be a non-empty string")
    if isinstance(observed_at, bool) or not isinstance(observed_at, (int, float)):
        raise ValueError("lead observed_at must be numeric")

    path = _text(lead.get("path")) or None
    revision = _text(lead.get("revision")) or None
    release_name = _text(lead.get("release_name")) or None
    content_type = _text(lead.get("content_type")) or None
    architecture_analogue = bool(lead.get("architecture_analogue"))
    release_asset = bool(lead.get("release_asset"))
    expected_sha = _normalize_expected_sha256(lead.get("expected_sha256"))

    body_sha = _sha256_text(text)
    expected_sha_match: Optional[bool] = None
    if expected_sha is not None:
        expected_sha_match = body_sha == expected_sha
        if not expected_sha_match:
            raise XoneXntPrimaryAllocationArtifactResolutionError(
                "expected_sha256 does not match lead content"
            )

    lowered = text.casefold()
    if (
        any(term in lowered for term in MOONPARTY_TERMS)
        and "allocation" not in lowered
        and XONE_CONTRACT.casefold() not in lowered
    ):
        return {
            **no_lead_resolution(observed_at=float(observed_at)),
            "resolution_state": REJECTED,
            "lead_supplied": True,
            "rejection_reason": "moonparty_substitute_without_exact_xone_allocation_source",
            "artifact_sha256": body_sha,
        }

    if _generic_config_path(path) and XONE_CONTRACT.casefold() not in lowered:
        return {
            **no_lead_resolution(observed_at=float(observed_at)),
            "resolution_state": REJECTED,
            "lead_supplied": True,
            "rejection_reason": "generic_config_without_exact_xone_binding",
            "artifact_sha256": body_sha,
        }

    try:
        candidates = extract_allocation_source_provenance(
            text,
            source_id=source_id,
            source_role=source_role,
            url=url,
            observed_at=float(observed_at),
            path=path,
            revision=revision,
            release_name=release_name,
            content_type=content_type,
            body_sha256=body_sha,
            release_asset=release_asset,
            architecture_analogue=architecture_analogue,
            max_candidates=10,
        )
    except XoneXntAllocationSourceProvenanceError as exc:
        raise XoneXntPrimaryAllocationArtifactResolutionError(str(exc)) from exc

    if not candidates:
        return {
            **no_lead_resolution(observed_at=float(observed_at)),
            "resolution_state": REJECTED,
            "lead_supplied": True,
            "rejection_reason": "no_concrete_allocation_source_provenance",
            "artifact_sha256": body_sha,
            "expected_sha256_supplied": expected_sha is not None,
            "expected_sha256_match": expected_sha_match,
        }

    # Current provenance extractor emits one consolidated candidate per lead.
    candidate = dict(candidates[0])
    source_classes = list(candidate.get("source_classes") or [])
    snapshot_blocks = _snapshot_blocks(text)
    pinned = _locator_pinned(
        revision=revision,
        release_name=release_name,
        source_classes=source_classes,
        candidate=candidate,
    )
    exact_xone = candidate.get("xone_source_binding_verified") is True
    qualifying = (
        candidate.get("qualifying_xone_allocation_source_candidate") is True
    )
    analogue = candidate.get("architecture_analogue") is True

    handoffs = _handoffs(candidate, snapshot_blocks=snapshot_blocks)
    content_integrity_verified = expected_sha_match is True
    content_addressed_locally = bool(body_sha)
    content_addressed_provenance_complete = bool(
        SOURCE_CLASS_CONTENT_ADDRESSED in source_classes
        and (candidate.get("ipfs_cids") or candidate.get("arweave_ids"))
        and url
        and body_sha
    )
    locator_provenance_complete = bool(
        candidate.get("source_provenance_fields_verified")
        or content_addressed_provenance_complete
    )

    resolved_for_handoff = bool(
        qualifying
        and exact_xone
        and not analogue
        and locator_provenance_complete
        and pinned
        and handoffs
    )

    if resolved_for_handoff:
        state = RESOLVED_FOR_HANDOFF
    else:
        state = CANDIDATE

    return {
        "status": "PASS",
        "contract_version": CONTRACT_VERSION,
        "source_provenance_contract": SOURCE_PROVENANCE_CONTRACT_VERSION,
        "resolution_state": state,
        "observed_at": float(observed_at),
        "network_discovery_performed": False,
        "network_request_count": 0,
        "lead_supplied": True,
        "source_id": source_id,
        "source_role": source_role,
        "url": url,
        "path": path,
        "revision": revision,
        "release_name": release_name,
        "artifact_sha256": body_sha,
        "expected_sha256_supplied": expected_sha is not None,
        "expected_sha256_match": expected_sha_match,
        "content_integrity_verified": content_integrity_verified,
        "content_addressed_locally": content_addressed_locally,
        "locator_pinned": pinned,
        "content_addressed_provenance_complete":
            content_addressed_provenance_complete,
        "locator_provenance_complete": locator_provenance_complete,
        "source_classes": source_classes,
        "snapshot_block_candidates": snapshot_blocks,
        "architecture_analogue": analogue,
        "xone_named": candidate.get("xone_named") is True,
        "exact_xone_contract_mentioned":
            candidate.get("exact_xone_contract_mentioned") is True,
        "xone_semantic_binding_discovered":
            candidate.get("xone_semantic_binding_discovered") is True,
        "xone_source_binding_verified": exact_xone,
        "primary_artifact_candidate_discovered": qualifying,
        "primary_artifact_resolved_for_handoff": resolved_for_handoff,
        "handoffs": handoffs if resolved_for_handoff else [],
        "candidate_handoffs": handoffs,
        "provenance_candidate": candidate,
        # Resolution makes the source reproducible enough for a stronger
        # verifier. It does not promote authority or allocation truth.
        "allocation_source_provenance_verified": False,
        "authoritative_allocation_source_verified": False,
        "official_xone_snapshot_verified": False,
        "official_registry_artifact_verified": False,
        "xone_snapshot_eligibility_verified": False,
        "xone_snapshot_xnt_allocation_binding_verified": False,
        "allocation_semantics_verified": False,
        "claim_state_verified": False,
        "vesting_or_unlock_state_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "october_6_unlock_applies_to_xone_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }
