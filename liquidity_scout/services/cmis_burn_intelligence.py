"""First-class CMIS X1 Burn Intelligence v1 contract.

This service is a read-only projection over already-deterministic CMIS tokenomics
burn evidence. It does not scan the chain, parse burn instructions, recompute
burn arithmetic, infer circulating supply, or perform historical valuation.
Those facts remain owned by the accepted CMIS tokenomics/burn-evidence path.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from liquidity_scout.services.cmis_contract import (
    ERROR,
    PARTIAL,
    UNAVAILABLE,
    build_service_envelope,
)
from liquidity_scout.services.cmis_x1_asset_identity import is_exact_x1_public_key


SERVICE = "burn_intelligence"
CONTRACT_VERSION = "burn_intelligence/v1"
_REQUIRED_WINDOWS = ("1h", "24h", "7d", "30d")


class BurnIntelligenceContractError(ValueError):
    """Raised when accepted tokenomics cannot satisfy Burn Intelligence v1."""


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _validate_exact_identity(
    asset: Mapping[str, Any],
    data: Mapping[str, Any],
) -> str:
    asset_mint = str(asset.get("mint") or "").strip()
    data_mint = str(data.get("mint") or "").strip()
    if not is_exact_x1_public_key(asset_mint):
        raise BurnIntelligenceContractError(
            "burn_intelligence requires an exact X1 mint identity"
        )
    if data_mint != asset_mint:
        raise BurnIntelligenceContractError(
            "tokenomics data mint does not match resolved asset mint"
        )
    return asset_mint


def _validate_metrics(metrics: Mapping[str, Any]) -> None:
    available = metrics.get("available")
    if not isinstance(available, bool):
        raise BurnIntelligenceContractError(
            "burn_metrics.available must be an explicit boolean"
        )
    status = metrics.get("status")
    if status not in {"ok", "partial", "unavailable"}:
        raise BurnIntelligenceContractError("unsupported burn_metrics status")

    lifetime = metrics.get("lifetime_total_burn_verified")
    if not isinstance(lifetime, bool):
        raise BurnIntelligenceContractError(
            "lifetime_total_burn_verified must be an explicit boolean"
        )

    if available is False:
        if status != "unavailable":
            raise BurnIntelligenceContractError(
                "unavailable burn metrics must preserve unavailable status"
            )
        return

    for key in (
        "coverage_verified",
        "time_buckets_verified",
        "observed_event_totals_verified",
    ):
        if not isinstance(metrics.get(key), bool):
            raise BurnIntelligenceContractError(
                f"{key} must be an explicit boolean"
            )

    windows = metrics.get("windows")
    if not isinstance(windows, Mapping):
        raise BurnIntelligenceContractError("burn_metrics.windows is required")
    for label in _REQUIRED_WINDOWS:
        window = windows.get(label)
        if not isinstance(window, Mapping):
            raise BurnIntelligenceContractError(
                f"burn window missing or malformed: {label}"
            )
        if window.get("status") not in {"ok", "unavailable"}:
            raise BurnIntelligenceContractError(
                f"unsupported burn window status: {label}"
            )
        if not isinstance(window.get("coverage_verified"), bool):
            raise BurnIntelligenceContractError(
                f"burn window coverage malformed: {label}"
            )


def _unavailable_from_upstream(tokenomics: Mapping[str, Any]) -> dict[str, Any]:
    response = build_service_envelope(
        SERVICE,
        "x1",
        UNAVAILABLE,
        asset=_mapping(tokenomics.get("asset")),
        data={
            "contract_version": CONTRACT_VERSION,
            "upstream_service": tokenomics.get("service"),
        },
        confidence=_mapping(tokenomics.get("confidence")),
        sources=tokenomics.get("sources") or [],
        observed_at=tokenomics.get("observed_at"),
        warnings=tokenomics.get("warnings") or [],
        errors=tokenomics.get("errors") or [],
    )
    response["execution_authorized"] = False
    return response


def build_burn_intelligence_response(
    tokenomics: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one accepted CMIS tokenomics envelope into Burn Intelligence v1."""

    if not isinstance(tokenomics, Mapping):
        return build_service_envelope(
            SERVICE,
            "x1",
            ERROR,
            data={"contract_version": CONTRACT_VERSION},
            errors=[{
                "code": "invalid_tokenomics_envelope",
                "message": "Burn Intelligence requires a CMIS tokenomics envelope.",
            }],
        )

    if tokenomics.get("service") != "tokenomics":
        response = build_service_envelope(
            SERVICE,
            "x1",
            ERROR,
            data={"contract_version": CONTRACT_VERSION},
            errors=[{
                "code": "wrong_upstream_service",
                "message": "Burn Intelligence accepts CMIS tokenomics only.",
            }],
        )
        response["execution_authorized"] = False
        return response

    if tokenomics.get("chain") != "x1":
        response = build_service_envelope(
            SERVICE,
            str(tokenomics.get("chain") or "unknown"),
            UNAVAILABLE,
            asset=_mapping(tokenomics.get("asset")),
            data={"contract_version": CONTRACT_VERSION},
            warnings=[{
                "code": "burn_intelligence_x1_only",
                "message": "Burn Intelligence v1 is promoted for X1 only.",
            }],
        )
        response["execution_authorized"] = False
        return response

    if tokenomics.get("status") not in {"ok", "partial"}:
        return _unavailable_from_upstream(tokenomics)

    asset = _mapping(tokenomics.get("asset"))
    data = _mapping(tokenomics.get("data"))
    metrics = data.get("burn_metrics")
    if not isinstance(metrics, Mapping):
        response = build_service_envelope(
            SERVICE,
            "x1",
            UNAVAILABLE,
            asset=asset,
            data={
                "contract_version": CONTRACT_VERSION,
                "upstream_service": "tokenomics",
            },
            confidence=_mapping(tokenomics.get("confidence")),
            sources=tokenomics.get("sources") or [],
            observed_at=tokenomics.get("observed_at"),
            warnings=[
                *(tokenomics.get("warnings") or []),
                {
                    "code": "burn_metrics_unavailable",
                    "message": "CMIS tokenomics supplied no usable burn_metrics object.",
                },
            ],
            errors=tokenomics.get("errors") or [],
        )
        response["execution_authorized"] = False
        return response

    try:
        mint = _validate_exact_identity(asset, data)
        _validate_metrics(metrics)
    except BurnIntelligenceContractError as exc:
        response = build_service_envelope(
            SERVICE,
            "x1",
            ERROR,
            asset=asset,
            data={"contract_version": CONTRACT_VERSION},
            confidence=_mapping(tokenomics.get("confidence")),
            sources=tokenomics.get("sources") or [],
            observed_at=tokenomics.get("observed_at"),
            warnings=tokenomics.get("warnings") or [],
            errors=[
                *(tokenomics.get("errors") or []),
                {
                    "code": "burn_intelligence_contract_violation",
                    "message": str(exc),
                },
            ],
        )
        response["execution_authorized"] = False
        return response

    metrics_copy = deepcopy(dict(metrics))
    result_status = (
        UNAVAILABLE
        if metrics.get("available") is False
        else (
            PARTIAL
            if tokenomics.get("status") == PARTIAL or metrics.get("status") == PARTIAL
            else "ok"
        )
    )
    response = build_service_envelope(
        SERVICE,
        "x1",
        result_status,
        asset=deepcopy(dict(asset)),
        data={
            "contract_version": CONTRACT_VERSION,
            "mint": mint,
            "symbol": data.get("symbol") or asset.get("symbol"),
            "name": data.get("name") or asset.get("name"),
            "cumulative": {
                "verified_burned_raw_observed": metrics.get(
                    "verified_burned_raw_observed"
                ),
                "verified_burned_observed": metrics.get(
                    "verified_burned_observed"
                ),
                "burn_events_observed": metrics.get("burn_events_observed"),
                "lifetime_total_burn_verified": metrics.get(
                    "lifetime_total_burn_verified"
                ),
            },
            "coverage": {
                "coverage_verified": metrics.get("coverage_verified"),
                "time_buckets_verified": metrics.get("time_buckets_verified"),
                "observed_event_totals_verified": metrics.get(
                    "observed_event_totals_verified"
                ),
                "coverage_start_time": metrics.get("coverage_start_time"),
                "coverage_end_time": metrics.get("coverage_end_time"),
                "observed_at": metrics.get("observed_at"),
            },
            "windows": deepcopy(dict(_mapping(metrics.get("windows")))),
            "valuation": deepcopy(dict(_mapping(metrics.get("valuation")))),
            "circulating_supply": deepcopy(
                dict(_mapping(metrics.get("circulating_supply")))
            ),
            "burn_metrics": metrics_copy,
        },
        confidence=deepcopy(dict(_mapping(tokenomics.get("confidence")))),
        sources=deepcopy(list(tokenomics.get("sources") or [])),
        observed_at=tokenomics.get("observed_at"),
        warnings=deepcopy(list(tokenomics.get("warnings") or [])),
        errors=deepcopy(list(tokenomics.get("errors") or [])),
    )
    response["execution_authorized"] = False
    return response


__all__ = [
    "BurnIntelligenceContractError",
    "CONTRACT_VERSION",
    "SERVICE",
    "build_burn_intelligence_response",
]
