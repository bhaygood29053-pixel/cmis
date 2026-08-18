"""Machine-readable execution-estimate capability reporting for pre-trade.

CMIS must not manufacture slippage, price impact, route quality, bridge
requirements, fees, or transaction simulation results when no verified producer
exists. This module reports those capabilities explicitly as unavailable and can
fail closed when a caller explicitly requires one of them.

An internal CMIS producer may supply an explicit route-evidence envelope. Such
evidence is accepted only after exact route, freshness, semantic, value, and
proof-basis validation. Generic pre-trade behavior remains unchanged when no
route evidence is supplied.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, Mapping

from .pre_trade_route_evidence import evaluate_route_evidence
from .risk import BLOCK, PASS


VERSION = "1.1"
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
    *,
    route_evidence: Any = None,
    target_chain: str = "x1",
    trade_route: Mapping[str, Any] | None = None,
    evaluated_at: Any = None,
    route_evidence_max_age_seconds: Any = None,
) -> Dict[str, Any]:
    """Report execution-estimate availability without synthesizing values."""
    required = normalize_required_capabilities(
        list(required_capabilities) if required_capabilities is not None else []
    )
    capabilities = deepcopy(_CAPABILITIES)

    route_result = evaluate_route_evidence(
        route_evidence,
        target_chain=target_chain,
        trade_route=trade_route,
        evaluated_at=evaluated_at,
        max_age_seconds=route_evidence_max_age_seconds,
    )
    route_overrides = route_result["overrides"]
    route_audit = route_result["audit"]

    for name, override in route_overrides.items():
        required_evidence = capabilities[name]["required_evidence"]
        capabilities[name].update(deepcopy(override))
        capabilities[name]["required_evidence"] = required_evidence

    rejected = route_audit.get("rejected_capabilities")
    rejected = rejected if isinstance(rejected, Mapping) else {}
    for name, rejection in rejected.items():
        if name not in capabilities or capabilities[name]["status"] == "ok":
            continue
        if isinstance(rejection, Mapping) and rejection.get("reason_code"):
            capabilities[name]["reason_code"] = str(rejection["reason_code"])

    unavailable_required = [
        name for name in required if capabilities[name]["status"] != "ok"
    ]

    reasons = [
        (
            f"Required pre-trade capability '{name}' is unavailable "
            f"({capabilities[name]['reason_code']})."
        )
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
            "route_evidence": route_audit,
            "execution_authorization_supported": False,
        },
    }


__all__ = [
    "CAPABILITY_NAMES",
    "VERSION",
    "build_execution_capability_report",
    "normalize_required_capabilities",
]
