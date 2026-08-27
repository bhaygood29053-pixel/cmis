#!/usr/bin/env python3
"""Read-only Oracle V2 X1 RPC qualification probe for CMIS issue #272.

This probe verifies only the repository-declared Oracle V2 on-chain contract
shape. It does not promote Oracle V2 into CMIS, declare any relay slot fresh,
or treat relay slots as independent market sources.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import struct
import sys
from datetime import datetime, timezone

from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, X1RPCProvider


CHAIN = "x1"
SERVICE = "x1_oracle_v2_rpc_probe"
VERSION = "0.1.0"

ORACLE_V2_REPOSITORY = "jacklevin74/oracle-v2"
ORACLE_V2_PINNED_COMMIT = "97177f772689e44ca4eed9bb95be32ffdf0c5e66"
PROGRAM_ID = "9mPmjK8NxJadYDiHiYAQH4WFCnKJr7ZV8ria63ZkMtv2"
STATE_PDA = "8XZBqbKhFXHqNGzxV3Tt6gEs9r8ZrNghsRg7zBwLMGJf"
ORACLE_SEED = b"oracle_vault_v1"
ASSETS = ("BTC", "ETH", "SOL", "HYPE", "ZEC", "FARTCOIN")
NUM_SLOTS = 5
DECIMALS = 6

# Anchor discriminator: sha256("account:OracleState")[:8].
ORACLE_STATE_DISCRIMINATOR = bytes.fromhex("619c9dbdc249080f")

# Source layout:
# 8 discriminator + 32 admin + 32 oracle pubkey + 1 decimals + 1 bump
# + 6 * (5 i64 prices + 5 i64 timestamps) = 554 serialized bytes.
SERIALIZED_STATE_BYTES = 554

# The reviewed initialize constraint allocates 8 + OracleState::INIT_SPACE,
# where INIT_SPACE includes a 64-byte future buffer.
ALLOCATED_STATE_BYTES = 618

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_ED25519_P = 2**255 - 19
_ED25519_D = (-121665 * pow(121666, _ED25519_P - 2, _ED25519_P)) % _ED25519_P
_ED25519_I = pow(2, (_ED25519_P - 1) // 4, _ED25519_P)
_PDA_MARKER = b"ProgramDerivedAddress"


class OracleV2ProbeError(RuntimeError):
    """Raised when the bounded Oracle V2 read contract cannot be verified."""


def _b58decode(value):
    value = str(value or "").strip()
    if not value:
        raise ValueError("base58 value is required")

    number = 0
    for character in value:
        try:
            digit = _B58_ALPHABET.index(character)
        except ValueError as exc:
            raise ValueError("invalid base58 value") from exc
        number = number * 58 + digit

    raw = (
        number.to_bytes((number.bit_length() + 7) // 8, "big")
        if number
        else b""
    )
    leading_zeroes = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading_zeroes + raw


def _b58encode(value):
    value = bytes(value)
    leading_zeroes = len(value) - len(value.lstrip(b"\x00"))
    number = int.from_bytes(value, "big")

    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _B58_ALPHABET[remainder] + encoded

    if not encoded and not leading_zeroes:
        encoded = "1"

    return "1" * leading_zeroes + encoded


def _is_ed25519_curve_point(value):
    """Return whether 32 compressed bytes decode to an Ed25519 curve point."""
    value = bytes(value)
    if len(value) != 32:
        return False

    y = int.from_bytes(value, "little") & ((1 << 255) - 1)
    if y >= _ED25519_P:
        return False

    y_squared = (y * y) % _ED25519_P
    numerator = (y_squared - 1) % _ED25519_P
    denominator = (_ED25519_D * y_squared + 1) % _ED25519_P
    x_squared = numerator * pow(
        denominator,
        _ED25519_P - 2,
        _ED25519_P,
    ) % _ED25519_P

    x = pow(x_squared, (_ED25519_P + 3) // 8, _ED25519_P)
    if (x * x - x_squared) % _ED25519_P:
        x = (x * _ED25519_I) % _ED25519_P

    return (x * x - x_squared) % _ED25519_P == 0


def derive_program_address(program_id=PROGRAM_ID, seed=ORACLE_SEED):
    """Derive the canonical Solana-compatible PDA and bump for one seed."""
    program_bytes = _b58decode(program_id)
    if len(program_bytes) != 32:
        raise ValueError("program ID must decode to exactly 32 bytes")

    seed = bytes(seed)
    if len(seed) > 32:
        raise ValueError("PDA seed exceeds 32 bytes")

    for bump in range(255, -1, -1):
        digest = hashlib.sha256(
            seed + bytes([bump]) + program_bytes + _PDA_MARKER
        ).digest()
        if not _is_ed25519_curve_point(digest):
            return {
                "address": _b58encode(digest),
                "bump": bump,
            }

    raise OracleV2ProbeError("no valid PDA bump found")


def oracle_state_discriminator():
    return hashlib.sha256(b"account:OracleState").digest()[:8]


def _decode_base64_account_data(value):
    data = value.get("data")
    if not isinstance(data, (list, tuple)) or len(data) < 2:
        raise OracleV2ProbeError("RPC account data is not base64 tuple data")
    if data[1] != "base64":
        raise OracleV2ProbeError("RPC account data encoding is not base64")

    try:
        return base64.b64decode(data[0], validate=True)
    except Exception as exc:
        raise OracleV2ProbeError("RPC account base64 data is malformed") from exc


def _scaled_i64(raw_value, decimals):
    negative = raw_value < 0
    digits = str(abs(raw_value)).rjust(decimals + 1, "0")
    whole = digits[:-decimals] if decimals else digits
    fraction = digits[-decimals:].rstrip("0") if decimals else ""
    text = whole if not fraction else f"{whole}.{fraction}"
    return f"-{text}" if negative else text


def decode_oracle_state(account_data):
    """Decode the exact OracleState layout from the pinned upstream source."""
    account_data = bytes(account_data)

    if len(account_data) < SERIALIZED_STATE_BYTES:
        raise OracleV2ProbeError(
            f"Oracle V2 state is too short: {len(account_data)} bytes"
        )

    discriminator = account_data[:8]
    if discriminator != ORACLE_STATE_DISCRIMINATOR:
        raise OracleV2ProbeError(
            "Oracle V2 Anchor discriminator mismatch"
        )

    offset = 8
    admin_bytes = account_data[offset : offset + 32]
    offset += 32

    oracle_pubkey = account_data[offset : offset + 32]
    offset += 32

    decimals = account_data[offset]
    offset += 1
    bump = account_data[offset]
    offset += 1

    assets = {}
    for asset in ASSETS:
        prices = list(struct.unpack_from("<5q", account_data, offset))
        offset += 5 * 8
        timestamps = list(struct.unpack_from("<5q", account_data, offset))
        offset += 5 * 8

        assets[asset] = {
            "prices_raw": prices,
            "prices": [_scaled_i64(price, decimals) for price in prices],
            "timestamps_unix_ms": timestamps,
        }

    if offset != SERIALIZED_STATE_BYTES:
        raise OracleV2ProbeError(
            f"Oracle V2 decoder consumed {offset} bytes, expected "
            f"{SERIALIZED_STATE_BYTES}"
        )

    trailing = account_data[SERIALIZED_STATE_BYTES:]

    return {
        "admin": _b58encode(admin_bytes),
        "oracle_pubkey_base64": base64.b64encode(oracle_pubkey).decode("ascii"),
        "oracle_pubkey_sha256": hashlib.sha256(oracle_pubkey).hexdigest(),
        "decimals": decimals,
        "bump": bump,
        "assets": assets,
        "account_data_length": len(account_data),
        "serialized_state_bytes": SERIALIZED_STATE_BYTES,
        "trailing_allocated_bytes": len(trailing),
        "trailing_nonzero_bytes": sum(byte != 0 for byte in trailing),
        "trailing_sha256": hashlib.sha256(trailing).hexdigest(),
    }


def _parse_account_result(result, address):
    if not isinstance(result, dict):
        raise OracleV2ProbeError(f"{address}: RPC result is not an object")

    context = result.get("context")
    context = context if isinstance(context, dict) else {}

    value = result.get("value")
    if value is None:
        return {
            "address": address,
            "exists": False,
            "context_slot": context.get("slot"),
            "owner": None,
            "executable": None,
            "lamports": None,
            "data": None,
        }

    if not isinstance(value, dict):
        raise OracleV2ProbeError(f"{address}: RPC value is not an object")

    return {
        "address": address,
        "exists": True,
        "context_slot": context.get("slot"),
        "owner": value.get("owner"),
        "executable": value.get("executable"),
        "lamports": value.get("lamports"),
        "data": _decode_base64_account_data(value),
    }


def _slot_observations(decoded_state, observed_at_ms):
    observations = []
    for asset in ASSETS:
        asset_state = decoded_state["assets"][asset]
        for index, (raw_price, timestamp_ms) in enumerate(
            zip(
                asset_state["prices_raw"],
                asset_state["timestamps_unix_ms"],
            ),
            start=1,
        ):
            age_ms = (
                observed_at_ms - timestamp_ms
                if isinstance(timestamp_ms, int) and timestamp_ms > 0
                else None
            )
            observations.append(
                {
                    "asset": asset,
                    "relay_index": index,
                    "price_raw": raw_price,
                    "price": _scaled_i64(
                        raw_price,
                        decoded_state["decimals"],
                    ),
                    "timestamp_unix_ms": timestamp_ms,
                    "age_ms_relative_to_probe_clock": age_ms,
                    "zero_price": raw_price == 0,
                    "timestamp_positive": timestamp_ms > 0,
                    "cmis_price_eligible": raw_price > 0 and timestamp_ms > 0,
                    "freshness_classification": "not_applied",
                }
            )
    return observations


def probe_oracle_v2(
    *,
    rpc_url=DEFAULT_X1_RPC_URL,
    rpc_provider=None,
    observed_at=None,
):
    """Perform the bounded live X1 RPC contract-shape verification."""
    provider = rpc_provider or X1RPCProvider(rpc_url=rpc_url)
    observed_at = observed_at or datetime.now(timezone.utc)
    observed_at_ms = int(observed_at.timestamp() * 1000)

    derived = derive_program_address()
    derived_match = derived["address"] == STATE_PDA

    program_result = provider.request(
        "getAccountInfo",
        [PROGRAM_ID, {"encoding": "base64", "commitment": "confirmed"}],
    )
    state_result = provider.request(
        "getAccountInfo",
        [STATE_PDA, {"encoding": "base64", "commitment": "confirmed"}],
    )

    program = _parse_account_result(program_result, PROGRAM_ID)
    state = _parse_account_result(state_result, STATE_PDA)

    decoded_state = None
    decode_error = None
    if state["exists"]:
        try:
            decoded_state = decode_oracle_state(state["data"])
        except OracleV2ProbeError as exc:
            decode_error = str(exc)

    checks = {
        "pda_derivation_matches_repository_declared_state": derived_match,
        "program_exists": program["exists"],
        "program_executable": program["executable"] is True,
        "state_exists": state["exists"],
        "state_owned_by_program": state["owner"] == PROGRAM_ID,
        "state_not_executable": state["executable"] is False,
        "state_decoded": decoded_state is not None,
        "state_allocated_length_matches_pinned_source": (
            decoded_state is not None
            and decoded_state["account_data_length"] == ALLOCATED_STATE_BYTES
        ),
        "state_decimals_match_pinned_source": (
            decoded_state is not None
            and decoded_state["decimals"] == DECIMALS
        ),
        "state_bump_matches_derived_bump": (
            decoded_state is not None
            and decoded_state["bump"] == derived["bump"]
        ),
        "anchor_discriminator_matches_pinned_source": (
            oracle_state_discriminator() == ORACLE_STATE_DISCRIMINATOR
        ),
    }

    required_checks_pass = all(checks.values())
    observations = (
        _slot_observations(decoded_state, observed_at_ms)
        if decoded_state is not None
        else []
    )

    nonzero_price_slots = sum(
        1 for item in observations if item["price_raw"] > 0
    )
    positive_timestamp_slots = sum(
        1 for item in observations if item["timestamp_positive"]
    )

    warnings = [
        (
            "The pinned upstream program validates timestamp > 0 but does not "
            "enforce freshness or monotonic timestamp progression. CMIS must "
            "apply its own explicit freshness policy before using any price."
        ),
        (
            "The reviewed five relay clients consume a common aggregated "
            "price-feed server; relay-slot agreement is not five-source "
            "independence."
        ),
        (
            "The pinned upstream program accepts zero prices. CMIS treats "
            "zero-price slots as ineligible candidate evidence, not as a "
            "verified market price."
        ),
        (
            "This probe verifies on-chain contract shape only. It does not "
            "prove upstream Pyth/CEX observations, their source independence, "
            "or current price correctness."
        ),
    ]

    return {
        "service": SERVICE,
        "version": VERSION,
        "chain": CHAIN,
        "status": (
            "verified_contract_shape"
            if required_checks_pass
            else "mismatch"
        ),
        "source": {
            "repository": ORACLE_V2_REPOSITORY,
            "pinned_commit": ORACLE_V2_PINNED_COMMIT,
            "rpc_url": rpc_url,
        },
        "observed_at": observed_at.isoformat(),
        "program": {
            key: value
            for key, value in program.items()
            if key != "data"
        },
        "state": {
            key: value
            for key, value in state.items()
            if key != "data"
        },
        "derived_pda": derived,
        "expected": {
            "program_id": PROGRAM_ID,
            "state_pda": STATE_PDA,
            "seed_utf8": ORACLE_SEED.decode("ascii"),
            "decimals": DECIMALS,
            "assets": list(ASSETS),
            "relay_slots_per_asset": NUM_SLOTS,
            "serialized_state_bytes": SERIALIZED_STATE_BYTES,
            "allocated_state_bytes": ALLOCATED_STATE_BYTES,
            "anchor_discriminator_hex": ORACLE_STATE_DISCRIMINATOR.hex(),
        },
        "decoded_state": decoded_state,
        "slot_observations": observations,
        "summary": {
            "total_slots": len(observations),
            "nonzero_price_slots": nonzero_price_slots,
            "positive_timestamp_slots": positive_timestamp_slots,
            "freshness_policy_applied": False,
            "source_independence_verified": False,
            "price_correctness_verified": False,
            "cmis_provider_promoted": False,
        },
        "checks": checks,
        "warnings": warnings,
        "errors": [decode_error] if decode_error else [],
        "promotion": {
            "cmis_promotable": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
            "reason": (
                "Issue #272 tracer-bullet verification only. Freshness, "
                "same-fact comparison, evidence integration, review, and "
                "promotion gates remain outstanding."
            ),
        },
    }


def _write_output(result, output_path):
    payload = json.dumps(result, indent=2, sort_keys=True)
    print(payload)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rpc-url",
        default=os.getenv("X1_RPC_URL", DEFAULT_X1_RPC_URL),
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        result = probe_oracle_v2(rpc_url=args.rpc_url)
    except Exception as exc:
        result = {
            "service": SERVICE,
            "version": VERSION,
            "chain": CHAIN,
            "status": "error",
            "source": {
                "repository": ORACLE_V2_REPOSITORY,
                "pinned_commit": ORACLE_V2_PINNED_COMMIT,
                "rpc_url": args.rpc_url,
            },
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "warnings": [
                "No CMIS capability or live Oracle V2 fact was promoted."
            ],
            "errors": [f"{type(exc).__name__}: {exc}"],
            "promotion": {
                "cmis_promotable": False,
                "public_service_promoted": False,
                "scout_reliance_promoted": False,
                "execution_authorized": False,
            },
        }

    _write_output(result, args.output)
    return 0 if result.get("status") == "verified_contract_shape" else 1


if __name__ == "__main__":
    sys.exit(main())
