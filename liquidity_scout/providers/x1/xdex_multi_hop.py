"""Read-only XDEX multi-hop quote discovery and deterministic response parsing.

The transport calls only the public quote endpoint. The parser verifies the
observed provider schema and arithmetic identities without promoting provider
labels into independent CMIS facts. It never calls prepare, constructs, signs,
broadcasts, simulates execution, or moves value.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

import requests

from liquidity_scout.providers.x1.xdex import (
    XDEX_API_BASE_URL,
    XDEX_NETWORK_X1_MAINNET,
)

CHAIN = "x1"
SOURCE = "XDEX multi-hop public quote API"
MULTI_HOP_QUOTE_URL = f"{XDEX_API_BASE_URL}/api/xdex/swap/multi-hop/quote"
OBSERVATION_SCHEMA = "xdex_multi_hop_quote_observation.v1"
PARSED_SCHEMA = "xdex_multi_hop_quote_parsed.v1"
DEFAULT_VENUE = "all"
DEFAULT_MAX_HOPS = 6
FEE_DENOMINATOR_PPM = 1_000_000
BPS_DENOMINATOR = 10_000


class XDEXMultiHopError(RuntimeError):
    """Raised when a multi-hop quote observation cannot be collected or parsed safely."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a normalized non-empty string")
    text = value.strip()
    if not text or text != value:
        raise ValueError(f"{field} must be a normalized non-empty string")
    return text


def _amount_text(value: Any) -> str:
    if value is None or isinstance(value, bool):
        raise ValueError("token_in_amount must be a positive finite decimal")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise ValueError("token_in_amount must be a positive finite decimal") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("token_in_amount must be a positive finite decimal")
    return format(amount, "f")


def _decimal(value: Any, field: str, *, nonnegative: bool = True) -> Decimal:
    if value is None or isinstance(value, bool):
        raise XDEXMultiHopError(f"{field} must be a finite decimal")
    if isinstance(value, str) and (not value or value.strip() != value):
        raise XDEXMultiHopError(f"{field} must be a finite decimal")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise XDEXMultiHopError(f"{field} must be a finite decimal") from exc
    if not parsed.is_finite() or (nonnegative and parsed < 0):
        raise XDEXMultiHopError(f"{field} must be a finite non-negative decimal")
    return parsed


def _canonical_uint(value: Any, field: str) -> int:
    if not isinstance(value, str) or not value.isdigit():
        raise XDEXMultiHopError(f"{field} must be a canonical non-negative integer string")
    parsed = int(value)
    if str(parsed) != value:
        raise XDEXMultiHopError(f"{field} must be a canonical non-negative integer string")
    return parsed


def _bounded_int(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise XDEXMultiHopError(f"{field} must be an integer from {minimum} through {maximum}")
    if value < minimum or value > maximum:
        raise XDEXMultiHopError(f"{field} must be an integer from {minimum} through {maximum}")
    return value


def _max_hops(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("max_hops must be an integer from 1 through 6")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_hops must be an integer from 1 through 6") from exc
    if str(parsed) != str(value).strip() and not isinstance(value, int):
        raise ValueError("max_hops must be an integer from 1 through 6")
    if parsed < 1 or parsed > 6:
        raise ValueError("max_hops must be an integer from 1 through 6")
    return parsed


def _ceil_fee(amount: int, rate_ppm: int) -> int:
    if rate_ppm <= 0:
        return 0
    return (amount * rate_ppm + FEE_DENOMINATOR_PPM - 1) // FEE_DENOMINATOR_PPM


def _cp_exact_in(raw_input: int, reserve_in: int, reserve_out: int, rate_ppm: int) -> int:
    fee = _ceil_fee(raw_input, rate_ppm)
    net = raw_input - fee
    if net <= 0 or reserve_in <= 0 or reserve_out <= 0:
        raise XDEXMultiHopError("provider hop curve inputs must remain positive")
    return net * reserve_out // (reserve_in + net)


def _ui_matches_raw(ui_value: Any, raw_value: int, decimals: int, field: str) -> None:
    ui = _decimal(ui_value, field)
    scaled = ui * (Decimal(10) ** decimals)
    if scaled != scaled.to_integral_value() or int(scaled) != raw_value:
        raise XDEXMultiHopError(f"{field} does not match its raw-token value")


def _token_decimals(tokens: Mapping[str, Any], mint: str) -> int:
    row = tokens.get(mint)
    if not isinstance(row, Mapping):
        raise XDEXMultiHopError(f"provider token metadata missing for {mint}")
    if row.get("mint") != mint:
        raise XDEXMultiHopError(f"provider token metadata mint mismatch for {mint}")
    decimals = row.get("decimals")
    if isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0 or decimals > 30:
        raise XDEXMultiHopError(f"provider token decimals invalid for {mint}")
    return decimals


def _bounded_response_text(response: Any, *, limit: int = 500) -> str:
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        return ""
    if len(text) > limit:
        text = f"{text[:limit]}..."
    return text


def collect_multi_hop_quote_observation(
    token_in: str,
    token_out: str,
    token_in_amount: Any,
    *,
    venue: str = DEFAULT_VENUE,
    max_hops: int = DEFAULT_MAX_HOPS,
    network: str = XDEX_NETWORK_X1_MAINNET,
    session=requests,
    timeout: int = 15,
) -> dict[str, Any]:
    """Collect one exact read-only provider response without promoting semantics."""

    token_in_text = _text(token_in, "token_in")
    token_out_text = _text(token_out, "token_out")
    if token_in_text == token_out_text:
        raise ValueError("token_in and token_out must differ")
    amount_text = _amount_text(token_in_amount)
    venue_text = _text(venue, "venue")
    network_text = _text(network, "network")
    hop_limit = _max_hops(max_hops)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise ValueError("timeout must be a positive integer")

    params = {
        "token_in": token_in_text,
        "token_out": token_out_text,
        "token_in_amount": amount_text,
        "venue": venue_text,
        "max_hops": str(hop_limit),
        "network": network_text,
    }
    response = None
    try:
        response = session.get(MULTI_HOP_QUOTE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        detail = _bounded_response_text(response)
        suffix = f" | response: {detail}" if detail else ""
        raise XDEXMultiHopError(f"XDEX multi-hop quote request failed: {exc}{suffix}") from exc

    if not isinstance(body, Mapping):
        raise XDEXMultiHopError("XDEX multi-hop quote response must be a JSON object")

    return {
        "schema": OBSERVATION_SCHEMA,
        "chain": CHAIN,
        "source": SOURCE,
        "endpoint": MULTI_HOP_QUOTE_URL,
        "request": params,
        "raw_response": dict(body),
        "provider_semantics_promoted": False,
        "prepare_called": False,
        "read_only": True,
        "execution_authorized": False,
    }


def parse_multi_hop_quote_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Verify the live provider schema and arithmetic without granting factual authority."""

    if not isinstance(observation, Mapping):
        raise XDEXMultiHopError("provider observation must be a mapping")
    if observation.get("schema") != OBSERVATION_SCHEMA:
        raise XDEXMultiHopError("provider observation schema mismatch")
    if observation.get("chain") != CHAIN:
        raise XDEXMultiHopError("provider observation must remain X1-only")
    if observation.get("prepare_called") is not False or observation.get("execution_authorized") is not False:
        raise XDEXMultiHopError("provider observation widened execution authority")
    if observation.get("read_only") is not True:
        raise XDEXMultiHopError("provider observation must remain read-only")

    request = observation.get("request")
    body = observation.get("raw_response")
    if not isinstance(request, Mapping) or not isinstance(body, Mapping):
        raise XDEXMultiHopError("provider request/raw response must be mappings")
    if body.get("success") is not True:
        raise XDEXMultiHopError("XDEX multi-hop quote did not return success=true")
    data = body.get("data")
    if not isinstance(data, Mapping):
        raise XDEXMultiHopError("XDEX multi-hop quote data must be a mapping")

    input_mint = _text(data.get("input_mint"), "data.input_mint")
    output_mint = _text(data.get("output_mint"), "data.output_mint")
    if input_mint != request.get("token_in") or output_mint != request.get("token_out"):
        raise XDEXMultiHopError("provider route endpoints do not match the request")
    if data.get("network") != request.get("network"):
        raise XDEXMultiHopError("provider network does not match the request")
    if data.get("venue") != request.get("venue"):
        raise XDEXMultiHopError("provider venue does not match the request")
    max_hops = _bounded_int(data.get("max_hops"), "data.max_hops", minimum=1, maximum=DEFAULT_MAX_HOPS)
    if str(max_hops) != str(request.get("max_hops")):
        raise XDEXMultiHopError("provider max_hops does not match the request")

    path = data.get("path")
    hops = data.get("hops")
    tokens = data.get("tokens")
    if isinstance(path, (str, bytes)) or not isinstance(path, Sequence):
        raise XDEXMultiHopError("provider path must be a sequence")
    if isinstance(hops, (str, bytes)) or not isinstance(hops, Sequence):
        raise XDEXMultiHopError("provider hops must be a sequence")
    if not isinstance(tokens, Mapping):
        raise XDEXMultiHopError("provider token metadata must be a mapping")
    path = [_text(value, f"data.path[{index}]") for index, value in enumerate(path)]
    hop_count = _bounded_int(data.get("hop_count"), "data.hop_count", minimum=1, maximum=max_hops)
    if len(hops) != hop_count or len(path) != hop_count + 1:
        raise XDEXMultiHopError("provider hop_count/path/hops lengths disagree")
    if path[0] != input_mint or path[-1] != output_mint:
        raise XDEXMultiHopError("provider path endpoints do not match input/output mints")

    decimals_by_mint = {mint: _token_decimals(tokens, mint) for mint in path}
    input_raw = _canonical_uint(data.get("input_amount_raw"), "data.input_amount_raw")
    gross_raw = _canonical_uint(data.get("output_amount_gross_raw"), "data.output_amount_gross_raw")
    output_raw = _canonical_uint(data.get("output_amount_raw"), "data.output_amount_raw")
    fee_amount_raw = _canonical_uint(data.get("fee_amount_raw"), "data.fee_amount_raw")
    _ui_matches_raw(data.get("input_amount"), input_raw, decimals_by_mint[input_mint], "data.input_amount")
    _ui_matches_raw(data.get("output_amount_gross"), gross_raw, decimals_by_mint[output_mint], "data.output_amount_gross")
    _ui_matches_raw(data.get("output_amount"), output_raw, decimals_by_mint[output_mint], "data.output_amount")
    _ui_matches_raw(data.get("fee_amount"), fee_amount_raw, decimals_by_mint[output_mint], "data.fee_amount")

    normalized_hops: list[dict[str, Any]] = []
    previous_output_raw = None
    venues: set[str] = set()
    for index, raw_hop in enumerate(hops):
        if not isinstance(raw_hop, Mapping):
            raise XDEXMultiHopError(f"data.hops[{index}] must be a mapping")
        token_in = _text(raw_hop.get("token_in"), f"data.hops[{index}].token_in")
        token_out = _text(raw_hop.get("token_out"), f"data.hops[{index}].token_out")
        pool = _text(raw_hop.get("pool"), f"data.hops[{index}].pool")
        venue = _text(raw_hop.get("venue"), f"data.hops[{index}].venue")
        if token_in != path[index] or token_out != path[index + 1]:
            raise XDEXMultiHopError("provider hop token chain does not match path")
        amount_in_raw = _canonical_uint(raw_hop.get("amount_in_raw"), f"data.hops[{index}].amount_in_raw")
        amount_out_raw = _canonical_uint(raw_hop.get("amount_out_raw"), f"data.hops[{index}].amount_out_raw")
        reserve_in_raw = _canonical_uint(raw_hop.get("reserve_in_raw"), f"data.hops[{index}].reserve_in_raw")
        reserve_out_raw = _canonical_uint(raw_hop.get("reserve_out_raw"), f"data.hops[{index}].reserve_out_raw")
        reserve_in_after_raw = _canonical_uint(raw_hop.get("reserve_in_after_raw"), f"data.hops[{index}].reserve_in_after_raw")
        reserve_out_after_raw = _canonical_uint(raw_hop.get("reserve_out_after_raw"), f"data.hops[{index}].reserve_out_after_raw")
        trade_fee_rate = _canonical_uint(raw_hop.get("trade_fee_rate"), f"data.hops[{index}].trade_fee_rate")
        if trade_fee_rate >= FEE_DENOMINATOR_PPM:
            raise XDEXMultiHopError("provider hop trade_fee_rate is outside the accepted ppm range")
        _ui_matches_raw(raw_hop.get("amount_in"), amount_in_raw, decimals_by_mint[token_in], f"data.hops[{index}].amount_in")
        _ui_matches_raw(raw_hop.get("amount_out"), amount_out_raw, decimals_by_mint[token_out], f"data.hops[{index}].amount_out")
        _ui_matches_raw(raw_hop.get("reserve_in"), reserve_in_raw, decimals_by_mint[token_in], f"data.hops[{index}].reserve_in")
        _ui_matches_raw(raw_hop.get("reserve_out"), reserve_out_raw, decimals_by_mint[token_out], f"data.hops[{index}].reserve_out")
        _ui_matches_raw(raw_hop.get("reserve_in_after"), reserve_in_after_raw, decimals_by_mint[token_in], f"data.hops[{index}].reserve_in_after")
        _ui_matches_raw(raw_hop.get("reserve_out_after"), reserve_out_after_raw, decimals_by_mint[token_out], f"data.hops[{index}].reserve_out_after")
        if reserve_in_after_raw != reserve_in_raw + amount_in_raw:
            raise XDEXMultiHopError("provider reserve_in_after arithmetic mismatch")
        if reserve_out_after_raw != reserve_out_raw - amount_out_raw:
            raise XDEXMultiHopError("provider reserve_out_after arithmetic mismatch")
        expected_output = _cp_exact_in(amount_in_raw, reserve_in_raw, reserve_out_raw, trade_fee_rate)
        if expected_output != amount_out_raw:
            raise XDEXMultiHopError("provider hop constant-product arithmetic mismatch")
        if index == 0 and amount_in_raw != input_raw:
            raise XDEXMultiHopError("first provider hop input does not match route input")
        if previous_output_raw is not None and amount_in_raw != previous_output_raw:
            raise XDEXMultiHopError("provider hop amount continuity mismatch")
        previous_output_raw = amount_out_raw
        venues.add(venue)
        normalized_hops.append({
            "index": index,
            "pool": pool,
            "venue": venue,
            "token_in_mint": token_in,
            "token_out_mint": token_out,
            "amount_in_raw": amount_in_raw,
            "amount_out_raw": amount_out_raw,
            "provider_reserve_in_raw": reserve_in_raw,
            "provider_reserve_out_raw": reserve_out_raw,
            "provider_trade_fee_rate_ppm": trade_fee_rate,
            "provider_curve_output_raw": expected_output,
        })

    if previous_output_raw != gross_raw:
        raise XDEXMultiHopError("last provider hop output does not match gross route output")

    fee_bps = _bounded_int(data.get("fee_bps"), "data.fee_bps", minimum=0, maximum=BPS_DENOMINATOR - 1)
    expected_fee_raw = gross_raw * fee_bps // BPS_DENOMINATOR
    expected_output_raw = gross_raw * (BPS_DENOMINATOR - fee_bps) // BPS_DENOMINATOR
    if expected_fee_raw != fee_amount_raw:
        raise XDEXMultiHopError("provider fee_amount_raw transform mismatch")
    if expected_output_raw != output_raw:
        raise XDEXMultiHopError("provider output_amount_raw transform mismatch")

    return {
        "schema": PARSED_SCHEMA,
        "chain": CHAIN,
        "source": SOURCE,
        "request": dict(request),
        "input_mint": input_mint,
        "output_mint": output_mint,
        "input_amount_raw": input_raw,
        "output_amount_gross_raw": gross_raw,
        "output_amount_raw": output_raw,
        "provider_fee_bps": fee_bps,
        "provider_fee_amount_raw": fee_amount_raw,
        "provider_fee_floor_rounding_delta_raw": gross_raw - fee_amount_raw - output_raw,
        "hop_count": hop_count,
        "path": path,
        "hops": normalized_hops,
        "provider_venues": sorted(venues),
        "provider_schema_verified": True,
        "provider_route_identity_verified": True,
        "provider_hop_continuity_verified": True,
        "provider_hop_curve_arithmetic_verified": True,
        "provider_fee_transform_verified": True,
        "provider_fee_business_semantics_verified": False,
        "provider_cross_dex_route_quoted": len(venues) > 1,
        "cross_dex_execution_observed": False,
        "route_optimality_verified": False,
        "provider_semantics_promoted": False,
        "prepare_called": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "BPS_DENOMINATOR",
    "CHAIN",
    "DEFAULT_MAX_HOPS",
    "DEFAULT_VENUE",
    "MULTI_HOP_QUOTE_URL",
    "OBSERVATION_SCHEMA",
    "PARSED_SCHEMA",
    "SOURCE",
    "XDEXMultiHopError",
    "collect_multi_hop_quote_observation",
    "parse_multi_hop_quote_observation",
]
