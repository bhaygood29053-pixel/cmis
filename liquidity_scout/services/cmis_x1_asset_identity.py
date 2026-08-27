"""Deterministic exact-mint identity helpers for X1 CMIS."""

from __future__ import annotations

from typing import Any

IDENTITY_CONTRACT = "x1_asset_identity/v1"
IDENTITY_ROOT = "mint"

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


__all__ = [
    "IDENTITY_CONTRACT",
    "IDENTITY_ROOT",
    "decode_base58_pubkey",
    "is_exact_x1_public_key",
]
