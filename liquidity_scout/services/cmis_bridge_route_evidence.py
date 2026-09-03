"""Deterministic bridge-route evidence and Warp qualification for CMIS.

This module sits above cross_chain_asset_provenance/v1 and below any future
public Bridge Intelligence service. It can preserve candidate bridge-route
facts, but it does not promote provider truth merely because a UI renders a
value, a host is known, an HTTP request succeeds, or JSON is returned.

Warp Bridge currently has no accepted machine-readable semantic contract in
CMIS. Therefore Warp qualification must remain blocked until an exact read URL
and its field/time semantics are separately accepted.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from liquidity_scout.services.cmis_cross_chain_provenance import (
    PROVENANCE_CONTRACT,
)

ROUTE_EVIDENCE_CONTRACT = "bridge_route_evidence/v1"
WARP_QUALIFICATION_CONTRACT = "warp_bridge_qualification/v1"
WARP_PROVIDER_ID = "warp_bridge"
DEFAULT_MAX_AGE_SECONDS = 300.0

# Promotion-safe by default. A future PR may add an entry only after exact URL
# provenance and endpoint/field/timestamp semantics have passed acceptance.
#
# Expected entry shape:
# {
#   "semantic_contract_id": {
#       "provider": "warp_bridge",
#       "source_url": "https://...",
#       "route_status_field": "...",
#       "backing_model_field": "...",
#       "custody_dependency_field": "...",
#       "source_timestamp_field": "...",
#   }
# }
ACCEPTED_ROUTE_SEMANTIC_CONTRACTS: dict[str, dict[str, str]] = {
    "warp_config/exact-mint-pair/v1": {
        "provider": "warp_bridge",
        "source_url": "https://app.bridge.x1.xyz/api/bridge/config",
        "route_status_field": (
            "solana.config.paused + x1.config.paused + "
            "exact source/destination token paused"
        ),
        "backing_model_field": (
            "exact source/destination token isNative topology"
        ),
        "custody_dependency_field": (
            "solana.config.guardians/threshold + x1.config.guardians/threshold"
        ),
        "source_timestamp_field": "fetchedAt(milliseconds)",
    }
}


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        mapped = to_dict()
        if isinstance(mapped, Mapping):
            return mapped
    raise ValueError(f"{field} must be a mapping or expose to_dict()")


def _epoch(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a numeric epoch timestamp")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a numeric epoch timestamp") from exc
    if number <= 0:
        raise ValueError(f"{field} must be positive")
    return number


def _endpoint(value: Any, field: str) -> dict[str, str]:
    mapped = _mapping(value, field)
    return {
        "chain": _required_text(mapped.get("chain"), f"{field}.chain").casefold(),
        "asset_id": _required_text(mapped.get("asset_id"), f"{field}.asset_id"),
        "asset_id_kind": _required_text(
            mapped.get("asset_id_kind"),
            f"{field}.asset_id_kind",
        ).casefold(),
    }


def _same_endpoint(left: Mapping[str, str], right: Mapping[str, str]) -> bool:
    return (
        left["chain"] == right["chain"]
        and left["asset_id"] == right["asset_id"]
        and left["asset_id_kind"] == right["asset_id_kind"]
    )


def _canonical_id(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "bre_" + hashlib.sha256(payload).hexdigest()[:32]


def evaluate_route_freshness(
    *,
    collected_at: Any,
    evaluated_at: Any,
    source_observed_at: Any = None,
    max_age_seconds: Any = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Return deterministic collection/source freshness without inventing semantics."""

    collected = _epoch(collected_at, "collected_at")
    evaluated = _epoch(evaluated_at, "evaluated_at")
    max_age = float(max_age_seconds)
    if max_age <= 0:
        raise ValueError("max_age_seconds must be positive")
    if collected > evaluated:
        raise ValueError("collected_at cannot be in the future")

    collection_age = evaluated - collected
    source_value: float | None = None
    source_age: float | None = None
    source_fresh: bool | None = None
    if source_observed_at is not None:
        source_value = _epoch(source_observed_at, "source_observed_at")
        if source_value > evaluated:
            raise ValueError("source_observed_at cannot be in the future")
        source_age = evaluated - source_value
        source_fresh = source_age <= max_age

    return {
        "collected_at": collected,
        "evaluated_at": evaluated,
        "source_observed_at": source_value,
        "max_age_seconds": max_age,
        "collection_age_seconds": collection_age,
        "source_age_seconds": source_age,
        "collection_fresh": collection_age <= max_age,
        "source_fresh": source_fresh,
    }


def _selected_hop(provenance: Any, hop_index: int) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    mapped = _mapping(provenance, "provenance")
    if mapped.get("contract") != PROVENANCE_CONTRACT:
        raise ValueError(
            f"provenance must use accepted contract {PROVENANCE_CONTRACT}"
        )
    lineage = mapped.get("lineage")
    if not isinstance(lineage, list) or not lineage:
        raise ValueError("provenance.lineage must be a non-empty list")
    if isinstance(hop_index, bool) or not isinstance(hop_index, int):
        raise ValueError("hop_index must be an integer")
    if hop_index < 0 or hop_index >= len(lineage):
        raise ValueError("hop_index is outside provenance lineage")
    hop = _mapping(lineage[hop_index], f"provenance.lineage[{hop_index}]")
    return mapped, hop


def _semantic_contract(
    *,
    semantic_contract_id: str,
    provider: str,
    source_url: str,
) -> tuple[dict[str, str] | None, bool]:
    spec = ACCEPTED_ROUTE_SEMANTIC_CONTRACTS.get(semantic_contract_id)
    if spec is None:
        return None, False
    verified = (
        spec.get("provider") == provider
        and spec.get("source_url") == source_url
        and bool(spec.get("route_status_field"))
        and bool(spec.get("backing_model_field"))
        and bool(spec.get("custody_dependency_field"))
        and bool(spec.get("source_timestamp_field"))
    )
    return spec, verified


def build_bridge_route_evidence(
    *,
    provenance: Any,
    hop_index: int,
    source_provenance: Any,
    observation: Any,
    evaluated_at: Any,
    max_age_seconds: Any = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Build one deterministic, fail-closed bridge-route evidence receipt."""

    provenance_map, hop = _selected_hop(provenance, hop_index)
    source_map = _mapping(source_provenance, "source_provenance")
    observation_map = _mapping(observation, "observation")

    provider = _required_text(observation_map.get("provider"), "observation.provider")
    source_url = _required_text(
        observation_map.get("source_url"),
        "observation.source_url",
    )
    semantic_contract_id = _required_text(
        observation_map.get("semantic_contract_id"),
        "observation.semantic_contract_id",
    )
    route_id = _required_text(
        observation_map.get("route_id"),
        "observation.route_id",
    )
    bridge = _required_text(observation_map.get("bridge"), "observation.bridge")

    hop_bridge = _required_text(hop.get("bridge"), "provenance hop bridge")
    if bridge.casefold() != hop_bridge.casefold():
        raise ValueError("observation bridge must equal provenance hop bridge")

    source = _endpoint(observation_map.get("source"), "observation.source")
    destination = _endpoint(
        observation_map.get("destination"),
        "observation.destination",
    )
    hop_source = _endpoint(hop.get("source"), "provenance hop source")
    hop_destination = _endpoint(
        hop.get("destination"),
        "provenance hop destination",
    )
    if not _same_endpoint(source, hop_source):
        raise ValueError("observation source must equal provenance hop source")
    if not _same_endpoint(destination, hop_destination):
        raise ValueError(
            "observation destination must equal provenance hop destination"
        )

    provenance_route_id = _optional_text(hop.get("bridge_route_id"))
    if provenance_route_id is not None and route_id != provenance_route_id:
        raise ValueError(
            "observation route_id must equal provenance bridge_route_id"
        )
    exact_route_identity_verified = provenance_route_id == route_id

    provenance_url = _optional_text(source_map.get("url"))
    if provenance_url is not None and provenance_url != source_url:
        raise ValueError(
            "observation source_url must equal source provenance exact URL"
        )

    source_provenance_verified = (
        source_map.get("source_provenance_verified") is True
        and source_map.get("read_probe_eligible") is True
        and provenance_url == source_url
    )

    _spec, endpoint_semantics_verified = _semantic_contract(
        semantic_contract_id=semantic_contract_id,
        provider=provider,
        source_url=source_url,
    )

    collected_at = observation_map.get("collected_at")
    source_observed_at = observation_map.get("source_observed_at")
    freshness = evaluate_route_freshness(
        collected_at=collected_at,
        source_observed_at=source_observed_at,
        evaluated_at=evaluated_at,
        max_age_seconds=max_age_seconds,
    )
    source_timestamp_semantics_verified = bool(
        endpoint_semantics_verified
        and freshness["source_observed_at"] is not None
    )

    route_status = _optional_text(observation_map.get("route_status"))
    backing_model = _optional_text(observation_map.get("backing_model"))
    custody_dependency = _optional_text(
        observation_map.get("custody_dependency")
    )

    route_status_verified = bool(endpoint_semantics_verified and route_status)
    backing_model_verified = bool(endpoint_semantics_verified and backing_model)
    custody_dependency_verified = bool(
        endpoint_semantics_verified and custody_dependency
    )
    freshness_verified = bool(
        source_timestamp_semantics_verified
        and freshness["source_fresh"] is True
        and freshness["collection_fresh"] is True
    )

    qualification_checks = {
        "source_provenance_verified": source_provenance_verified,
        "endpoint_semantics_verified": endpoint_semantics_verified,
        "exact_route_identity_verified": exact_route_identity_verified,
        "source_timestamp_semantics_verified": source_timestamp_semantics_verified,
        "freshness_verified": freshness_verified,
        "route_status_verified": route_status_verified,
        "backing_model_verified": backing_model_verified,
        "custody_dependency_verified": custody_dependency_verified,
    }

    if not source_provenance_verified:
        qualification_state = "blocked_source_provenance"
    elif not endpoint_semantics_verified:
        qualification_state = "blocked_endpoint_semantics"
    elif not exact_route_identity_verified:
        qualification_state = "blocked_route_identity"
    elif not source_timestamp_semantics_verified:
        qualification_state = "blocked_source_timestamp_semantics"
    elif not freshness_verified:
        qualification_state = "blocked_stale_evidence"
    elif not (
        route_status_verified
        and backing_model_verified
        and custody_dependency_verified
    ):
        qualification_state = "blocked_required_route_fields"
    else:
        qualification_state = "qualified"

    qualified = all(qualification_checks.values())

    core = {
        "contract": ROUTE_EVIDENCE_CONTRACT,
        "canonical_asset_id": provenance_map.get("canonical_asset_id"),
        "hop_index": hop_index,
        "provider": provider,
        "bridge": bridge,
        "route_id": route_id,
        "source": source,
        "destination": destination,
        "source_url": source_url,
        "semantic_contract_id": semantic_contract_id,
        "candidate_facts": {
            "route_status": route_status,
            "backing_model": backing_model,
            "custody_dependency": custody_dependency,
        },
        "freshness": freshness,
        "qualification_checks": qualification_checks,
        "qualification_state": qualification_state,
        "qualified": qualified,
    }

    return {
        **core,
        "evidence_id": _canonical_id(core),
        "facts": {
            "route_status": {
                "value": route_status,
                "verified": route_status_verified,
            },
            "backing_model": {
                "value": backing_model,
                "verified": backing_model_verified,
            },
            "custody_dependency": {
                "value": custody_dependency,
                "verified": custody_dependency_verified,
            },
        },
        "limitations": [
            limitation
            for limitation, active in (
                (
                    "exact machine-readable source provenance not accepted",
                    not source_provenance_verified,
                ),
                (
                    "endpoint/field/timestamp semantics not accepted",
                    not endpoint_semantics_verified,
                ),
                (
                    "exact route identity not proven",
                    not exact_route_identity_verified,
                ),
                (
                    "source timestamp semantics not proven",
                    not source_timestamp_semantics_verified,
                ),
                (
                    "route evidence is stale or collection freshness failed",
                    not freshness_verified,
                ),
            )
            if active
        ],
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


def qualify_warp_bridge_route(
    *,
    provenance: Any,
    hop_index: int,
    source_provenance: Any,
    observation: Any,
    evaluated_at: Any,
    max_age_seconds: Any = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Apply the locked Warp provider identity to bridge-route evidence."""

    mapped = dict(_mapping(observation, "observation"))
    provider = _required_text(mapped.get("provider"), "observation.provider")
    if provider != WARP_PROVIDER_ID:
        raise ValueError(
            f"Warp qualification requires provider={WARP_PROVIDER_ID}"
        )

    evidence = build_bridge_route_evidence(
        provenance=provenance,
        hop_index=hop_index,
        source_provenance=source_provenance,
        observation=mapped,
        evaluated_at=evaluated_at,
        max_age_seconds=max_age_seconds,
    )
    return {
        "contract": WARP_QUALIFICATION_CONTRACT,
        "provider": WARP_PROVIDER_ID,
        "route_evidence": evidence,
        "warp_qualified": evidence["qualified"],
        "qualification_state": evidence["qualification_state"],
        "accepted_warp_semantic_contracts": sorted(
            contract_id
            for contract_id, spec in ACCEPTED_ROUTE_SEMANTIC_CONTRACTS.items()
            if spec.get("provider") == WARP_PROVIDER_ID
        ),
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "ACCEPTED_ROUTE_SEMANTIC_CONTRACTS",
    "DEFAULT_MAX_AGE_SECONDS",
    "ROUTE_EVIDENCE_CONTRACT",
    "WARP_PROVIDER_ID",
    "WARP_QUALIFICATION_CONTRACT",
    "build_bridge_route_evidence",
    "evaluate_route_freshness",
    "qualify_warp_bridge_route",
]
