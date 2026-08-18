"""Internal read-only XDEX exact-route evidence resolver for CMIS pre-trade.

The resolver starts from an already explicit route. It does not select a pool,
discover a route, prepare a swap, or accept an HTTP request payload as proof.
It re-reads the exact X1 program accounts and vaults, obtains an exact-in
zero-slippage quote scoped to the requested AMM config, independently
reconstructs the accepted direct-CP price-impact semantic, and emits only the
internal ``cmis_xdex_route_resolver`` evidence envelope accepted by the
pre-trade route-evidence contract.

Expected execution slippage, route quality, fill quality, simulation, global
execution semantics, and transaction authority remain outside this module.
"""

from __future__ import annotations

import struct
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.rpc import get_token_account_info
from liquidity_scout.providers.x1.xdex import fetch_swap_quote
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import (
    classify_xdex_execution_fee_sequence_evidence,
)


SOURCE = "cmis_xdex_route_resolver"
SCHEMA_VERSION = 1
XDEX_X1_MAINNET_PROGRAM = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
POOL_STATE_SIZE = 637
CONFIG_MIN_SIZE = 116
FEE_DENOMINATOR = 1_000_000
PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS = Decimal("0.002")

_ROUTE_FIELDS = frozenset({"token_in_mint", "token_out_mint", "pool", "amm_config"})


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a normalized non-empty string")
    text = value.strip()
    if not text or text != value:
        raise ValueError(f"{field} must be a normalized non-empty string")
    return text


def _route(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("route must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise ValueError("route keys must be strings")
    unknown = sorted(set(value) - set(_ROUTE_FIELDS))
    missing = sorted(set(_ROUTE_FIELDS) - set(value))
    if unknown or missing:
        raise ValueError(f"route fields mismatch: missing={missing!r}, unknown={unknown!r}")
    result = {field: _text(value.get(field), f"route.{field}") for field in _ROUTE_FIELDS}
    if result["token_in_mint"] == result["token_out_mint"]:
        raise ValueError("route token_in_mint and token_out_mint must differ")
    return result


def _decimal(value: Any, field: str, *, nonnegative: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field} must be a finite decimal")
    if isinstance(value, str) and (not value or value.strip() != value):
        raise ValueError(f"{field} must be a finite decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a finite decimal") from exc
    if not result.is_finite() or (result < 0 if nonnegative else result <= 0):
        qualifier = "non-negative" if nonnegative else "positive"
        raise ValueError(f"{field} must be a finite {qualifier} decimal")
    return result


def _u64(data: bytes, offset: int, field: str) -> int:
    if offset < 0 or offset + 8 > len(data):
        raise ValueError(f"{field} offset is outside account data")
    return struct.unpack_from("<Q", data, offset)[0]


def _pubkey(data: bytes, offset: int, field: str) -> str:
    if offset < 0 or offset + 32 > len(data):
        raise ValueError(f"{field} offset is outside account data")
    return encode_base58_pubkey(data[offset : offset + 32])


def _verified_account_state(
    fetcher: Callable[..., Mapping[str, Any]],
    account: str,
    *,
    expected_size: int | None,
    minimum_size: int | None = None,
) -> bytes:
    state = fetcher(account)
    if not isinstance(state, Mapping):
        raise ValueError(f"account {account} returned no usable state")
    if state.get("account") != account:
        raise ValueError(f"account identity mismatch for {account}")
    if state.get("account_exists") is not True:
        raise ValueError(f"account {account} does not exist")
    if state.get("response_integrity_verified") is not True:
        raise ValueError(f"account integrity is not verified for {account}")
    if state.get("owner") != XDEX_X1_MAINNET_PROGRAM:
        raise ValueError(f"account {account} is not owned by the accepted XDEX program")
    data = state.get("data")
    if not isinstance(data, bytes):
        raise ValueError(f"account {account} returned no verified binary data")
    if expected_size is not None and len(data) != expected_size:
        raise ValueError(f"account {account} data length must be {expected_size}")
    if minimum_size is not None and len(data) < minimum_size:
        raise ValueError(f"account {account} data length must be at least {minimum_size}")
    return data


def _decode_pool(data: bytes) -> dict[str, Any]:
    if len(data) != POOL_STATE_SIZE:
        raise ValueError("XDEX pool state must use the accepted 637-byte layout")
    return {
        "amm_config": _pubkey(data, 8, "amm_config"),
        "vault_0": _pubkey(data, 72, "vault_0"),
        "vault_1": _pubkey(data, 104, "vault_1"),
        "mint_0": _pubkey(data, 168, "mint_0"),
        "mint_1": _pubkey(data, 200, "mint_1"),
        "decimals_0": data[331],
        "decimals_1": data[332],
        "protocol_fees_0": _u64(data, 341, "protocol_fees_0"),
        "protocol_fees_1": _u64(data, 349, "protocol_fees_1"),
        "fund_fees_0": _u64(data, 357, "fund_fees_0"),
        "fund_fees_1": _u64(data, 365, "fund_fees_1"),
        "creator_fees_0": _u64(data, 397, "creator_fees_0"),
        "creator_fees_1": _u64(data, 405, "creator_fees_1"),
    }


def _decode_config(data: bytes) -> dict[str, int]:
    if len(data) < CONFIG_MIN_SIZE:
        raise ValueError("XDEX AMM config state is shorter than the accepted layout")
    result = {
        "trade_fee_rate": _u64(data, 12, "trade_fee_rate"),
        "protocol_fee_rate": _u64(data, 20, "protocol_fee_rate"),
        "fund_fee_rate": _u64(data, 28, "fund_fee_rate"),
        "creator_fee_rate": _u64(data, 108, "creator_fee_rate"),
    }
    if result["trade_fee_rate"] >= FEE_DENOMINATOR:
        raise ValueError("XDEX trade fee rate is outside the accepted ppm domain")
    return result


def _token_account(
    fetcher: Callable[..., Mapping[str, Any]],
    account: str,
    *,
    expected_mint: str,
    expected_decimals: int,
) -> tuple[int, str]:
    record = fetcher(account)
    if not isinstance(record, Mapping):
        raise ValueError(f"vault {account} returned no usable token-account record")
    if record.get("account") != account:
        raise ValueError(f"vault account identity mismatch for {account}")
    if record.get("account_exists") is not True or record.get("identity_verified") is not True:
        raise ValueError(f"vault identity is not verified for {account}")
    if record.get("mint") != expected_mint:
        raise ValueError(f"vault mint identity mismatch for {account}")
    if record.get("decimals") != expected_decimals:
        raise ValueError(f"vault decimals mismatch for {account}")
    authority = _text(record.get("token_authority"), f"vault {account} token_authority")
    raw = record.get("raw_amount")
    if not isinstance(raw, str) or not raw.isdigit() or str(int(raw)) != raw:
        raise ValueError(f"vault raw amount must be a canonical non-negative integer string for {account}")
    return int(raw), authority


def _raw_input_amount(amount: Decimal, decimals: int) -> int:
    scaled = amount * (Decimal(10) ** decimals)
    if scaled != scaled.to_integral_value():
        raise ValueError("token_in_amount is not exactly representable in route token decimals")
    raw = int(scaled)
    if raw <= 0:
        raise ValueError("token_in_amount must resolve to a positive raw amount")
    return raw


def _ceil_fee(raw_amount: int, fee_rate_ppm: int) -> int:
    return (
        (raw_amount * fee_rate_ppm + FEE_DENOMINATOR - 1) // FEE_DENOMINATOR
        if fee_rate_ppm
        else 0
    )


def _price_impact(raw_input: int, reserve_in: int, fee_rate_ppm: int) -> Decimal:
    fee = _ceil_fee(raw_input, fee_rate_ppm)
    net = raw_input - fee
    if net <= 0:
        raise ValueError("verified trade fee consumes the entire raw input")
    return Decimal(net) / Decimal(reserve_in + net) * Decimal(100)


def _canonical_observed_at(value: Any) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, bool):
        raise ValueError("observation clock returned an invalid value")
    elif isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(float(value), tz=timezone.utc)
    else:
        raise ValueError("observation clock must return datetime or epoch seconds")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observation clock must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _maybe_fee_capability(
    execution_fee_observation: Any,
    *,
    route: Mapping[str, str],
    current_trade_fee_ppm: int,
) -> dict[str, Any] | None:
    if execution_fee_observation is None:
        return None
    if not isinstance(execution_fee_observation, Mapping):
        raise ValueError("execution_fee_observation must be a mapping when supplied")

    result = classify_xdex_execution_fee_sequence_evidence(execution_fee_observation)
    if result.get("status") != "STRONGLY_CORROBORATED":
        raise ValueError("execution fee evidence is not strongly corroborated")
    if result.get("bounded_execution_model_supported") is not True:
        raise ValueError("execution fee evidence does not support a bounded execution model")
    if result.get("program") != XDEX_X1_MAINNET_PROGRAM:
        raise ValueError("execution fee evidence program does not match the resolved route")
    if result.get("pool") != route["pool"] or result.get("amm_config") != route["amm_config"]:
        raise ValueError("execution fee evidence pool/config does not match the resolved route")
    if {result.get("asset_a_mint"), result.get("asset_b_mint")} != {
        route["token_in_mint"],
        route["token_out_mint"],
    }:
        raise ValueError("execution fee evidence asset pair does not match the resolved route")

    bounded_fee_ppm = result.get("bounded_supported_execution_fee_ppm")
    if bounded_fee_ppm != current_trade_fee_ppm:
        raise ValueError("historical bounded execution fee does not match current verified config fee")

    fee_percent = float(Decimal(current_trade_fee_ppm) / Decimal(10000))
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


def resolve_xdex_exact_route_evidence(
    *,
    route: Mapping[str, Any],
    token_in_amount: Any,
    pool_state_fetcher: Callable[..., Mapping[str, Any]] = fetch_account_state,
    token_account_fetcher: Callable[..., Mapping[str, Any]] = get_token_account_info,
    quote_fetcher: Callable[..., Mapping[str, Any]] = fetch_swap_quote,
    now_fn: Callable[[], Any] = lambda: datetime.now(timezone.utc),
    execution_fee_observation: Mapping[str, Any] | None = None,
    price_impact_tolerance_percentage_points: Any = PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS,
) -> dict[str, Any]:
    """Resolve one explicit X1/XDEX exact-in route into internal pre-trade evidence."""

    resolved_route = _route(route)
    amount = _decimal(token_in_amount, "token_in_amount")
    tolerance = _decimal(
        price_impact_tolerance_percentage_points,
        "price_impact_tolerance_percentage_points",
        nonnegative=True,
    )

    pool_data = _verified_account_state(
        pool_state_fetcher,
        resolved_route["pool"],
        expected_size=POOL_STATE_SIZE,
    )
    pool = _decode_pool(pool_data)
    if pool["amm_config"] != resolved_route["amm_config"]:
        raise ValueError("resolved pool AMM config does not match the explicit route")
    if {pool["mint_0"], pool["mint_1"]} != {
        resolved_route["token_in_mint"],
        resolved_route["token_out_mint"],
    }:
        raise ValueError("resolved pool mint pair does not match the explicit route")

    config_data = _verified_account_state(
        pool_state_fetcher,
        resolved_route["amm_config"],
        expected_size=None,
        minimum_size=CONFIG_MIN_SIZE,
    )
    config = _decode_config(config_data)

    vault0_raw, authority0 = _token_account(
        token_account_fetcher,
        pool["vault_0"],
        expected_mint=pool["mint_0"],
        expected_decimals=pool["decimals_0"],
    )
    vault1_raw, authority1 = _token_account(
        token_account_fetcher,
        pool["vault_1"],
        expected_mint=pool["mint_1"],
        expected_decimals=pool["decimals_1"],
    )
    if authority0 != authority1:
        raise ValueError("resolved XDEX vaults do not share the same verified token authority")

    active0 = (
        vault0_raw
        - pool["protocol_fees_0"]
        - pool["fund_fees_0"]
        - pool["creator_fees_0"]
    )
    active1 = (
        vault1_raw
        - pool["protocol_fees_1"]
        - pool["fund_fees_1"]
        - pool["creator_fees_1"]
    )
    if active0 <= 0 or active1 <= 0:
        raise ValueError("resolved XDEX active reserves must both be positive")

    by_mint = {
        pool["mint_0"]: (active0, pool["decimals_0"]),
        pool["mint_1"]: (active1, pool["decimals_1"]),
    }
    reserve_in, decimals_in = by_mint[resolved_route["token_in_mint"]]
    raw_input = _raw_input_amount(amount, decimals_in)
    independent_impact = _price_impact(raw_input, reserve_in, config["trade_fee_rate"])

    amount_text = format(amount, "f")
    quote = quote_fetcher(
        resolved_route["token_in_mint"],
        resolved_route["token_out_mint"],
        amount_text,
        is_exact_amount_in=True,
        slippage=Decimal("0"),
        amm_config_address=resolved_route["amm_config"],
    )
    if not isinstance(quote, Mapping):
        raise ValueError("XDEX quote returned no usable mapping")
    if quote.get("inputMint") != resolved_route["token_in_mint"]:
        raise ValueError("XDEX quote inputMint does not match the explicit route")
    if quote.get("outputMint") != resolved_route["token_out_mint"]:
        raise ValueError("XDEX quote outputMint does not match the explicit route")
    if quote.get("amm_config_address") != resolved_route["amm_config"]:
        raise ValueError("XDEX quote AMM config does not match the explicit route")

    provider_impact = _decimal(
        quote.get("priceImpactPct"),
        "XDEX quote priceImpactPct",
        nonnegative=True,
    )
    impact_delta = abs(provider_impact - independent_impact)
    if impact_delta > tolerance:
        raise ValueError(
            "XDEX quote priceImpactPct exceeds the accepted independent reconstruction tolerance"
        )

    capabilities: dict[str, Any] = {
        "price_impact": {
            "status": "verified",
            "semantic": "route_price_impact_percent",
            "value": float(provider_impact),
            "unit": "percent",
            "proof_basis": [
                "verified_direct_cp_route",
                "verified_pool_reserves",
                "verified_price_impact_semantics",
            ],
        }
    }
    fee_capability = _maybe_fee_capability(
        execution_fee_observation,
        route=resolved_route,
        current_trade_fee_ppm=config["trade_fee_rate"],
    )
    if fee_capability is not None:
        capabilities["fees"] = fee_capability

    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "chain": "x1",
        "route": dict(resolved_route),
        "observed_at": _canonical_observed_at(now_fn()),
        "capabilities": capabilities,
    }


__all__ = [
    "CONFIG_MIN_SIZE",
    "FEE_DENOMINATOR",
    "POOL_STATE_SIZE",
    "PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS",
    "SCHEMA_VERSION",
    "SOURCE",
    "XDEX_X1_MAINNET_PROGRAM",
    "resolve_xdex_exact_route_evidence",
]
