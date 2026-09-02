"""Public contract for bounded X1 Discovery Intelligence v1.

The protected runtime derives this projection from CMIS-owned Discovery Ledger
records.  This module validates and envelopes the projection; it does not read
the ledger, discover assets, or infer a token launch time.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from liquidity_scout.services.cmis_contract import ERROR, PARTIAL, UNAVAILABLE, build_service_envelope
from liquidity_scout.services.cmis_x1_asset_identity import is_exact_x1_public_key


SERVICE = "discovery_intelligence"
CONTRACT_VERSION = "discovery_intelligence/v1"


class DiscoveryIntelligenceContractError(ValueError):
    """Raised when a protected Discovery projection violates the public contract."""


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _validated_identity(identity: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]]:
    if identity.get("service") != "asset_lookup" or identity.get("chain") != "x1":
        raise DiscoveryIntelligenceContractError(
            "discovery_intelligence requires an X1 asset_lookup envelope"
        )
    asset = _mapping(identity.get("asset"))
    mint = str(asset.get("mint") or "").strip()
    if not is_exact_x1_public_key(mint):
        raise DiscoveryIntelligenceContractError(
            "discovery_intelligence requires an exact X1 mint identity"
        )
    return mint, asset


def _validated_projection(mint: str, projection: Mapping[str, Any]) -> None:
    if projection.get("mint") != mint:
        raise DiscoveryIntelligenceContractError(
            "Discovery projection mint does not match resolved asset mint"
        )
    count = projection.get("verified_observation_count")
    if type(count) is not int or count < 0:
        raise DiscoveryIntelligenceContractError(
            "verified_observation_count must be a non-negative integer"
        )
    available = projection.get("available")
    if not isinstance(available, bool) or available is not (count > 0):
        raise DiscoveryIntelligenceContractError(
            "Discovery projection availability must match its verified count"
        )
    if projection.get("token_launch_time_verified") is not False:
        raise DiscoveryIntelligenceContractError(
            "Discovery Intelligence must not promote first observation as launch time"
        )
    if projection.get("token_launch_time") is not None:
        raise DiscoveryIntelligenceContractError(
            "token_launch_time must remain null when it is not independently verified"
        )

    first = projection.get("first_verified_observation")
    recent = projection.get("most_recent_verified_observation")
    coverage = projection.get("coverage")
    if not isinstance(coverage, Mapping):
        raise DiscoveryIntelligenceContractError("Discovery coverage must be a mapping")
    if coverage.get("continuous_coverage_verified") is not False:
        raise DiscoveryIntelligenceContractError(
            "Discovery sparse observations cannot claim continuous coverage"
        )
    if coverage.get("archive_completeness_verified") is not False:
        raise DiscoveryIntelligenceContractError(
            "Discovery sparse observations cannot claim archive completeness"
        )

    if count == 0:
        if first is not None or recent is not None:
            raise DiscoveryIntelligenceContractError(
                "empty Discovery projections cannot expose observation records"
            )
        for key in ("start_fact_time_unix", "end_fact_time_unix", "elapsed_observed_seconds"):
            if coverage.get(key) is not None:
                raise DiscoveryIntelligenceContractError(
                    "empty Discovery coverage bounds must remain null"
                )
        return

    if not isinstance(first, Mapping) or not isinstance(recent, Mapping):
        raise DiscoveryIntelligenceContractError(
            "non-empty Discovery projections require first and most-recent records"
        )
    start = coverage.get("start_fact_time_unix")
    end = coverage.get("end_fact_time_unix")
    elapsed = coverage.get("elapsed_observed_seconds")
    if type(start) is not int or type(end) is not int or type(elapsed) is not int:
        raise DiscoveryIntelligenceContractError(
            "Discovery coverage bounds must be integer Unix seconds"
        )
    if start < 0 or end < start or elapsed != end - start:
        raise DiscoveryIntelligenceContractError("Discovery coverage bounds are inconsistent")
    if first.get("fact_time_unix") != start or recent.get("fact_time_unix") != end:
        raise DiscoveryIntelligenceContractError(
            "Discovery observation records do not match coverage bounds"
        )


def build_discovery_intelligence_response(
    identity: Mapping[str, Any],
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and expose one protected Discovery Ledger projection."""

    try:
        if not isinstance(identity, Mapping) or not isinstance(projection, Mapping):
            raise DiscoveryIntelligenceContractError(
                "identity and Discovery projection must be mappings"
            )
        mint, asset = _validated_identity(identity)
        _validated_projection(mint, projection)
    except DiscoveryIntelligenceContractError as exc:
        response = build_service_envelope(
            SERVICE,
            "x1",
            ERROR,
            data={"contract_version": CONTRACT_VERSION},
            errors=[{"code": "discovery_intelligence_contract_violation", "message": str(exc)}],
        )
        response["execution_authorized"] = False
        return response

    count = projection["verified_observation_count"]
    warnings = deepcopy(list(identity.get("warnings") or []))
    if count == 0:
        warnings.append({
            "code": "verified_discovery_observations_unavailable",
            "message": "No verified fact-time Discovery observations are available for this scope.",
        })
    else:
        warnings.extend([
            {
                "code": "first_observation_is_not_launch_time",
                "message": "The first verified observation is not the token launch time.",
            },
            {
                "code": "discovery_history_is_sparse",
                "message": "Observed-history bounds do not prove continuous or complete archival coverage.",
            },
        ])

    response = build_service_envelope(
        SERVICE,
        "x1",
        UNAVAILABLE if count == 0 else PARTIAL,
        asset=deepcopy(dict(asset)),
        data={"contract_version": CONTRACT_VERSION, **deepcopy(dict(projection))},
        confidence=deepcopy(dict(_mapping(identity.get("confidence")))),
        sources=deepcopy(list(projection.get("sources") or [])),
        observed_at=projection.get("observed_at"),
        warnings=warnings,
        errors=deepcopy(list(identity.get("errors") or [])),
    )
    response["execution_authorized"] = False
    return response


__all__ = [
    "CONTRACT_VERSION",
    "DiscoveryIntelligenceContractError",
    "SERVICE",
    "build_discovery_intelligence_response",
]
