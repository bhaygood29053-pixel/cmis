"""Internal read-only XDEX exact-route evidence producer for CMIS pre-trade.

This module converts one verified provider snapshot into the exact
``cmis_xdex_route_resolver`` envelope accepted by the deterministic pre-trade
route-evidence contract. It does not accept caller-supplied proof claims, select
routes, prepare transactions, simulate execution, sign, broadcast, or move
value.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from liquidity_scout.providers.x1.xdex_exact_route import (
    SOURCE as COLLECTOR_SOURCE,
    collect_exact_route_snapshot,
)
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import (
    X1_PROGRAM,
    classify_xdex_execution_fee_sequence_evidence,
)
from liquidity_scout.services.pre_trade_route_evidence import normalize_token_in_amount


SCHEMA_VERSION = 2
SOURCE = "cmis_xdex_route_resolver"
SNAPSHOT_SCHEMA = "xdex_exact_route_snapshot.v1"
PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS = Decimal("0.001")
FEE_DENOMINATOR = 1_000_000
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
    missing = sorted(set(ROUTE_FIELDS) - set(value))
    if unknown or missing:
        raise XDEXRouteResolverError(
            f"route fields mismatch: missing={missing!r}, unknown={unknown!r}"
        )
    result = {field: _text(value.get(field), f"route.{field}") for field in ROUTE_FIELDS}
    if result["token_in_mint"] == result["token_out_mint"]:
        raise XDEXRouteResolverError("route token_in_mint and token_out_mint must differ")
    return result


def _decimal(value: Any, field: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise XDEXRouteResolverError(f"{field} must be a finite decimal")
    if isinstance(value, str) and (not value or value.strip() != value):
        raise XDEXRouteResolverError(f"{field} must be a finite decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise XDEXRouteResolverError(f"{field} must be a finite decimal") from exc
    if not result.is_finite():
        raise XDEXRouteResolverError(f"{field} must be a finite decimal")
    return result


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise XDEXRouteResolverError(f"{field} must be a positive integer")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise XDEXRouteResolverError(f"{field} must be a non-negative integer")
    return value


def _literal_true(snapshot: Mapping[str, Any], field: str) -> None:
    if snapshot.get(field) is not True:
        raise XDEXRouteResolverError(f"snapshot {field} must be literally true")


def _canonical_utc(value: Any, field: str) -> str:
    text = _text(value, field)
    if not text.endswith("Z"):
        raise XDEXRouteResolverError(f"{field} must be canonical UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise XDEXRouteResolverError(f"{field} must be canonical UTC ending in Z") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise XDEXRouteResolverError(f"{field} must be timezone-aware")
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != text:
        raise XDEXRouteResolverError(f"{field} must be canonical UTC ending in Z")
    return text


def _ceil_fee(amount: int, rate_ppm: int) -> int:
    if rate_ppm == 0:
        return 0
    return (amount * rate_ppm + FEE_DENOMINATOR - 1) // FEE_DENOMINATOR


def _reconstruct_continuous_impact(
    raw_input: int,
    reserve_in: int,
    trade_fee_ppm: int,
) -> Decimal:
    if trade_fee_ppm < 0 or trade_fee_ppm >= FEE_DENOMINATOR:
        raise XDEXRouteResolverError("snapshot trade_fee_rate_ppm is outside the accepted range")
    net_input = raw_input - _ceil_fee(raw_input, trade_fee_ppm)
    if net_input <= 0:
        raise XDEXRouteResolverError("snapshot trade fee consumes the complete raw input")
    return Decimal(net_input) * Decimal(100) / Decimal(reserve_in + net_input)


def _reconstruct_quote_impact(
    raw_input: int,
    reserve_in: int,
    reserve_out: int,
    trade_fee_ppm: int,
) -> Decimal:
    """Reproduce XDEX priceImpactPct using integer-rounded CP output."""
    net_input = raw_input - _ceil_fee(raw_input, trade_fee_ppm)
    if net_input <= 0:
        raise XDEXRouteResolverError("snapshot trade fee consumes the complete raw input")
    raw_output = net_input * reserve_out // (reserve_in + net_input)
    return Decimal(raw_output) * Decimal(100) / Decimal(reserve_out)


def _validated_snapshot(
    snapshot: Any,
    requested_route: Mapping[str, Any],
    requested_amount: str,
) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise XDEXRouteResolverError("route collector did not return a mapping")
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise XDEXRouteResolverError("route collector returned an unsupported snapshot schema")
    if snapshot.get("source") != COLLECTOR_SOURCE:
        raise XDEXRouteResolverError("route collector snapshot source is not accepted")
    if snapshot.get("chain") != "x1":
        raise XDEXRouteResolverError("route collector snapshot chain must be x1")
    if snapshot.get("program") != X1_PROGRAM:
        raise XDEXRouteResolverError("route collector snapshot program must be the accepted XDEX program")
    if snapshot.get("read_only") is not True:
        raise XDEXRouteResolverError("route collector snapshot must be read-only")
    if snapshot.get("execution_authorized") is not False:
        raise XDEXRouteResolverError("route collector must not authorize execution")

    route = _route(snapshot.get("route"))
    if route != dict(requested_route):
        raise XDEXRouteResolverError("route collector snapshot does not match the requested exact route")
    try:
        snapshot_amount = normalize_token_in_amount(snapshot.get("token_in_amount"))
    except ValueError as exc:
        raise XDEXRouteResolverError("route collector snapshot input amount is invalid") from exc
    if snapshot_amount is None or snapshot_amount != requested_amount:
        raise XDEXRouteResolverError("route collector snapshot does not match the requested exact input amount")

    for field in (
        "quote_identity_verified",
        "pool_state_verified",
        "vault_identity_verified",
        "active_reserves_verified",
        "amm_config_verified",
    ):
        _literal_true(snapshot, field)

    if snapshot.get("quote_slippage_percent") != 0:
        raise XDEXRouteResolverError("route collector snapshot must use the accepted zero-slippage quote")

    observed_at = _canonical_utc(snapshot.get("observed_at"), "snapshot.observed_at")
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

    trade_fee_ppm = _nonnegative_int(
        snapshot.get("trade_fee_rate_ppm"),
        "snapshot.trade_fee_rate_ppm",
    )
    if trade_fee_ppm >= FEE_DENOMINATOR:
        raise XDEXRouteResolverError("snapshot trade_fee_rate_ppm is outside the accepted range")
    raw_input = _positive_int(snapshot.get("raw_input_amount"), "snapshot.raw_input_amount")
    reserve_in = _positive_int(
        snapshot.get("active_reserve_in_raw"),
        "snapshot.active_reserve_in_raw",
    )
    reserve_out = _positive_int(
        snapshot.get("active_reserve_out_raw"),
        "snapshot.active_reserve_out_raw",
    )
    input_decimals = _nonnegative_int(snapshot.get("input_decimals"), "snapshot.input_decimals")
    output_decimals = _nonnegative_int(snapshot.get("output_decimals"), "snapshot.output_decimals")
    if input_decimals > 255 or output_decimals > 255:
        raise XDEXRouteResolverError("snapshot token decimals are outside the accepted u8 domain")

    token_in_amount = _decimal(snapshot_amount, "snapshot.token_in_amount")
    scaled = token_in_amount * (Decimal(10) ** input_decimals)
    if scaled != Decimal(raw_input):
        raise XDEXRouteResolverError("snapshot token_in_amount/raw_input_amount are inconsistent")

    independently_reconstructed = _reconstruct_continuous_impact(
        raw_input,
        reserve_in,
        trade_fee_ppm,
    )
    if reconstructed != independently_reconstructed:
        raise XDEXRouteResolverError(
            "snapshot reconstructed price impact does not match deterministic reserve arithmetic"
        )
    quote_semantic_reconstructed = _reconstruct_quote_impact(
        raw_input,
        reserve_in,
        reserve_out,
        trade_fee_ppm,
    )

    return {
        **dict(snapshot),
        "route": route,
        "token_in_amount": snapshot_amount,
        "observed_at": observed_at,
        "reconstructed_price_impact": reconstructed,
        "quote_semantic_price_impact": quote_semantic_reconstructed,
        "quote_price_impact": quoted,
        "trade_fee_rate_ppm": trade_fee_ppm,
    }


def _price_impact_capability(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    reconstructed = snapshot["quote_semantic_price_impact"]
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


def _bounded_fee_capability(
    route: Mapping[str, str],
    trade_fee_ppm: int,
    execution_fee_observation: Any,
) -> dict[str, Any] | None:
    if execution_fee_observation is None:
        return None
    if not isinstance(execution_fee_observation, Mapping):
        raise XDEXRouteResolverError(
            "execution_fee_observation must be a mapping when supplied"
        )
    try:
        classified = classify_xdex_execution_fee_sequence_evidence(execution_fee_observation)
    except (TypeError, ValueError) as exc:
        raise XDEXRouteResolverError("execution fee evidence failed accepted classification") from exc

    if classified.get("status") != "STRONGLY_CORROBORATED":
        raise XDEXRouteResolverError("execution fee evidence is not strongly corroborated")
    if classified.get("bounded_execution_model_supported") is not True:
        raise XDEXRouteResolverError("execution fee evidence does not support a bounded execution model")
    if classified.get("program") != X1_PROGRAM:
        raise XDEXRouteResolverError("execution fee evidence program does not match the route")
    if classified.get("pool") != route["pool"] or classified.get("amm_config") != route["amm_config"]:
        raise XDEXRouteResolverError("execution fee evidence pool/config does not match the route")
    if {classified.get("asset_a_mint"), classified.get("asset_b_mint")} != {
        route["token_in_mint"],
        route["token_out_mint"],
    }:
        raise XDEXRouteResolverError("execution fee evidence asset pair does not match the route")
    bounded_fee_ppm = classified.get("bounded_supported_execution_fee_ppm")
    if bounded_fee_ppm != trade_fee_ppm:
        raise XDEXRouteResolverError(
            "bounded historical execution fee does not match the current verified config fee"
        )

    fee_percent = float(Decimal(trade_fee_ppm) / Decimal(10_000))
    return {
        "status": "verified",
        "semantic": "route_execution_fee_estimate",
        "value": {
            "amm_trade_fee_rate_percent": fee_percent,
            "bounded_historical_execution_model_fee_percent": fee_percent,
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
    execution_fee_observation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return trusted route-and-amount evidence accepted by pre-trade v1.2.

    Only capabilities with an accepted proof basis are emitted. User slippage
    tolerance is deliberately absent because it is not an expected execution-
    slippage observation. Bounded fee evidence is absent unless the accepted
    historical execution-evidence classifier is explicitly satisfied for this
    exact route and current config fee.
    """
    normalized_route = _route(route)
    try:
        normalized_amount = normalize_token_in_amount(token_in_amount)
    except ValueError as exc:
        raise XDEXRouteResolverError("token_in_amount must be a positive finite decimal") from exc
    if normalized_amount is None:
        raise XDEXRouteResolverError("token_in_amount is required for route evidence")

    snapshot = _validated_snapshot(
        collector(normalized_route, normalized_amount),
        normalized_route,
        normalized_amount,
    )

    capabilities: dict[str, Any] = {
        "price_impact": _price_impact_capability(snapshot),
    }
    fee_capability = _bounded_fee_capability(
        normalized_route,
        snapshot["trade_fee_rate_ppm"],
        execution_fee_observation,
    )
    if fee_capability is not None:
        capabilities["fees"] = fee_capability

    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "chain": "x1",
        "route": normalized_route,
        "token_in_amount": normalized_amount,
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
