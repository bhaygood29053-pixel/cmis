"""Caller-selector boundary for bounded Tokenized Equity Intelligence.

Callers may select an exact X1 representation and requested intelligence
components. They may not supply facts, evidence, provider material, Proof Score,
risk, legal conclusions, route/deployment claims, or execution authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from liquidity_scout.services.cmis_tokenized_equity_provenance import (
    ALLOWED_SECURITY_ID_KINDS,
)
from liquidity_scout.services.cmis_x1_asset_identity import is_exact_x1_public_key

REQUEST_CONTRACT_VERSION = "tokenized_equity_intelligence_request/v1"
SUPPORTED_CHAIN = "x1"
SUPPORTED_COMPONENTS = (
    "provenance",
    "cross_chain",
    "rights",
    "market_activity",
)
_ALLOWED_KEYS = frozenset(
    {
        "contract_version",
        "chain",
        "asset_mint",
        "security_id",
        "security_id_kind",
        "requested_components",
    }
)
_FORBIDDEN_CALLER_KEYS = frozenset(
    {
        "tokenized_equity_provenance",
        "cross_chain_equity_provenance",
        "tokenized_equity_rights",
        "tokenized_equity_market_activity",
        "tokenized_equity_evidence_quality",
        "component_states",
        "components",
        "resolved_subject",
        "subject_resolution_state",
        "provider",
        "providers",
        "provider_facts",
        "source",
        "sources",
        "evidence",
        "evidence_id",
        "evidence_ids",
        "evidence_receipt",
        "evidence_receipts",
        "content_sha256",
        "proof_score",
        "proof_scores",
        "confidence",
        "freshness",
        "source_independence_verified",
        "same_fact_agreement_verified",
        "rights",
        "voting_rights",
        "dividend_treatment",
        "redemption_rights",
        "backing_collateral",
        "custody_structure",
        "market_metrics",
        "liquidity",
        "volume",
        "price",
        "bridge_route",
        "bridge_routes",
        "bridge_activity",
        "deployment",
        "deployment_verified",
        "adoption",
        "ownership",
        "beneficial_ownership",
        "legal_conclusion",
        "compliance_conclusion",
        "risk",
        "risk_interpretation",
        "public_service_promoted",
        "scout_reliance_promoted",
        "execution_authorized",
    }
)


class TokenizedEquityIntelligenceRequestError(ValueError):
    pass


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise TokenizedEquityIntelligenceRequestError(
            f"{field} must be normalized non-empty text"
        )
    return value


def validate_tokenized_equity_intelligence_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TokenizedEquityIntelligenceRequestError("request must be a mapping")
    request = dict(value)

    forbidden = sorted(_FORBIDDEN_CALLER_KEYS.intersection(request))
    if forbidden:
        raise TokenizedEquityIntelligenceRequestError(
            "caller may not supply CMIS-owned Tokenized Equity trust material: "
            + ", ".join(forbidden)
        )
    unknown = sorted(set(request) - _ALLOWED_KEYS)
    if unknown:
        raise TokenizedEquityIntelligenceRequestError(
            "unsupported Tokenized Equity request fields: " + ", ".join(unknown)
        )
    if request.get("contract_version") != REQUEST_CONTRACT_VERSION:
        raise TokenizedEquityIntelligenceRequestError(
            f"request contract must be {REQUEST_CONTRACT_VERSION}"
        )
    if request.get("chain") != SUPPORTED_CHAIN:
        raise TokenizedEquityIntelligenceRequestError("initial service scope requires chain=x1")

    asset_mint = _text(request.get("asset_mint"), "asset_mint")
    if not is_exact_x1_public_key(asset_mint):
        raise TokenizedEquityIntelligenceRequestError(
            "asset_mint must be an exact 32-byte base58 X1 public key"
        )

    security_id = request.get("security_id")
    security_id_kind = request.get("security_id_kind")
    if (security_id is None) != (security_id_kind is None):
        raise TokenizedEquityIntelligenceRequestError(
            "security_id and security_id_kind must be supplied together"
        )
    if security_id is not None:
        security_id = _text(security_id, "security_id")
        security_id_kind = _text(security_id_kind, "security_id_kind").casefold()
        if security_id_kind not in ALLOWED_SECURITY_ID_KINDS:
            raise TokenizedEquityIntelligenceRequestError(
                "security_id_kind must use an accepted exact security identifier"
            )

    raw_components = request.get("requested_components")
    if not isinstance(raw_components, Sequence) or isinstance(raw_components, (str, bytes)):
        raise TokenizedEquityIntelligenceRequestError(
            "requested_components must be a non-empty list"
        )
    selected: set[str] = set()
    for index, raw in enumerate(raw_components):
        component = _text(raw, f"requested_components[{index}]").casefold()
        if component not in SUPPORTED_COMPONENTS:
            raise TokenizedEquityIntelligenceRequestError(
                f"unsupported requested component: {component}"
            )
        if component in selected:
            raise TokenizedEquityIntelligenceRequestError(
                "requested_components must be unique"
            )
        selected.add(component)
    if not selected:
        raise TokenizedEquityIntelligenceRequestError(
            "requested_components must not be empty"
        )
    if "provenance" not in selected:
        raise TokenizedEquityIntelligenceRequestError(
            "requested_components must include provenance as the identity foundation"
        )
    components = [name for name in SUPPORTED_COMPONENTS if name in selected]

    return {
        "contract_version": REQUEST_CONTRACT_VERSION,
        "chain": SUPPORTED_CHAIN,
        "asset_mint": asset_mint,
        "security_id": security_id,
        "security_id_kind": security_id_kind,
        "requested_components": components,
        "evidence_quality_implicitly_required": True,
        "caller_fact_evidence_provider_material_supplied": False,
        "caller_proof_score_risk_legal_material_supplied": False,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "REQUEST_CONTRACT_VERSION",
    "SUPPORTED_CHAIN",
    "SUPPORTED_COMPONENTS",
    "TokenizedEquityIntelligenceRequestError",
    "validate_tokenized_equity_intelligence_request",
]
