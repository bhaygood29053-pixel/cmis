"""Deterministic provider-agnostic snapshot for verified XDEX multi-hop routes.

The snapshot composes the accepted normalized XDEX quote parser with the
independent X1-RPC verifier. Raw provider JSON never crosses this boundary.
Unsupported price-impact, slippage/minimum-received, network-fee, cross-DEX
execution, and route-optimality semantics remain explicitly unverified.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from liquidity_scout.providers.x1.xdex_multi_hop import PARSED_SCHEMA
from liquidity_scout.providers.x1.xdex_multi_hop_onchain import VERIFICATION_SCHEMA

CONTRACT_VERSION = "xdex_multi_hop_route_snapshot/v1"
CHAIN = "x1"


class XDEXMultiHopRouteSnapshotError(ValueError):
    """Raised when normalized quote and on-chain evidence cannot be safely bound."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise XDEXMultiHopRouteSnapshotError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise XDEXMultiHopRouteSnapshotError(f"{field} must be a sequence")
    return value


def _canonical_nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise XDEXMultiHopRouteSnapshotError(f"{field} must be a non-negative integer")
    return value


def _required_true(record: Mapping[str, Any], field: str, label: str) -> None:
    if record.get(field) is not True:
        raise XDEXMultiHopRouteSnapshotError(f"{label}.{field} must be verified true")


def _required_false(record: Mapping[str, Any], field: str, label: str) -> None:
    if record.get(field) is not False:
        raise XDEXMultiHopRouteSnapshotError(f"{label}.{field} must remain false")


def _validate_parsed_quote(value: Any) -> dict[str, Any]:
    quote = _mapping(value, "parsed_quote")
    if quote.get("schema") != PARSED_SCHEMA:
        raise XDEXMultiHopRouteSnapshotError("parsed_quote schema mismatch")
    if quote.get("chain") != CHAIN:
        raise XDEXMultiHopRouteSnapshotError("parsed_quote must remain X1-only")
    _required_true(quote, "provider_schema_verified", "parsed_quote")
    _required_true(quote, "provider_route_identity_verified", "parsed_quote")
    _required_true(quote, "provider_hop_continuity_verified", "parsed_quote")
    _required_true(quote, "provider_hop_curve_arithmetic_verified", "parsed_quote")
    _required_true(quote, "provider_fee_transform_verified", "parsed_quote")
    _required_false(quote, "provider_fee_business_semantics_verified", "parsed_quote")
    _required_false(quote, "cross_dex_execution_observed", "parsed_quote")
    _required_false(quote, "route_optimality_verified", "parsed_quote")
    _required_false(quote, "provider_semantics_promoted", "parsed_quote")
    _required_false(quote, "prepare_called", "parsed_quote")
    _required_true(quote, "read_only", "parsed_quote")
    _required_false(quote, "execution_authorized", "parsed_quote")
    if "raw_response" in quote:
        raise XDEXMultiHopRouteSnapshotError("parsed_quote must not expose raw provider response")
    return deepcopy(dict(quote))


def _validate_verification(value: Any) -> dict[str, Any]:
    verification = _mapping(value, "onchain_verification")
    if verification.get("schema") != VERIFICATION_SCHEMA:
        raise XDEXMultiHopRouteSnapshotError("onchain_verification schema mismatch")
    if verification.get("chain") != CHAIN:
        raise XDEXMultiHopRouteSnapshotError("onchain_verification must remain X1-only")
    for field in (
        "route_structure_verified",
        "pool_identity_verified",
        "pool_state_verified",
        "fee_math_verified",
        "reserve_math_verified",
        "current_state_alignment_verified",
    ):
        _required_true(verification, field, "onchain_verification")
    _required_false(verification, "provider_fact_time_verified", "onchain_verification")
    _required_false(verification, "route_optimality_verified", "onchain_verification")
    _required_false(verification, "cross_dex_execution_observed", "onchain_verification")
    _required_false(verification, "cross_dex_execution_verified", "onchain_verification")
    _required_true(verification, "read_only", "onchain_verification")
    _required_false(verification, "execution_authorized", "onchain_verification")

    slot_min = _canonical_nonnegative_int(
        verification.get("verification_slot_min"), "onchain_verification.verification_slot_min"
    )
    slot_max = _canonical_nonnegative_int(
        verification.get("verification_slot_max"), "onchain_verification.verification_slot_max"
    )
    slot_span = _canonical_nonnegative_int(
        verification.get("verification_slot_span"), "onchain_verification.verification_slot_span"
    )
    max_slot_span = _canonical_nonnegative_int(
        verification.get("max_slot_span"), "onchain_verification.max_slot_span"
    )
    if slot_max < slot_min or slot_max - slot_min != slot_span:
        raise XDEXMultiHopRouteSnapshotError("onchain verification slot window is inconsistent")
    if slot_span > max_slot_span:
        raise XDEXMultiHopRouteSnapshotError("onchain verification exceeded its slot-alignment bound")
    return deepcopy(dict(verification))


def build_xdex_multi_hop_route_snapshot(
    parsed_quote: Mapping[str, Any],
    onchain_verification: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind normalized provider and X1-RPC facts into one fail-closed route snapshot."""

    quote = _validate_parsed_quote(parsed_quote)
    verification = _validate_verification(onchain_verification)

    quote_hops = list(_sequence(quote.get("hops"), "parsed_quote.hops"))
    verified_hops = list(_sequence(verification.get("hops"), "onchain_verification.hops"))
    hop_count = _canonical_nonnegative_int(quote.get("hop_count"), "parsed_quote.hop_count")
    if hop_count < 1:
        raise XDEXMultiHopRouteSnapshotError("parsed_quote.hop_count must be positive")
    if verification.get("hop_count") != hop_count or len(quote_hops) != hop_count or len(verified_hops) != hop_count:
        raise XDEXMultiHopRouteSnapshotError("quote/verification hop counts disagree")

    path = list(_sequence(quote.get("path"), "parsed_quote.path"))
    if len(path) != hop_count + 1:
        raise XDEXMultiHopRouteSnapshotError("parsed quote path length does not match hop count")
    if path[0] != quote.get("input_mint") or path[-1] != quote.get("output_mint"):
        raise XDEXMultiHopRouteSnapshotError("parsed quote path endpoints are inconsistent")

    normalized_hops: list[dict[str, Any]] = []
    previous_output_raw: int | None = None
    for index, (quote_hop_raw, verified_hop_raw) in enumerate(zip(quote_hops, verified_hops)):
        quote_hop = _mapping(quote_hop_raw, f"parsed_quote.hops[{index}]")
        verified_hop = _mapping(verified_hop_raw, f"onchain_verification.hops[{index}]")
        if quote_hop.get("index") != index or verified_hop.get("index") != index:
            raise XDEXMultiHopRouteSnapshotError("hop indexes must be contiguous from zero")

        identity_fields = ("pool", "venue", "token_in_mint", "token_out_mint")
        for field in identity_fields:
            if quote_hop.get(field) != verified_hop.get(field):
                raise XDEXMultiHopRouteSnapshotError(f"hop {index} {field} mismatch between provider and X1-RPC evidence")
        if quote_hop.get("token_in_mint") != path[index] or quote_hop.get("token_out_mint") != path[index + 1]:
            raise XDEXMultiHopRouteSnapshotError("hop identity does not match normalized route path")

        for field in (
            "pool_identity_verified",
            "pool_state_verified",
            "venue_identity_verified",
            "reserve_math_verified",
            "fee_math_verified",
        ):
            _required_true(verified_hop, field, f"onchain_verification.hops[{index}]")
        _required_false(verified_hop, "price_impact_verified", f"onchain_verification.hops[{index}]")
        _required_false(verified_hop, "minimum_received_bounded", f"onchain_verification.hops[{index}]")
        _required_false(verified_hop, "execution_authorized", f"onchain_verification.hops[{index}]")

        amount_in_raw = _canonical_nonnegative_int(quote_hop.get("amount_in_raw"), f"parsed_quote.hops[{index}].amount_in_raw")
        amount_out_raw = _canonical_nonnegative_int(quote_hop.get("amount_out_raw"), f"parsed_quote.hops[{index}].amount_out_raw")
        if verified_hop.get("reconstructed_output_raw") != amount_out_raw:
            raise XDEXMultiHopRouteSnapshotError(f"hop {index} reconstructed output does not match provider-normalized output")
        if quote_hop.get("provider_reserve_in_raw") != verified_hop.get("active_reserve_in_raw"):
            raise XDEXMultiHopRouteSnapshotError(f"hop {index} input reserve mismatch")
        if quote_hop.get("provider_reserve_out_raw") != verified_hop.get("active_reserve_out_raw"):
            raise XDEXMultiHopRouteSnapshotError(f"hop {index} output reserve mismatch")
        if quote_hop.get("provider_trade_fee_rate_ppm") != verified_hop.get("trade_fee_rate_ppm"):
            raise XDEXMultiHopRouteSnapshotError(f"hop {index} trade-fee configuration mismatch")
        if index == 0 and amount_in_raw != quote.get("input_amount_raw"):
            raise XDEXMultiHopRouteSnapshotError("first hop input does not match route input")
        if previous_output_raw is not None and amount_in_raw != previous_output_raw:
            raise XDEXMultiHopRouteSnapshotError("verified hop amounts are not contiguous")
        previous_output_raw = amount_out_raw

        pool_slot = verified_hop.get("pool_context_slot")
        config_slot = verified_hop.get("config_context_slot")
        if pool_slot is not None:
            _canonical_nonnegative_int(pool_slot, f"onchain_verification.hops[{index}].pool_context_slot")
        if config_slot is not None:
            _canonical_nonnegative_int(config_slot, f"onchain_verification.hops[{index}].config_context_slot")

        normalized_hops.append({
            "index": index,
            "venue": verified_hop["venue"],
            "pool": verified_hop["pool"],
            "token_in_mint": verified_hop["token_in_mint"],
            "token_out_mint": verified_hop["token_out_mint"],
            "amm_config": verified_hop.get("amm_config"),
            "pool_context_slot": pool_slot,
            "config_context_slot": config_slot,
            "amount_in_raw": amount_in_raw,
            "expected_output_raw": verified_hop["reconstructed_output_raw"],
            "active_reserve_in_raw": verified_hop["active_reserve_in_raw"],
            "active_reserve_out_raw": verified_hop["active_reserve_out_raw"],
            "trade_fee_rate_ppm": verified_hop["trade_fee_rate_ppm"],
            "reconstructed_trade_fee_raw": verified_hop.get("reconstructed_trade_fee_raw"),
            "reconstructed_creator_fee_raw": verified_hop.get("reconstructed_creator_fee_raw"),
            "protocol_fee_rate_ppm_of_trade_fee": verified_hop.get("protocol_fee_rate_ppm_of_trade_fee"),
            "fund_fee_rate_ppm_of_trade_fee": verified_hop.get("fund_fee_rate_ppm_of_trade_fee"),
            "creator_fee_rate_ppm": verified_hop.get("creator_fee_rate_ppm"),
            "pool_identity_verified": True,
            "pool_state_verified": True,
            "venue_identity_verified": True,
            "reserve_math_verified": True,
            "fee_math_verified": True,
            "price_impact_verified": False,
            "minimum_received_bounded": False,
            "execution_authorized": False,
        })

    gross_output_raw = _canonical_nonnegative_int(
        quote.get("output_amount_gross_raw"), "parsed_quote.output_amount_gross_raw"
    )
    if previous_output_raw != gross_output_raw:
        raise XDEXMultiHopRouteSnapshotError("aggregate reconstructed route output does not match gross provider-normalized output")

    net_output_raw = _canonical_nonnegative_int(quote.get("output_amount_raw"), "parsed_quote.output_amount_raw")
    provider_fee_amount_raw = _canonical_nonnegative_int(
        quote.get("provider_fee_amount_raw"), "parsed_quote.provider_fee_amount_raw"
    )
    provider_fee_bps = _canonical_nonnegative_int(quote.get("provider_fee_bps"), "parsed_quote.provider_fee_bps")
    if gross_output_raw - provider_fee_amount_raw - net_output_raw != quote.get("provider_fee_floor_rounding_delta_raw"):
        raise XDEXMultiHopRouteSnapshotError("provider fee transform accounting no longer balances")

    provider_cross_dex_route_quoted = quote.get("provider_cross_dex_route_quoted")
    if provider_cross_dex_route_quoted not in (True, False):
        raise XDEXMultiHopRouteSnapshotError("provider cross-DEX route state must be boolean")

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "status": "ok",
        "input_mint": quote["input_mint"],
        "output_mint": quote["output_mint"],
        "input_amount_raw": quote["input_amount_raw"],
        "gross_output_raw": gross_output_raw,
        "net_output_raw": net_output_raw,
        "hop_count": hop_count,
        "path": path,
        "hops": normalized_hops,
        "observation_window": {
            "slot_min": verification["verification_slot_min"],
            "slot_max": verification["verification_slot_max"],
            "slot_span": verification["verification_slot_span"],
            "max_slot_span": verification["max_slot_span"],
            "current_state_alignment_verified": True,
            "provider_fact_time_verified": False,
        },
        "route_output": {
            "gross_output_raw": gross_output_raw,
            "aggregate_hop_output_verified": True,
        },
        "pool_fee_evidence": [
            {
                "hop_index": hop["index"],
                "input_mint": hop["token_in_mint"],
                "trade_fee_rate_ppm": hop["trade_fee_rate_ppm"],
                "reconstructed_trade_fee_raw": hop["reconstructed_trade_fee_raw"],
                "reconstructed_creator_fee_raw": hop["reconstructed_creator_fee_raw"],
                "fee_math_verified": True,
            }
            for hop in normalized_hops
        ],
        "provider_routing_fee_transform": {
            "fee_bps": provider_fee_bps,
            "fee_amount_raw": provider_fee_amount_raw,
            "net_output_raw": net_output_raw,
            "floor_rounding_delta_raw": quote["provider_fee_floor_rounding_delta_raw"],
            "arithmetic_transform_verified": True,
            "business_semantics_verified": False,
        },
        "price_impact": {"status": "EVIDENCE_REQUIRED", "verified": False},
        "minimum_received": {"status": "EVIDENCE_REQUIRED", "bounded": False},
        "network_fee": {"status": "EVIDENCE_REQUIRED", "verified": False},
        "cross_dex_configured": None,
        "cross_dex_route_available": provider_cross_dex_route_quoted,
        "cross_dex_execution_observed": False,
        "cross_dex_execution_verified": False,
        "route_optimality_verified": False,
        "provider_raw_json_exposed": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CHAIN",
    "CONTRACT_VERSION",
    "XDEXMultiHopRouteSnapshotError",
    "build_xdex_multi_hop_route_snapshot",
]
