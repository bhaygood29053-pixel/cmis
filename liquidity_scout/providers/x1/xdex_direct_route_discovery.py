"""Fail-closed read-only discovery of direct XDEX routes for explicit token pairs.

Discovery is exhaustive inside the already accepted XDEX program/account family:
X1 RPC ``getProgramAccounts`` is queried twice with the verified 637-byte pool
size and both verified mint slots (168/200), once for each mint orientation.
Every returned account is then re-read and must satisfy the accepted XDEX
pool/config/vault structure plus positive active reserves.

A unique verified direct candidate may be returned as an exact route. Multiple
verified candidates are reported as ambiguous and are never ranked or selected.
This is a program-family claim only, not proof that the recognized XDEX program
registry is globally exhaustive across every X1 DEX.

This module performs no quote, route-quality, multi-hop, prepare, simulation,
signing, broadcasting, custody, execution, or value-moving work.
"""

from __future__ import annotations

from collections.abc import Mapping
import struct
from typing import Any, Callable

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.program_accounts import parse_program_accounts_result
from liquidity_scout.providers.x1.rpc import (
    DEFAULT_X1_RPC_URL,
    get_token_account_info,
    rpc_request,
)
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import X1_PROGRAM


CHAIN = "x1"
SOURCE = "X1 RPC exact-pair XDEX program discovery"
VERSION = "1.1"
POOL_STATE_LENGTH = 637
CONFIG_MIN_LENGTH = 116
MINT_0_OFFSET = 168
MINT_1_OFFSET = 200


class XDEXDirectRouteDiscoveryError(RuntimeError):
    """Raised when exact-pair discovery cannot be evaluated safely."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a normalized non-empty string")
    text = value.strip()
    if not text or text != value:
        raise ValueError(f"{field} must be a normalized non-empty string")
    return text


def _pubkey(data: bytes, offset: int) -> str:
    return encode_base58_pubkey(data[offset : offset + 32])


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def discover_pair_program_accounts(
    token_in_mint: str,
    token_out_mint: str,
    *,
    program_id: str = X1_PROGRAM,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    commitment: str = "confirmed",
    requester: Callable[..., Any] = rpc_request,
) -> dict[str, Any]:
    """Enumerate every exact-pair account in the accepted XDEX 637-byte family.

    Both mint orientations are queried because requested trade direction is
    independent of pool-state mint-0/mint-1 ordering. A partial/failed
    orientation is never treated as enough evidence for uniqueness.
    """
    token_in = _text(token_in_mint, "token_in_mint")
    token_out = _text(token_out_mint, "token_out_mint")
    program = _text(program_id, "program_id")
    rpc = _text(rpc_url, "rpc_url")
    commitment_name = _text(commitment, "commitment")
    if token_in == token_out:
        raise ValueError("token_in_mint and token_out_mint must differ")

    reports: list[dict[str, Any]] = []
    union: dict[str, dict[str, Any]] = {}
    for mint_0, mint_1 in ((token_in, token_out), (token_out, token_in)):
        config = {
            "encoding": "base64",
            "commitment": commitment_name,
            "dataSlice": {"offset": 0, "length": 0},
            "filters": [
                {"dataSize": POOL_STATE_LENGTH},
                {"memcmp": {"offset": MINT_0_OFFSET, "bytes": mint_0}},
                {"memcmp": {"offset": MINT_1_OFFSET, "bytes": mint_1}},
            ],
        }
        try:
            raw = requester(
                "getProgramAccounts",
                [program, config],
                rpc_url=rpc,
            )
            parsed = parse_program_accounts_result(raw, program_id=program)
        except Exception as exc:
            raise XDEXDirectRouteDiscoveryError(
                "exact-pair XDEX program enumeration failed for one mint orientation: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        accounts = parsed.get("accounts") or []
        space_mismatch_count = sum(
            1
            for row in accounts
            if isinstance(row, Mapping) and row.get("space") != POOL_STATE_LENGTH
        )
        integrity = bool(
            parsed.get("response_integrity_verified") is True
            and space_mismatch_count == 0
        )
        reports.append({
            "mint_0": mint_0,
            "mint_1": mint_1,
            "returned_row_count": parsed.get("returned_row_count"),
            "unique_account_count": parsed.get("unique_account_count"),
            "context_slot": parsed.get("context_slot"),
            "space_mismatch_count": space_mismatch_count,
            "response_integrity_verified": integrity,
        })
        if not integrity:
            raise XDEXDirectRouteDiscoveryError(
                "exact-pair XDEX program enumeration response integrity was not verified"
            )

        for row in accounts:
            if not isinstance(row, Mapping):
                continue
            pubkey = row.get("pubkey")
            if not isinstance(pubkey, str) or not pubkey.strip():
                continue
            if row.get("owner_matches_program") is not True:
                raise XDEXDirectRouteDiscoveryError(
                    "exact-pair enumeration returned an owner-mismatched account"
                )
            union.setdefault(pubkey, {
                "pubkey": pubkey,
                "owner": row.get("owner"),
                "space": row.get("space"),
            })

    return {
        "service": "xdex_exact_pair_program_account_discovery",
        "version": VERSION,
        "chain": CHAIN,
        "program_id": program,
        "account_space": POOL_STATE_LENGTH,
        "mint_offsets": [MINT_0_OFFSET, MINT_1_OFFSET],
        "token_in_mint": token_in,
        "token_out_mint": token_out,
        "queries": reports,
        "accounts": sorted(union.values(), key=lambda row: row["pubkey"]),
        "summary": {
            "both_mint_orientations_integrity_verified": True,
            "unique_matching_program_account_count": len(union),
            "accepted_xdex_program_family_pair_enumeration_complete": True,
            "recognized_program_registry_globally_exhaustive": False,
            "all_x1_dex_pair_enumeration_complete": False,
        },
    }


def _decode_pool(account: Mapping[str, Any], pool: str) -> dict[str, Any]:
    if account.get("owner") != X1_PROGRAM:
        raise XDEXDirectRouteDiscoveryError(
            "candidate pool owner is not the accepted XDEX program"
        )
    data = account.get("data")
    if not isinstance(data, (bytes, bytearray)) or len(data) != POOL_STATE_LENGTH:
        raise XDEXDirectRouteDiscoveryError(
            "candidate pool does not match the accepted 637-byte layout"
        )
    raw = bytes(data)
    return {
        "pool": pool,
        "amm_config": _pubkey(raw, 8),
        "vault_0": _pubkey(raw, 72),
        "vault_1": _pubkey(raw, 104),
        "mint_0": _pubkey(raw, MINT_0_OFFSET),
        "mint_1": _pubkey(raw, MINT_1_OFFSET),
        "protocol_fees_0": _u64(raw, 341),
        "protocol_fees_1": _u64(raw, 349),
        "fund_fees_0": _u64(raw, 357),
        "fund_fees_1": _u64(raw, 365),
        "creator_fees_0": _u64(raw, 397),
        "creator_fees_1": _u64(raw, 405),
    }


def _verify_config(account: Any) -> None:
    if not isinstance(account, Mapping):
        raise XDEXDirectRouteDiscoveryError("candidate AMM config account is unavailable")
    if account.get("owner") != X1_PROGRAM:
        raise XDEXDirectRouteDiscoveryError(
            "candidate AMM config owner is not the accepted XDEX program"
        )
    data = account.get("data")
    if not isinstance(data, (bytes, bytearray)) or len(data) < CONFIG_MIN_LENGTH:
        raise XDEXDirectRouteDiscoveryError(
            "candidate AMM config does not match the accepted layout"
        )
    trade_fee_rate_ppm = _u64(bytes(data), 12)
    if trade_fee_rate_ppm >= 1_000_000:
        raise XDEXDirectRouteDiscoveryError(
            "candidate AMM config trade fee rate is invalid"
        )


def _vault_raw_amount(fetcher: Callable[[str], Any], vault: str, mint: str) -> int:
    record = fetcher(vault)
    if not isinstance(record, Mapping) or record.get("identity_verified") is not True:
        raise XDEXDirectRouteDiscoveryError(
            "candidate pool vault identity is not verified"
        )
    if record.get("mint") != mint:
        raise XDEXDirectRouteDiscoveryError(
            "candidate pool vault mint does not match pool state"
        )
    raw_amount = record.get("raw_amount")
    if isinstance(raw_amount, bool):
        raise XDEXDirectRouteDiscoveryError("candidate pool vault raw amount is invalid")
    try:
        amount = int(raw_amount)
    except (TypeError, ValueError) as exc:
        raise XDEXDirectRouteDiscoveryError(
            "candidate pool vault raw amount is invalid"
        ) from exc
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
        raise XDEXDirectRouteDiscoveryError(
            "candidate on-chain mint pair does not match requested pair"
        )

    config_state = account_state_fetcher(decoded["amm_config"])
    _verify_config(config_state)

    gross_0 = _vault_raw_amount(
        token_account_fetcher,
        decoded["vault_0"],
        decoded["mint_0"],
    )
    gross_1 = _vault_raw_amount(
        token_account_fetcher,
        decoded["vault_1"],
        decoded["mint_1"],
    )
    active_0 = (
        gross_0
        - decoded["protocol_fees_0"]
        - decoded["fund_fees_0"]
        - decoded["creator_fees_0"]
    )
    active_1 = (
        gross_1
        - decoded["protocol_fees_1"]
        - decoded["fund_fees_1"]
        - decoded["creator_fees_1"]
    )
    if active_0 <= 0 or active_1 <= 0:
        raise XDEXDirectRouteDiscoveryError(
            "candidate pool active reserves are not positive"
        )

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
    candidate_provider: Callable[..., Mapping[str, Any]] = (
        discover_pair_program_accounts
    ),
    account_state_fetcher: Callable[[str], Any] = fetch_account_state,
    token_account_fetcher: Callable[[str], Any] = get_token_account_info,
) -> dict[str, Any]:
    """Discover a unique verified direct XDEX route or fail closed on ambiguity."""
    token_in = _text(token_in_mint, "token_in_mint")
    token_out = _text(token_out_mint, "token_out_mint")
    if token_in == token_out:
        raise ValueError("token_in_mint and token_out_mint must differ")

    try:
        discovery = candidate_provider(token_in, token_out)
    except Exception as exc:
        if isinstance(exc, XDEXDirectRouteDiscoveryError):
            raise
        raise XDEXDirectRouteDiscoveryError(
            f"exact-pair candidate enumeration failed: {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(discovery, Mapping):
        raise XDEXDirectRouteDiscoveryError(
            "exact-pair candidate provider did not return a mapping"
        )
    summary = discovery.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    if summary.get("accepted_xdex_program_family_pair_enumeration_complete") is not True:
        raise XDEXDirectRouteDiscoveryError(
            "exact-pair candidate enumeration completeness was not verified"
        )
    raw_accounts = discovery.get("accounts")
    if not isinstance(raw_accounts, list):
        raise XDEXDirectRouteDiscoveryError(
            "exact-pair candidate enumeration did not return an account list"
        )

    candidate_addresses: list[str] = []
    for row in raw_accounts:
        if not isinstance(row, Mapping):
            raise XDEXDirectRouteDiscoveryError(
                "exact-pair candidate enumeration returned a malformed account"
            )
        pubkey = row.get("pubkey")
        if not isinstance(pubkey, str) or not pubkey.strip():
            raise XDEXDirectRouteDiscoveryError(
                "exact-pair candidate enumeration returned an invalid pubkey"
            )
        if pubkey not in candidate_addresses:
            candidate_addresses.append(pubkey)

    verified_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    rejected: list[dict[str, str]] = []
    for pool in candidate_addresses:
        try:
            candidate = _verified_candidate(
                pool,
                token_in,
                token_out,
                account_state_fetcher=account_state_fetcher,
                token_account_fetcher=token_account_fetcher,
            )
        except Exception as exc:
            rejected.append({
                "pool": pool,
                "reason": f"{type(exc).__name__}: {exc}",
            })
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
        selection_claim = (
            "unique_verified_direct_candidate_in_accepted_xdex_program_family"
        )
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
        "program_id": discovery.get("program_id") or X1_PROGRAM,
        "program_family_pair_enumeration_complete": True,
        "recognized_program_registry_globally_exhaustive": False,
        "all_x1_dex_pair_enumeration_complete": False,
        "enumerated_candidate_count": len(candidate_addresses),
        "verified_candidate_count": len(verified),
        "candidates": verified,
        "rejected_candidates": rejected,
        "enumeration_evidence": dict(discovery),
        "read_only": True,
        "best_route_claimed": False,
        "global_optimality_claimed": False,
        "multi_hop_evaluated": False,
        "execution_authorized": False,
    }


__all__ = [
    "CHAIN",
    "MINT_0_OFFSET",
    "MINT_1_OFFSET",
    "SOURCE",
    "VERSION",
    "XDEXDirectRouteDiscoveryError",
    "discover_direct_route",
    "discover_pair_program_accounts",
]
