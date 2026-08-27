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


def _sources(
    *,
    metaplex: Mapping[str, Any] | None,
    xdex_source: Any,
    xdex_observed_at: Any,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    if metaplex is not None:
        sources.append(
            {
                "source": "X1 RPC / Metaplex Token Metadata",
                "role": "descriptive_identity_metadata",
                "context_slot": metaplex.get("context_slot"),
                "program_id": metaplex.get("program_id"),
            }
        )
    source = _text(xdex_source)
    if source:
        record: dict[str, Any] = {
            "source": source,
            "role": "market_representation",
        }
        if xdex_observed_at is not None:
            record["observed_at"] = xdex_observed_at
        sources.append(record)
    return sources


def _confidence(
    *,
    metaplex_verified: bool,
    descriptor_conflict: bool,
) -> dict[str, Any]:
    checks = {
        "exact_mint_identity": True,
        "metaplex_mint_bound": metaplex_verified,
        "descriptor_conflict_absent": not descriptor_conflict,
    }
    verified = sum(1 for value in checks.values() if value is True)
    return {
        "complete": bool(metaplex_verified and not descriptor_conflict),
        "verified_checks": verified,
        "total_checks": len(checks),
        "verification_ratio": verified / len(checks),
        "checks": checks,
    }


def build_exact_mint_identity_response(
    mint: Any,
    *,
    metadata_evidence: Any,
    xdex_pools: Any = None,
    xdex_source: Any = None,
    xdex_observed_at: Any = None,
) -> dict[str, Any]:
    """Return one mint-rooted CMIS identity response."""
    mint_text = _text(mint)
    if not mint_text or not is_exact_x1_public_key(mint_text):
        raise ValueError("exact X1 mint must be a valid 32-byte base58 public key")

    metaplex = _metadata_record(metadata_evidence, mint=mint_text)
    xdex_variants = exact_xdex_descriptors(mint_text, xdex_pools)

    if metaplex is None:
        selected = xdex_variants[0] if len(xdex_variants) == 1 else {}
        status = PARTIAL if xdex_variants else UNAVAILABLE
        return build_service_envelope(
            "asset_lookup",
            "x1",
            status,
            asset={
                "mint": mint_text,
                "symbol": selected.get("symbol"),
                "name": selected.get("name"),
            },
            data={
                "query": mint_text,
                "resolved_term": mint_text,
                "resolved_by": "mint",
                "identity_key": mint_text,
                "identity_contract": IDENTITY_CONTRACT,
                "normalized_identity": {
                    "mint": mint_text,
                    "symbol": selected.get("symbol"),
                    "name": selected.get("name"),
                    "identity_root": IDENTITY_ROOT,
                    "descriptor_source": (
                        XDEX_DESCRIPTOR_SOURCE if len(xdex_variants) == 1 else None
                    ),
                    "normalized_onchain_identity_verified": False,
                },
                "identity_reconciliation": {
                    "state": "metadata_unavailable",
                    "comparable_fields": [],
                    "conflicting_fields": (
                        ["xdex_descriptor_variants"]
                        if len(xdex_variants) > 1
                        else []
                    ),
                    "metaplex": None,
                    "xdex": {
                        "present": bool(xdex_variants),
                        "variants": xdex_variants,
                    },
                },
            },
            confidence=_confidence(
                metaplex_verified=False,
                descriptor_conflict=len(xdex_variants) > 1,
            ),
            sources=_sources(
                metaplex=None,
                xdex_source=xdex_source,
                xdex_observed_at=xdex_observed_at,
            ),
            observed_at=xdex_observed_at,
            warnings=[
                {
                    "code": "x1_metadata_identity_unavailable",
                    "message": (
                        "CMIS could not verify normalized on-chain Metaplex "
                        "descriptors for the exact mint."
                    ),
                }
            ],
        )

    comparable, conflicting = _reconcile_fields(metaplex, xdex_variants)
    if not xdex_variants:
        state = "metaplex_only"
    elif conflicting:
        state = "descriptor_conflict"
    else:
        state = "agreement"

    warnings = []
    if conflicting:
        warnings.append(
            {
                "code": "x1_asset_descriptor_conflict",
                "message": (
                    "Metaplex and XDEX refer to the same exact mint but expose "
                    "conflicting descriptive identity fields."
                ),
            }
        )

    return build_service_envelope(
        "asset_lookup",
        "x1",
        PARTIAL if conflicting else OK,
        asset={
            "mint": mint_text,
            "symbol": metaplex.get("symbol"),
            "name": metaplex.get("name"),
        },
        data={
            "query": mint_text,
            "resolved_term": mint_text,
            "resolved_by": "mint",
            "identity_key": mint_text,
            "identity_contract": IDENTITY_CONTRACT,
            "normalized_identity": {
                "mint": mint_text,
                "symbol": metaplex.get("symbol"),
                "name": metaplex.get("name"),
                "identity_root": IDENTITY_ROOT,
                "descriptor_source": METAPLEX_DESCRIPTOR_SOURCE,
                "normalized_onchain_identity_verified": True,
            },
            "identity_reconciliation": {
                "state": state,
                "comparable_fields": comparable,
                "conflicting_fields": conflicting,
                "metaplex": metaplex,
                "xdex": {
                    "present": bool(xdex_variants),
                    "variants": xdex_variants,
                },
            },
        },
        confidence=_confidence(
            metaplex_verified=True,
            descriptor_conflict=bool(conflicting),
        ),
        sources=_sources(
            metaplex=metaplex,
            xdex_source=xdex_source,
            xdex_observed_at=xdex_observed_at,
        ),
        observed_at=xdex_observed_at,
        warnings=warnings,
        errors=[],
    )


__all__ = [
    "IDENTITY_CONTRACT",
    "IDENTITY_ROOT",
    "METAPLEX_DESCRIPTOR_SOURCE",
    "XDEX_DESCRIPTOR_SOURCE",
    "build_exact_mint_identity_response",
    "decode_base58_pubkey",
    "exact_xdex_descriptors",
    "is_exact_x1_public_key",
]
