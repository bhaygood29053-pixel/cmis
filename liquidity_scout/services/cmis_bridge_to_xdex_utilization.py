"""Deterministic Bridge-to-XDEX Utilization Intelligence for CMIS #410.

This contract composes already-verified bridge-flow/supply evidence with an
exact XDEX pool universe and verified/fresh pool market metrics. It never
discovers pools, prices, liquidity, or volume itself.

The core ratio is produced only when numerator and denominator are explicitly
comparable value units. USD-denominated XDEX liquidity is never divided by raw
bridged token supply.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.providers.x1.warp_bridge_flow_integration import (
    CONTRACT as WARP_BRIDGE_FLOW_CONTRACT,
)

SERVICE = "bridge_to_xdex_utilization"
CONTRACT_VERSION = "bridge_to_xdex_utilization/v1"
POOL_UNIVERSE_CONTRACT = "xdex_exact_representation_pool_universe/v1"
POOL_METRIC_CONTRACT = "xdex_verified_pool_market_metrics/v1"
VALUE_BASIS_CONTRACT = "verified_representation_value_basis/v1"
VALUE_UNIT = "USD"
DEFAULT_MAX_MARKET_AGE_SECONDS = 300.0
DEFAULT_MAX_FUTURE_SKEW_SECONDS = 30.0


class BridgeToXdexUtilizationError(ValueError):
    """Raised when #410 inputs cannot be composed without widening semantics."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BridgeToXdexUtilizationError(f"{field} must be a mapping")
    return value


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise BridgeToXdexUtilizationError(f"{field} is required")
    return text


def _bool_true(value: Any, field: str) -> None:
    if value is not True:
        raise BridgeToXdexUtilizationError(f"{field} must be true")


def _bool_false(value: Any, field: str) -> None:
    if value is not False:
        raise BridgeToXdexUtilizationError(f"{field} must be false")


def _epoch(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise BridgeToXdexUtilizationError(f"{field} must be epoch seconds")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise BridgeToXdexUtilizationError(
            f"{field} must be epoch seconds"
        ) from exc
    if parsed <= 0:
        raise BridgeToXdexUtilizationError(f"{field} must be positive")
    return parsed


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise BridgeToXdexUtilizationError(
            f"{field} must be a nonnegative integer"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise BridgeToXdexUtilizationError(
            f"{field} must be a nonnegative integer"
        ) from exc
    if parsed < 0:
        raise BridgeToXdexUtilizationError(f"{field} must be nonnegative")
    return parsed


def _decimal(value: Any, field: str, *, allow_zero: bool = True) -> Decimal:
    if value is None or isinstance(value, bool):
        raise BridgeToXdexUtilizationError(f"{field} must be a finite number")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BridgeToXdexUtilizationError(
            f"{field} must be a finite number"
        ) from exc
    if not parsed.is_finite():
        raise BridgeToXdexUtilizationError(f"{field} must be finite")
    if parsed < 0 or (not allow_zero and parsed == 0):
        qualifier = "positive" if not allow_zero else "nonnegative"
        raise BridgeToXdexUtilizationError(f"{field} must be {qualifier}")
    return parsed


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _ratio(numerator: Decimal, denominator: Decimal) -> str | None:
    if denominator == 0:
        return None
    return format(numerator / denominator, "f")


def _require_current(
    *,
    observed_at: Any,
    as_of: float,
    field: str,
    max_age_seconds: float,
    max_future_skew_seconds: float,
) -> float:
    observed = _epoch(observed_at, field)
    age = as_of - observed
    if age > max_age_seconds:
        raise BridgeToXdexUtilizationError(f"{field} is stale")
    if age < -max_future_skew_seconds:
        raise BridgeToXdexUtilizationError(f"{field} is too far in the future")
    return observed


def _bridge_inputs(bridge_integration: Any) -> dict[str, Any]:
    bridge = _mapping(bridge_integration, "bridge_integration")
    if bridge.get("contract") != WARP_BRIDGE_FLOW_CONTRACT:
        raise BridgeToXdexUtilizationError(
            f"bridge_integration must use {WARP_BRIDGE_FLOW_CONTRACT}"
        )
    _bool_true(bridge.get("integration_verified"), "bridge_integration.integration_verified")
    _bool_false(bridge.get("execution_authorized"), "bridge_integration.execution_authorized")

    source_raw = bridge.get("source")
    source_chain = None
    source_mint = None
    if isinstance(source_raw, Mapping):
        source_chain = _text(
            source_raw.get("chain"),
            "bridge_integration.source.chain",
        ).casefold()
        if source_raw.get("asset_id_kind") != "mint":
            raise BridgeToXdexUtilizationError(
                "bridge_integration.source.asset_id_kind must be mint"
            )
        source_mint = _text(
            source_raw.get("asset_id"),
            "bridge_integration.source.asset_id",
        )

    destination = _mapping(bridge.get("destination"), "bridge_integration.destination")
    if str(destination.get("chain") or "").strip().casefold() != "x1":
        raise BridgeToXdexUtilizationError(
            "bridge_integration.destination.chain must be x1"
        )
    if destination.get("asset_id_kind") != "mint":
        raise BridgeToXdexUtilizationError(
            "bridge_integration.destination.asset_id_kind must be mint"
        )
    representation_mint = _text(
        destination.get("asset_id"),
        "bridge_integration.destination.asset_id",
    )

    flow = _mapping(bridge.get("flow"), "bridge_integration.flow")
    as_of = _epoch(flow.get("as_of"), "bridge_integration.flow.as_of")
    decimals = _nonnegative_int(
        flow.get("decimals"),
        "bridge_integration.flow.decimals",
    )
    supply = _mapping(
        flow.get("bridged_supply"),
        "bridge_integration.flow.bridged_supply",
    )
    _bool_true(supply.get("verified"), "bridge_integration.flow.bridged_supply.verified")
    supply_raw = _nonnegative_int(
        supply.get("amount_raw"),
        "bridge_integration.flow.bridged_supply.amount_raw",
    )
    supply_decimals = _nonnegative_int(
        supply.get("decimals"),
        "bridge_integration.flow.bridged_supply.decimals",
    )
    if supply_decimals != decimals:
        raise BridgeToXdexUtilizationError(
            "bridged supply decimals must match bridge flow decimals"
        )

    windows = _mapping(flow.get("windows"), "bridge_integration.flow.windows")
    current_24h = _mapping(
        _mapping(windows.get("24h"), "bridge_integration.flow.windows.24h").get("current"),
        "bridge_integration.flow.windows.24h.current",
    )
    _bool_true(
        current_24h.get("coverage_complete"),
        "bridge_integration.flow.windows.24h.current.coverage_complete",
    )
    inflow_raw = _nonnegative_int(
        current_24h.get("inflow_raw"),
        "bridge_integration.flow.windows.24h.current.inflow_raw",
    )
    outflow_raw = _nonnegative_int(
        current_24h.get("outflow_raw"),
        "bridge_integration.flow.windows.24h.current.outflow_raw",
    )
    net_flow_raw = current_24h.get("net_flow_raw")
    if isinstance(net_flow_raw, bool):
        raise BridgeToXdexUtilizationError(
            "bridge_integration.flow.windows.24h.current.net_flow_raw must be integer"
        )
    try:
        net_flow_raw = int(net_flow_raw)
    except (TypeError, ValueError) as exc:
        raise BridgeToXdexUtilizationError(
            "bridge_integration.flow.windows.24h.current.net_flow_raw must be integer"
        ) from exc
    if net_flow_raw != inflow_raw - outflow_raw:
        raise BridgeToXdexUtilizationError(
            "bridge 24h net flow does not equal inflow minus outflow"
        )

    return {
        "route_id": _text(bridge.get("route_id"), "bridge_integration.route_id"),
        "source_chain": source_chain,
        "source_mint": source_mint,
        "destination_chain": "x1",
        "representation_mint": representation_mint,
        "source_independence_verified": bridge.get("source_independence_verified") is True,
        "as_of": as_of,
        "decimals": decimals,
        "supply_raw": supply_raw,
        "inflow_24h_raw": inflow_raw,
        "outflow_24h_raw": outflow_raw,
        "net_flow_24h_raw": net_flow_raw,
    }


def _pool_universe(
    pool_universe: Any,
    *,
    representation_mint: str,
) -> dict[str, Any]:
    universe = _mapping(pool_universe, "pool_universe")
    if universe.get("contract") != POOL_UNIVERSE_CONTRACT:
        raise BridgeToXdexUtilizationError(
            f"pool_universe must use {POOL_UNIVERSE_CONTRACT}"
        )
    if universe.get("representation_mint") != representation_mint:
        raise BridgeToXdexUtilizationError(
            "pool_universe representation mint mismatch"
        )
    _bool_true(
        universe.get("enumeration_verified"),
        "pool_universe.enumeration_verified",
    )
    _bool_true(
        universe.get("all_pool_identities_verified"),
        "pool_universe.all_pool_identities_verified",
    )
    _bool_false(
        universe.get("execution_authorized"),
        "pool_universe.execution_authorized",
    )

    unresolved = universe.get("unresolved_pools")
    if not isinstance(unresolved, list):
        raise BridgeToXdexUtilizationError(
            "pool_universe.unresolved_pools must be a list"
        )
    if unresolved:
        raise BridgeToXdexUtilizationError(
            "pool_universe contains unresolved pools"
        )

    raw_addresses = universe.get("pool_addresses")
    if not isinstance(raw_addresses, list):
        raise BridgeToXdexUtilizationError(
            "pool_universe.pool_addresses must be a list"
        )
    addresses = [
        _text(value, f"pool_universe.pool_addresses[{index}]")
        for index, value in enumerate(raw_addresses)
    ]
    if len(set(addresses)) != len(addresses):
        raise BridgeToXdexUtilizationError(
            "pool_universe.pool_addresses contains duplicates"
        )

    verified_zero_set = universe.get("verified_zero_set") is True
    current_liquidity_zero_verified = (
        universe.get("current_liquidity_zero_verified") is True
    )
    volume_24h_window_coverage_verified = (
        universe.get("volume_24h_window_coverage_verified") is True
    )
    if not addresses and not verified_zero_set:
        raise BridgeToXdexUtilizationError(
            "empty pool universe requires explicit verified_zero_set"
        )
    if verified_zero_set and addresses:
        raise BridgeToXdexUtilizationError(
            "verified_zero_set cannot contain pool addresses"
        )
    if verified_zero_set and not current_liquidity_zero_verified:
        raise BridgeToXdexUtilizationError(
            "verified zero pool set lacks current liquidity-zero proof"
        )

    return {
        "addresses": sorted(addresses),
        "verified_zero_set": verified_zero_set,
        "current_liquidity_zero_verified": current_liquidity_zero_verified,
        "volume_24h_window_coverage_verified": (
            volume_24h_window_coverage_verified
        ),
        "scope": universe.get("scope"),
        "recognized_program_registry_globally_exhaustive": (
            universe.get("recognized_program_registry_globally_exhaustive") is True
        ),
        "global_onchain_pool_discovery_proven": (
            universe.get("global_onchain_pool_discovery_proven") is True
        ),
    }


def _value_basis(
    value_basis: Any,
    *,
    representation_mint: str,
    as_of: float,
    max_age_seconds: float,
    max_future_skew_seconds: float,
) -> dict[str, Any]:
    basis = _mapping(value_basis, "value_basis")
    if basis.get("contract") != VALUE_BASIS_CONTRACT:
        raise BridgeToXdexUtilizationError(
            f"value_basis must use {VALUE_BASIS_CONTRACT}"
        )
    evidence_id = _text(basis.get("evidence_id"), "value_basis.evidence_id")
    if basis.get("asset_mint") != representation_mint:
        raise BridgeToXdexUtilizationError("value_basis asset mint mismatch")
    if str(basis.get("unit") or "").strip().upper() != VALUE_UNIT:
        raise BridgeToXdexUtilizationError("value_basis unit must be USD")
    _bool_true(
        basis.get("price_semantics_verified"),
        "value_basis.price_semantics_verified",
    )
    _bool_true(
        basis.get("price_freshness_verified"),
        "value_basis.price_freshness_verified",
    )
    _bool_false(
        basis.get("execution_authorized"),
        "value_basis.execution_authorized",
    )
    price = _decimal(
        basis.get("price_per_token"),
        "value_basis.price_per_token",
        allow_zero=False,
    )
    observed_at = _require_current(
        observed_at=basis.get("observed_at"),
        as_of=as_of,
        field="value_basis.observed_at",
        max_age_seconds=max_age_seconds,
        max_future_skew_seconds=max_future_skew_seconds,
    )
    return {
        "evidence_id": evidence_id,
        "price_per_token": price,
        "observed_at": observed_at,
    }


def _pool_metrics(
    pool_metrics: Any,
    *,
    representation_mint: str,
    expected_pool_addresses: list[str],
    verified_zero_set: bool = False,
    volume_24h_window_coverage_verified: bool = False,
    as_of: float,
    max_age_seconds: float,
    max_future_skew_seconds: float,
) -> dict[str, Any]:
    if not isinstance(pool_metrics, Sequence) or isinstance(
        pool_metrics, (str, bytes, bytearray)
    ):
        raise BridgeToXdexUtilizationError("pool_metrics must be a sequence")

    expected = set(expected_pool_addresses)
    seen: set[str] = set()
    accepted: list[dict[str, Any]] = []
    total_liquidity = Decimal(0)
    total_volume_24h: Decimal | None = (
        Decimal(0)
        if expected or volume_24h_window_coverage_verified
        else None
    )

    for index, raw in enumerate(pool_metrics):
        metric = _mapping(raw, f"pool_metrics[{index}]")
        if metric.get("contract") != POOL_METRIC_CONTRACT:
            raise BridgeToXdexUtilizationError(
                f"pool_metrics[{index}] must use {POOL_METRIC_CONTRACT}"
            )
        address = _text(
            metric.get("pool_address"),
            f"pool_metrics[{index}].pool_address",
        )
        if address in seen:
            raise BridgeToXdexUtilizationError(
                f"duplicate pool metric for {address}"
            )
        seen.add(address)
        if address not in expected:
            raise BridgeToXdexUtilizationError(
                f"pool metric {address} is outside exact pool universe"
            )
        if metric.get("representation_mint") != representation_mint:
            raise BridgeToXdexUtilizationError(
                f"pool metric {address} representation mint mismatch"
            )
        for field in (
            "exact_pool_identity_verified",
            "contains_representation_mint",
            "liquidity_semantics_verified",
            "liquidity_freshness_verified",
            "volume_24h_semantics_verified",
            "volume_24h_freshness_verified",
        ):
            _bool_true(metric.get(field), f"pool metric {address}.{field}")
        _bool_false(
            metric.get("execution_authorized"),
            f"pool metric {address}.execution_authorized",
        )
        if str(metric.get("value_unit") or "").strip().upper() != VALUE_UNIT:
            raise BridgeToXdexUtilizationError(
                f"pool metric {address} value_unit must be USD"
            )
        observed_at = _require_current(
            observed_at=metric.get("observed_at"),
            as_of=as_of,
            field=f"pool metric {address}.observed_at",
            max_age_seconds=max_age_seconds,
            max_future_skew_seconds=max_future_skew_seconds,
        )
        liquidity = _decimal(
            metric.get("liquidity_value"),
            f"pool metric {address}.liquidity_value",
        )
        volume_24h = _decimal(
            metric.get("volume_24h_value"),
            f"pool metric {address}.volume_24h_value",
        )
        total_liquidity += liquidity
        if total_volume_24h is None:
            raise BridgeToXdexUtilizationError(
                "pool volume observed without verified volume aggregation state"
            )
        total_volume_24h += volume_24h
        accepted.append(
            {
                "pool_address": address,
                "liquidity_value": format(liquidity, "f"),
                "volume_24h_value": format(volume_24h, "f"),
                "value_unit": VALUE_UNIT,
                "observed_at": observed_at,
            }
        )

    missing = sorted(expected - seen)
    if missing:
        raise BridgeToXdexUtilizationError(
            "pool metrics do not cover exact pool universe: " + ", ".join(missing)
        )
    if not expected and accepted:
        raise BridgeToXdexUtilizationError(
            "verified zero pool universe cannot contain pool metrics"
        )
    if not expected and not verified_zero_set:
        raise BridgeToXdexUtilizationError(
            "empty pool metric set requires verified zero pool universe"
        )

    accepted.sort(key=lambda item: item["pool_address"])
    return {
        "pools": accepted,
        "total_liquidity": total_liquidity,
        "total_volume_24h": total_volume_24h,
    }


def build_bridge_to_xdex_utilization(
    *,
    bridge_integration: Any,
    pool_universe: Any,
    pool_metrics: Any,
    value_basis: Any,
    max_market_age_seconds: Any = DEFAULT_MAX_MARKET_AGE_SECONDS,
    max_future_skew_seconds: Any = DEFAULT_MAX_FUTURE_SKEW_SECONDS,
) -> dict[str, Any]:
    """Build the bounded #410 utilization contract from accepted inputs."""

    max_age = float(
        _decimal(
            max_market_age_seconds,
            "max_market_age_seconds",
            allow_zero=False,
        )
    )
    max_future = float(
        _decimal(
            max_future_skew_seconds,
            "max_future_skew_seconds",
            allow_zero=True,
        )
    )

    bridge = _bridge_inputs(bridge_integration)
    universe = _pool_universe(
        pool_universe,
        representation_mint=bridge["representation_mint"],
    )
    basis = _value_basis(
        value_basis,
        representation_mint=bridge["representation_mint"],
        as_of=bridge["as_of"],
        max_age_seconds=max_age,
        max_future_skew_seconds=max_future,
    )
    markets = _pool_metrics(
        pool_metrics,
        representation_mint=bridge["representation_mint"],
        expected_pool_addresses=universe["addresses"],
        verified_zero_set=universe["verified_zero_set"],
        volume_24h_window_coverage_verified=universe[
            "volume_24h_window_coverage_verified"
        ],
        as_of=bridge["as_of"],
        max_age_seconds=max_age,
        max_future_skew_seconds=max_future,
    )

    scale = Decimal(10) ** bridge["decimals"]
    price = basis["price_per_token"]
    supply_tokens = Decimal(bridge["supply_raw"]) / scale
    inflow_tokens = Decimal(bridge["inflow_24h_raw"]) / scale
    outflow_tokens = Decimal(bridge["outflow_24h_raw"]) / scale
    net_tokens = Decimal(bridge["net_flow_24h_raw"]) / scale

    supply_value = supply_tokens * price
    inflow_value = inflow_tokens * price
    outflow_value = outflow_tokens * price
    net_value = net_tokens * price
    gross_flow_value = inflow_value + outflow_value

    liquidity_value = markets["total_liquidity"]
    volume_24h_value = markets["total_volume_24h"]

    liquidity_ratio = _ratio(liquidity_value, supply_value)
    gross_flow_to_volume = (
        _ratio(gross_flow_value, volume_24h_value)
        if volume_24h_value is not None
        else None
    )
    net_flow_to_volume = (
        _ratio(net_value, volume_24h_value)
        if volume_24h_value is not None
        else None
    )

    utilization_verified = liquidity_ratio is not None
    core = {
        "service": SERVICE,
        "contract": CONTRACT_VERSION,
        "route_id": bridge["route_id"],
        "source_chain": bridge["source_chain"],
        "source_mint": bridge["source_mint"],
        "destination_chain": bridge["destination_chain"],
        "destination_mint": bridge["representation_mint"],
        "representation_mint": bridge["representation_mint"],
        "as_of": bridge["as_of"],
        "pool_universe_contract": POOL_UNIVERSE_CONTRACT,
        "pool_metric_contract": POOL_METRIC_CONTRACT,
        "value_basis_contract": VALUE_BASIS_CONTRACT,
        "value_basis_evidence_id": basis["evidence_id"],
        "value_unit": VALUE_UNIT,
        "comparable_value_basis_verified": True,
        "xdex_pool_count": len(universe["addresses"]),
        "xdex_pool_addresses": universe["addresses"],
        "xdex_pool_universe_scope": universe["scope"],
        "recognized_program_registry_globally_exhaustive": universe[
            "recognized_program_registry_globally_exhaustive"
        ],
        "global_onchain_pool_discovery_proven": universe[
            "global_onchain_pool_discovery_proven"
        ],
        "verified_zero_pool_set": universe["verified_zero_set"],
        "current_liquidity_zero_verified": universe[
            "current_liquidity_zero_verified"
        ],
        "volume_24h_window_coverage_verified": universe[
            "volume_24h_window_coverage_verified"
        ],
        "pool_metrics": markets["pools"],
        "verified_xdex_liquidity_value": _decimal_text(liquidity_value),
        "verified_xdex_volume_24h_value": _decimal_text(volume_24h_value),
        "bridged_supply_raw": bridge["supply_raw"],
        "bridged_supply_decimals": bridge["decimals"],
        "bridged_supply_token_amount": _decimal_text(supply_tokens),
        "bridged_supply_value": _decimal_text(supply_value),
        "bridge_flow_24h": {
            "inflow_raw": bridge["inflow_24h_raw"],
            "outflow_raw": bridge["outflow_24h_raw"],
            "net_flow_raw": bridge["net_flow_24h_raw"],
            "inflow_value": _decimal_text(inflow_value),
            "outflow_value": _decimal_text(outflow_value),
            "net_flow_value": _decimal_text(net_value),
            "gross_flow_value": _decimal_text(gross_flow_value),
            "value_unit": VALUE_UNIT,
        },
        "bridge_to_xdex_liquidity_ratio": liquidity_ratio,
        "bridge_to_xdex_liquidity_ratio_state": (
            "verified" if liquidity_ratio is not None else "undefined_zero_bridged_supply"
        ),
        "bridge_gross_flow_24h_to_xdex_volume_24h_ratio": gross_flow_to_volume,
        "bridge_net_flow_24h_to_xdex_volume_24h_ratio": net_flow_to_volume,
        "bridge_flow_to_xdex_volume_ratio_state": (
            "descriptive"
            if gross_flow_to_volume is not None
            else (
                "unavailable_unverified_volume_window"
                if volume_24h_value is None
                else "undefined_zero_xdex_volume"
            )
        ),
        "market_activity_24h_verified": volume_24h_value is not None,
        "utilization_verified": utilization_verified,
        "issue_410_acceptance_verified": bool(
            utilization_verified and volume_24h_value is not None
        ),
        "source_independence_verified": bridge["source_independence_verified"],
        "causal_bridge_to_xdex_claim_authorized": False,
        "adoption_claim_authorized": False,
        "risk_promotion_authorized": False,
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
    "BridgeToXdexUtilizationError",
    "CONTRACT_VERSION",
    "DEFAULT_MAX_FUTURE_SKEW_SECONDS",
    "DEFAULT_MAX_MARKET_AGE_SECONDS",
    "POOL_METRIC_CONTRACT",
    "POOL_UNIVERSE_CONTRACT",
    "SERVICE",
    "VALUE_BASIS_CONTRACT",
    "VALUE_UNIT",
    "build_bridge_to_xdex_utilization",
]
