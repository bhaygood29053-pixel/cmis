"""Read-only exact-route XDEX evidence collection for CMIS.

This provider module verifies one caller-specified direct XDEX route against
current X1 account state and obtains a read-only zero-slippage quote pinned to
the same AMM config. It never selects a route, prepares a transaction, signs,
broadcasts, simulates execution, or moves value.

The returned snapshot is provider evidence only. CMIS decides whether any field
is strong enough to satisfy a public pre-trade capability.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import struct
from typing import Any, Callable

import requests

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.rpc import get_token_account_info
from liquidity_scout.providers.x1.xdex import (
    SWAP_QUOTE_URL,
    XDEXAPIError,
    XDEX_NETWORK_X1_MAINNET,
)
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import X1_PROGRAM


CHAIN = "x1"
SOURCE = "XDEX exact-route read-only collector"
POOL_STATE_LENGTH = 637
FEE_DENOMINATOR = 1_000_000
ROUTE_FIELDS = (
    "token_in_mint",
    "token_out_mint",
    "pool",
    "amm_config",
)


class XDEXExactRouteError(RuntimeError):
    """Raised when exact-route evidence cannot be verified safely."""


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
    unknown = sorted(set(value) - set(ROUTE_FIELDS))
    missing = sorted(set(ROUTE_FIELDS) - set(value))
    if unknown or missing:
        raise ValueError(f"route fields mismatch: missing={missing!r}, unknown={unknown!r}")
    result = {field: _text(value.get(field), f"route.{field}") for field in ROUTE_FIELDS}
    if result["token_in_mint"] == result["token_out_mint"]:
        raise ValueError("route token_in_mint and token_out_mint must differ")
    return result


def _decimal(value: Any, field: str, *, positive: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field} must be a finite decimal")
    if isinstance(value, str) and (not value or value.strip() != value):
        raise ValueError(f"{field} must be a finite decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise ValueError(f"{field} must be a finite decimal") from exc
    if not result.is_finite() or (positive and result <= 0):
        qualifier = "positive finite" if positive else "finite"
        raise ValueError(f"{field} must be a {qualifier} decimal")
    return result


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def _pubkey(data: bytes, offset: int) -> str:
    return encode_base58_pubkey(data[offset : offset + 32])


def _verified_program_account(
    account: Mapping[str, Any],
    *,
    expected_account: str,
    label: str,
) -> bytes:
    if not isinstance(account, Mapping):
        raise XDEXExactRouteError(f"{label} account state is unavailable")
    if account.get("account") != expected_account:
        raise XDEXExactRouteError(f"{label} account identity does not match the requested address")
    if account.get("account_exists") is not True:
        raise XDEXExactRouteError(f"{label} account does not exist")
    if account.get("response_integrity_verified") is not True:
        raise XDEXExactRouteError(f"{label} account response integrity is not verified")
    if account.get("owner") != X1_PROGRAM:
        raise XDEXExactRouteError(f"{label} is not owned by the accepted XDEX X1 program")
    data = account.get("data")
    if not isinstance(data, (bytes, bytearray)):
        raise XDEXExactRouteError(f"{label} account returned no verified binary data")
    return bytes(data)


def _decode_pool_state(account: Mapping[str, Any], *, pool: str) -> dict[str, Any]:
    raw = _verified_program_account(account, expected_account=pool, label="exact pool")
    if len(raw) != POOL_STATE_LENGTH:
        raise XDEXExactRouteError("exact pool state does not match the accepted XDEX layout")
    return {
        "pool": pool,
        "amm_config": _pubkey(raw, 8),
        "vault_0": _pubkey(raw, 72),
        "vault_1": _pubkey(raw, 104),
        "mint_0": _pubkey(raw, 168),
        "mint_1": _pubkey(raw, 200),
        "decimals_0": raw[331],
        "decimals_1": raw[332],
        "protocol_fees_0": _u64(raw, 341),
        "protocol_fees_1": _u64(raw, 349),
        "fund_fees_0": _u64(raw, 357),
        "fund_fees_1": _u64(raw, 365),
        "creator_fees_0": _u64(raw, 397),
        "creator_fees_1": _u64(raw, 405),
    }


def _decode_config_state(account: Mapping[str, Any], *, amm_config: str) -> dict[str, Any]:
    raw = _verified_program_account(
        account,
        expected_account=amm_config,
        label="AMM config",
    )
    if len(raw) < 116:
        raise XDEXExactRouteError("AMM config state does not match the accepted XDEX layout")
    return {
        "amm_config": amm_config,
        "trade_fee_rate_ppm": _u64(raw, 12),
        "protocol_fee_rate_ppm_of_trade_fee": _u64(raw, 20),
        "fund_fee_rate_ppm_of_trade_fee": _u64(raw, 28),
        "creator_fee_rate_ppm": _u64(raw, 108),
    }


def _verified_vault(
    fetcher: Callable[[str], Any],
    vault: str,
    mint: str,
    decimals: int,
) -> tuple[int, str]:
    record = fetcher(vault)
    if not isinstance(record, Mapping):
        raise XDEXExactRouteError("pool vault token-account evidence is unavailable")
    if record.get("account") != vault:
        raise XDEXExactRouteError("pool vault account identity does not match the requested vault")
    if record.get("account_exists") is not True:
        raise XDEXExactRouteError("pool vault token account does not exist")
    if record.get("identity_verified") is not True:
        raise XDEXExactRouteError("pool vault token-account identity is not verified")
    if record.get("mint") != mint:
        raise XDEXExactRouteError("pool vault mint identity does not match decoded pool state")
    if record.get("decimals") != decimals:
        raise XDEXExactRouteError("pool vault decimals do not match decoded pool state")
    authority = record.get("token_authority")
    if not isinstance(authority, str) or not authority or authority.strip() != authority:
        raise XDEXExactRouteError("pool vault token authority is not verified")
    raw = record.get("raw_amount")
    if not isinstance(raw, str) or not raw.isdigit():
        raise XDEXExactRouteError("pool vault raw amount must be a canonical non-negative integer string")
    amount = int(raw)
    if str(amount) != raw:
        raise XDEXExactRouteError("pool vault raw amount must be a canonical non-negative integer string")
    return amount, authority


def _active_reserves(
    pool: Mapping[str, Any],
    token_account_fetcher: Callable[[str], Any],
) -> tuple[int, int]:
    gross_0, authority_0 = _verified_vault(
        token_account_fetcher,
        pool["vault_0"],
        pool["mint_0"],
        pool["decimals_0"],
    )
    gross_1, authority_1 = _verified_vault(
        token_account_fetcher,
        pool["vault_1"],
        pool["mint_1"],
        pool["decimals_1"],
    )
    if authority_0 != authority_1:
        raise XDEXExactRouteError("verified XDEX pool vaults do not share the same token authority")
    reserve_0 = gross_0 - pool["protocol_fees_0"] - pool["fund_fees_0"] - pool["creator_fees_0"]
    reserve_1 = gross_1 - pool["protocol_fees_1"] - pool["fund_fees_1"] - pool["creator_fees_1"]
    if reserve_0 <= 0 or reserve_1 <= 0:
        raise XDEXExactRouteError("verified active reserves must be positive")
    return reserve_0, reserve_1


def _raw_amount(ui_amount: Any, decimals: int) -> int:
    amount = _decimal(ui_amount, "token_in_amount", positive=True)
    scaled = amount * (Decimal(10) ** decimals)
    if scaled != scaled.to_integral_value():
        raise XDEXExactRouteError("token_in_amount is not exactly representable in raw token units")
    raw = int(scaled)
    if raw <= 0:
        raise XDEXExactRouteError("token_in_amount must convert to a positive raw amount")
    return raw


def _ceil_fee(amount: int, rate_ppm: int) -> int:
    if isinstance(rate_ppm, bool) or not isinstance(rate_ppm, int):
        raise XDEXExactRouteError("AMM trade fee rate must be an integer")
    if rate_ppm < 0 or rate_ppm >= FEE_DENOMINATOR:
        raise XDEXExactRouteError("AMM trade fee rate is outside the accepted range")
    if rate_ppm == 0:
        return 0
    return (amount * rate_ppm + FEE_DENOMINATOR - 1) // FEE_DENOMINATOR


def _price_impact_percent(raw_input: int, reserve_in: int, trade_fee_rate_ppm: int) -> Decimal:
    fee = _ceil_fee(raw_input, trade_fee_rate_ppm)
    net_input = raw_input - fee
    if net_input <= 0:
        raise XDEXExactRouteError("trade fee consumes the complete raw input")
    return Decimal(net_input) * Decimal(100) / Decimal(reserve_in + net_input)


def _bounded_response_text(response: Any, limit: int = 500) -> str:
    text = str(getattr(response, "text", "") or "").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def fetch_explicit_config_quote(
    token_in: str,
    token_out: str,
    token_in_amount: Any,
    amm_config: str,
    *,
    network: str = XDEX_NETWORK_X1_MAINNET,
    session=requests,
    timeout: int = 15,
) -> dict[str, Any]:
    """Fetch a read-only exact-in quote pinned to one AMM config at slippage=0."""
    token_in = _text(token_in, "token_in")
    token_out = _text(token_out, "token_out")
    amm_config = _text(amm_config, "amm_config")
    network = _text(network, "network")
    if token_in == token_out:
        raise ValueError("token_in and token_out must differ")
    amount = _decimal(token_in_amount, "token_in_amount", positive=True)
    params = {
        "network": network,
        "token_in": token_in,
        "token_out": token_out,
        "token_in_amount": format(amount, "f"),
        "is_exact_amount_in": "true",
        "slippage": "0",
        "amm_config_address": amm_config,
    }
    response = None
    try:
        response = session.get(SWAP_QUOTE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        detail = _bounded_response_text(response)
        suffix = f" | response: {detail}" if detail else ""
        raise XDEXAPIError(f"XDEX exact-config quote request failed: {exc}{suffix}") from exc
    if not isinstance(body, Mapping) or body.get("success") is not True:
        raise XDEXAPIError("XDEX exact-config quote did not return success=true")
    data = body.get("data")
    if not isinstance(data, Mapping):
        raise XDEXAPIError("XDEX exact-config quote data must be a JSON object")
    return dict(data)


def collect_exact_route_snapshot(
    route: Mapping[str, Any],
    token_in_amount: Any,
    *,
    account_state_fetcher: Callable[[str], Any] = fetch_account_state,
    token_account_fetcher: Callable[[str], Any] = get_token_account_info,
    quote_fetcher: Callable[..., Mapping[str, Any]] = fetch_explicit_config_quote,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Collect a fully verified direct-route snapshot without preparing execution."""
    normalized = _route(route)
    pool_account = account_state_fetcher(normalized["pool"])
    pool = _decode_pool_state(pool_account, pool=normalized["pool"])
    if pool["amm_config"] != normalized["amm_config"]:
        raise XDEXExactRouteError("decoded pool AMM config does not match the requested route")
    if {pool["mint_0"], pool["mint_1"]} != {
        normalized["token_in_mint"],
        normalized["token_out_mint"],
    }:
        raise XDEXExactRouteError("decoded pool mint pair does not match the requested route")

    config_account = account_state_fetcher(normalized["amm_config"])
    config = _decode_config_state(config_account, amm_config=normalized["amm_config"])

    reserve_0, reserve_1 = _active_reserves(pool, token_account_fetcher)
    if normalized["token_in_mint"] == pool["mint_0"]:
        reserve_in, reserve_out = reserve_0, reserve_1
        decimals_in, decimals_out = pool["decimals_0"], pool["decimals_1"]
    else:
        reserve_in, reserve_out = reserve_1, reserve_0
        decimals_in, decimals_out = pool["decimals_1"], pool["decimals_0"]

    raw_input = _raw_amount(token_in_amount, decimals_in)
    reconstructed_price_impact = _price_impact_percent(
        raw_input,
        reserve_in,
        config["trade_fee_rate_ppm"],
    )

    quote = quote_fetcher(
        normalized["token_in_mint"],
        normalized["token_out_mint"],
        token_in_amount,
        normalized["amm_config"],
    )
    if not isinstance(quote, Mapping):
        raise XDEXExactRouteError("exact-config quote payload is unavailable")
    if quote.get("inputMint") != normalized["token_in_mint"]:
        raise XDEXExactRouteError("quote inputMint does not match the requested route")
    if quote.get("outputMint") != normalized["token_out_mint"]:
        raise XDEXExactRouteError("quote outputMint does not match the requested route")
    if quote.get("amm_config_address") != normalized["amm_config"]:
        raise XDEXExactRouteError("quote AMM config does not match the requested route")

    quote_price_impact = _decimal(quote.get("priceImpactPct"), "quote.priceImpactPct")
    if quote_price_impact < 0:
        raise XDEXExactRouteError("quote priceImpactPct must be non-negative")

    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise XDEXExactRouteError("collector clock must return a timezone-aware datetime")
    observed_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "schema": "xdex_exact_route_snapshot.v1",
        "source": SOURCE,
        "chain": CHAIN,
        "program": X1_PROGRAM,
        "route": normalized,
        "observed_at": observed_at,
        "token_in_amount": format(_decimal(token_in_amount, "token_in_amount", positive=True), "f"),
        "raw_input_amount": raw_input,
        "input_decimals": decimals_in,
        "output_decimals": decimals_out,
        "active_reserve_in_raw": reserve_in,
        "active_reserve_out_raw": reserve_out,
        "trade_fee_rate_ppm": config["trade_fee_rate_ppm"],
        "protocol_fee_rate_ppm_of_trade_fee": config["protocol_fee_rate_ppm_of_trade_fee"],
        "fund_fee_rate_ppm_of_trade_fee": config["fund_fee_rate_ppm_of_trade_fee"],
        "creator_fee_rate_ppm": config["creator_fee_rate_ppm"],
        "reconstructed_price_impact_percent": format(reconstructed_price_impact, "f"),
        "quote_price_impact_percent": format(quote_price_impact, "f"),
        "quote_output_amount": quote.get("outputAmount"),
        "quote_rate": quote.get("rate"),
        "quote_slippage_percent": 0,
        "quote_identity_verified": True,
        "pool_state_verified": True,
        "vault_identity_verified": True,
        "active_reserves_verified": True,
        "amm_config_verified": True,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CHAIN",
    "SOURCE",
    "XDEXExactRouteError",
    "collect_exact_route_snapshot",
    "fetch_explicit_config_quote",
]
