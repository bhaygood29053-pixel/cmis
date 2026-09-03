"""Fail-closed Warp rare-account semantic layout discovery.

This slice builds on warp_rare_account_capture/v1.  It uses a pinned public IDL
only as corroborating evidence, then requires exact live owner/space, Anchor
account discriminator, and reproducible PDA identity before assigning an account
TYPE name.  IDL field names remain unpromoted semantic hypotheses.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from collections.abc import Mapping
from typing import Any

from liquidity_scout.providers.x1.warp_onchain_inventory import WARP_PROGRAM_ID
from liquidity_scout.providers.x1.warp_rare_account_capture import (
    CONTRACT as RARE_CAPTURE_CONTRACT,
)

CONTRACT = "warp_semantic_layout_discovery/v1"
IDL_SOURCE_REPOSITORY = "nibty/warp-bridge-dashboard"
IDL_SOURCE_COMMIT = "6a9ea7187879778d3a46e313d1fec177541adce8"
IDL_SOURCE_BLOB_SHA = "59da74924923a7155c5187c35c4a5c559c32ad0b"
IDL_SOURCE_PATH = "src/idl/warp_bridge.json"
IDL_TRUST = "public_third_party_corroboration_only"

_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_PDA_MARKER = b"ProgramDerivedAddress"
_ED25519_P = 2**255 - 19
_ED25519_D = (-121665 * pow(121666, _ED25519_P - 2, _ED25519_P)) % _ED25519_P
_ED25519_I = pow(2, (_ED25519_P - 1) // 4, _ED25519_P)

ACCOUNT_LAYOUTS: dict[str, dict[str, Any]] = {
    "TokenRegistryEntry": {
        "space": 170,
        "discriminator_hex": "c5344915bfef2a86",
        "pda_seed": "token_registry",
        "pda_seed_uses_local_mint": True,
    },
    "Roles": {
        "space": 236,
        "discriminator_hex": "b12511c9f29ed441",
        "pda_seed": "roles",
        "pda_seed_uses_local_mint": False,
    },
    "Config": {
        "space": 321,
        "discriminator_hex": "9b0caae01efacc82",
        "pda_seed": "config",
        "pda_seed_uses_local_mint": False,
    },
    "GuardianSet": {
        "space": 335,
        "discriminator_hex": "784d4a622253607d",
        "pda_seed": "guardian_set",
        "pda_seed_uses_local_mint": False,
    },
}
SPACE_TO_ACCOUNT = {row["space"]: name for name, row in ACCOUNT_LAYOUTS.items()}


class WarpSemanticLayoutError(RuntimeError):
    """Raised when semantic-layout evidence fails closed."""


def anchor_account_discriminator(account_name: str) -> bytes:
    name = str(account_name or "").strip()
    if not name:
        raise ValueError("account_name is required")
    return hashlib.sha256(f"account:{name}".encode("utf-8")).digest()[:8]


def _b58decode(value: str) -> bytes:
    text = str(value or "").strip()
    if not text:
        raise ValueError("base58 value is required")
    number = 0
    for char in text:
        try:
            digit = _BASE58.index(char)
        except ValueError:
            raise ValueError("invalid base58 value") from None
        number = number * 58 + digit
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    pad = len(text) - len(text.lstrip("1"))
    return (b"\x00" * pad) + raw


def _b58encode(raw: bytes) -> str:
    if not isinstance(raw, (bytes, bytearray)):
        raise TypeError("raw must be bytes")
    data = bytes(raw)
    number = int.from_bytes(data, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _BASE58[remainder] + encoded
    pad = len(data) - len(data.lstrip(b"\x00"))
    return ("1" * pad) + encoded


def _ed25519_point_is_on_curve(compressed: bytes) -> bool:
    if len(compressed) != 32:
        return False
    y = int.from_bytes(compressed, "little") & ((1 << 255) - 1)
    sign = compressed[31] >> 7
    if y >= _ED25519_P:
        return False
    y2 = (y * y) % _ED25519_P
    numerator = (y2 - 1) % _ED25519_P
    denominator = (_ED25519_D * y2 + 1) % _ED25519_P
    x2 = numerator * pow(denominator, _ED25519_P - 2, _ED25519_P) % _ED25519_P
    x = pow(x2, (_ED25519_P + 3) // 8, _ED25519_P)
    if (x * x - x2) % _ED25519_P:
        x = x * _ED25519_I % _ED25519_P
    if (x * x - x2) % _ED25519_P:
        return False
    if x == 0 and sign:
        return False
    return True


def create_program_address(seeds: list[bytes], program_id: str = WARP_PROGRAM_ID) -> str:
    if len(seeds) > 16 or any(not isinstance(seed, bytes) or len(seed) > 32 for seed in seeds):
        raise ValueError("invalid PDA seeds")
    program = _b58decode(program_id)
    if len(program) != 32:
        raise ValueError("program_id must decode to 32 bytes")
    digest = hashlib.sha256(b"".join(seeds) + program + _PDA_MARKER).digest()
    if _ed25519_point_is_on_curve(digest):
        raise WarpSemanticLayoutError("derived address is on curve")
    return _b58encode(digest)


def find_program_address(
    seeds: list[bytes], program_id: str = WARP_PROGRAM_ID
) -> tuple[str, int]:
    for bump in range(255, -1, -1):
        try:
            return create_program_address(seeds + [bytes([bump])], program_id), bump
        except WarpSemanticLayoutError:
            continue
    raise WarpSemanticLayoutError("unable to derive PDA")


class _Reader:
    def __init__(self, data: bytes, offset: int = 8):
        self.data = data
        self.offset = offset

    def take(self, count: int) -> bytes:
        end = self.offset + count
        if count < 0 or end > len(self.data):
            raise WarpSemanticLayoutError("account layout exceeds captured bytes")
        value = self.data[self.offset:end]
        self.offset = end
        return value

    def u8(self) -> int:
        return self.take(1)[0]

    def bool(self) -> bool:
        value = self.u8()
        if value not in (0, 1):
            raise WarpSemanticLayoutError("invalid Borsh bool")
        return bool(value)

    def u16(self) -> int:
        return int.from_bytes(self.take(2), "little")

    def u32(self) -> int:
        return int.from_bytes(self.take(4), "little")

    def u64(self) -> int:
        return int.from_bytes(self.take(8), "little")

    def i64(self) -> int:
        return int.from_bytes(self.take(8), "little", signed=True)

    def pubkey(self) -> str:
        return _b58encode(self.take(32))


def _decode_raw(capture: Mapping[str, Any]) -> bytes:
    encoded = capture.get("data_base64")
    if not isinstance(encoded, str) or not encoded:
        raise WarpSemanticLayoutError("ephemeral data_base64 is required")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise WarpSemanticLayoutError("invalid ephemeral base64") from None
    return raw


def _decode_token_registry(raw: bytes) -> dict[str, Any]:
    r = _Reader(raw)
    local_mint = r.pubkey()
    decimals = r.u8()
    is_native = r.bool()
    symbol_raw = r.take(12)
    try:
        symbol = symbol_raw.rstrip(b"\x00").decode("ascii")
    except UnicodeDecodeError:
        symbol = None
    paused = r.bool()
    daily_cap = r.u64()
    daily_volume = r.u64()
    last_reset = r.i64()
    min_amount = r.u64()
    max_amount = r.u64()
    bump = r.u8()
    flat_fee_amount = r.u64()
    percentage_fee_bps = r.u16()
    fee_collector_ata = r.pubkey()
    whale_threshold = r.u64()
    whale_delay_seconds = r.i64()
    reserved = r.take(16)
    return {
        "local_mint": local_mint,
        "decimals": decimals,
        "is_native": is_native,
        "symbol_candidate": symbol,
        "paused_candidate": paused,
        "daily_cap_candidate": daily_cap,
        "daily_volume_candidate": daily_volume,
        "last_reset_candidate": last_reset,
        "min_amount_candidate": min_amount,
        "max_amount_candidate": max_amount,
        "bump": bump,
        "flat_fee_amount_candidate": flat_fee_amount,
        "percentage_fee_bps_candidate": percentage_fee_bps,
        "fee_collector_ata_candidate": fee_collector_ata,
        "whale_threshold_candidate": whale_threshold,
        "whale_delay_seconds_candidate": whale_delay_seconds,
        "reserved_all_zero": not any(reserved),
    }


def _decode_guardian_set(raw: bytes) -> dict[str, Any]:
    r = _Reader(raw)
    index = r.u32()
    num_guardians = r.u8()
    threshold = r.u8()
    guardians = [r.pubkey() for _ in range(9)]
    bump = r.u8()
    reserved = r.take(32)
    if num_guardians > 9 or threshold > num_guardians:
        raise WarpSemanticLayoutError("guardian cardinality is invalid")
    return {
        "guardian_set_index_candidate": index,
        "num_guardians_candidate": num_guardians,
        "threshold_candidate": threshold,
        "active_guardians_candidate": guardians[:num_guardians],
        "bump": bump,
        "reserved_all_zero": not any(reserved),
    }


def _decode_roles(raw: bytes) -> dict[str, Any]:
    r = _Reader(raw)

    def option_pubkey() -> str | None:
        tag = r.u8()
        if tag == 0:
            return None
        if tag == 1:
            return r.pubkey()
        raise WarpSemanticLayoutError("invalid Borsh option tag")

    pauser = option_pubkey()
    fee_manager = option_pubkey()
    registrar = option_pubkey()
    bump = r.u8()
    reserved = r.take(128)
    trailing = raw[r.offset:]
    return {
        "pauser_candidate": pauser,
        "fee_manager_candidate": fee_manager,
        "registrar_candidate": registrar,
        "bump": bump,
        "reserved_all_zero": not any(reserved),
        "trailing_padding_all_zero": not any(trailing),
    }


def _decode_config(raw: bytes) -> dict[str, Any]:
    r = _Reader(raw)
    admin = r.pubkey()
    paused = r.bool()
    guardians = [r.pubkey() for _ in range(5)]
    num_guardians = r.u8()
    threshold = r.u8()
    out_seq_counter = r.u64()
    in_seq_counter = r.u64()
    flat_fee_lamports = r.u64()
    percentage_fee_bps = r.u16()
    fee_collector = r.pubkey()
    bump = r.u8()
    paused_at = r.i64()
    paused_by = r.pubkey()

    pause_variant = r.u8()
    pause_reason_code = r.u16() if pause_variant == 7 else None
    if pause_variant > 7:
        raise WarpSemanticLayoutError("invalid pause reason enum variant")

    chain_id = r.u8()
    v1_in_disabled = r.bool()
    reserved = r.take(14)
    trailing = raw[r.offset:]

    if num_guardians > 5 or threshold > num_guardians:
        raise WarpSemanticLayoutError("config guardian cardinality is invalid")

    return {
        "admin_candidate": admin,
        "paused_candidate": paused,
        "active_guardians_candidate": guardians[:num_guardians],
        "num_guardians_candidate": num_guardians,
        "threshold_candidate": threshold,
        "out_seq_counter_candidate": out_seq_counter,
        "in_seq_counter_candidate": in_seq_counter,
        "flat_fee_lamports_candidate": flat_fee_lamports,
        "percentage_fee_bps_candidate": percentage_fee_bps,
        "fee_collector_candidate": fee_collector,
        "bump": bump,
        "paused_at_candidate": paused_at,
        "paused_by_candidate": paused_by,
        "pause_reason_variant_candidate": pause_variant,
        "pause_reason_code_candidate": pause_reason_code,
        "chain_id_candidate": chain_id,
        "v1_in_disabled_candidate": v1_in_disabled,
        "reserved_all_zero": not any(reserved),
        "trailing_padding_all_zero": not any(trailing),
    }


_DECODERS = {
    "TokenRegistryEntry": _decode_token_registry,
    "Roles": _decode_roles,
    "Config": _decode_config,
    "GuardianSet": _decode_guardian_set,
}


def classify_rare_account(capture: Any) -> dict[str, Any]:
    if not isinstance(capture, Mapping):
        raise ValueError("capture must be a mapping")
    if capture.get("contract") != RARE_CAPTURE_CONTRACT:
        raise ValueError(f"capture must use {RARE_CAPTURE_CONTRACT}")
    chain = capture.get("chain")
    if chain not in {"solana", "x1"}:
        raise ValueError("capture.chain must be solana or x1")
    if capture.get("program_id") != WARP_PROGRAM_ID:
        raise WarpSemanticLayoutError("capture program id is not Warp")
    if capture.get("owner_verified") is not True:
        raise WarpSemanticLayoutError("Warp owner must already be verified")
    if capture.get("data_length_verified") is not True:
        raise WarpSemanticLayoutError("capture byte length must already be verified")
    if capture.get("non_executable_verified") is not True:
        raise WarpSemanticLayoutError("capture must be non-executable")

    pubkey = capture.get("pubkey")
    space = capture.get("inventory_space")
    if not isinstance(pubkey, str) or not pubkey:
        raise WarpSemanticLayoutError("capture pubkey is required")
    if space not in SPACE_TO_ACCOUNT:
        raise WarpSemanticLayoutError("capture space is not a recognized rare family")

    account_name = SPACE_TO_ACCOUNT[space]
    layout = ACCOUNT_LAYOUTS[account_name]
    raw = _decode_raw(capture)
    if len(raw) != space:
        raise WarpSemanticLayoutError("raw byte length does not match rare family")

    expected_discriminator = anchor_account_discriminator(account_name)
    if expected_discriminator.hex() != layout["discriminator_hex"]:
        raise WarpSemanticLayoutError("pinned discriminator does not match Anchor derivation")
    discriminator = raw[:8]
    discriminator_verified = discriminator == expected_discriminator
    if not discriminator_verified:
        raise WarpSemanticLayoutError("live account discriminator does not match layout")

    decoded = _DECODERS[account_name](raw)

    if account_name == "TokenRegistryEntry":
        mint_bytes = _b58decode(decoded["local_mint"])
        expected_pubkey, expected_bump = find_program_address(
            [b"token_registry", mint_bytes]
        )
    else:
        expected_pubkey, expected_bump = find_program_address(
            [layout["pda_seed"].encode("ascii")]
        )

    pda_verified = pubkey == expected_pubkey
    bump_verified = decoded.get("bump") == expected_bump
    if not pda_verified:
        raise WarpSemanticLayoutError("live account pubkey does not match derived PDA")
    if not bump_verified:
        raise WarpSemanticLayoutError("decoded bump does not match derived PDA bump")

    return {
        "contract": CONTRACT,
        "chain": chain,
        "pubkey": pubkey,
        "space": space,
        "account_name": account_name,
        "anchor_discriminator_hex": discriminator.hex(),
        "anchor_discriminator_verified": True,
        "pda_expected": expected_pubkey,
        "pda_bump_expected": expected_bump,
        "pda_identity_verified": True,
        "pda_bump_verified": True,
        "account_type_identity_verified": True,
        "decoded_fields": decoded,
        "field_layout_corroborated": True,
        "field_semantics_verified": False,
        "source_provenance": {
            "repository": IDL_SOURCE_REPOSITORY,
            "commit": IDL_SOURCE_COMMIT,
            "blob_sha": IDL_SOURCE_BLOB_SHA,
            "path": IDL_SOURCE_PATH,
            "trust": IDL_TRUST,
        },
        "account_role_verified": False,
        "route_semantics_verified": False,
        "bridge_health_verified": False,
        "semantic_contract_accepted": False,
        "cmis_promotable": False,
        "read_only": True,
        "execution_authorized": False,
    }


def discover_warp_semantic_layout(capture_result: Any) -> dict[str, Any]:
    if not isinstance(capture_result, Mapping):
        raise ValueError("capture_result must be a mapping")
    if capture_result.get("contract") != RARE_CAPTURE_CONTRACT:
        raise ValueError(f"capture_result must use {RARE_CAPTURE_CONTRACT}")

    result: dict[str, Any] = {}
    for chain, key in (("solana", "solana_capture"), ("x1", "x1_capture")):
        source = capture_result.get(key)
        if not isinstance(source, Mapping) or source.get("chain") != chain:
            raise WarpSemanticLayoutError(f"{key} is missing or invalid")
        rows = source.get("captures")
        if not isinstance(rows, list) or not rows:
            raise WarpSemanticLayoutError(f"{key}.captures is missing")
        classified = [classify_rare_account(row) for row in rows]
        counts: dict[str, int] = {}
        for row in classified:
            counts[row["account_name"]] = counts.get(row["account_name"], 0) + 1

        for singleton in ("Config", "GuardianSet", "Roles"):
            if counts.get(singleton) != 1:
                raise WarpSemanticLayoutError(
                    f"{chain} must contain exactly one {singleton} rare account"
                )
        if counts.get("TokenRegistryEntry", 0) < 1:
            raise WarpSemanticLayoutError(
                f"{chain} must contain at least one TokenRegistryEntry"
            )

        result[chain] = {
            "classified_count": len(classified),
            "account_type_counts": dict(sorted(counts.items())),
            "accounts": classified,
            "all_account_type_identities_verified": all(
                row["account_type_identity_verified"] for row in classified
            ),
            "all_pda_identities_verified": all(
                row["pda_identity_verified"] for row in classified
            ),
        }

    def one(chain: str, account_name: str) -> Mapping[str, Any]:
        matches = [
            row for row in result[chain]["accounts"]
            if row["account_name"] == account_name
        ]
        if len(matches) != 1:
            raise WarpSemanticLayoutError(
                f"{chain} must have exactly one {account_name}"
            )
        return matches[0]

    config_sol = one("solana", "Config")
    config_x1 = one("x1", "Config")
    guardian_sol = one("solana", "GuardianSet")
    guardian_x1 = one("x1", "GuardianSet")
    roles_sol = one("solana", "Roles")
    roles_x1 = one("x1", "Roles")

    comparison = {
        "config_same_pubkey": config_sol["pubkey"] == config_x1["pubkey"],
        "guardian_set_same_pubkey": guardian_sol["pubkey"] == guardian_x1["pubkey"],
        "roles_same_pubkey": roles_sol["pubkey"] == roles_x1["pubkey"],
        "config_chain_id_candidates": {
            "solana": config_sol["decoded_fields"]["chain_id_candidate"],
            "x1": config_x1["decoded_fields"]["chain_id_candidate"],
        },
        "guardian_set_index_candidates": {
            "solana": guardian_sol["decoded_fields"]["guardian_set_index_candidate"],
            "x1": guardian_x1["decoded_fields"]["guardian_set_index_candidate"],
        },
        "guardian_threshold_candidates": {
            "solana": guardian_sol["decoded_fields"]["threshold_candidate"],
            "x1": guardian_x1["decoded_fields"]["threshold_candidate"],
        },
        "roles_bytes_may_match_without_semantic_promotion": True,
    }

    return {
        "contract": CONTRACT,
        "source_capture_contract": RARE_CAPTURE_CONTRACT,
        "program_id": WARP_PROGRAM_ID,
        "solana": result["solana"],
        "x1": result["x1"],
        "comparison": comparison,
        "account_type_identity_verified": (
            result["solana"]["all_account_type_identities_verified"]
            and result["x1"]["all_account_type_identities_verified"]
        ),
        "pda_identity_verified": (
            result["solana"]["all_pda_identities_verified"]
            and result["x1"]["all_pda_identities_verified"]
        ),
        "field_layout_corroborated": True,
        "field_semantics_verified": False,
        "account_role_verified": False,
        "route_semantics_verified": False,
        "bridge_health_verified": False,
        "semantic_contract_accepted": False,
        "cmis_promotable": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "ACCOUNT_LAYOUTS",
    "CONTRACT",
    "IDL_SOURCE_BLOB_SHA",
    "IDL_SOURCE_COMMIT",
    "IDL_SOURCE_PATH",
    "IDL_SOURCE_REPOSITORY",
    "IDL_TRUST",
    "WarpSemanticLayoutError",
    "anchor_account_discriminator",
    "classify_rare_account",
    "create_program_address",
    "discover_warp_semantic_layout",
    "find_program_address",
]
