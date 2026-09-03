"""Bounded semantic adapter for the official Warp bridge config endpoint.

The accepted endpoint is:
https://app.bridge.x1.xyz/api/bridge/config

This adapter proves only semantics directly represented by that machine response:
- exact chain-scoped token mint identity;
- route pause/active state derived from exact chain + token pause booleans;
- provider-declared native/non-native representation topology;
- configured guardian quorum dependency;
- fetchedAt timestamp in milliseconds.

It does not prove reserve sufficiency, legal custody, guardian honesty, route
availability beyond the freshness window, or execution safety.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

WARP_CONFIG_SEMANTICS_CONTRACT = "warp_config_semantics/v1"
WARP_CONFIG_SEMANTIC_CONTRACT_ID = "warp_config/exact-mint-pair/v1"
WARP_CONFIG_SOURCE_URL = "https://app.bridge.x1.xyz/api/bridge/config"
WARP_PROGRAM_ID = "6JbPTuxVuoTgyQeXFb9MH8C8nUY8NBbLP1Lu4B13JfMD"

# Canonical JSON hash for the 2026-09-03 fixture supplied from the exact
# provenance-approved endpoint. Canonicalization uses sort_keys=True and
# separators=(",", ":").
ACCEPTED_FIXTURE_CANONICAL_SHA256 = (
    "b8ce53645c1f9495171bea65fa4a59588dfb2bae4a36227b39a05a4ae4f38687"
)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    return value


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be boolean")
    return value


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be positive")
    return parsed


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _chain_block(document: Mapping[str, Any], chain: str) -> Mapping[str, Any]:
    if chain not in {"solana", "x1"}:
        raise ValueError("chain must be solana or x1")
    return _mapping(document.get(chain), chain)


def _validate_config(chain_block: Mapping[str, Any], chain: str) -> Mapping[str, Any]:
    config = _mapping(chain_block.get("config"), f"{chain}.config")
    if _text(config.get("programId"), f"{chain}.config.programId") != WARP_PROGRAM_ID:
        raise ValueError(f"{chain}.config.programId must equal exact Warp program id")

    paused = config.get("paused")
    _bool(paused, f"{chain}.config.paused")

    guardians = config.get("guardians")
    if not isinstance(guardians, list) or not guardians:
        raise ValueError(f"{chain}.config.guardians must be a non-empty list")
    normalized_guardians = [_text(item, f"{chain}.config.guardians[]") for item in guardians]
    if len(set(normalized_guardians)) != len(normalized_guardians):
        raise ValueError(f"{chain}.config.guardians must not contain duplicates")

    threshold = _positive_int(config.get("threshold"), f"{chain}.config.threshold")
    if threshold > len(normalized_guardians):
        raise ValueError(f"{chain}.config.threshold cannot exceed guardian count")

    return config


def _find_exact_token(
    chain_block: Mapping[str, Any],
    *,
    chain: str,
    mint: str,
) -> Mapping[str, Any]:
    tokens = chain_block.get("tokens")
    if not isinstance(tokens, list):
        raise ValueError(f"{chain}.tokens must be a list")

    matches = []
    for item in tokens:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("mint") or "").strip() == mint:
            matches.append(item)

    if len(matches) != 1:
        raise ValueError(
            f"{chain}.tokens must contain exactly one entry for mint {mint}"
        )
    token = matches[0]
    _text(token.get("symbol"), f"{chain}.token.symbol")
    _bool(token.get("isNative"), f"{chain}.token.isNative")
    _bool(token.get("paused"), f"{chain}.token.paused")
    _positive_int(token.get("decimals"), f"{chain}.token.decimals")
    return token


def _endpoint(value: Any, field: str) -> dict[str, str]:
    mapped = _mapping(value, field)
    chain = _text(mapped.get("chain"), f"{field}.chain").casefold()
    if chain not in {"solana", "x1"}:
        raise ValueError(f"{field}.chain must be solana or x1")
    asset_id = _text(mapped.get("asset_id"), f"{field}.asset_id")
    kind = _text(mapped.get("asset_id_kind"), f"{field}.asset_id_kind").casefold()
    if kind != "mint":
        raise ValueError(f"{field}.asset_id_kind must be mint")
    return {"chain": chain, "asset_id": asset_id, "asset_id_kind": "mint"}


def build_warp_config_route_observation(
    *,
    config_response: Any,
    route_id: Any,
    source: Any,
    destination: Any,
    collected_at: Any = None,
) -> dict[str, Any]:
    """Build a route-evidence observation from the exact official config response.

    Route identity is never inferred from symbols. The caller supplies the exact
    route id and chain-scoped mint endpoints already accepted by provenance.
    """

    document = _mapping(config_response, "config_response")
    source_ep = _endpoint(source, "source")
    destination_ep = _endpoint(destination, "destination")
    if source_ep["chain"] == destination_ep["chain"]:
        raise ValueError("source and destination must be different chains")

    source_block = _chain_block(document, source_ep["chain"])
    destination_block = _chain_block(document, destination_ep["chain"])
    source_config = _validate_config(source_block, source_ep["chain"])
    destination_config = _validate_config(destination_block, destination_ep["chain"])

    source_token = _find_exact_token(
        source_block,
        chain=source_ep["chain"],
        mint=source_ep["asset_id"],
    )
    destination_token = _find_exact_token(
        destination_block,
        chain=destination_ep["chain"],
        mint=destination_ep["asset_id"],
    )

    source_decimals = _positive_int(
        source_token.get("decimals"),
        f"{source_ep['chain']}.token.decimals",
    )
    destination_decimals = _positive_int(
        destination_token.get("decimals"),
        f"{destination_ep['chain']}.token.decimals",
    )
    if source_decimals != destination_decimals:
        raise ValueError("source and destination token decimals must match")

    fetched_at_ms = _positive_int(document.get("fetchedAt"), "fetchedAt")
    source_observed_at = fetched_at_ms / 1000.0

    if collected_at is None:
        collection_epoch = source_observed_at
    else:
        try:
            collection_epoch = float(collected_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("collected_at must be numeric epoch seconds") from exc
        if collection_epoch <= 0:
            raise ValueError("collected_at must be positive")
        if collection_epoch < source_observed_at:
            raise ValueError("collected_at cannot predate fetchedAt")

    global_paused = (
        _bool(source_config.get("paused"), f"{source_ep['chain']}.config.paused")
        or _bool(
            destination_config.get("paused"),
            f"{destination_ep['chain']}.config.paused",
        )
    )
    token_paused = (
        _bool(source_token.get("paused"), f"{source_ep['chain']}.token.paused")
        or _bool(
            destination_token.get("paused"),
            f"{destination_ep['chain']}.token.paused",
        )
    )
    route_status = "paused" if (global_paused or token_paused) else "active"

    source_native = _bool(
        source_token.get("isNative"),
        f"{source_ep['chain']}.token.isNative",
    )
    destination_native = _bool(
        destination_token.get("isNative"),
        f"{destination_ep['chain']}.token.isNative",
    )
    if source_native and not destination_native:
        backing_model = "provider_config_native_source_to_non_native_destination"
    elif not source_native and destination_native:
        backing_model = "provider_config_non_native_source_to_native_destination"
    else:
        backing_model = (
            "provider_config_native_to_native"
            if source_native
            else "provider_config_non_native_to_non_native"
        )

    source_guardians = source_config.get("guardians")
    destination_guardians = destination_config.get("guardians")
    source_threshold = _positive_int(
        source_config.get("threshold"),
        f"{source_ep['chain']}.config.threshold",
    )
    destination_threshold = _positive_int(
        destination_config.get("threshold"),
        f"{destination_ep['chain']}.config.threshold",
    )
    custody_dependency = (
        "guardian_quorum:"
        f"{source_ep['chain']}={source_threshold}/{len(source_guardians)};"
        f"{destination_ep['chain']}={destination_threshold}/{len(destination_guardians)}"
    )

    return {
        "contract": WARP_CONFIG_SEMANTICS_CONTRACT,
        "provider": "warp_bridge",
        "bridge": "Warp Bridge",
        "route_id": _text(route_id, "route_id"),
        "source": source_ep,
        "destination": destination_ep,
        "source_url": WARP_CONFIG_SOURCE_URL,
        "semantic_contract_id": WARP_CONFIG_SEMANTIC_CONTRACT_ID,
        "route_status": route_status,
        "backing_model": backing_model,
        "custody_dependency": custody_dependency,
        "source_observed_at": source_observed_at,
        "collected_at": collection_epoch,
        "source_timestamp_field": "fetchedAt",
        "source_timestamp_unit": "milliseconds",
        "program_id": WARP_PROGRAM_ID,
        "source_symbol": source_token["symbol"],
        "destination_symbol": destination_token["symbol"],
        "source_is_native": source_native,
        "destination_is_native": destination_native,
        "source_decimals": source_decimals,
        "destination_decimals": destination_decimals,
        "route_decimals": source_decimals,
        "source_guardian_threshold": source_threshold,
        "source_guardian_count": len(source_guardians),
        "destination_guardian_threshold": destination_threshold,
        "destination_guardian_count": len(destination_guardians),
        "fixture_canonical_sha256": canonical_sha256(document),
        "backing_reserve_sufficiency_verified": False,
        "legal_custodian_identity_verified": False,
        "guardian_honesty_verified": False,
        "execution_authorized": False,
    }


__all__ = [
    "ACCEPTED_FIXTURE_CANONICAL_SHA256",
    "WARP_CONFIG_SEMANTICS_CONTRACT",
    "WARP_CONFIG_SEMANTIC_CONTRACT_ID",
    "WARP_CONFIG_SOURCE_URL",
    "WARP_PROGRAM_ID",
    "build_warp_config_route_observation",
    "canonical_sha256",
]
