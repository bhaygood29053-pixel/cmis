"""Final fail-closed Warp Bridge Flow Intelligence binding for CMIS #454.

This module does not discover new facts or recalculate chain evidence. It binds
four already-separated accepted evidence layers:
- exact Warp route qualification;
- canonical settled events from warp_onchain_transfer_history/v1;
- bounded 60-day retention from warp_message_lifecycle_retention/v1;
- exact bridged supply from warp_bridged_supply_evidence/v1.

Only accepted lifecycle coverage is allowed to authorize complete zero windows.
Source independence remains explicit and is never inferred from endpoint count.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from liquidity_scout.providers.x1.warp_bridged_supply_evidence import (
    CONTRACT as SUPPLY_CONTRACT,
)
from liquidity_scout.providers.x1.warp_config_semantics import (
    WARP_CONFIG_SEMANTIC_CONTRACT_ID,
)
from liquidity_scout.providers.x1.warp_message_lifecycle_retention import (
    CONTRACT as LIFECYCLE_CONTRACT,
)
from liquidity_scout.providers.x1.warp_onchain_transfer_history import (
    CONTRACT as TRANSFER_CONTRACT,
)
from liquidity_scout.services.cmis_bridge_flow_intelligence import (
    build_bridge_flow_intelligence,
)
from liquidity_scout.services.cmis_bridge_route_evidence import (
    WARP_QUALIFICATION_CONTRACT,
)

CONTRACT = "warp_bridge_flow_integration/v1"
MISSING_HISTORY_ZERO_SCOPE = "exact_message_universe_requested_lookback_only"


class WarpBridgeFlowIntegrationError(RuntimeError):
    """Raised when accepted #409 evidence layers cannot be bound safely."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WarpBridgeFlowIntegrationError(f"{field} must be a mapping")
    return value


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise WarpBridgeFlowIntegrationError(f"{field} is required")
    return text


def _epoch(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise WarpBridgeFlowIntegrationError(f"{field} must be epoch seconds")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise WarpBridgeFlowIntegrationError(
            f"{field} must be epoch seconds"
        ) from None
    if parsed <= 0:
        raise WarpBridgeFlowIntegrationError(f"{field} must be positive")
    return parsed


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def _route_identity(route_qualification: Any) -> dict[str, Any]:
    qualification = _mapping(route_qualification, "route_qualification")
    if qualification.get("contract") != WARP_QUALIFICATION_CONTRACT:
        raise WarpBridgeFlowIntegrationError(
            f"route_qualification must use {WARP_QUALIFICATION_CONTRACT}"
        )
    if qualification.get("warp_qualified") is not True:
        raise WarpBridgeFlowIntegrationError("Warp route must be qualified")
    evidence = _mapping(
        qualification.get("route_evidence"),
        "route_qualification.route_evidence",
    )
    if evidence.get("qualified") is not True:
        raise WarpBridgeFlowIntegrationError("route evidence must be qualified")
    if evidence.get("semantic_contract_id") != WARP_CONFIG_SEMANTIC_CONTRACT_ID:
        raise WarpBridgeFlowIntegrationError(
            "exact Warp mint-pair semantic contract is required"
        )
    return {
        "route_id": _text(evidence.get("route_id"), "route_id"),
        "source": dict(_mapping(evidence.get("source"), "route source")),
        "destination": dict(
            _mapping(evidence.get("destination"), "route destination")
        ),
        "semantic_contract_id": evidence["semantic_contract_id"],
    }


def _validate_events(normalized_events: Any, *, route_id: str) -> Mapping[str, Any]:
    normalized = _mapping(normalized_events, "normalized_events")
    if normalized.get("contract") != TRANSFER_CONTRACT:
        raise WarpBridgeFlowIntegrationError(
            f"normalized_events must use {TRANSFER_CONTRACT}"
        )
    if normalized.get("route_id") != route_id:
        raise WarpBridgeFlowIntegrationError("normalized event route mismatch")
    for field in (
        "pairing_semantics_verified",
        "settled_event_semantics_verified",
        "flow_event_normalization_authorized",
    ):
        if normalized.get(field) is not True:
            raise WarpBridgeFlowIntegrationError(
                f"normalized_events.{field} must be true"
            )
    if normalized.get("execution_authorized") is not False:
        raise WarpBridgeFlowIntegrationError(
            "normalized event evidence must remain read-only"
        )
    events = normalized.get("events")
    if not isinstance(events, Sequence) or isinstance(
        events, (str, bytes, bytearray)
    ):
        raise WarpBridgeFlowIntegrationError("normalized_events.events must be a sequence")
    unresolved = normalized.get("unresolved_counts")
    if not isinstance(unresolved, Mapping):
        raise WarpBridgeFlowIntegrationError(
            "normalized_events.unresolved_counts must be a mapping"
        )
    return normalized


def _validate_lifecycle(lifecycle_retention: Any) -> Mapping[str, Any]:
    lifecycle = _mapping(lifecycle_retention, "lifecycle_retention")
    if lifecycle.get("contract") != LIFECYCLE_CONTRACT:
        raise WarpBridgeFlowIntegrationError(
            f"lifecycle_retention must use {LIFECYCLE_CONTRACT}"
        )
    for field in (
        "program_signature_trace_complete_verified",
        "requested_history_boundary_verified",
        "no_message_account_closure_observed",
        "no_message_account_recreation_observed",
        "no_ambiguous_zero_zero_lifecycle_touch",
        "expected_outgoing_creations_verified",
        "retention_deletion_semantics_verified",
        "historical_retention_complete_verified",
        "requested_window_coverage_verified",
        "coverage_complete_verified",
        "missing_history_zero_authorized",
    ):
        if lifecycle.get(field) is not True:
            raise WarpBridgeFlowIntegrationError(
                f"lifecycle_retention.{field} must be true"
            )
    if lifecycle.get("missing_history_zero_scope") != MISSING_HISTORY_ZERO_SCOPE:
        raise WarpBridgeFlowIntegrationError(
            "lifecycle missing-history zero scope is not accepted"
        )
    if lifecycle.get("execution_authorized") is not False:
        raise WarpBridgeFlowIntegrationError(
            "lifecycle evidence must remain read-only"
        )
    requested_start = _epoch(
        lifecycle.get("requested_start"),
        "lifecycle_retention.requested_start",
    )
    as_of = _epoch(lifecycle.get("as_of"), "lifecycle_retention.as_of")
    if requested_start >= as_of:
        raise WarpBridgeFlowIntegrationError(
            "lifecycle requested_start must predate as_of"
        )
    return lifecycle


def _validate_supply(bridged_supply: Any, *, route_id: str) -> Mapping[str, Any]:
    supply = _mapping(bridged_supply, "bridged_supply")
    if supply.get("contract") != SUPPLY_CONTRACT:
        raise WarpBridgeFlowIntegrationError(
            f"bridged_supply must use {SUPPLY_CONTRACT}"
        )
    if supply.get("route_id") != route_id:
        raise WarpBridgeFlowIntegrationError("bridged supply route mismatch")
    for field in (
        "current_backing_closure_verified",
        "bridged_supply_verified",
    ):
        if supply.get(field) is not True:
            raise WarpBridgeFlowIntegrationError(
                f"bridged_supply.{field} must be true"
            )
    evidence = _mapping(supply.get("supply_evidence"), "bridged_supply.supply_evidence")
    if evidence.get("verified") is not True:
        raise WarpBridgeFlowIntegrationError("supply evidence must be verified")
    if evidence.get("semantic_contract_accepted") is not True:
        raise WarpBridgeFlowIntegrationError(
            "supply semantic contract must be accepted"
        )
    if supply.get("provider_tvl_label_promoted") is not False:
        raise WarpBridgeFlowIntegrationError(
            "provider TVL label cannot be promoted as supply truth"
        )
    if supply.get("execution_authorized") is not False:
        raise WarpBridgeFlowIntegrationError(
            "bridged supply evidence must remain read-only"
        )
    return supply


def build_warp_bridge_flow_integration(
    *,
    route_qualification: Any,
    normalized_events: Any,
    lifecycle_retention: Any,
    bridged_supply: Any,
    source_independence_verified: bool = False,
) -> dict[str, Any]:
    """Bind accepted #441 + #451 evidence into bridge_flow_intelligence/v1."""

    if not isinstance(source_independence_verified, bool):
        raise WarpBridgeFlowIntegrationError(
            "source_independence_verified must be boolean"
        )

    route = _route_identity(route_qualification)
    normalized = _validate_events(normalized_events, route_id=route["route_id"])
    lifecycle = _validate_lifecycle(lifecycle_retention)
    supply = _validate_supply(bridged_supply, route_id=route["route_id"])

    as_of = _epoch(lifecycle["as_of"], "lifecycle_retention.as_of")
    coverage_start = _epoch(
        lifecycle["requested_start"],
        "lifecycle_retention.requested_start",
    )

    flow = build_bridge_flow_intelligence(
        route_qualification=route_qualification,
        events=normalized["events"],
        as_of=as_of,
        coverage_start=coverage_start,
        coverage_end=as_of,
        supply_evidence=supply["supply_evidence"],
        coverage_verified=True,
        source_independence_verified=source_independence_verified,
    )

    windows_complete = all(
        window[period]["coverage_complete"] is True
        for window in flow["windows"].values()
        for period in ("current", "prior")
    )
    windows_non_null = all(
        window[period][field] is not None
        for window in flow["windows"].values()
        for period in ("current", "prior")
        for field in (
            "inflow_raw",
            "outflow_raw",
            "net_flow_raw",
            "inflow_event_count",
            "outflow_event_count",
        )
    )
    unresolved_counts = dict(sorted(normalized["unresolved_counts"].items()))
    normalized_unresolved_count = sum(
        int(value) for value in unresolved_counts.values()
    )
    canonical_event_pairing_complete = bool(
        normalized.get("candidate_route_outgoing_count")
        == normalized.get("accepted_settled_event_count")
        and normalized_unresolved_count == 0
    )
    integration_verified = bool(
        flow["coverage"]["complete_for_all_current_and_prior_windows"]
        and windows_complete
        and windows_non_null
        and flow["bridged_supply"]["verified"] is True
        and canonical_event_pairing_complete
    )

    core = {
        "contract": CONTRACT,
        "route_id": route["route_id"],
        "source": route["source"],
        "destination": route["destination"],
        "semantic_contract_id": route["semantic_contract_id"],
        "route_qualification_verified": True,
        "canonical_event_pairing_verified": canonical_event_pairing_complete,
        "normalized_unresolved_counts": unresolved_counts,
        "lifecycle_retention_contract": lifecycle["contract"],
        "historical_retention_complete_verified": True,
        "requested_window_coverage_verified": True,
        "coverage_complete_verified": True,
        "missing_history_zero_authorized": True,
        "missing_history_zero_scope": lifecycle["missing_history_zero_scope"],
        "coverage_start": coverage_start,
        "coverage_end": as_of,
        "bridged_supply_contract": supply["contract"],
        "bridged_supply_verified": flow["bridged_supply"]["verified"] is True,
        "source_independence_verified": source_independence_verified,
        "all_current_and_prior_windows_complete": windows_complete,
        "all_current_and_prior_window_values_non_null": windows_non_null,
        "integration_verified": integration_verified,
        "flow": flow,
        "provider_tvl_label_promoted": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }
    return {
        **core,
        "evidence_sha256": _canonical_sha256(core),
    }


__all__ = [
    "CONTRACT",
    "MISSING_HISTORY_ZERO_SCOPE",
    "WarpBridgeFlowIntegrationError",
    "build_warp_bridge_flow_integration",
]
