"""Public service-envelope projection for X1 Intelligence Brief inputs.

This module wraps one already-validated/non-promoted
`x1_intelligence_brief_inputs/v1` composition inside the standard CMIS
service envelope.

The nested composition contract remains a factual foundation and therefore
keeps its own promotion flags false. The outer service envelope carries the
candidate runtime/service promotion state for CMIS 1.28. This separation avoids
silently mutating the accepted `x1_intelligence_brief_inputs/v1` payload while
still exposing an explicit promoted service boundary after protected acceptance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from liquidity_scout.services.cmis_contract import OK, PARTIAL, build_service_envelope
from liquidity_scout.services.cmis_x1_intelligence_brief_inputs import (
    CONTRACT_VERSION,
    SUPPORTED_CHAIN,
    SUPPORTED_COMPONENT_CONTRACTS,
)


SERVICE = "x1_intelligence_brief_inputs"


class X1IntelligenceBriefServiceContractError(ValueError):
    """Raised when a brief composition cannot be projected safely."""


def _mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise X1IntelligenceBriefServiceContractError(f"{name} must be a mapping")
    return value


def _sequence(name: str, value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray, Mapping)
    ):
        raise X1IntelligenceBriefServiceContractError(f"{name} must be a list")
    return list(value)


def validate_x1_intelligence_brief_service_input(value: Any) -> dict[str, Any]:
    """Validate one accepted non-promoted brief composition."""

    brief = deepcopy(dict(_mapping("brief_inputs", value)))

    if brief.get("contract_version") != CONTRACT_VERSION:
        raise X1IntelligenceBriefServiceContractError(
            f"brief_inputs must use {CONTRACT_VERSION}"
        )
    if brief.get("chain") != SUPPORTED_CHAIN:
        raise X1IntelligenceBriefServiceContractError(
            "X1 Intelligence Brief service accepts X1 compositions only"
        )
    if brief.get("read_only") is not True:
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs must remain read_only=true"
        )
    for field in (
        "public_service_promoted",
        "scout_reliance_promoted",
        "priority_is_risk_severity",
        "missing_evidence_zero_filled",
        "complete_x1_ecosystem_coverage_verified",
        "execution_authorized",
    ):
        if brief.get(field) is not False:
            raise X1IntelligenceBriefServiceContractError(
                f"brief_inputs must keep {field}=false"
            )
    if brief.get("proof_score_separate_from_risk") is not True:
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs must keep Proof Score separate from risk"
        )

    subjects = _sequence("brief_inputs.subjects", brief.get("subjects"))
    services = _sequence(
        "brief_inputs.requested_services", brief.get("requested_services")
    )
    if not subjects or not services:
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs subjects and requested_services must not be empty"
        )
    if len(set(subjects)) != len(subjects):
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs subjects must be unique"
        )
    if len(set(services)) != len(services):
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs requested_services must be unique"
        )
    unsupported = sorted(set(services) - set(SUPPORTED_COMPONENT_CONTRACTS))
    if unsupported:
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs contains unsupported services: " + ", ".join(unsupported)
        )

    window = _mapping("brief_inputs.window", brief.get("window"))
    if window.get("end_exclusive") is not True:
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs must preserve end-exclusive window semantics"
        )
    duration = window.get("duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, int):
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs window duration_seconds must be integer"
        )
    if duration <= 0 or duration > 86400:
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs window must be >0 and <=86400 seconds"
        )

    items = _sequence("brief_inputs.items", brief.get("items"))
    for index, raw in enumerate(items):
        item = _mapping(f"brief_inputs.items[{index}]", raw)
        if item.get("execution_authorized") is not False:
            raise X1IntelligenceBriefServiceContractError(
                "brief item execution_authorized must remain false"
            )
        if item.get("priority_is_risk_severity") is not False:
            raise X1IntelligenceBriefServiceContractError(
                "brief item priority must remain separate from risk severity"
            )
        if item.get("proof_strength_separate_from_risk") is not True:
            raise X1IntelligenceBriefServiceContractError(
                "brief item Proof Score must remain separate from risk"
            )
        if item.get("complete_x1_ecosystem_coverage_verified") is not False:
            raise X1IntelligenceBriefServiceContractError(
                "brief item must not claim complete X1 ecosystem coverage"
            )

    coverage = _mapping("brief_inputs.coverage", brief.get("coverage"))
    if coverage.get("complete_x1_ecosystem_coverage_verified") is not False:
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs coverage must not claim complete X1 ecosystem coverage"
        )
    if coverage.get("component_response_matrix_complete") is not True:
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs requires a complete subject/service response matrix"
        )
    if coverage.get("included_item_count") != len(items):
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs coverage item count must match items"
        )
    if coverage.get("window_end_exclusive") is not True:
        raise X1IntelligenceBriefServiceContractError(
            "brief_inputs coverage must preserve end-exclusive window semantics"
        )

    return brief


def _response_status(coverage: Mapping[str, Any]) -> str:
    for key in (
        "partial_service_classes",
        "unavailable_service_classes",
        "error_or_ambiguous_service_classes",
    ):
        values = coverage.get(key)
        if isinstance(values, Sequence) and not isinstance(
            values, (str, bytes, bytearray, Mapping)
        ) and len(values) > 0:
            return PARTIAL
    return OK


def build_x1_intelligence_brief_service_response(
    brief_inputs: Any,
) -> dict[str, Any]:
    """Wrap bounded brief inputs in the standard public CMIS envelope."""

    validated = validate_x1_intelligence_brief_service_input(brief_inputs)
    coverage = _mapping("brief_inputs.coverage", validated["coverage"])
    services = list(validated["requested_services"])

    warnings = [
        {
            "code": "bounded_x1_intelligence_brief_scope",
            "message": (
                "Complete X1 ecosystem coverage is not verified; this response "
                "covers only the exact requested subjects, services, and window."
            ),
        }
    ]
    if not validated["items"]:
        warnings.append(
            {
                "code": "empty_bounded_brief_is_not_global_no_activity",
                "message": (
                    "No included item in this bounded response does not mean "
                    "nothing happened on X1."
                ),
            }
        )

    response = build_service_envelope(
        SERVICE,
        SUPPORTED_CHAIN,
        _response_status(coverage),
        asset={},
        data=validated,
        risk=None,
        confidence={
            "basis": "deterministic_bounded_cmis_component_composition",
            "proof_score_separate_from_risk": True,
            "complete_x1_ecosystem_coverage_verified": False,
        },
        sources=[
            {
                "component_service": service,
                "component_contract_version": SUPPORTED_COMPONENT_CONTRACTS[service],
            }
            for service in services
        ],
        observed_at=None,
        freshness=None,
        warnings=warnings,
        errors=[],
    )
    response["read_only"] = True
    response["public_service_promoted"] = True
    response["scout_reliance_promoted"] = True
    response["runtime_capability_promoted"] = True
    response["complete_x1_ecosystem_coverage_verified"] = False
    response["execution_authorized"] = False
    return response


__all__ = [
    "CONTRACT_VERSION",
    "SERVICE",
    "SUPPORTED_CHAIN",
    "X1IntelligenceBriefServiceContractError",
    "build_x1_intelligence_brief_service_response",
    "validate_x1_intelligence_brief_service_input",
]
