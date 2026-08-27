"""Deterministic exact-mint identity helpers for X1 CMIS."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from liquidity_scout.services.cmis_contract import (
    OK,
    PARTIAL,
    UNAVAILABLE,
    build_service_envelope,
)

IDENTITY_CONTRACT = "x1_asset_identity/v1"
IDENTITY_ROOT = "mint"
METAPLEX_DESCRIPTOR_SOURCE = "metaplex_token_metadata"
XDEX_DESCRIPTOR_SOURCE = "xdex_provider"

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {char: index for index, char in enumerate(_BASE58_ALPHABET)}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def decode_base58_pubkey(value: Any) -> bytes | None:
    """Return exactly 32 decoded bytes for a canonical base58 public key."""
    text = _text(value)
    if not text:
        return None

    number = 0
    for char in text:
        digit = _BASE58_INDEX.get(char)
        if digit is None:
            return None
        number = (number * 58) + digit

    leading_zeroes = len(text) - len(text.lstrip("1"))
    payload = (
        b""
        if number == 0
        else number.to_bytes((number.bit_length() + 7) // 8, "big")
    )
    raw = (b"\x00" * leading_zeroes) + payload
    return raw if len(raw) == 32 else None


def is_exact_x1_public_key(value: Any) -> bool:
    return decode_base58_pubkey(value) is not None


def _descriptor_text(value: Any) -> str | None:
    text = _text(value)
    return " ".join(text.split()) if text else None


def _descriptor_key(value: Any) -> str | None:
    text = _descriptor_text(value)
    return text.casefold() if text else None


def exact_xdex_descriptors(mint: str, pools: Any) -> list[dict[str, Any]]:
    """Preserve every unique XDEX descriptor for the exact requested mint."""
    mint_text = _text(mint)
    if not mint_text:
        raise ValueError("mint is required")
    if not isinstance(pools, Sequence) or isinstance(pools, (str, bytes)):
        return []

    by_descriptor: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    for pool in pools:
        if not isinstance(pool, Mapping):
            continue
        for side in ("baseToken", "quoteToken"):
            token = pool.get(side)
            if not isinstance(token, Mapping):
                continue
            token_mint = _text(token.get("mint") or token.get("address"))
            if token_mint != mint_text:
                continue
            symbol = _descriptor_text(token.get("symbol"))
            name = _descriptor_text(token.get("name"))
            key = (_descriptor_key(symbol), _descriptor_key(name))
            by_descriptor.setdefault(
                key,
                {"mint": token_mint, "symbol": symbol, "name": name},
            )
    return [
        by_descriptor[key]
        for key in sorted(by_descriptor, key=lambda item: (item[0] or "", item[1] or ""))
    ]


def _metadata_record(metadata_evidence: Any, *, mint: str) -> dict[str, Any] | None:
    if not isinstance(metadata_evidence, Mapping):
        return None
    if metadata_evidence.get("identity_verified") is not True:
        return None
    metadata = metadata_evidence.get("metadata")
    program = metadata_evidence.get("program")
    if not isinstance(metadata, Mapping) or not isinstance(program, Mapping):
        return None
    if metadata.get("identity_verified") is not True:
        return None
    if _text(metadata.get("mint")) != mint:
        raise ValueError("Metaplex metadata mint does not equal requested mint")
    if program.get("program_executable_verified") is not True:
        raise ValueError("Metaplex program identity is not verified")
    return {
        "mint": mint,
        "symbol": _descriptor_text(metadata.get("symbol")),
        "name": _descriptor_text(metadata.get("name")),
        "uri": _text(metadata.get("uri")),
        "metadata_account": _text(metadata.get("metadata_account")),
        "metadata_update_authority": _text(metadata.get("metadata_update_authority")),
        "is_mutable": (
            metadata.get("is_mutable")
            if isinstance(metadata.get("is_mutable"), bool)
            else None
        ),
        "token_standard": _text(metadata.get("token_standard")),
        "context_slot": metadata.get("context_slot"),
        "program_id": _text(metadata.get("program_id")),
        "program_context_slot": program.get("context_slot"),
        "project_truth_verified": False,
        "uri_contents_verified": False,
    }


def _reconcile_fields(
    metaplex: Mapping[str, Any],
    xdex_variants: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    comparable: list[str] = []
    conflicting: list[str] = []
    if len(xdex_variants) != 1:
        if len(xdex_variants) > 1:
            conflicting.append("xdex_descriptor_variants")
        return comparable, conflicting

    xdex = xdex_variants[0]
    for field in ("symbol", "name"):
        left = _descriptor_key(metaplex.get(field))
        right = _descriptor_key(xdex.get(field))
        if left is None or right is None:
            continue
        comparable.append(field)
        if left != right:
            conflicting.append(field)
    return comparable, conflicting


__all__ = [
    "IDENTITY_CONTRACT",
    "IDENTITY_ROOT",
    "METAPLEX_DESCRIPTOR_SOURCE",
    "XDEX_DESCRIPTOR_SOURCE",
    "decode_base58_pubkey",
    "exact_xdex_descriptors",
    "is_exact_x1_public_key",
]
