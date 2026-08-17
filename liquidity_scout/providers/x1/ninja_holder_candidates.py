"""Surface X1.Ninja holder-looking fields without assigning holder semantics.

The single-pool detail response currently exposes provider fields that may look
holder-related. This adapter performs lexical discovery only: any JSON key whose
name contains ``holder`` is recorded with its path and raw value. It does not
claim that a field counts token accounts, wallets, beneficial owners, or total
asset holders, and it does not bind a holder-looking field to base/quote token
metadata without separate semantic evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


VERSION = "1.0"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _holder_candidates(value: Any, prefix: str = "") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if "holder" in key_text.casefold():
                found.append({"field_path": path, "raw_value": child})
            found.extend(_holder_candidates(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            found.extend(_holder_candidates(child, path))
    return found


def _token_metadata(raw_pool: Mapping[str, Any], name: str) -> dict[str, Any] | None:
    value = raw_pool.get(name)
    if not isinstance(value, Mapping):
        return None
    return {
        "address": _text(value.get("address")),
        "symbol": _text(value.get("symbol")),
        "name": _text(value.get("name")),
        "decimals": value.get("decimals"),
    }


def extract_x1_ninja_holder_candidates(
    pool_detail: Mapping[str, Any],
    *,
    expected_pool_address: Any | None = None,
) -> dict[str, Any]:
    """Extract lexical holder candidates from one raw pool-detail observation."""
    if not isinstance(pool_detail, Mapping):
        raise TypeError("pool_detail must be a mapping")

    errors: list[str] = []
    warnings: list[str] = []

    if pool_detail.get("chain") != "x1":
        errors.append("wrong_chain")

    requested_pool = _text(pool_detail.get("pool_address_requested"))
    expected_pool = _text(expected_pool_address)
    if requested_pool is None:
        errors.append("requested_pool_missing")
    if expected_pool is not None and requested_pool != expected_pool:
        errors.append("requested_pool_scope_mismatch")

    raw_response = pool_detail.get("raw_response")
    if not isinstance(raw_response, Mapping):
        errors.append("raw_response_missing_or_malformed")
        raw_response = {}

    raw_pool = raw_response.get("pool")
    raw_pool = raw_pool if isinstance(raw_pool, Mapping) else {}
    response_pool_address = _text(raw_pool.get("address"))
    if response_pool_address is None:
        warnings.append("response_pool_address_unavailable")
    elif requested_pool is not None and response_pool_address != requested_pool:
        errors.append("response_pool_identity_mismatch")

    candidates = _holder_candidates(raw_response)
    if not candidates:
        warnings.append("no_lexical_holder_fields_observed")

    status = "error" if errors else ("partial" if warnings else "ok")

    return {
        "service": "x1_ninja_holder_candidates",
        "version": VERSION,
        "chain": "x1",
        "status": status,
        "pool_address_requested": requested_pool,
        "pool_address_observed": response_pool_address,
        "provider_observed_at": pool_detail.get("observed_at"),
        "holder_field_candidates": candidates,
        "token_metadata_candidates": {
            "base_token": _token_metadata(raw_pool, "baseToken"),
            "quote_token": _token_metadata(raw_pool, "quoteToken"),
        },
        "pool_identity_transport_consistent": (
            requested_pool is not None
            and response_pool_address is not None
            and requested_pool == response_pool_address
        ),
        "holder_field_semantics_verified": False,
        "holder_field_asset_binding_verified": False,
        "holder_uniqueness_semantics_verified": False,
        "holder_coverage_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
        "warnings": list(dict.fromkeys(warnings)),
        "errors": list(dict.fromkeys(errors)),
    }


__all__ = ["VERSION", "extract_x1_ninja_holder_candidates"]
