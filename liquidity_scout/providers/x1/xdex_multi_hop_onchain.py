"""Independent X1-RPC verification for XDEX multi-hop quote routes.

This module verifies only XDEX-program hops. It decodes each quoted pool and AMM
config, verifies vault identities and active reserves, and independently
reconstructs exact-in constant-product output. It does not select a route,
prepare a transaction, sign, broadcast, simulate execution, or move value.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import struct
from typing import Any, Callable

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.rpc import get_token_account_info, rpc_request
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import X1_PROGRAM
from liquidity_scout.providers.x1.xdex_multi_hop import PARSED_SCHEMA

CHAIN = "x1"
SOURCE = "X1 RPC independent XDEX multi-hop verifier"
VERIFICATION_SCHEMA = "xdex_multi_hop_onchain_verification.v1"
POOL_STATE_LENGTH = 637
FEE_DENOMINATOR = 1_000_000


class XDEXMultiHopOnchainError(RuntimeError):
    """Raised when independent hop verification cannot be completed safely."""


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def _pubkey(data: bytes, offset: int) -> str:
    return encode_base58_pubkey(data[offset : offset + 32])


def _verified_program_account(account: Any, *, expected_account: str, label: str) -> tuple[bytes, int | None]:
    if not isinstance(account, Mapping):
        raise XDEXMultiHopOnchainError(f"{label} account state is unavailable")
    if account.get("account") != expected_account:
        raise XDEXMultiHopOnchainError(f"{label} account identity mismatch")
    if account.get("account_exists") is not True:
        raise XDEXMultiHopOnchainError(f"{label} account does not exist")
    if account.get("response_integrity_verified") is not True:
        raise XDEXMultiHopOnchainError(f"{label} account response integrity is unverified")
    if account.get("owner") != X1_PROGRAM:
        raise XDEXMultiHopOnchainError(f"{label} is not owned by the accepted XDEX program")
    data = account.get("data")
    if not isinstance(data, (bytes, bytearray)):
        raise XDEXMultiHopOnchainError(f"{label} returned no verified binary data")
    context_slot = account.get("context_slot")
    if context_slot is not None and (isinstance(context_slot, bool) or not isinstance(context_slot, int) or context_slot < 0):
        raise XDEXMultiHopOnchainError(f"{label} context slot is invalid")
    return bytes(data), context_slot


def _decode_pool(account: Any, *, pool: str) -> dict[str, Any]:
    raw, context_slot = _verified_program_account(account, expected_account=pool, label="XDEX hop pool")
    if len(raw) != POOL_STATE_LENGTH:
        raise XDEXMultiHopOnchainError("XDEX hop pool state does not match the accepted 637-byte layout")
    return {
        "pool": pool,
        "context_slot": context_slot,
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
        "creator_fee_on": raw[389],
        "enable_creator_fee": bool(raw[390]),
        "creator_fees_0": _u64(raw, 397),
        "creator_fees_1": _u64(raw, 405),
    }


def _decode_config(account: Any, *, amm_config: str) -> dict[str, Any]:
    raw, context_slot = _verified_program_account(account, expected_account=amm_config, label="XDEX AMM config")
    if len(raw) < 116:
        raise XDEXMultiHopOnchainError("XDEX AMM config does not match the accepted layout")
    return {
        "amm_config": amm_config,
        "context_slot": context_slot,
        "trade_fee_rate_ppm": _u64(raw, 12),
        "protocol_fee_rate_ppm_of_trade_fee": _u64(raw, 20),
        "fund_fee_rate_ppm_of_trade_fee": _u64(raw, 28),
        "creator_fee_rate_ppm": _u64(raw, 108),
    }


def _verified_vault(fetcher: Callable[[str], Any], vault: str, mint: str, decimals: int) -> tuple[int, str]:
    record = fetcher(vault)
    if not isinstance(record, Mapping):
        raise XDEXMultiHopOnchainError("XDEX hop vault evidence is unavailable")
    if record.get("account") != vault or record.get("account_exists") is not True:
        raise XDEXMultiHopOnchainError("XDEX hop vault identity/existence mismatch")
    if record.get("identity_verified") is not True:
        raise XDEXMultiHopOnchainError("XDEX hop vault token-account identity is unverified")
    if record.get("mint") != mint or record.get("decimals") != decimals:
        raise XDEXMultiHopOnchainError("XDEX hop vault mint/decimals mismatch")
    authority = record.get("token_authority")
    if not isinstance(authority, str) or not authority.strip() or authority.strip() != authority:
        raise XDEXMultiHopOnchainError("XDEX hop vault authority is unverified")
    raw_amount = record.get("raw_amount")
    if not isinstance(raw_amount, str) or not raw_amount.isdigit() or str(int(raw_amount)) != raw_amount:
        raise XDEXMultiHopOnchainError("XDEX hop vault raw amount is not canonical")
    return int(raw_amount), authority


def _active_reserves(pool: Mapping[str, Any], fetcher: Callable[[str], Any]) -> tuple[int, int]:
    gross_0, authority_0 = _verified_vault(fetcher, pool["vault_0"], pool["mint_0"], pool["decimals_0"])
    gross_1, authority_1 = _verified_vault(fetcher, pool["vault_1"], pool["mint_1"], pool["decimals_1"])
    if authority_0 != authority_1:
        raise XDEXMultiHopOnchainError("XDEX hop vaults do not share one verified authority")
    reserve_0 = gross_0 - pool["protocol_fees_0"] - pool["fund_fees_0"] - pool["creator_fees_0"]
    reserve_1 = gross_1 - pool["protocol_fees_1"] - pool["fund_fees_1"] - pool["creator_fees_1"]
    if reserve_0 <= 0 or reserve_1 <= 0:
        raise XDEXMultiHopOnchainError("XDEX hop active reserves must remain positive")
    return reserve_0, reserve_1


def _ceil_fee(amount: int, rate: int) -> int:
    if isinstance(rate, bool) or not isinstance(rate, int) or rate < 0 or rate >= FEE_DENOMINATOR:
        raise XDEXMultiHopOnchainError("XDEX fee rate is outside the accepted ppm range")
    if rate == 0:
        return 0
    return (amount * rate + FEE_DENOMINATOR - 1) // FEE_DENOMINATOR


def _creator_fee_on_input(pool: Mapping[str, Any], config: Mapping[str, Any], *, zero_to_one: bool) -> bool:
    rate = config["creator_fee_rate_ppm"]
    if not pool["enable_creator_fee"] or rate == 0:
        return False
    mode = pool["creator_fee_on"]
    if mode == 0:
        return True
    if mode == 1:
        return zero_to_one
    if mode == 2:
        return not zero_to_one
    raise XDEXMultiHopOnchainError("XDEX creator_fee_on mode is outside the accepted layout")


def _curve_exact_in(
    raw_input: int,
    reserve_in: int,
    reserve_out: int,
    pool: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    zero_to_one: bool,
) -> dict[str, int]:
    trade_rate = config["trade_fee_rate_ppm"]
    creator_rate = config["creator_fee_rate_ppm"]
    creator_on_input = _creator_fee_on_input(pool, config, zero_to_one=zero_to_one)

    if creator_on_input:
        combined_rate = trade_rate + creator_rate
        if combined_rate >= FEE_DENOMINATOR:
            raise XDEXMultiHopOnchainError("combined XDEX input fee rate is invalid")
        total_input_fee = _ceil_fee(raw_input, combined_rate)
        creator_fee = (
            total_input_fee * creator_rate // combined_rate
            if creator_rate and combined_rate
            else 0
        )
        trade_fee = total_input_fee - creator_fee
        net_input = raw_input - total_input_fee
    else:
        trade_fee = _ceil_fee(raw_input, trade_rate)
        creator_fee = 0
        net_input = raw_input - trade_fee

    if net_input <= 0:
        raise XDEXMultiHopOnchainError("XDEX hop fees consume the complete input")
    swapped_output = net_input * reserve_out // (reserve_in + net_input)

    if not creator_on_input and creator_rate:
        creator_fee = _ceil_fee(swapped_output, creator_rate)
        output = swapped_output - creator_fee
    else:
        output = swapped_output
    if output <= 0:
        raise XDEXMultiHopOnchainError("XDEX reconstructed hop output is non-positive")
    return {
        "output_raw": output,
        "trade_fee_raw": trade_fee,
        "creator_fee_raw": creator_fee,
        "net_input_raw": net_input,
    }


def _slot(fetcher: Callable[[], Any], field: str) -> int:
    value = fetcher()
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise XDEXMultiHopOnchainError(f"{field} must be a non-negative integer slot")
    return value


def verify_multi_hop_quote_onchain(
    parsed_quote: Mapping[str, Any],
    *,
    account_state_fetcher: Callable[[str], Any] = fetch_account_state,
    token_account_fetcher: Callable[[str], Any] = get_token_account_info,
    slot_fetcher: Callable[[], Any] | None = None,
    max_slot_span: int = 8,
) -> dict[str, Any]:
    """Verify all quoted XDEX hops against current X1 account state."""

    if not isinstance(parsed_quote, Mapping) or parsed_quote.get("schema") != PARSED_SCHEMA:
        raise XDEXMultiHopOnchainError("parsed multi-hop quote schema mismatch")
    if parsed_quote.get("chain") != CHAIN:
        raise XDEXMultiHopOnchainError("parsed multi-hop quote must remain X1-only")
    if parsed_quote.get("execution_authorized") is not False or parsed_quote.get("read_only") is not True:
        raise XDEXMultiHopOnchainError("parsed multi-hop quote widened execution authority")
    hops = parsed_quote.get("hops")
    if isinstance(hops, (str, bytes)) or not isinstance(hops, Sequence) or not hops:
        raise XDEXMultiHopOnchainError("parsed multi-hop quote contains no hops")
    if isinstance(max_slot_span, bool) or not isinstance(max_slot_span, int) or max_slot_span < 0:
        raise ValueError("max_slot_span must be a non-negative integer")

    fetch_slot = slot_fetcher or (lambda: rpc_request("getSlot", [{"commitment": "confirmed"}]))
    slot_before = _slot(fetch_slot, "verification_slot_before")
    verified_hops: list[dict[str, Any]] = []
    account_slots: list[int] = []

    for index, hop in enumerate(hops):
        if not isinstance(hop, Mapping) or hop.get("index") != index:
            raise XDEXMultiHopOnchainError("parsed hop indexes are invalid")
        if hop.get("venue") != "xdex":
            raise XDEXMultiHopOnchainError("X1-RPC XDEX verifier cannot verify a non-XDEX venue hop")
        pool_address = hop.get("pool")
        if not isinstance(pool_address, str) or not pool_address:
            raise XDEXMultiHopOnchainError("parsed XDEX hop pool is missing")

        pool = _decode_pool(account_state_fetcher(pool_address), pool=pool_address)
        if pool["context_slot"] is not None:
            account_slots.append(pool["context_slot"])
        token_in = hop["token_in_mint"]
        token_out = hop["token_out_mint"]
        if {pool["mint_0"], pool["mint_1"]} != {token_in, token_out}:
            raise XDEXMultiHopOnchainError("decoded XDEX hop pool mint pair does not match provider route")
        zero_to_one = token_in == pool["mint_0"]
        if not zero_to_one and token_in != pool["mint_1"]:
            raise XDEXMultiHopOnchainError("decoded XDEX hop direction is unavailable")

        config = _decode_config(account_state_fetcher(pool["amm_config"]), amm_config=pool["amm_config"])
        if config["context_slot"] is not None:
            account_slots.append(config["context_slot"])
        if config["trade_fee_rate_ppm"] != hop["provider_trade_fee_rate_ppm"]:
            raise XDEXMultiHopOnchainError("provider hop trade_fee_rate does not match decoded AMM config")

        reserve_0, reserve_1 = _active_reserves(pool, token_account_fetcher)
        if zero_to_one:
            reserve_in, reserve_out = reserve_0, reserve_1
        else:
            reserve_in, reserve_out = reserve_1, reserve_0
        if reserve_in != hop["provider_reserve_in_raw"] or reserve_out != hop["provider_reserve_out_raw"]:
            raise XDEXMultiHopOnchainError("provider hop reserves do not match independently verified active reserves")

        reconstruction = _curve_exact_in(
            hop["amount_in_raw"],
            reserve_in,
            reserve_out,
            pool,
            config,
            zero_to_one=zero_to_one,
        )
        if reconstruction["output_raw"] != hop["amount_out_raw"]:
            raise XDEXMultiHopOnchainError("independently reconstructed XDEX hop output does not match provider output")

        verified_hops.append({
            "index": index,
            "pool": pool_address,
            "venue": "xdex",
            "token_in_mint": token_in,
            "token_out_mint": token_out,
            "amm_config": pool["amm_config"],
            "pool_context_slot": pool["context_slot"],
            "config_context_slot": config["context_slot"],
            "active_reserve_in_raw": reserve_in,
            "active_reserve_out_raw": reserve_out,
            "trade_fee_rate_ppm": config["trade_fee_rate_ppm"],
            "protocol_fee_rate_ppm_of_trade_fee": config["protocol_fee_rate_ppm_of_trade_fee"],
            "fund_fee_rate_ppm_of_trade_fee": config["fund_fee_rate_ppm_of_trade_fee"],
            "creator_fee_rate_ppm": config["creator_fee_rate_ppm"],
            "creator_fee_on": pool["creator_fee_on"],
            "enable_creator_fee": pool["enable_creator_fee"],
            "reconstructed_output_raw": reconstruction["output_raw"],
            "reconstructed_trade_fee_raw": reconstruction["trade_fee_raw"],
            "reconstructed_creator_fee_raw": reconstruction["creator_fee_raw"],
            "pool_identity_verified": True,
            "pool_state_verified": True,
            "venue_identity_verified": True,
            "reserve_math_verified": True,
            "fee_math_verified": True,
            "price_impact_verified": False,
            "minimum_received_bounded": False,
            "execution_authorized": False,
        })

    slot_after = _slot(fetch_slot, "verification_slot_after")
    all_slots = [slot_before, slot_after, *account_slots]
    slot_min = min(all_slots)
    slot_max = max(all_slots)
    slot_span = slot_max - slot_min
    if slot_span > max_slot_span:
        raise XDEXMultiHopOnchainError(
            f"independent XDEX hop verification exceeded slot-alignment bound: {slot_span}>{max_slot_span}"
        )

    return {
        "schema": VERIFICATION_SCHEMA,
        "chain": CHAIN,
        "source": SOURCE,
        "verification_slot_before": slot_before,
        "verification_slot_after": slot_after,
        "verification_slot_min": slot_min,
        "verification_slot_max": slot_max,
        "verification_slot_span": slot_span,
        "max_slot_span": max_slot_span,
        "hop_count": len(verified_hops),
        "hops": verified_hops,
        "route_structure_verified": True,
        "pool_identity_verified": True,
        "pool_state_verified": True,
        "fee_math_verified": True,
        "reserve_math_verified": True,
        "current_state_alignment_verified": True,
        "provider_fact_time_verified": False,
        "route_optimality_verified": False,
        "cross_dex_execution_observed": False,
        "cross_dex_execution_verified": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CHAIN",
    "SOURCE",
    "VERIFICATION_SCHEMA",
    "XDEXMultiHopOnchainError",
    "verify_multi_hop_quote_onchain",
]
