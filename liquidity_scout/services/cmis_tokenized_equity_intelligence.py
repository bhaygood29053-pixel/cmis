"""Public projection contract for bounded Tokenized Equity Intelligence.

The protected runtime owns canonical subject/component resolution. This module
revalidates one protected materialization and projects it into the standard CMIS
service envelope. Shipping the module alone does not register or promote the
runtime service.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from liquidity_scout.services.cmis_contract import OK, PARTIAL, build_service_envelope
from liquidity_scout.services.cmis_tokenized_equity_evidence_quality import (
    TOKENIZED_EQUITY_EVIDENCE_QUALITY_CONTRACT,
    build_tokenized_equity_evidence_quality,
)
from liquidity_scout.services.cmis_tokenized_equity_intelligence_request import (
    REQUEST_CONTRACT_VERSION,
    SUPPORTED_CHAIN,
    validate_tokenized_equity_intelligence_request,
)
from liquidity_scout.services.cmis_tokenized_equity_provenance import (
    TOKENIZED_EQUITY_PROVENANCE_CONTRACT,
)
from liquidity_scout.services.cmis_cross_chain_equity_provenance import (
    CROSS_CHAIN_EQUITY_PROVENANCE_CONTRACT,
)
from liquidity_scout.services.cmis_tokenized_equity_rights import (
    TOKENIZED_EQUITY_RIGHTS_CONTRACT,
)
from liquidity_scout.services.cmis_tokenized_equity_market_activity import (
    TOKENIZED_EQUITY_MARKET_ACTIVITY_CONTRACT,
)

SERVICE = "tokenized_equity_intelligence"
CONTRACT_VERSION = "tokenized_equity_intelligence/v1"
MATERIALIZATION_CONTRACT_VERSION = "tokenized_equity_intelligence_materialization/v1"
MATERIALIZATION_ID_PREFIX = "tei_"
SUBJECT_STATES = frozenset({"RESOLVED", "EVIDENCE_REQUIRED"})
COMPONENT_STATES = frozenset({"AVAILABLE", "EVIDENCE_REQUIRED", "UNAVAILABLE", "ERROR"})
COMPONENT_CONTRACTS = {
    "provenance": TOKENIZED_EQUITY_PROVENANCE_CONTRACT,
    "cross_chain": CROSS_CHAIN_EQUITY_PROVENANCE_CONTRACT,
    "rights": TOKENIZED_EQUITY_RIGHTS_CONTRACT,
    "market_activity": TOKENIZED_EQUITY_MARKET_ACTIVITY_CONTRACT,
}
PROMOTED = False
_ID_RE = re.compile(r"^tei_[0-9a-f]{64}$")
_MATERIALIZATION_KEYS = frozenset(
    {
        "materialization_id",
        "contract_version",
        "chain",
        "request",
        "subject_resolution_state",
        "resolved_subject",
        "component_states",
        "components",
        "evidence_quality",
        "read_only",
        "public_service_promoted",
        "scout_reliance_promoted",
        "caller_fact_evidence_provider_material_accepted",
        "caller_proof_score_risk_legal_material_accepted",
        "live_x1_equity_deployment_verified",
        "live_robinhood_x1_route_verified",
        "execution_authorized",
    }
)


class TokenizedEquityIntelligenceContractError(ValueError):
    pass


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TokenizedEquityIntelligenceContractError(f"{field} must be a mapping")
    return value


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise TokenizedEquityIntelligenceContractError(
            "materialization must be canonical JSON-compatible data"
        ) from exc


def _materialization_id(value: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
    return f"{MATERIALIZATION_ID_PREFIX}{digest}"


def content_address_tokenized_equity_intelligence_materialization(
    value: Any,
) -> dict[str, Any]:
    """Content-address protected material without accepting caller identity."""

    material = deepcopy(dict(_mapping(value, "materialization")))
    if "materialization_id" in material:
        raise TokenizedEquityIntelligenceContractError(
            "materialization must not contain caller/precomputed materialization_id"
        )
    return {**material, "materialization_id": _materialization_id(material)}


def _subject_from_provenance(value: Mapping[str, Any]) -> dict[str, Any]:
    token = _mapping(value.get("token"), "components.provenance.token")
    security = _mapping(
        value.get("underlying_security"),
        "components.provenance.underlying_security",
    )
    return {
        "chain": token.get("chain"),
        "asset_mint": token.get("asset_id"),
        "asset_id_kind": token.get("asset_id_kind"),
        "security_id": security.get("security_id"),
        "security_id_kind": security.get("security_id_kind"),
    }


def _validate_resolved_subject(
    value: Any,
    *,
    request: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    subject = dict(_mapping(value, "resolved_subject"))
    expected = _subject_from_provenance(provenance)
    if subject != expected:
        raise TokenizedEquityIntelligenceContractError(
            "resolved_subject must exactly equal accepted provenance subject"
        )
    if subject.get("chain") != SUPPORTED_CHAIN:
        raise TokenizedEquityIntelligenceContractError(
            "resolved subject must be current X1 representation"
        )
    if subject.get("asset_mint") != request.get("asset_mint"):
        raise TokenizedEquityIntelligenceContractError(
            "resolved asset mint must equal caller selector"
        )
    if request.get("security_id") is not None:
        if subject.get("security_id") != request.get("security_id"):
            raise TokenizedEquityIntelligenceContractError(
                "resolved security id must equal optional caller selector"
            )
        if subject.get("security_id_kind") != request.get("security_id_kind"):
            raise TokenizedEquityIntelligenceContractError(
                "resolved security id kind must equal optional caller selector"
            )
    return subject


def validate_tokenized_equity_intelligence_materialization(value: Any) -> dict[str, Any]:
    original = deepcopy(dict(_mapping(value, "materialization")))
    missing = sorted(_MATERIALIZATION_KEYS - set(original))
    unknown = sorted(set(original) - _MATERIALIZATION_KEYS)
    if missing:
        raise TokenizedEquityIntelligenceContractError(
            "materialization missing required fields: " + ", ".join(missing)
        )
    if unknown:
        raise TokenizedEquityIntelligenceContractError(
            "materialization contains unsupported fields: " + ", ".join(unknown)
        )

    supplied = deepcopy(original)
    supplied_id = supplied.pop("materialization_id")
    if not isinstance(supplied_id, str) or not _ID_RE.fullmatch(supplied_id):
        raise TokenizedEquityIntelligenceContractError(
            "materialization_id must be canonical tei_ SHA-256 identity"
        )
    if supplied_id != _materialization_id(supplied):
        raise TokenizedEquityIntelligenceContractError(
            "materialization content identity mismatch"
        )
    if supplied.get("contract_version") != MATERIALIZATION_CONTRACT_VERSION:
        raise TokenizedEquityIntelligenceContractError(
            f"materialization must use {MATERIALIZATION_CONTRACT_VERSION}"
        )
    if supplied.get("chain") != SUPPORTED_CHAIN:
        raise TokenizedEquityIntelligenceContractError(
            "materialization must use chain=x1"
        )
    for field in (
        "public_service_promoted",
        "scout_reliance_promoted",
        "caller_fact_evidence_provider_material_accepted",
        "caller_proof_score_risk_legal_material_accepted",
        "live_x1_equity_deployment_verified",
        "live_robinhood_x1_route_verified",
        "execution_authorized",
    ):
        if supplied.get(field) is not False:
            raise TokenizedEquityIntelligenceContractError(
                f"protected materialization must keep {field}=false"
            )
    if supplied.get("read_only") is not True:
        raise TokenizedEquityIntelligenceContractError(
            "protected materialization must remain read_only=true"
        )

    try:
        request = validate_tokenized_equity_intelligence_request(supplied.get("request"))
    except ValueError as exc:
        raise TokenizedEquityIntelligenceContractError(str(exc)) from exc

    subject_state = supplied.get("subject_resolution_state")
    if subject_state not in SUBJECT_STATES:
        raise TokenizedEquityIntelligenceContractError(
            "subject_resolution_state is not accepted"
        )
    states = dict(_mapping(supplied.get("component_states"), "component_states"))
    requested = request["requested_components"]
    if set(states) != set(requested):
        raise TokenizedEquityIntelligenceContractError(
            "component_states must exactly cover requested_components"
        )
    if any(state not in COMPONENT_STATES for state in states.values()):
        raise TokenizedEquityIntelligenceContractError(
            "component_states contains unsupported state"
        )
    components = dict(_mapping(supplied.get("components"), "components"))
    if set(components) != {name for name, state in states.items() if state == "AVAILABLE"}:
        raise TokenizedEquityIntelligenceContractError(
            "components must contain exactly AVAILABLE requested components"
        )

    if subject_state == "EVIDENCE_REQUIRED":
        if supplied.get("resolved_subject") is not None:
            raise TokenizedEquityIntelligenceContractError(
                "unresolved subject cannot carry resolved_subject"
            )
        if components:
            raise TokenizedEquityIntelligenceContractError(
                "unresolved subject cannot carry resolved components"
            )
        if any(state != "EVIDENCE_REQUIRED" for state in states.values()):
            raise TokenizedEquityIntelligenceContractError(
                "unresolved subject keeps every requested component EVIDENCE_REQUIRED"
            )
        if supplied.get("evidence_quality") is not None:
            raise TokenizedEquityIntelligenceContractError(
                "unresolved subject cannot carry evidence quality material"
            )
        return {**supplied, "materialization_id": supplied_id}

    if states.get("provenance") != "AVAILABLE":
        raise TokenizedEquityIntelligenceContractError(
            "resolved subject requires AVAILABLE provenance"
        )
    provenance = dict(_mapping(components.get("provenance"), "components.provenance"))
    if provenance.get("contract") != TOKENIZED_EQUITY_PROVENANCE_CONTRACT:
        raise TokenizedEquityIntelligenceContractError(
            "provenance component must use accepted contract"
        )
    if provenance.get("execution_authorized") is not False:
        raise TokenizedEquityIntelligenceContractError(
            "provenance component must preserve execution_authorized=false"
        )
    resolved_subject = _validate_resolved_subject(
        supplied.get("resolved_subject"), request=request, provenance=provenance
    )

    optional_args: dict[str, Any] = {}
    for name, argument_name in (
        ("cross_chain", "cross_chain_equity_provenance"),
        ("rights", "tokenized_equity_rights"),
        ("market_activity", "tokenized_equity_market_activity"),
    ):
        if states.get(name) == "AVAILABLE":
            component = dict(_mapping(components.get(name), f"components.{name}"))
            if component.get("contract") != COMPONENT_CONTRACTS[name]:
                raise TokenizedEquityIntelligenceContractError(
                    f"{name} component must use accepted contract"
                )
            if component.get("execution_authorized") is not False:
                raise TokenizedEquityIntelligenceContractError(
                    f"{name} component must preserve execution_authorized=false"
                )
            optional_args[argument_name] = component

    try:
        expected_quality = build_tokenized_equity_evidence_quality(
            tokenized_equity_provenance=provenance,
            **optional_args,
        )
    except ValueError as exc:
        raise TokenizedEquityIntelligenceContractError(str(exc)) from exc
    if expected_quality.get("contract") != TOKENIZED_EQUITY_EVIDENCE_QUALITY_CONTRACT:
        raise TokenizedEquityIntelligenceContractError(
            "evidence quality contract mismatch"
        )
    if supplied.get("evidence_quality") != expected_quality:
        raise TokenizedEquityIntelligenceContractError(
            "evidence_quality must exactly equal deterministic accepted reconstruction"
        )
    if expected_quality.get("execution_authorized") is not False:
        raise TokenizedEquityIntelligenceContractError(
            "evidence quality must preserve execution_authorized=false"
        )

    return {
        **supplied,
        "resolved_subject": resolved_subject,
        "materialization_id": supplied_id,
    }


def build_tokenized_equity_intelligence_response(materialization: Any) -> dict[str, Any]:
    safe = validate_tokenized_equity_intelligence_materialization(materialization)
    request = validate_tokenized_equity_intelligence_request(safe["request"])
    states = safe["component_states"]
    complete = safe["subject_resolution_state"] == "RESOLVED" and all(
        states[name] == "AVAILABLE" for name in request["requested_components"]
    )
    status = OK if complete else PARTIAL
    warnings = [
        {
            "code": "bounded_tokenized_equity_scope",
            "message": (
                "This service covers only the exact X1 mint, optional exact security "
                "selector, and requested components; service availability does not "
                "prove a tokenized equity is deployed on X1."
            ),
        }
    ]
    if not complete:
        warnings.append(
            {
                "code": "tokenized_equity_evidence_incomplete",
                "message": (
                    "One or more requested components lack accepted CMIS evidence; "
                    "missing evidence remains unknown/evidence-required."
                ),
            }
        )

    response = build_service_envelope(
        SERVICE,
        SUPPORTED_CHAIN,
        status,
        asset={
            "canonical_id": request["asset_mint"],
            "asset_id": request["asset_mint"],
            "asset_id_kind": "mint",
        },
        data={
            "contract_version": CONTRACT_VERSION,
            "request_contract_version": REQUEST_CONTRACT_VERSION,
            "materialization_contract_version": MATERIALIZATION_CONTRACT_VERSION,
            "materialization_id": safe["materialization_id"],
            "subject_resolution_state": safe["subject_resolution_state"],
            "resolved_subject": deepcopy(safe.get("resolved_subject")),
            "requested_components": list(request["requested_components"]),
            "component_states": deepcopy(states),
            "components": deepcopy(safe["components"]),
            "evidence_quality": deepcopy(safe.get("evidence_quality")),
            "live_x1_equity_deployment_verified": False,
            "live_robinhood_x1_route_verified": False,
            "rights_are_legal_adjudication": False,
            "liquidity_equals_volume": False,
            "transfer_equals_trade": False,
            "bridge_flow_equals_adoption": False,
            "reference_price_equals_executed_price": False,
            "proof_score_separate_from_risk": True,
            "read_only": True,
            "public_service_promoted": PROMOTED,
            "scout_reliance_promoted": PROMOTED,
            "execution_authorized": False,
        },
        risk=None,
        confidence={
            "basis": "accepted_rwa_component_and_evidence_quality_contracts",
            "proof_score": None,
            "proof_score_owned_by_protected_runtime": True,
            "proof_score_separate_from_risk": True,
            "complete_requested_component_coverage": complete,
        },
        warnings=warnings,
        errors=[],
    )
    response["read_only"] = True
    response["public_service_promoted"] = PROMOTED
    response["scout_reliance_promoted"] = PROMOTED
    response["runtime_capability_promoted"] = PROMOTED
    response["execution_authorized"] = False
    return response


__all__ = [
    "COMPONENT_CONTRACTS",
    "COMPONENT_STATES",
    "CONTRACT_VERSION",
    "MATERIALIZATION_CONTRACT_VERSION",
    "PROMOTED",
    "SERVICE",
    "SUBJECT_STATES",
    "TokenizedEquityIntelligenceContractError",
    "build_tokenized_equity_intelligence_response",
    "content_address_tokenized_equity_intelligence_materialization",
    "validate_tokenized_equity_intelligence_materialization",
]
