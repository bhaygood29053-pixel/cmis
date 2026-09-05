"""Public promotion wrapper for accepted Bridge-to-XDEX Utilization Intelligence.

Issue #482 promotes only canonical CMIS-owned bridge_to_xdex_utilization/v1
records. The wrapper validates identity, scope, freshness, units, evidence
integrity, and safety boundaries, then exposes the accepted record without
recomputing bridge flow, XDEX liquidity/volume, value basis, or utilization.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any

from liquidity_scout.services.cmis_bridge_to_xdex_utilization import (
    CONTRACT_VERSION,
    SERVICE,
)
from liquidity_scout.services.cmis_contract import ERROR, OK, build_service_envelope

SUPPORTED_CHAIN = "x1"
PROMOTED_SCOPE = "verified_xdex_program_family"
DEFAULT_MAX_EVIDENCE_AGE_SECONDS = 300.0


class BridgeToXdexPublicContractError(ValueError):
    pass


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise BridgeToXdexPublicContractError(f"{field} must be normalized text")
    return value


def _positive_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise BridgeToXdexPublicContractError(f"{field} must be positive")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise BridgeToXdexPublicContractError(f"{field} must be positive") from exc
    if parsed <= 0:
        raise BridgeToXdexPublicContractError(f"{field} must be positive")
    return parsed


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


def validate_bridge_to_xdex_public_record(
    record: Mapping[str, Any],
    *,
    expected_route_id: str,
    expected_source_mint: str,
    expected_destination_mint: str,
    evaluated_at: Any,
    max_evidence_age_seconds: Any = DEFAULT_MAX_EVIDENCE_AGE_SECONDS,
) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise BridgeToXdexPublicContractError(
            "canonical utilization record must be a mapping"
        )
    safe = deepcopy(dict(record))
    evidence_sha = _text(safe.get("evidence_sha256"), "evidence_sha256")
    material = deepcopy(safe)
    material.pop("evidence_sha256", None)
    if evidence_sha != _canonical_sha256(material):
        raise BridgeToXdexPublicContractError(
            "canonical utilization evidence hash mismatch"
        )

    if safe.get("service") != SERVICE or safe.get("contract") != CONTRACT_VERSION:
        raise BridgeToXdexPublicContractError(
            f"canonical utilization must use {CONTRACT_VERSION}"
        )

    route_id = _text(safe.get("route_id"), "route_id")
    source_mint = _text(safe.get("source_mint"), "source_mint")
    destination_mint = _text(safe.get("destination_mint"), "destination_mint")
    if safe.get("representation_mint") != destination_mint:
        raise BridgeToXdexPublicContractError(
            "representation mint must equal exact destination mint"
        )
    if route_id != _text(expected_route_id, "expected_route_id"):
        raise BridgeToXdexPublicContractError("route identity mismatch")
    if source_mint != _text(expected_source_mint, "expected_source_mint"):
        raise BridgeToXdexPublicContractError("source mint identity mismatch")
    if destination_mint != _text(
        expected_destination_mint, "expected_destination_mint"
    ):
        raise BridgeToXdexPublicContractError("destination mint identity mismatch")
    if safe.get("source_chain") != "solana" or safe.get("destination_chain") != "x1":
        raise BridgeToXdexPublicContractError(
            "accepted #482 route must preserve Solana source and X1 destination"
        )

    if safe.get("xdex_pool_universe_scope") != PROMOTED_SCOPE:
        raise BridgeToXdexPublicContractError(
            "only verified XDEX program-family scope is promotable"
        )
    if safe.get("recognized_program_registry_globally_exhaustive") is not False:
        raise BridgeToXdexPublicContractError(
            "recognized XDEX program registry must not be globally exhaustive"
        )
    if safe.get("global_onchain_pool_discovery_proven") is not False:
        raise BridgeToXdexPublicContractError(
            "global X1 DEX discovery must remain unproven"
        )

    for field in (
        "comparable_value_basis_verified",
        "volume_24h_window_coverage_verified",
        "market_activity_24h_verified",
        "utilization_verified",
        "issue_410_acceptance_verified",
    ):
        if safe.get(field) is not True:
            raise BridgeToXdexPublicContractError(f"{field} must be true")

    if safe.get("value_unit") != "USD":
        raise BridgeToXdexPublicContractError("value_unit must be USD")
    flow = safe.get("bridge_flow_24h")
    if not isinstance(flow, Mapping) or flow.get("value_unit") != "USD":
        raise BridgeToXdexPublicContractError(
            "bridge_flow_24h must preserve USD value semantics"
        )
    _text(safe.get("value_basis_evidence_id"), "value_basis_evidence_id")

    addresses = safe.get("xdex_pool_addresses")
    if not isinstance(addresses, list) or len(addresses) != len(set(addresses)):
        raise BridgeToXdexPublicContractError(
            "XDEX pool addresses must be a unique list"
        )
    count = safe.get("xdex_pool_count")
    if isinstance(count, bool) or not isinstance(count, int) or count != len(addresses):
        raise BridgeToXdexPublicContractError(
            "XDEX pool count does not match addresses"
        )
    if safe.get("verified_zero_pool_set") is True:
        if count != 0 or addresses:
            raise BridgeToXdexPublicContractError(
                "verified zero pool set cannot contain pool addresses"
            )
        if safe.get("current_liquidity_zero_verified") is not True:
            raise BridgeToXdexPublicContractError(
                "zero pool set requires verified current zero liquidity"
            )
        if safe.get("verified_xdex_liquidity_value") != "0":
            raise BridgeToXdexPublicContractError(
                "zero pool set must preserve zero XDEX liquidity"
            )

    if safe.get("verified_xdex_volume_24h_value") is None:
        raise BridgeToXdexPublicContractError(
            "verified 24h XDEX volume must be present"
        )

    for field in (
        "causal_bridge_to_xdex_claim_authorized",
        "adoption_claim_authorized",
        "risk_promotion_authorized",
        "public_service_promoted",
        "scout_reliance_promoted",
        "execution_authorized",
    ):
        if safe.get(field) is not False:
            raise BridgeToXdexPublicContractError(
                f"canonical #410 record must keep {field}=false"
            )
    if safe.get("read_only") is not True:
        raise BridgeToXdexPublicContractError(
            "canonical #410 record must remain read-only"
        )
    if not isinstance(safe.get("source_independence_verified"), bool):
        raise BridgeToXdexPublicContractError(
            "source_independence_verified must remain explicit"
        )

    fact_time = _positive_number(safe.get("as_of"), "as_of")
    evaluated = _positive_number(evaluated_at, "evaluated_at")
    max_age = _positive_number(
        max_evidence_age_seconds, "max_evidence_age_seconds"
    )
    age = evaluated - fact_time
    if age < 0:
        raise BridgeToXdexPublicContractError(
            "canonical #410 fact time is in the future"
        )
    if age > max_age:
        raise BridgeToXdexPublicContractError(
            "canonical #410 evidence is stale"
        )
    safe["_public_freshness"] = {
        "fact_time": fact_time,
        "evaluated_at": evaluated,
        "age_seconds": age,
        "max_evidence_age_seconds": max_age,
        "freshness_verified": True,
    }
    return safe


def build_bridge_to_xdex_utilization_response(
    record: Mapping[str, Any],
    *,
    expected_route_id: str,
    expected_source_mint: str,
    expected_destination_mint: str,
    evaluated_at: Any,
    max_evidence_age_seconds: Any = DEFAULT_MAX_EVIDENCE_AGE_SECONDS,
) -> dict[str, Any]:
    try:
        safe = validate_bridge_to_xdex_public_record(
            record,
            expected_route_id=expected_route_id,
            expected_source_mint=expected_source_mint,
            expected_destination_mint=expected_destination_mint,
            evaluated_at=evaluated_at,
            max_evidence_age_seconds=max_evidence_age_seconds,
        )
    except BridgeToXdexPublicContractError as exc:
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
                "code": "bridge_to_xdex_utilization_contract_violation",
                "message": str(exc),
            }],
        )
        response["execution_authorized"] = False
        return response

    freshness = safe.pop("_public_freshness")
    canonical = deepcopy(safe)
    response = build_service_envelope(
        SERVICE,
        SUPPORTED_CHAIN,
        OK,
        asset={
            "canonical_id": canonical["destination_mint"],
            "mint": canonical["destination_mint"],
        },
        data={
            "contract_version": CONTRACT_VERSION,
            "public_service_promoted": True,
            "scout_reliance_promoted": True,
            "read_only": True,
            "route": {
                "route_id": canonical["route_id"],
                "source_chain": canonical["source_chain"],
                "source_mint": canonical["source_mint"],
                "destination_chain": canonical["destination_chain"],
                "destination_mint": canonical["destination_mint"],
            },
            "scope": {
                "xdex_pool_universe_scope": canonical[
                    "xdex_pool_universe_scope"
                ],
                "recognized_program_registry_globally_exhaustive": False,
                "global_onchain_pool_discovery_proven": False,
            },
            "bridge": {
                "bridged_supply_raw": canonical["bridged_supply_raw"],
                "bridged_supply_decimals": canonical["bridged_supply_decimals"],
                "bridged_supply_token_amount": canonical[
                    "bridged_supply_token_amount"
                ],
                "bridged_supply_value": canonical["bridged_supply_value"],
                "flow_24h": deepcopy(canonical["bridge_flow_24h"]),
            },
            "xdex_market": {
                "pool_count": canonical["xdex_pool_count"],
                "pool_addresses": deepcopy(canonical["xdex_pool_addresses"]),
                "verified_zero_pool_set": canonical["verified_zero_pool_set"],
                "current_liquidity_zero_verified": canonical[
                    "current_liquidity_zero_verified"
                ],
                "volume_24h_window_coverage_verified": canonical[
                    "volume_24h_window_coverage_verified"
                ],
                "liquidity_value": canonical["verified_xdex_liquidity_value"],
                "volume_24h_value": canonical[
                    "verified_xdex_volume_24h_value"
                ],
                "value_unit": canonical["value_unit"],
            },
            "utilization": {
                "bridge_to_xdex_liquidity_ratio": canonical[
                    "bridge_to_xdex_liquidity_ratio"
                ],
                "bridge_to_xdex_liquidity_ratio_state": canonical[
                    "bridge_to_xdex_liquidity_ratio_state"
                ],
                "bridge_gross_flow_24h_to_xdex_volume_24h_ratio": canonical[
                    "bridge_gross_flow_24h_to_xdex_volume_24h_ratio"
                ],
                "bridge_net_flow_24h_to_xdex_volume_24h_ratio": canonical[
                    "bridge_net_flow_24h_to_xdex_volume_24h_ratio"
                ],
                "bridge_flow_to_xdex_volume_ratio_state": canonical[
                    "bridge_flow_to_xdex_volume_ratio_state"
                ],
            },
            "freshness": freshness,
            "evidence": {
                "evidence_sha256": canonical["evidence_sha256"],
                "value_basis_evidence_id": canonical[
                    "value_basis_evidence_id"
                ],
                "comparable_value_basis_verified": canonical[
                    "comparable_value_basis_verified"
                ],
                "issue_410_acceptance_verified": True,
                "source_independence_verified": canonical[
                    "source_independence_verified"
                ],
            },
            "canonical_utilization": canonical,
            "causal_bridge_to_xdex_claim_authorized": False,
            "adoption_claim_authorized": False,
            "risk_promotion_authorized": False,
            "execution_authorized": False,
        },
        risk=None,
        confidence={
            "canonical_issue_410_record_validated": True,
            "identity_verified": True,
            "scope_verified": True,
            "freshness_verified": True,
            "unit_compatibility_verified": True,
        },
        sources=[{
            "source": "CMIS accepted #410 evidence",
            "observed_at": canonical["as_of"],
            "scope": canonical["xdex_pool_universe_scope"],
        }],
        observed_at=canonical["as_of"],
        warnings=[{
            "code": "bounded_xdex_program_family_scope",
            "message": (
                "Verified XDEX program-family evidence is not every X1 DEX. "
                "Bridge flow, liquidity, and volume are separate descriptive "
                "facts; adoption, causality, and risk are not inferred."
            ),
        }],
        errors=[],
    )
    response["execution_authorized"] = False
    return response


__all__ = [
    "BridgeToXdexPublicContractError",
    "CONTRACT_VERSION",
    "DEFAULT_MAX_EVIDENCE_AGE_SECONDS",
    "PROMOTED_SCOPE",
    "SERVICE",
    "SUPPORTED_CHAIN",
    "build_bridge_to_xdex_utilization_response",
    "validate_bridge_to_xdex_public_record",
]
