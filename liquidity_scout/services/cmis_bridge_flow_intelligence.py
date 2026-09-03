"""Deterministic route-scoped Bridge Flow Intelligence v1.

This foundation computes 24h/7d/30d bridge-flow facts only from already
verified, normalized settled-transfer records for one exact qualified route.
It does not discover provider endpoints, pair raw chain events, infer supply,
or construct/sign/broadcast transfers.

Missing coverage remains unknown. A partially observed interval is never
silently reported as a complete total.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.services.cmis_bridge_route_evidence import (
    WARP_QUALIFICATION_CONTRACT,
)

SERVICE = "bridge_flow_intelligence"
CONTRACT_VERSION = "bridge_flow_intelligence/v1"
WINDOWS = {
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
}
SETTLED_STATE = "settled"


class BridgeFlowContractError(ValueError):
    """Raised when route or event evidence violates the deterministic contract."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BridgeFlowContractError(f"{field} must be a mapping")
    return value


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise BridgeFlowContractError(f"{field} is required")
    return text


def _epoch(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise BridgeFlowContractError(f"{field} must be numeric epoch seconds")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise BridgeFlowContractError(
            f"{field} must be numeric epoch seconds"
        ) from exc
    if parsed <= 0:
        raise BridgeFlowContractError(f"{field} must be positive")
    return parsed


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise BridgeFlowContractError(f"{field} must be a nonnegative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise BridgeFlowContractError(
            f"{field} must be a nonnegative integer"
        ) from exc
    if parsed < 0:
        raise BridgeFlowContractError(f"{field} must be nonnegative")
    return parsed


def _positive_int(value: Any, field: str) -> int:
    parsed = _nonnegative_int(value, field)
    if parsed <= 0:
        raise BridgeFlowContractError(f"{field} must be positive")
    return parsed


def _exact_endpoint(value: Any, field: str) -> dict[str, str]:
    mapped = _mapping(value, field)
    chain = _required_text(mapped.get("chain"), f"{field}.chain").casefold()
    asset_id = _required_text(mapped.get("asset_id"), f"{field}.asset_id")
    asset_id_kind = _required_text(
        mapped.get("asset_id_kind"), f"{field}.asset_id_kind"
    ).casefold()
    if asset_id_kind != "mint":
        raise BridgeFlowContractError(f"{field}.asset_id_kind must be mint")
    return {
        "chain": chain,
        "asset_id": asset_id,
        "asset_id_kind": "mint",
    }


def _same_endpoint(left: Mapping[str, str], right: Mapping[str, str]) -> bool:
    return (
        left["chain"] == right["chain"]
        and left["asset_id"] == right["asset_id"]
        and left["asset_id_kind"] == right["asset_id_kind"]
    )


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decimal_string(raw: int | None, decimals: int) -> str | None:
    if raw is None:
        return None
    scale = Decimal(10) ** decimals
    return format(Decimal(raw) / scale, "f")


def _change(current: int | None, prior: int | None) -> dict[str, Any]:
    if current is None or prior is None:
        return {
            "absolute_raw": None,
            "percentage": None,
            "percentage_state": "unavailable_incomplete_coverage",
        }

    absolute = current - prior
    if prior == 0:
        return {
            "absolute_raw": absolute,
            "percentage": None,
            "percentage_state": (
                "unchanged_zero_baseline"
                if current == 0
                else "undefined_zero_baseline"
            ),
        }

    try:
        percentage = (Decimal(absolute) / abs(Decimal(prior))) * Decimal(100)
    except (InvalidOperation, ZeroDivisionError):
        percentage = None

    return {
        "absolute_raw": absolute,
        "percentage": (
            None if percentage is None else format(percentage, "f")
        ),
        "percentage_state": "ok" if percentage is not None else "unavailable",
    }


def _validate_qualified_route(route_qualification: Any) -> dict[str, Any]:
    qualification = _mapping(route_qualification, "route_qualification")
    if qualification.get("contract") != WARP_QUALIFICATION_CONTRACT:
        raise BridgeFlowContractError(
            f"route_qualification must use {WARP_QUALIFICATION_CONTRACT}"
        )
    if qualification.get("warp_qualified") is not True:
        raise BridgeFlowContractError("route_qualification must be qualified")

    evidence = _mapping(
        qualification.get("route_evidence"),
        "route_qualification.route_evidence",
    )
    if evidence.get("qualified") is not True:
        raise BridgeFlowContractError("route evidence must be qualified")

    route_id = _required_text(evidence.get("route_id"), "route_id")
    source = _exact_endpoint(evidence.get("source"), "route source")
    destination = _exact_endpoint(evidence.get("destination"), "route destination")
    semantic_contract_id = _required_text(
        evidence.get("semantic_contract_id"),
        "semantic_contract_id",
    )

    return {
        "route_id": route_id,
        "source": source,
        "destination": destination,
        "semantic_contract_id": semantic_contract_id,
        "route_evidence_id": evidence.get("evidence_id"),
        "source_url": evidence.get("source_url"),
    }


def _normalize_event(
    raw: Any,
    *,
    route: Mapping[str, Any],
    event_index: int,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(raw, Mapping):
        return None, "malformed_event"

    try:
        event_id = _required_text(raw.get("event_id"), f"events[{event_index}].event_id")
        transfer_id = _required_text(
            raw.get("transfer_id"), f"events[{event_index}].transfer_id"
        )
        route_id = _required_text(raw.get("route_id"), f"events[{event_index}].route_id")
        direction = _required_text(
            raw.get("direction"), f"events[{event_index}].direction"
        ).casefold()
        lifecycle_state = _required_text(
            raw.get("lifecycle_state"),
            f"events[{event_index}].lifecycle_state",
        ).casefold()
        amount_raw = _nonnegative_int(
            raw.get("amount_raw"), f"events[{event_index}].amount_raw"
        )
        decimals = _nonnegative_int(
            raw.get("decimals"), f"events[{event_index}].decimals"
        )
        settled_at = _epoch(
            raw.get("settled_at"), f"events[{event_index}].settled_at"
        )
        source = _exact_endpoint(raw.get("source"), f"events[{event_index}].source")
        destination = _exact_endpoint(
            raw.get("destination"),
            f"events[{event_index}].destination",
        )
    except BridgeFlowContractError:
        return None, "malformed_event"

    if route_id != route["route_id"]:
        return None, "route_identity_mismatch"
    if not _same_endpoint(source, route["source"]):
        return None, "source_identity_mismatch"
    if not _same_endpoint(destination, route["destination"]):
        return None, "destination_identity_mismatch"
    if direction not in {"inflow", "outflow"}:
        return None, "unsupported_direction"

    settlement_verified = raw.get("settlement_verified")
    pairing_verified = raw.get("pairing_verified")
    if not isinstance(settlement_verified, bool):
        return None, "missing_settlement_verification"
    if not isinstance(pairing_verified, bool):
        return None, "missing_pairing_verification"

    if lifecycle_state != SETTLED_STATE:
        return None, f"excluded_{lifecycle_state}"
    if settlement_verified is not True:
        return None, "unverified_settlement"
    if pairing_verified is not True:
        return None, "unverified_pairing"

    return {
        "event_id": event_id,
        "transfer_id": transfer_id,
        "route_id": route_id,
        "direction": direction,
        "amount_raw": amount_raw,
        "decimals": decimals,
        "settled_at": settled_at,
        "source": source,
        "destination": destination,
    }, None


def _window_metric(
    events: Sequence[Mapping[str, Any]],
    *,
    start: float,
    end: float,
) -> dict[str, int]:
    inflow = 0
    outflow = 0
    inflow_count = 0
    outflow_count = 0
    for event in events:
        timestamp = float(event["settled_at"])
        if timestamp < start or timestamp >= end:
            continue
        amount = int(event["amount_raw"])
        if event["direction"] == "inflow":
            inflow += amount
            inflow_count += 1
        else:
            outflow += amount
            outflow_count += 1
    return {
        "inflow_raw": inflow,
        "outflow_raw": outflow,
        "net_flow_raw": inflow - outflow,
        "inflow_event_count": inflow_count,
        "outflow_event_count": outflow_count,
    }


def _coverage_complete(
    *,
    coverage_verified: bool,
    coverage_start: float,
    coverage_end: float,
    start: float,
    end: float,
) -> bool:
    return bool(
        coverage_verified
        and coverage_start <= start
        and coverage_end >= end
    )


def _supply_projection(
    supply_evidence: Any,
    *,
    decimals: int,
) -> dict[str, Any]:
    if supply_evidence is None:
        return {
            "status": "unavailable",
            "amount_raw": None,
            "amount": None,
            "decimals": decimals,
            "verified": False,
            "reason": "accepted_supply_evidence_not_supplied",
        }

    evidence = _mapping(supply_evidence, "supply_evidence")
    if (
        evidence.get("verified") is not True
        or evidence.get("semantic_contract_accepted") is not True
    ):
        return {
            "status": "unavailable",
            "amount_raw": None,
            "amount": None,
            "decimals": decimals,
            "verified": False,
            "reason": "accepted_supply_semantics_not_verified",
        }

    evidence_decimals = _nonnegative_int(
        evidence.get("decimals"), "supply_evidence.decimals"
    )
    if evidence_decimals != decimals:
        raise BridgeFlowContractError(
            "supply_evidence decimals must match route event decimals"
        )
    amount_raw = _nonnegative_int(
        evidence.get("amount_raw"), "supply_evidence.amount_raw"
    )
    basis = _required_text(evidence.get("basis"), "supply_evidence.basis")
    observed_at = _epoch(
        evidence.get("observed_at"), "supply_evidence.observed_at"
    )

    return {
        "status": "ok",
        "amount_raw": amount_raw,
        "amount": _decimal_string(amount_raw, decimals),
        "decimals": decimals,
        "verified": True,
        "basis": basis,
        "observed_at": observed_at,
    }


def build_bridge_flow_intelligence(
    *,
    route_qualification: Any,
    events: Any,
    as_of: Any,
    coverage_start: Any,
    coverage_end: Any,
    supply_evidence: Any = None,
    coverage_verified: bool = False,
    source_independence_verified: bool = False,
) -> dict[str, Any]:
    """Compute deterministic bridge flow windows for one qualified route."""

    route = _validate_qualified_route(route_qualification)
    as_of_epoch = _epoch(as_of, "as_of")
    coverage_start_epoch = _epoch(coverage_start, "coverage_start")
    coverage_end_epoch = _epoch(coverage_end, "coverage_end")
    if coverage_start_epoch > coverage_end_epoch:
        raise BridgeFlowContractError("coverage_start cannot exceed coverage_end")
    if coverage_end_epoch < as_of_epoch:
        raise BridgeFlowContractError("coverage_end must reach as_of")
    if not isinstance(coverage_verified, bool):
        raise BridgeFlowContractError("coverage_verified must be boolean")
    if not isinstance(source_independence_verified, bool):
        raise BridgeFlowContractError(
            "source_independence_verified must be boolean"
        )
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes, bytearray)):
        raise BridgeFlowContractError("events must be a sequence")

    accepted: list[dict[str, Any]] = []
    unresolved_counts: dict[str, int] = {}
    seen_event_ids: set[str] = set()
    seen_transfer_ids: set[str] = set()
    decimals: int | None = None

    for index, raw in enumerate(events):
        normalized, reason = _normalize_event(raw, route=route, event_index=index)
        if normalized is None:
            unresolved_counts[reason or "unknown"] = (
                unresolved_counts.get(reason or "unknown", 0) + 1
            )
            continue

        if normalized["event_id"] in seen_event_ids:
            unresolved_counts["duplicate_event_id"] = (
                unresolved_counts.get("duplicate_event_id", 0) + 1
            )
            continue
        seen_event_ids.add(normalized["event_id"])

        if normalized["transfer_id"] in seen_transfer_ids:
            unresolved_counts["duplicate_transfer_id"] = (
                unresolved_counts.get("duplicate_transfer_id", 0) + 1
            )
            continue
        seen_transfer_ids.add(normalized["transfer_id"])

        if normalized["settled_at"] >= as_of_epoch:
            unresolved_counts["outside_as_of"] = (
                unresolved_counts.get("outside_as_of", 0) + 1
            )
            continue
        if normalized["settled_at"] < coverage_start_epoch:
            unresolved_counts["before_declared_coverage"] = (
                unresolved_counts.get("before_declared_coverage", 0) + 1
            )
            continue

        if decimals is None:
            decimals = int(normalized["decimals"])
        elif int(normalized["decimals"]) != decimals:
            unresolved_counts["decimals_mismatch"] = (
                unresolved_counts.get("decimals_mismatch", 0) + 1
            )
            continue

        accepted.append(normalized)

    accepted.sort(key=lambda item: (item["settled_at"], item["event_id"]))
    if decimals is None:
        if supply_evidence is not None and isinstance(supply_evidence, Mapping):
            decimals = _nonnegative_int(
                supply_evidence.get("decimals"), "supply_evidence.decimals"
            )
        else:
            decimals = 0

    windows: dict[str, Any] = {}
    any_incomplete = False
    for label, seconds in WINDOWS.items():
        current_start = as_of_epoch - seconds
        prior_start = current_start - seconds
        current_complete = _coverage_complete(
            coverage_verified=coverage_verified,
            coverage_start=coverage_start_epoch,
            coverage_end=coverage_end_epoch,
            start=current_start,
            end=as_of_epoch,
        )
        prior_complete = _coverage_complete(
            coverage_verified=coverage_verified,
            coverage_start=coverage_start_epoch,
            coverage_end=coverage_end_epoch,
            start=prior_start,
            end=current_start,
        )

        current_observed = _window_metric(
            accepted,
            start=current_start,
            end=as_of_epoch,
        )
        prior_observed = _window_metric(
            accepted,
            start=prior_start,
            end=current_start,
        )

        if not current_complete:
            any_incomplete = True
        if not prior_complete:
            any_incomplete = True

        current_values = {
            key: value if current_complete else None
            for key, value in current_observed.items()
        }
        prior_values = {
            key: value if prior_complete else None
            for key, value in prior_observed.items()
        }

        changes = {}
        for metric in ("inflow_raw", "outflow_raw", "net_flow_raw"):
            changes[metric] = _change(
                current_values[metric],
                prior_values[metric],
            )

        windows[label] = {
            "current": {
                "start": current_start,
                "end": as_of_epoch,
                "coverage_complete": current_complete,
                **current_values,
                "inflow": _decimal_string(
                    current_values["inflow_raw"], decimals
                ),
                "outflow": _decimal_string(
                    current_values["outflow_raw"], decimals
                ),
                "net_flow": _decimal_string(
                    current_values["net_flow_raw"], decimals
                ),
            },
            "prior": {
                "start": prior_start,
                "end": current_start,
                "coverage_complete": prior_complete,
                **prior_values,
                "inflow": _decimal_string(
                    prior_values["inflow_raw"], decimals
                ),
                "outflow": _decimal_string(
                    prior_values["outflow_raw"], decimals
                ),
                "net_flow": _decimal_string(
                    prior_values["net_flow_raw"], decimals
                ),
            },
            "changes": changes,
        }

    supply = _supply_projection(supply_evidence, decimals=decimals)
    evidence_core = {
        "contract": CONTRACT_VERSION,
        "route_id": route["route_id"],
        "source": route["source"],
        "destination": route["destination"],
        "semantic_contract_id": route["semantic_contract_id"],
        "route_evidence_id": route["route_evidence_id"],
        "as_of": as_of_epoch,
        "coverage_start": coverage_start_epoch,
        "coverage_end": coverage_end_epoch,
        "accepted_event_ids": [item["event_id"] for item in accepted],
        "accepted_transfer_ids": [item["transfer_id"] for item in accepted],
        "unresolved_counts": dict(sorted(unresolved_counts.items())),
        "decimals": decimals,
        "windows": windows,
        "bridged_supply": supply,
    }

    unresolved_count = sum(unresolved_counts.values())
    status = "partial" if any_incomplete or unresolved_count else "ok"

    return {
        "service": SERVICE,
        "contract": CONTRACT_VERSION,
        "status": status,
        "provider": "warp_bridge",
        "route_id": route["route_id"],
        "source": route["source"],
        "destination": route["destination"],
        "semantic_contract_id": route["semantic_contract_id"],
        "route_evidence_id": route["route_evidence_id"],
        "decimals": decimals,
        "as_of": as_of_epoch,
        "coverage": {
            "start": coverage_start_epoch,
            "end": coverage_end_epoch,
            "coverage_verified": coverage_verified,
            "source_independence_verified": source_independence_verified,
            "complete_for_all_current_and_prior_windows": not any_incomplete,
        },
        "bridged_supply": supply,
        "windows": windows,
        "event_accounting": {
            "input_event_count": len(events),
            "accepted_settled_event_count": len(accepted),
            "unresolved_or_excluded_event_count": unresolved_count,
            "unresolved_counts": dict(sorted(unresolved_counts.items())),
        },
        "evidence_sha256": _canonical_sha256(evidence_core),
        "route_scoped_only": True,
        "missing_history_zero_filled": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "BridgeFlowContractError",
    "CONTRACT_VERSION",
    "SERVICE",
    "SETTLED_STATE",
    "WINDOWS",
    "build_bridge_flow_intelligence",
]
