"""Internal read-only XDEX exact-route evidence producer for CMIS pre-trade.

This module converts one verified provider snapshot into the exact
``cmis_xdex_route_resolver`` envelope accepted by the deterministic pre-trade
route-evidence contract. It does not accept caller-supplied proof claims, select
routes, prepare transactions, simulate execution, sign, broadcast, or move
value.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from liquidity_scout.providers.x1.xdex_exact_route import (
    collect_exact_route_snapshot,
)
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import (
    AMM_CONFIG as BOUNDED_FEE_AMM_CONFIG,
    CONFIGURED_FEE_PPM as BOUNDED_FEE_PPM,
    POOL as BOUNDED_FEE_POOL,
    XENCAT_MINT,
    XNT_MINT,
)


SCHEMA_VERSION = 1
SOURCE = "cmis_xdex_route_resolver"
SNAPSHOT_SCHEMA = "xdex_exact_route_snapshot.v1"
PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS = Decimal("0.001")
ROUTE_FIELDS = (
    "token_in_mint",
    "token_out_mint",
    "pool",
    "amm_config",
)


class XDEXRouteResolverError(RuntimeError):
    """Raised when trusted exact-route evidence cannot be promoted safely."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise XDEXRouteResolverError(f"{field} must be a normalized non-empty string")
    text = value.strip()
    if not text or text != value:
        raise XDEXRouteResolverError(f"{field} must be a normalized non-empty string")
    return text


def _route(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise XDEXRouteResolverError("route must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise XDEXRouteResolverError("route keys must be strings")
    unknown = sorted(set(value) - set(ROUTE_FIELDS))
    if unknown:
        raise XDEXRouteResolverError("unknown route fields: " + ", ".join(unknown))
    result = {field: _text(value.get(field), f"route.{field}") for field in ROUTE_FIELDS}
    if result["token_in_mint"] == result["token_out_mint"]:
        raise XDEXRouteResolverError("route token_in_mint and token_out_mint must differ")
    return result


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise XDEXRouteResolverError(f"{field} must be a finite decimal")
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise XDEXRouteResolverError(f"{field} must be a finite decimal") from exc
    if not result.is_finite():
        raise XDEXRouteResolverError(f"{field} must be a finite decimal")
    return result


def _literal_true(snapshot: Mapping[str, Any], field: str) -> None:
    if snapshot.get(field) is not True:
        raise XDEXRouteResolverError(f"snapshot {field} must be literally true")


def _validated_snapshot(snapshot: Any, requested_route: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise XDEXRouteResolverError("route collector did not return a mapping")
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise XDEXRouteResolverError("route collector returned an unsupported snapshot schema")
    if snapshot.get("chain") != "x1":
        raise XDEXRouteResolverError("route collector snapshot chain must be x1")
    if snapshot.get("read_only") is not True:
        raise XDEXRouteResolverError("route collector snapshot must be read-only")
    if snapshot.get("execution_authorized") is not False:
        raise XDEXRouteResolverError("route collector must not authorize execution")

    route = _route(snapshot.get("route"))
    if route != dict(requested_route):
        raise XDEXRouteResolverError("route collector snapshot does not match the requested exact route")

    for field in (
        "quote_identity_verified",
        "pool_state_verified",
        "vault_identity_verified",
        "active_reserves_verified",
        "amm_config_verified",
    ):
        _literal_true(snapshot, field)

    observed_at = _text(snapshot.get("observed_at"), "snapshot.observed_at")
    reconstructed = _decimal(
        snapshot.get("reconstructed_price_impact_percent"),
        "snapshot.reconstructed_price_impact_percent",
    )
    quoted = _decimal(
        snapshot.get("quote_price_impact_percent"),
        "snapshot.quote_price_impact_percent",
    )
    if reconstructed < 0 or quoted < 0:
        raise XDEXRouteResolverError("price impact values must be non-negative")

    trade_fee_ppm = snapshot.get("trade_fee_rate_ppm")
    if isinstance(trade_fee_ppm, bool) or not isinstance(trade_fee_ppm, int):
        raise XDEXRouteResolverError("snapshot trade_fee_rate_ppm must be an integer")
    if trade_fee_ppm < 0 or trade_fee_ppm >= 1_000_000:
        raise XDEXRouteResolverError("snapshot trade_fee_rate_ppm is outside the accepted range")

    return {
        **dict(snapshot),
        "route": route,
        "observed_at": observed_at,
        "reconstructed_price_impact": reconstructed,
        "quote_price_impact": quoted,
        "trade_fee_rate_ppm": trade_fee_ppm,
    }


def _price_impact_capability(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    reconstructed = snapshot["reconstructed_price_impact"]
    quoted = snapshot["quote_price_impact"]
    delta = abs(reconstructed - quoted)
    if delta > PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS:
        raise XDEXRouteResolverError(
            "XDEX quote priceImpactPct does not match independent verified-reserve reconstruction"
        )
    return {
        "status": "verified",
        "semantic": "route_price_impact_percent",
        "value": float(quoted),
        "unit": "percent",
        "proof_basis": [
            "verified_direct_cp_route",
            "verified_pool_reserves",
            "verified_price_impact_semantics",
        ],
    }


def _bounded_fee_scope_matches(route: Mapping[str, str], trade_fee_ppm: int) -> bool:
    return bool(
        route["pool"] == BOUNDED_FEE_POOL
        and route["amm_config"] == BOUNDED_FEE_AMM_CONFIG
        and {route["token_in_mint"], route["token_out_mint"]} == {XENCAT_MINT, XNT_MINT}
        and trade_fee_ppm == BOUNDED_FEE_PPM
    )


def _bounded_fee_capability(route: Mapping[str, str], trade_fee_ppm: int) -> dict[str, Any] | None:
    if not _bounded_fee_scope_matches(route, trade_fee_ppm):
        return None
    fee_percent = Decimal(trade_fee_ppm) / Decimal(10_000)
    value = float(fee_percent)
    return {
        "status": "verified",
        "semantic": "route_execution_fee_estimate",
        "value": {
            "amm_trade_fee_rate_percent": value,
            "bounded_historical_execution_model_fee_percent": value,
        },
        "unit": "structured",
        "proof_basis": [
            "verified_amm_config_trade_fee_rate",
            "bounded_historical_execution_corroboration",
        ],
    }


def resolve_xdex_route_evidence(
    route: Mapping[str, Any],
    token_in_amount: Any,
    *,
    collector: Callable[..., Mapping[str, Any]] = collect_exact_route_snapshot,
) -> dict[str, Any]:
    """Return the trusted route-evidence envelope accepted by pre-trade v1.1.

    Only capabilities with an accepted proof basis are emitted. In particular,
    user slippage tolerance is deliberately absent because it is not an expected
    execution-slippage observation.
    """
    normalized_route = _route(route)
    snapshot = _validated_snapshot(
        collector(normalized_route, token_in_amount),
        normalized_route,
    )

    capabilities: dict[str, Any] = {
        "price_impact": _price_impact_capability(snapshot),
    }
    fee_capability = _bounded_fee_capability(
        normalized_route,
        snapshot["trade_fee_rate_ppm"],
    )
    if fee_capability is not None:
        capabilities["fees"] = fee_capability

    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "chain": "x1",
        "route": normalized_route,
        "observed_at": snapshot["observed_at"],
        "capabilities": capabilities,
    }


__all__ = [
    "PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS",
    "SCHEMA_VERSION",
    "SOURCE",
    "XDEXRouteResolverError",
    "resolve_xdex_route_evidence",
]
