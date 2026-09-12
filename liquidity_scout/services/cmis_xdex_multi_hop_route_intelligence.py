"""Deterministic CMIS boundary for XDEX multi-hop route intelligence v1.

Phase 1 deliberately separates provider discovery from independently verified
route facts. The provider response is preserved verbatim; verification fields
remain false unless explicit CMIS-produced hop evidence is supplied. A quote is
never treated as executed-route evidence or proof of global optimality.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from liquidity_scout.providers.x1.xdex_multi_hop import OBSERVATION_SCHEMA

CONTRACT_VERSION = "xdex_multi_hop_route_intelligence/v1"
CHAIN = "x1"


class XDEXMultiHopRouteIntelligenceError(ValueError):
    """Raised when a route-intelligence input violates the CMIS truth boundary."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise XDEXMultiHopRouteIntelligenceError(f"{field} must be a normalized non-empty string")
    text = value.strip()
    if not text or text != value:
        raise XDEXMultiHopRouteIntelligenceError(f"{field} must be a normalized non-empty string")
    return text


def _validate_observation(observation: Any) -> dict[str, Any]:
    if not isinstance(observation, Mapping):
        raise XDEXMultiHopRouteIntelligenceError("provider observation must be a mapping")
    required = {
        "schema",
        "chain",
        "source",
        "endpoint",
        "request",
        "raw_response",
        "provider_semantics_promoted",
        "prepare_called",
        "read_only",
        "execution_authorized",
    }
    missing = sorted(required - set(observation))
    if missing:
        raise XDEXMultiHopRouteIntelligenceError(f"provider observation missing fields: {missing!r}")
    if observation.get("schema") != OBSERVATION_SCHEMA:
        raise XDEXMultiHopRouteIntelligenceError("provider observation schema mismatch")
    if observation.get("chain") != CHAIN:
        raise XDEXMultiHopRouteIntelligenceError("provider observation must remain X1-only")
    if observation.get("provider_semantics_promoted") is not False:
        raise XDEXMultiHopRouteIntelligenceError("provider semantics must not be pre-promoted")
    if observation.get("prepare_called") is not False:
        raise XDEXMultiHopRouteIntelligenceError("prepare must not be called")
    if observation.get("read_only") is not True:
        raise XDEXMultiHopRouteIntelligenceError("provider observation must remain read-only")
    if observation.get("execution_authorized") is not False:
        raise XDEXMultiHopRouteIntelligenceError("execution_authorized must remain false")
    if not isinstance(observation.get("request"), Mapping):
        raise XDEXMultiHopRouteIntelligenceError("provider request must be a mapping")
    if not isinstance(observation.get("raw_response"), Mapping):
        raise XDEXMultiHopRouteIntelligenceError("provider raw_response must be a mapping")
    return deepcopy(dict(observation))


def _normalize_hop_evidence(rows: Any) -> list[dict[str, Any]]:
    if rows is None:
        return []
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise XDEXMultiHopRouteIntelligenceError("hop_evidence must be a sequence")
    normalized: list[dict[str, Any]] = []
    for expected_index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise XDEXMultiHopRouteIntelligenceError(f"hop_evidence[{expected_index}] must be a mapping")
        if row.get("index") != expected_index:
            raise XDEXMultiHopRouteIntelligenceError("hop evidence indexes must be contiguous from zero")
        item = deepcopy(dict(row))
        for field in ("token_in_mint", "token_out_mint", "pool", "venue"):
            item[field] = _text(item.get(field), f"hop_evidence[{expected_index}].{field}")
        if item["token_in_mint"] == item["token_out_mint"]:
            raise XDEXMultiHopRouteIntelligenceError("hop input and output mints must differ")
        for field in (
            "pool_identity_verified",
            "pool_state_verified",
            "fee_math_verified",
            "reserve_math_verified",
            "price_impact_verified",
            "minimum_received_bounded",
            "venue_identity_verified",
        ):
            if item.get(field) not in (True, False):
                raise XDEXMultiHopRouteIntelligenceError(f"hop_evidence[{expected_index}].{field} must be boolean")
        if item.get("execution_authorized") is not False:
            raise XDEXMultiHopRouteIntelligenceError("hop evidence execution_authorized must remain false")
        normalized.append(item)

    for left, right in zip(normalized, normalized[1:]):
        if left["token_out_mint"] != right["token_in_mint"]:
            raise XDEXMultiHopRouteIntelligenceError("hop sequence is not mint-contiguous")
    return normalized


def build_xdex_multi_hop_route_intelligence(
    provider_observation: Mapping[str, Any],
    *,
    hop_evidence: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a fail-closed Phase-1 intelligence object from bounded evidence."""

    observation = _validate_observation(provider_observation)
    hops = _normalize_hop_evidence(hop_evidence)
    request = observation["request"]

    route_structure_verified = bool(hops)
    if hops:
        request_in = request.get("token_in")
        request_out = request.get("token_out")
        if request_in != hops[0]["token_in_mint"] or request_out != hops[-1]["token_out_mint"]:
            raise XDEXMultiHopRouteIntelligenceError("verified hop endpoints do not match provider request")

    def all_hops(field: str) -> bool:
        return bool(hops) and all(row[field] is True for row in hops)

    venues = {row["venue"] for row in hops if row.get("venue_identity_verified") is True}
    verification = {
        "route_structure_verified": route_structure_verified,
        "pool_identity_verified": all_hops("pool_identity_verified"),
        "pool_state_verified": all_hops("pool_state_verified"),
        "fee_math_verified": all_hops("fee_math_verified"),
        "reserve_math_verified": all_hops("reserve_math_verified"),
        "price_impact_verified": all_hops("price_impact_verified"),
        "minimum_received_bounded": all_hops("minimum_received_bounded"),
        "cross_dex_observed": False,
        "route_optimality_verified": False,
    }

    evidence_quality = "EVIDENCE_REQUIRED"
    if route_structure_verified:
        evidence_quality = "BOUNDED"
    if (
        verification["pool_identity_verified"]
        and verification["pool_state_verified"]
        and verification["fee_math_verified"]
        and verification["reserve_math_verified"]
    ):
        evidence_quality = "VERIFIED_ROUTE_STRUCTURE"

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "status": "ok" if route_structure_verified else "evidence_required",
        "request": deepcopy(dict(request)),
        "provider_observation": observation,
        "hop_count": len(hops) if hops else None,
        "hops": hops,
        "verified_venues": sorted(venues),
        "verification": verification,
        "evidence_quality": evidence_quality,
        "provider_route_is_independent_verification": False,
        "quote_is_executed_output": False,
        "minimum_received_is_guaranteed_fill": False,
        "cross_dex_configured": None,
        "cross_dex_route_available": None,
        "cross_dex_execution_observed": False,
        "cross_dex_execution_verified": False,
        "global_route_optimality_claimed": False,
        "network_fee_verified": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CHAIN",
    "CONTRACT_VERSION",
    "XDEXMultiHopRouteIntelligenceError",
    "build_xdex_multi_hop_route_intelligence",
]
