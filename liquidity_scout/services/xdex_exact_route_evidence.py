"""Internal read-only XDEX exact-route evidence producer for CMIS pre-trade analysis.

The resolver binds one caller-internal exact route to current X1/XDEX state. It
re-reads the named pool, AMM config, and vault token accounts; obtains a forced-
config zero-slippage quote; and independently reconstructs only the already-
evidenced direct constant-product ``priceImpactPct`` semantic.

It never selects a route, never accepts free-form caller evidence, never calls a
swap preparation endpoint, and never prepares/signs/broadcasts a transaction.
Fees and expected execution slippage remain unavailable in this first producer
because their stronger proof bases are not established by a current quote.
"""

from __future__ import annotations

import math
import struct
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import requests

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.program_accounts import RECOGNIZED_AMM_PROGRAM_IDS
from liquidity_scout.providers.x1.rpc import get_token_account_info
from liquidity_scout.providers.x1.xdex import SWAP_QUOTE_URL, XDEX_NETWORK_X1_MAINNET

VERSION = "1.0"
ROUTE_EVIDENCE_SCHEMA_VERSION = 1
SOURCE = "cmis_xdex_route_resolver"
CHAIN = "x1"
POOL_STATE_SIZE = 637
FEE_DENOMINATOR = 1_000_000
PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS = Decimal("0.002")

_POOL_OFFSETS = {
    "amm_config": 8,
    "vault_0": 72,
    "vault_1": 104,
    "mint_0": 168,
    "mint_1": 200,
}
_DECIMAL_OFFSETS = {"decimals_0": 331, "decimals_1": 332}
_FEE_COUNTER_OFFSETS = {
    "protocol_fees_0": 341,
    "protocol_fees_1": 349,
    "fund_fees_0": 357,
    "fund_fees_1": 365,
    "creator_fees_0": 397,
    "creator_fees_1": 405,
}


class XDEXExactRouteEvidenceError(RuntimeError):
    """Raised only for invalid caller-internal route/amount inputs."""


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise XDEXExactRouteEvidenceError(f"{name} must be a string")
    text = value.strip()
    if not text or text != value:
        raise XDEXExactRouteEvidenceError(f"{name} must be a normalized non-empty string")
    return text


def _decimal(name: str, value: Any, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise XDEXExactRouteEvidenceError(f"{name} must be numeric")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise XDEXExactRouteEvidenceError(f"{name} must be numeric") from None
    if not number.is_finite() or (positive and number <= 0):
        qualifier = "positive finite" if positive else "finite"
        raise XDEXExactRouteEvidenceError(f"{name} must be {qualifier}")
    return number


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def _pubkey(data: bytes, offset: int) -> str:
    return encode_base58_pubkey(data[offset : offset + 32])


def _parse_pool_state(raw: Any, *, route: Mapping[str, str]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("pool_state_unavailable")
    if raw.get("response_integrity_verified") is not True:
        raise ValueError("pool_state_integrity_unverified")
    owner = raw.get("owner")
    data = raw.get("data")
    if owner not in RECOGNIZED_AMM_PROGRAM_IDS:
        raise ValueError("pool_program_owner_unrecognized")
    if not isinstance(data, (bytes, bytearray)) or len(data) != POOL_STATE_SIZE:
        raise ValueError("pool_state_layout_unverified")
    data = bytes(data)

    decoded = {name: _pubkey(data, offset) for name, offset in _POOL_OFFSETS.items()}
    decoded.update({name: data[offset] for name, offset in _DECIMAL_OFFSETS.items()})
    decoded.update({name: _u64(data, offset) for name, offset in _FEE_COUNTER_OFFSETS.items()})
    decoded["program_id"] = owner

    if decoded["amm_config"] != route["amm_config"]:
        raise ValueError("pool_amm_config_mismatch")
    if decoded["mint_0"] == decoded["mint_1"]:
        raise ValueError("pool_mint_identity_ambiguous")
    if {decoded["mint_0"], decoded["mint_1"]} != {
        route["token_in_mint"],
        route["token_out_mint"],
    }:
        raise ValueError("pool_route_mint_pair_mismatch")
    if decoded["vault_0"] == decoded["vault_1"]:
        raise ValueError("pool_vault_identity_ambiguous")
    return decoded


def _parse_config_state(raw: Any, *, expected_program_id: str, expected_config: str) -> dict[str, int]:
    if not isinstance(raw, Mapping):
        raise ValueError("amm_config_state_unavailable")
    if raw.get("response_integrity_verified") is not True:
        raise ValueError("amm_config_integrity_unverified")
    if raw.get("owner") != expected_program_id:
        raise ValueError("amm_config_program_owner_mismatch")
    data = raw.get("data")
    if not isinstance(data, (bytes, bytearray)) or len(data) < 36:
        raise ValueError("amm_config_layout_unverified")
    data = bytes(data)
    trade_fee_rate = _u64(data, 12)
    if not (0 <= trade_fee_rate < FEE_DENOMINATOR):
        raise ValueError("amm_config_trade_fee_rate_invalid")
    return {"trade_fee_rate": trade_fee_rate}


def _verified_active_reserves(
    pool: Mapping[str, Any],
    *,
    token_account_fetcher: Callable[[str], Any],
) -> dict[str, dict[str, int]]:
    observations = []
    for index in (0, 1):
        account = pool[f"vault_{index}"]
        record = token_account_fetcher(account)
        if not isinstance(record, Mapping) or record.get("identity_verified") is not True:
            raise ValueError("pool_vault_identity_unverified")
        if record.get("account") not in {None, account}:
            raise ValueError("pool_vault_account_mismatch")
        if record.get("mint") != pool[f"mint_{index}"]:
            raise ValueError("pool_vault_mint_mismatch")
        authority = record.get("token_authority")
        if not isinstance(authority, str) or not authority:
            raise ValueError("pool_vault_authority_unverified")
        raw_amount = record.get("raw_amount")
        if not isinstance(raw_amount, str) or not raw_amount.isdigit():
            raise ValueError("pool_vault_amount_unverified")
        decimals = record.get("decimals")
        if isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0:
            raise ValueError("pool_vault_decimals_unverified")
        if decimals != pool[f"decimals_{index}"]:
            raise ValueError("pool_vault_decimals_mismatch")
        observations.append((authority, int(raw_amount), decimals))

    if observations[0][0] != observations[1][0]:
        raise ValueError("pool_vault_shared_authority_unverified")

    result: dict[str, dict[str, int]] = {}
    for index, (_, gross_amount, decimals) in enumerate(observations):
        accrued = (
            pool[f"protocol_fees_{index}"]
            + pool[f"fund_fees_{index}"]
            + pool[f"creator_fees_{index}"]
        )
        active = gross_amount - accrued
        if active <= 0:
            raise ValueError("pool_active_reserve_nonpositive")
        result[pool[f"mint_{index}"]] = {
            "raw_amount": active,
            "decimals": decimals,
        }
    return result


def _raw_input(amount: Decimal, decimals: int) -> int:
    scaled = amount * (Decimal(10) ** decimals)
    if scaled != scaled.to_integral_value():
        raise XDEXExactRouteEvidenceError(
            "token_in_amount is not exactly representable in token base units"
        )
    raw = int(scaled)
    if raw <= 0:
        raise XDEXExactRouteEvidenceError("token_in_amount must resolve to positive base units")
    return raw


def _ceil_fee(amount: int, rate: int) -> int:
    return (amount * rate + FEE_DENOMINATOR - 1) // FEE_DENOMINATOR if rate else 0


def _direct_cp_price_impact_percent(raw_input: int, reserve_in: int, trade_fee_rate: int) -> Decimal:
    trade_fee = _ceil_fee(raw_input, trade_fee_rate)
    less_fees = raw_input - trade_fee
    if less_fees <= 0 or reserve_in <= 0:
        raise ValueError("direct_cp_inputs_invalid")
    return Decimal(less_fees) / Decimal(reserve_in + less_fees) * Decimal(100)


def _default_quote_fetcher(
    token_in: str,
    token_out: str,
    amount: Decimal,
    amm_config: str,
) -> dict[str, Any]:
    response = requests.get(
        SWAP_QUOTE_URL,
        params={
            "network": XDEX_NETWORK_X1_MAINNET,
            "token_in": token_in,
            "token_out": token_out,
            "token_in_amount": format(amount, "f"),
            "is_exact_amount_in": "true",
            "slippage": "0",
            "amm_config_address": amm_config,
        },
        timeout=15,
        headers={"User-Agent": "CMIS-XDEX-readonly-route-evidence/1.0"},
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, Mapping) or body.get("success") is not True:
        raise ValueError("xdex_quote_unsuccessful")
    data = body.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("xdex_quote_data_unavailable")
    return dict(data)


def _empty_evidence(route: Mapping[str, str], observed_at: str) -> dict[str, Any]:
    return {
        "schema_version": ROUTE_EVIDENCE_SCHEMA_VERSION,
        "source": SOURCE,
        "chain": CHAIN,
        "route": dict(route),
        "observed_at": observed_at,
        "capabilities": {},
    }


def resolve_xdex_exact_route_evidence_with_audit(
    *,
    route: Mapping[str, Any],
    token_in_amount: Any,
    pool_state_fetcher: Callable[[str], Any] = fetch_account_state,
    config_state_fetcher: Callable[[str], Any] = fetch_account_state,
    token_account_fetcher: Callable[[str], Any] = get_token_account_info,
    quote_fetcher: Callable[[str, str, Decimal, str], Any] = _default_quote_fetcher,
    clock: Callable[[], datetime] | None = None,
    price_impact_tolerance_percentage_points: Any = PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS,
) -> dict[str, Any]:
    """Resolve one explicit exact-in route into fail-closed CMIS route evidence."""
    if not isinstance(route, Mapping):
        raise XDEXExactRouteEvidenceError("route must be a mapping")
    allowed = {"token_in_mint", "token_out_mint", "pool", "amm_config"}
    if set(route) != allowed:
        raise XDEXExactRouteEvidenceError("route must contain exactly token_in_mint, token_out_mint, pool, and amm_config")
    normalized = {name: _text(name, route.get(name)) for name in allowed}
    if normalized["token_in_mint"] == normalized["token_out_mint"]:
        raise XDEXExactRouteEvidenceError("route token mints must be different")

    amount = _decimal("token_in_amount", token_in_amount, positive=True)
    tolerance = _decimal(
        "price_impact_tolerance_percentage_points",
        price_impact_tolerance_percentage_points,
    )
    if tolerance < 0:
        raise XDEXExactRouteEvidenceError("price impact tolerance must be non-negative")

    now = clock() if clock is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise XDEXExactRouteEvidenceError("clock must return a timezone-aware datetime")
    observed_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    evidence = _empty_evidence(normalized, observed_at)
    audit: dict[str, Any] = {
        "version": VERSION,
        "chain": CHAIN,
        "route": dict(normalized),
        "exact_in": True,
        "zero_slippage_quote_requested": False,
        "pool_identity_verified": False,
        "amm_config_identity_verified": False,
        "vault_identity_verified": False,
        "active_reserves_verified": False,
        "quote_identity_verified": False,
        "direct_cp_price_impact_reconstructed": False,
        "price_impact_semantics_verified": False,
        "price_impact_delta_percentage_points": None,
        "fees_verified": False,
        "expected_execution_slippage_verified": False,
        "failure_reason": None,
    }

    try:
        pool = _parse_pool_state(pool_state_fetcher(normalized["pool"]), route=normalized)
        audit["pool_identity_verified"] = True

        config = _parse_config_state(
            config_state_fetcher(normalized["amm_config"]),
            expected_program_id=pool["program_id"],
            expected_config=normalized["amm_config"],
        )
        audit["amm_config_identity_verified"] = True

        reserves = _verified_active_reserves(pool, token_account_fetcher=token_account_fetcher)
        audit["vault_identity_verified"] = True
        audit["active_reserves_verified"] = True

        input_leg = reserves.get(normalized["token_in_mint"])
        output_leg = reserves.get(normalized["token_out_mint"])
        if input_leg is None or output_leg is None:
            raise ValueError("route_reserve_leg_unavailable")
        raw_input = _raw_input(amount, input_leg["decimals"])
        computed_impact = _direct_cp_price_impact_percent(
            raw_input,
            input_leg["raw_amount"],
            config["trade_fee_rate"],
        )
        audit["direct_cp_price_impact_reconstructed"] = True

        audit["zero_slippage_quote_requested"] = True
        quote = quote_fetcher(
            normalized["token_in_mint"],
            normalized["token_out_mint"],
            amount,
            normalized["amm_config"],
        )
        if not isinstance(quote, Mapping):
            raise ValueError("xdex_quote_unavailable")
        if quote.get("inputMint") != normalized["token_in_mint"]:
            raise ValueError("xdex_quote_input_mint_mismatch")
        if quote.get("outputMint") != normalized["token_out_mint"]:
            raise ValueError("xdex_quote_output_mint_mismatch")
        if quote.get("amm_config_address") != normalized["amm_config"]:
            raise ValueError("xdex_quote_amm_config_mismatch")
        audit["quote_identity_verified"] = True

        provider_impact = _decimal("priceImpactPct", quote.get("priceImpactPct"))
        if provider_impact < 0:
            raise ValueError("xdex_quote_price_impact_invalid")
        delta = abs(provider_impact - computed_impact)
        audit["price_impact_delta_percentage_points"] = format(delta, "f")
        if delta > tolerance:
            raise ValueError("xdex_quote_price_impact_not_independently_reproduced")

        audit["price_impact_semantics_verified"] = True
        evidence["capabilities"]["price_impact"] = {
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
    except XDEXExactRouteEvidenceError:
        raise
    except Exception as exc:
        reason = str(exc).strip()
        # Only deterministic internal classifications are retained. Provider or
        # transport exception details are intentionally not surfaced.
        known_prefixes = (
            "pool_", "amm_config_", "route_", "xdex_", "direct_cp_"
        )
        audit["failure_reason"] = (
            reason if reason.startswith(known_prefixes) else "read_only_route_evidence_collection_failed"
        )

    return {"route_evidence": evidence, "audit": audit}


def resolve_xdex_exact_route_evidence(**kwargs: Any) -> dict[str, Any]:
    """Return only the accepted pre-trade route-evidence envelope."""
    return resolve_xdex_exact_route_evidence_with_audit(**kwargs)["route_evidence"]


__all__ = [
    "CHAIN",
    "PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS",
    "SOURCE",
    "VERSION",
    "XDEXExactRouteEvidenceError",
    "resolve_xdex_exact_route_evidence",
    "resolve_xdex_exact_route_evidence_with_audit",
]
