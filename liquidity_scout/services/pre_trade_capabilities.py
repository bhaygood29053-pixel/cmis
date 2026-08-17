"""Machine-readable execution-estimate capability reporting for pre-trade.

CMIS must not manufacture slippage, price impact, route quality, bridge
requirements, fees, or transaction simulation results when no verified producer
exists. This module reports those capabilities explicitly as unavailable and can
fail closed when a caller explicitly requires one of them.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable

from .risk import BLOCK, PASS


VERSION = "1.0"
CAPABILITY_NAMES = (
    "slippage",
    "price_impact",
    "route_quality",
    "bridge_dependency",
    "fees",
    "transaction_simulation",
)

_CAPABILITIES = {
    "slippage": {
        "status": "unavailable",
        "value": None,
        "unit": "percent",
        "reason_code": "verified_slippage_evidence_unavailable",
        "required_evidence": [
            "verified_route_quote_or_verified_pool_depth_curve",
        ],
    },
    "price_impact": {
        "status": "unavailable",
        "value": None,
        "unit": "percent",
        "reason_code": "verified_price_impact_evidence_unavailable",
        "required_evidence": [
            "verified_route_quote_or_verified_pool_depth_curve",
        ],
    },
    "route_quality": {
        "status": "unavailable",
        "value": None,
        "unit": None,
        "reason_code": "verified_route_evidence_unavailable",
        "required_evidence": [
            "verified_route_candidates_and_execution_cost_model",
        ],
    },
    "bridge_dependency": {
        "status": "unavailable",
        "value": None,
        "unit": None,
        "reason_code": "verified_route_representation_dependency_unavailable",
        "required_evidence": [
            "verified_route_and_canonical_representation_mapping",
        ],
    },
    "fees": {
        "status": "unavailable",
        "value": None,
        "unit": "usd",
        "reason_code": "verified_execution_fee_evidence_unavailable",
        "required_evidence": [
            "verified_route_fee_quote_or_deterministic_fee_model",
        ],
    },
    "transaction_simulation": {
        "status": "unavailable",
        "value": None,
        "unit": None,
        "reason_code": "transaction_simulation_not_implemented",
        "required_evidence": [
            "read_only_unsigned_transaction_simulation_contract",
        ],
    },
}


def normalize_required_capabilities(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("required_capabilities must be a list when supplied")

    normalized: list[str] = []
    for item in value:
        name = str(item or "").strip().lower()
        if not name:
            raise ValueError("required_capabilities entries must not be empty")
        if name not in CAPABILITY_NAMES:
            raise ValueError(
                "unsupported required pre-trade capability: " + name
            )
        if name not in normalized:
            normalized.append(name)
    return normalized


def build_execution_capability_report(
    required_capabilities: Iterable[str] | None = None,
) -> Dict[str, Any]:
    """Report unsupported execution estimates without synthesizing values."""
    required = normalize_required_capabilities(
        list(required_capabilities) if required_capabilities is not None else []
    )
    capabilities = deepcopy(_CAPABILITIES)
    unavailable_required = [
        name for name in required if capabilities[name]["status"] != "ok"
    ]

    reasons = [
        f"Required pre-trade capability '{name}' is unavailable because verified supporting evidence is not implemented."
        for name in unavailable_required
    ]

    return {
        "status": BLOCK if unavailable_required else PASS,
        "flags": (
            ["required_pretrade_capability_unavailable"]
            if unavailable_required
            else []
        ),
        "reasons": reasons,
        "evidence": {
            "capability_contract_version": VERSION,
            "capabilities": capabilities,
            "required_capabilities": required,
            "unavailable_required_capabilities": unavailable_required,
            "all_required_capabilities_available": not unavailable_required,
            "execution_authorization_supported": False,
        },
    }


__all__ = [
    "CAPABILITY_NAMES",
    "VERSION",
    "build_execution_capability_report",
    "normalize_required_capabilities",
]
