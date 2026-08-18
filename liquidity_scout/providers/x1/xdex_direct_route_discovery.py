"""Fail-closed read-only discovery of direct XDEX routes for explicit token pairs.

The XDEX public pool catalog is used only to shortlist candidate pool addresses.
Every candidate that can affect the result is re-read from X1 and must satisfy
the accepted XDEX pool/config/vault structure plus positive active reserves.

A unique verified direct candidate may be returned as an exact route. Multiple
verified candidates are reported as ambiguous and are never ranked or selected.
This module performs no quote, route-quality, multi-hop, prepare, simulation,
signing, broadcasting, custody, execution, or value-moving work.
"""

from __future__ import annotations

from collections.abc import Mapping
import struct
from typing import Any, Callable

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.rpc import get_token_account_info
from liquidity_scout.providers.x1.xdex import fetch_pool_list
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import X1_PROGRAM


CHAIN = "x1"
SOURCE = "XDEX direct-route discovery"
VERSION = "1.0"
POOL_STATE_LENGTH = 637
CONFIG_MIN_LENGTH = 116


class XDEXDirectRouteDiscoveryError(RuntimeError):
    """Raised when discovery transport/input cannot be evaluated safely."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a normalized non-empty string")
    text = value.strip()
    if not text or text != value:
        raise ValueError(f"{field} must be a normalized non-empty string")
    return text


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _pubkey(data: bytes, offset: int) -> str:
    return encode_base58_pubkey(data[offset : offset + 32])


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def _catalog_token_identities(token: Any) -> frozenset[str]:
    """Return every explicit catalog identity for one token side.

    XDEX catalog rows have exposed both ``mint`` and ``address``. They are only
    discovery hints, so either may shortlist a row. Exact trust is established
    later by decoding the pool account's on-chain mint slots.
    """
    if not isinstance(token, Mapping):
        return frozenset()
    identities = {
        text
        for text in (
            _optional_text(token.get("mint")),
            _optional_text(token.get("address")),
        )
        if text
    }
    return frozenset(identities)


def _catalog_candidate_addresses(
    rows: Any,
    token_in_mint: str,
    token_out_mint: str,
) -> list[str]:
    if not isinstance(rows, list):
        raise XDEXDirectRouteDiscoveryError("XDEX pool catalog must be a list")
    addresses: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        base_ids = _catalog_token_identities(row.get("baseToken"))
        quote_ids = _catalog_token_identities(row.get("quoteToken"))
        directional_match = (
            token_in_mint in base_ids and token_out_mint in quote_ids
        ) or (
            token_out_mint in base_ids and token_in_mint in quote_ids
        )
        if not directional_match:
            continue
        address = _optional_text(row.get("address"))
        if address and address not in addresses:
            addresses.append(address)
    return addresses


def _decode_pool(account: Mapping[str, Any], pool: str) -> dict[str, Any]:
    if account.get("owner") != X1_PROGRAM:
        raise XDEXDirectRouteDiscoveryError("candidate pool owner is not the accepted XDEX program")
    data = account.get("data")
    if not isinstance(data, (bytes, bytearray)) or len(data) != POOL_STATE_LENGTH:
        raise XDEXDirectRouteDiscoveryError("candidate pool does not match the accepted 637-byte layout")
    raw = bytes(data)
    return {
        "pool": pool,
        "amm_config": _pubkey(raw, 8),
        "vault_0": _pubkey(raw, 72),
        "vault_1": _pubkey(raw, 104),
        "mint_0": _pubkey(raw, 168),
        "mint_1": _pubkey(raw, 200),
        "protocol_fees_0": _u64(raw, 341),
        "protocol_fees_1": _u64(raw, 349),
        "fund_fees_0": _u64(raw, 357),
        "fund_fees_1": _u64(raw, 365),
        "creator_fees_0": _u64(raw, 397),
        "creator_fees_1": _u64(raw, 405),
    }


def _verify_config(account: Any, amm_config: str) -> None:
    if not isinstance(account, Mapping):
        raise XDEXDirectRouteDiscoveryError("candidate AMM config account is unavailable")
    if account.get("owner") != X1_PROGRAM:
        raise XDEXDirectRouteDiscoveryError("candidate AMM config owner is not the accepted XDEX program")
    data = account.get("data")
    if not isinstance(data, (bytes, bytearray)) or len(data) < CONFIG_MIN_LENGTH:
        raise XDEXDirectRouteDiscoveryError("candidate AMM config does not match the accepted layout")
    trade_fee_rate_ppm = _u64(bytes(data), 12)
    if trade_fee_rate_ppm >= 1_000_000:
        raise XDEXDirectRouteDiscoveryError("candidate AMM config trade fee rate is invalid")


def _vault_raw_amount(fetcher: Callable[[str], Any], vault: str, mint: str) -> int:
    record = fetcher(vault)
    if not isinstance(record, Mapping) or record.get("identity_verified") is not True:
        raise XDEXDirectRouteDiscoveryError("candidate pool vault identity is not verified")
    if record.get("mint") != mint:
        raise XDEXDirectRouteDiscoveryError("candidate pool vault mint does not match pool state")
    raw_amount = record.get("raw_amount")
    if isinstance(raw_amount, bool):
        raise XDEXDirectRouteDiscoveryError("candidate pool vault raw amount is invalid")
    try:
        amount = int(raw_amount)
    except (TypeError, ValueError) as exc:
        raise XDEXDirectRouteDiscoveryError("candidate pool vault raw amount is invalid") from exc
    if amount < 0:
        raise XDEXDirectRouteDiscoveryError("candidate pool vault raw amount is invalid")
    return amount


def _verified_candidate(
    pool: str,
    token_in_mint: str,
    token_out_mint: str,
    *,
    account_state_fetcher: Callable[[str], Any],
    token_account_fetcher: Callable[[str], Any],
) -> dict[str, Any]:
    state = account_state_fetcher(pool)
    if not isinstance(state, Mapping):
        raise XDEXDirectRouteDiscoveryError("candidate pool account is unavailable")
    decoded = _decode_pool(state, pool)
    if {decoded["mint_0"], decoded["mint_1"]} != {token_in_mint, token_out_mint}:
        raise XDEXDirectRouteDiscoveryError("candidate on-chain mint pair does not match requested pair")

    config_state = account_state_fetcher(decoded["amm_config"])
    _verify_config(config_state, decoded["amm_config"])

    gross_0 = _vault_raw_amount(token_account_fetcher, decoded["vault_0"], decoded["mint_0"])
    gross_1 = _vault_raw_amount(token_account_fetcher, decoded["vault_1"], decoded["mint_1"])
    active_0 = gross_0 - decoded["protocol_fees_0"] - decoded["fund_fees_0"] - decoded["creator_fees_0"]
    active_1 = gross_1 - decoded["protocol_fees_1"] - decoded["fund_fees_1"] - decoded["creator_fees_1"]
    if active_0 <= 0 or active_1 <= 0:
        raise XDEXDirectRouteDiscoveryError("candidate pool active reserves are not positive")

    reserve_in = active_0 if decoded["mint_0"] == token_in_mint else active_1
    reserve_out = active_1 if decoded["mint_1"] == token_out_mint else active_0
    return {
        "pool": pool,
        "amm_config": decoded["amm_config"],
        "token_in_mint": token_in_mint,
        "token_out_mint": token_out_mint,
        "active_reserve_in_raw": reserve_in,
        "active_reserve_out_raw": reserve_out,
        "pool_state_verified": True,
        "amm_config_verified": True,
        "vault_identity_verified": True,
        "active_reserves_verified": True,
    }


def discover_direct_route(
    token_in_mint: str,
    token_out_mint: str,
    *,
    pool_fetcher: Callable[[], Any] = fetch_pool_list,
    account_state_fetcher: Callable[[str], Any] = fetch_account_state,
    token_account_fetcher: Callable[[str], Any] = get_token_account_info,
) -> dict[str, Any]:
    """Discover a unique verified direct XDEX route or fail closed on ambiguity."""
    token_in = _text(token_in_mint, "token_in_mint")
    token_out = _text(token_out_mint, "token_out_mint")
    if token_in == token_out:
        raise ValueError("token_in_mint and token_out_mint must differ")

    try:
        rows = pool_fetcher()
    except Exception as exc:
        raise XDEXDirectRouteDiscoveryError(f"XDEX pool catalog unavailable: {exc}") from exc

    catalog_candidates = _catalog_candidate_addresses(rows, token_in, token_out)
    verified_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    rejected: list[dict[str, str]] = []

    for pool in catalog_candidates:
        try:
            candidate = _verified_candidate(
                pool,
                token_in,
                token_out,
                account_state_fetcher=account_state_fetcher,
                token_account_fetcher=token_account_fetcher,
            )
        except Exception as exc:
            rejected.append({"pool": pool, "reason": f"{type(exc).__name__}: {exc}"})
            continue
        key = (candidate["pool"], candidate["amm_config"])
        verified_by_key.setdefault(key, candidate)

    verified = list(verified_by_key.values())
    if not verified:
        status = "unavailable"
        route = None
        selection_claim = None
    elif len(verified) == 1:
        status = "verified_unique"
        unique = verified[0]
        route = {
            "token_in_mint": unique["token_in_mint"],
            "token_out_mint": unique["token_out_mint"],
            "pool": unique["pool"],
            "amm_config": unique["amm_config"],
        }
        selection_claim = "unique_verified_direct_candidate"
    else:
        status = "ambiguous"
        route = None
        selection_claim = None

    return {
        "service": "xdex_direct_route_discovery",
        "version": VERSION,
        "source": SOURCE,
        "chain": CHAIN,
        "token_in_mint": token_in,
        "token_out_mint": token_out,
        "status": status,
        "route": route,
        "selection_claim": selection_claim,
        "catalog_candidate_count": len(catalog_candidates),
        "verified_candidate_count": len(verified),
        "candidates": verified,
        "rejected_candidates": rejected,
        "read_only": True,
        "best_route_claimed": False,
        "global_optimality_claimed": False,
        "multi_hop_evaluated": False,
        "execution_authorized": False,
    }


__all__ = [
    "CHAIN",
    "SOURCE",
    "VERSION",
    "XDEXDirectRouteDiscoveryError",
    "discover_direct_route",
]
