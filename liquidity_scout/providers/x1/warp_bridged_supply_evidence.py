"""Fail-closed current bridged-supply evidence for one exact Warp route.

This module proves a bounded current supply/backing closure for a native-source
-> wrapped-destination route by comparing:
1. the exact native source token balance held by the deterministic Warp vault;
2. the exact destination wrapped mint total supply; and
3. the destination mint authority against the deterministic Warp
   mint_authority PDA.

Provider labels such as /api/bridge/tvl are not supply truth.

Read-only RPC only. No transaction construction, signing, broadcast, custody,
mint, burn, transfer, or authority mutation.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from typing import Any, Callable

import requests

from liquidity_scout.providers.x1.warp_config_semantics import (
    WARP_CONFIG_SEMANTICS_CONTRACT,
    WARP_CONFIG_SEMANTIC_CONTRACT_ID,
    WARP_PROGRAM_ID,
)
from liquidity_scout.providers.x1.warp_semantic_layout_discovery import (
    find_program_address,
)

CONTRACT = "warp_bridged_supply_evidence/v1"
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
X1_RPC_URL = "https://rpc.mainnet.x1.xyz"
DEFAULT_COMMITMENT = "finalized"
DEFAULT_MAX_OBSERVATION_SKEW_SECONDS = 120.0

WSOL_SOURCE_MINT = "So11111111111111111111111111111111111111112"
WSOL_X_DESTINATION_MINT = "JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8"
WSOL_ROUTE_ID = "warp-solana-x1-wsol"

_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class WarpBridgedSupplyEvidenceError(RuntimeError):
    """Raised when exact bridged-supply evidence cannot be established safely."""


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise WarpBridgedSupplyEvidenceError(f"{field} is required")
    return text


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise WarpBridgedSupplyEvidenceError(f"{field} must be a non-negative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise WarpBridgedSupplyEvidenceError(
            f"{field} must be a non-negative integer"
        ) from None
    if parsed < 0:
        raise WarpBridgedSupplyEvidenceError(f"{field} must be a non-negative integer")
    return parsed


def _epoch(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise WarpBridgedSupplyEvidenceError(f"{field} must be epoch seconds")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise WarpBridgedSupplyEvidenceError(f"{field} must be epoch seconds") from None
    if parsed < 0:
        raise WarpBridgedSupplyEvidenceError(f"{field} must be epoch seconds")
    return parsed


def _b58decode(value: str) -> bytes:
    text = _text(value, "base58")
    number = 0
    for char in text:
        try:
            digit = _BASE58.index(char)
        except ValueError:
            raise WarpBridgedSupplyEvidenceError("invalid base58 value") from None
        number = number * 58 + digit
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    pad = len(text) - len(text.lstrip("1"))
    decoded = (b"\x00" * pad) + raw
    if len(decoded) != 32:
        raise WarpBridgedSupplyEvidenceError("public key must decode to 32 bytes")
    return decoded


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def _decimal_string(amount_raw: int, decimals: int) -> str:
    raw = str(amount_raw).rjust(decimals + 1, "0")
    if decimals == 0:
        return raw
    whole = raw[:-decimals] or "0"
    fraction = raw[-decimals:].rstrip("0")
    return whole if not fraction else f"{whole}.{fraction}"


def derive_vault_pda(source_mint: str) -> dict[str, Any]:
    address, bump = find_program_address(
        [b"vault", _b58decode(source_mint)],
        WARP_PROGRAM_ID,
    )
    return {"address": address, "bump": bump, "seed": "vault"}


def derive_mint_authority_pda(destination_mint: str) -> dict[str, Any]:
    address, bump = find_program_address(
        [b"mint_authority", _b58decode(destination_mint)],
        WARP_PROGRAM_ID,
    )
    return {"address": address, "bump": bump, "seed": "mint_authority"}


def _rpc_request(
    method: str,
    params: Sequence[Any],
    *,
    rpc_url: str,
    retries: int = 4,
    timeout: int = 30,
    post: Callable[..., Any] = requests.post,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    if retries < 1:
        raise ValueError("retries must be at least 1")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": list(params),
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = post(
                rpc_url,
                json=payload,
                headers={
                    "content-type": "application/json",
                    "user-agent": "CMIS-Warp-Bridged-Supply/1.0",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, Mapping):
                raise WarpBridgedSupplyEvidenceError(
                    f"{method} returned a non-object response"
                )
            if body.get("error") is not None:
                raise WarpBridgedSupplyEvidenceError(
                    f"{method} JSON-RPC error: {body.get('error')!r}"
                )
            if "result" not in body:
                raise WarpBridgedSupplyEvidenceError(
                    f"{method} response missing result"
                )
            return body.get("result")
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                sleep(0.75 * (2**attempt))
    raise WarpBridgedSupplyEvidenceError(
        f"{method} failed after {retries} attempts ({type(last_error).__name__})"
    ) from last_error


def _context_slot(result: Any, field: str) -> int:
    if not isinstance(result, Mapping):
        raise WarpBridgedSupplyEvidenceError(f"{field} result must be an object")
    context = result.get("context")
    if not isinstance(context, Mapping):
        raise WarpBridgedSupplyEvidenceError(f"{field} context is required")
    return _nonnegative_int(context.get("slot"), f"{field}.context.slot")


def _block_time(slot: int, *, rpc_url: str, requester: Callable[..., Any]) -> float:
    value = requester("getBlockTime", [slot], rpc_url=rpc_url)
    return _epoch(value, "getBlockTime.result")


def capture_source_vault_observation(
    *,
    source_mint: str,
    rpc_url: str = SOLANA_RPC_URL,
    requester: Callable[..., Any] = _rpc_request,
) -> dict[str, Any]:
    source_mint = _text(source_mint, "source_mint")
    vault = derive_vault_pda(source_mint)
    result = requester(
        "getTokenAccountsByOwner",
        [
            vault["address"],
            {"mint": source_mint},
            {"encoding": "jsonParsed", "commitment": DEFAULT_COMMITMENT},
        ],
        rpc_url=rpc_url,
    )
    slot = _context_slot(result, "getTokenAccountsByOwner")
    observed_at = _block_time(slot, rpc_url=rpc_url, requester=requester)
    rows = result.get("value")
    if not isinstance(rows, list) or len(rows) != 1:
        raise WarpBridgedSupplyEvidenceError(
            "exact Warp source vault must resolve to exactly one token account"
        )
    row = rows[0]
    if not isinstance(row, Mapping):
        raise WarpBridgedSupplyEvidenceError("source vault row must be an object")
    account = _text(row.get("pubkey"), "source_vault_token_account")
    account_value = row.get("account")
    if not isinstance(account_value, Mapping):
        raise WarpBridgedSupplyEvidenceError("source vault account value is required")
    parsed = (account_value.get("data") or {}).get("parsed")
    if not isinstance(parsed, Mapping) or parsed.get("type") != "account":
        raise WarpBridgedSupplyEvidenceError("source vault must be a parsed token account")
    info = parsed.get("info")
    if not isinstance(info, Mapping):
        raise WarpBridgedSupplyEvidenceError("source vault parsed info is required")
    token_amount = info.get("tokenAmount")
    if not isinstance(token_amount, Mapping):
        raise WarpBridgedSupplyEvidenceError("source vault token amount is required")

    mint = _text(info.get("mint"), "source_vault.mint")
    authority = _text(info.get("owner"), "source_vault.owner")
    amount_raw = _nonnegative_int(token_amount.get("amount"), "source_vault.amount")
    decimals = _nonnegative_int(token_amount.get("decimals"), "source_vault.decimals")

    return {
        "chain": "solana",
        "source_mint": source_mint,
        "vault_pda": vault["address"],
        "vault_bump": vault["bump"],
        "vault_token_account": account,
        "token_account_program_owner": _text(
            account_value.get("owner"), "source_vault.program_owner"
        ),
        "token_account_mint": mint,
        "token_account_authority": authority,
        "amount_raw": amount_raw,
        "decimals": decimals,
        "observation_slot": slot,
        "observed_at": observed_at,
        "identity_verified": bool(
            mint == source_mint and authority == vault["address"]
        ),
        "source": "Solana RPC getTokenAccountsByOwner + getBlockTime",
    }


def capture_destination_mint_observation(
    *,
    destination_mint: str,
    rpc_url: str = X1_RPC_URL,
    requester: Callable[..., Any] = _rpc_request,
) -> dict[str, Any]:
    destination_mint = _text(destination_mint, "destination_mint")
    authority = derive_mint_authority_pda(destination_mint)

    mint_result = requester(
        "getAccountInfo",
        [
            destination_mint,
            {"encoding": "jsonParsed", "commitment": DEFAULT_COMMITMENT},
        ],
        rpc_url=rpc_url,
    )
    mint_slot = _context_slot(mint_result, "getAccountInfo")
    mint_observed_at = _block_time(
        mint_slot, rpc_url=rpc_url, requester=requester
    )

    value = mint_result.get("value")
    if not isinstance(value, Mapping):
        raise WarpBridgedSupplyEvidenceError("destination mint account is required")
    parsed = (value.get("data") or {}).get("parsed")
    if not isinstance(parsed, Mapping) or parsed.get("type") != "mint":
        raise WarpBridgedSupplyEvidenceError("destination must be a parsed mint account")
    info = parsed.get("info")
    if not isinstance(info, Mapping):
        raise WarpBridgedSupplyEvidenceError("destination mint parsed info is required")

    mint_authority = _text(info.get("mintAuthority"), "destination.mint_authority")
    mint_raw_supply = _nonnegative_int(info.get("supply"), "destination.mint_supply")
    mint_decimals = _nonnegative_int(info.get("decimals"), "destination.mint_decimals")

    supply_result = requester(
        "getTokenSupply",
        [destination_mint, {"commitment": DEFAULT_COMMITMENT}],
        rpc_url=rpc_url,
    )
    supply_slot = _context_slot(supply_result, "getTokenSupply")
    supply_observed_at = _block_time(
        supply_slot, rpc_url=rpc_url, requester=requester
    )
    supply_value = supply_result.get("value")
    if not isinstance(supply_value, Mapping):
        raise WarpBridgedSupplyEvidenceError("destination token supply is required")
    supply_raw = _nonnegative_int(
        supply_value.get("amount"), "destination.token_supply.amount"
    )
    supply_decimals = _nonnegative_int(
        supply_value.get("decimals"), "destination.token_supply.decimals"
    )
    if mint_raw_supply != supply_raw or mint_decimals != supply_decimals:
        raise WarpBridgedSupplyEvidenceError(
            "destination mint account and getTokenSupply must agree exactly"
        )

    return {
        "chain": "x1",
        "destination_mint": destination_mint,
        "mint_program_owner": _text(value.get("owner"), "destination.program_owner"),
        "mint_authority": mint_authority,
        "expected_warp_mint_authority": authority["address"],
        "mint_authority_bump": authority["bump"],
        "raw_supply": supply_raw,
        "decimals": supply_decimals,
        "mint_observation_slot": mint_slot,
        "mint_observed_at": mint_observed_at,
        "supply_observation_slot": supply_slot,
        "supply_observed_at": supply_observed_at,
        "authority_verified": mint_authority == authority["address"],
        "supply_crosscheck_verified": True,
        "source": "X1 RPC getAccountInfo(jsonParsed) + getTokenSupply + getBlockTime",
    }


def build_warp_bridged_supply_evidence(
    *,
    route_observation: Any,
    source_vault: Any,
    destination_mint: Any,
    evaluated_at: Any,
    max_observation_skew_seconds: float = DEFAULT_MAX_OBSERVATION_SKEW_SECONDS,
) -> dict[str, Any]:
    if not isinstance(route_observation, Mapping):
        raise WarpBridgedSupplyEvidenceError("route_observation must be an object")
    if not isinstance(source_vault, Mapping):
        raise WarpBridgedSupplyEvidenceError("source_vault must be an object")
    if not isinstance(destination_mint, Mapping):
        raise WarpBridgedSupplyEvidenceError("destination_mint must be an object")

    if route_observation.get("contract") != WARP_CONFIG_SEMANTICS_CONTRACT:
        raise WarpBridgedSupplyEvidenceError("accepted Warp config semantics are required")
    if route_observation.get("semantic_contract_id") != WARP_CONFIG_SEMANTIC_CONTRACT_ID:
        raise WarpBridgedSupplyEvidenceError("exact-mint-pair semantic contract is required")
    if route_observation.get("program_id") != WARP_PROGRAM_ID:
        raise WarpBridgedSupplyEvidenceError("Warp program id mismatch")
    if route_observation.get("source_is_native") is not True:
        raise WarpBridgedSupplyEvidenceError("source route representation must be native")
    if route_observation.get("destination_is_native") is not False:
        raise WarpBridgedSupplyEvidenceError(
            "destination route representation must be non-native"
        )

    source = route_observation.get("source")
    destination = route_observation.get("destination")
    if not isinstance(source, Mapping) or not isinstance(destination, Mapping):
        raise WarpBridgedSupplyEvidenceError("route endpoints are required")
    if source.get("chain") != "solana" or destination.get("chain") != "x1":
        raise WarpBridgedSupplyEvidenceError("this contract currently supports Solana -> X1")

    source_mint = _text(source.get("asset_id"), "route.source.asset_id")
    destination_mint_id = _text(
        destination.get("asset_id"), "route.destination.asset_id"
    )

    expected_vault = derive_vault_pda(source_mint)
    expected_authority = derive_mint_authority_pda(destination_mint_id)

    source_identity_verified = bool(
        source_vault.get("chain") == "solana"
        and source_vault.get("source_mint") == source_mint
        and source_vault.get("vault_pda") == expected_vault["address"]
        and source_vault.get("token_account_mint") == source_mint
        and source_vault.get("token_account_authority") == expected_vault["address"]
        and source_vault.get("identity_verified") is True
    )
    destination_identity_verified = bool(
        destination_mint.get("chain") == "x1"
        and destination_mint.get("destination_mint") == destination_mint_id
        and destination_mint.get("expected_warp_mint_authority")
        == expected_authority["address"]
        and destination_mint.get("mint_authority") == expected_authority["address"]
        and destination_mint.get("authority_verified") is True
        and destination_mint.get("supply_crosscheck_verified") is True
    )

    source_amount = _nonnegative_int(source_vault.get("amount_raw"), "source.amount_raw")
    destination_amount = _nonnegative_int(
        destination_mint.get("raw_supply"), "destination.raw_supply"
    )
    source_decimals = _nonnegative_int(source_vault.get("decimals"), "source.decimals")
    destination_decimals = _nonnegative_int(
        destination_mint.get("decimals"), "destination.decimals"
    )
    route_decimals = _nonnegative_int(
        route_observation.get("route_decimals"), "route.route_decimals"
    )
    decimals_verified = (
        source_decimals == destination_decimals == route_decimals
    )

    source_observed_at = _epoch(source_vault.get("observed_at"), "source.observed_at")
    destination_observed_at = max(
        _epoch(destination_mint.get("mint_observed_at"), "destination.mint_observed_at"),
        _epoch(
            destination_mint.get("supply_observed_at"),
            "destination.supply_observed_at",
        ),
    )
    evaluated_at_epoch = _epoch(evaluated_at, "evaluated_at")
    if max_observation_skew_seconds < 0:
        raise WarpBridgedSupplyEvidenceError(
            "max_observation_skew_seconds cannot be negative"
        )
    observation_skew_seconds = abs(source_observed_at - destination_observed_at)
    observation_time_compatible = (
        observation_skew_seconds <= float(max_observation_skew_seconds)
        and source_observed_at <= evaluated_at_epoch
        and destination_observed_at <= evaluated_at_epoch
    )

    balance_supply_equal = source_amount == destination_amount
    current_backing_closure_verified = bool(
        source_identity_verified
        and destination_identity_verified
        and decimals_verified
        and observation_time_compatible
        and balance_supply_equal
    )

    amount_raw = destination_amount if current_backing_closure_verified else None
    supply_evidence = (
        {
            "verified": True,
            "semantic_contract_accepted": True,
            "amount_raw": amount_raw,
            "decimals": route_decimals,
            "basis": (
                "exact_native_source_warp_vault_balance_equals_"
                "exact_wrapped_destination_mint_supply_with_warp_mint_authority"
            ),
            "observed_at": max(source_observed_at, destination_observed_at),
        }
        if current_backing_closure_verified
        else None
    )

    result = {
        "contract": CONTRACT,
        "route_id": _text(route_observation.get("route_id"), "route_id"),
        "program_id": WARP_PROGRAM_ID,
        "source": {
            "chain": "solana",
            "mint": source_mint,
            "vault_pda": expected_vault["address"],
            "vault_token_account": source_vault.get("vault_token_account"),
            "amount_raw": source_amount,
            "decimals": source_decimals,
            "observed_at": source_observed_at,
            "identity_verified": source_identity_verified,
        },
        "destination": {
            "chain": "x1",
            "mint": destination_mint_id,
            "mint_authority": destination_mint.get("mint_authority"),
            "expected_warp_mint_authority": expected_authority["address"],
            "raw_supply": destination_amount,
            "decimals": destination_decimals,
            "observed_at": destination_observed_at,
            "identity_verified": destination_identity_verified,
        },
        "source_native_destination_wrapped_verified": True,
        "decimals_verified": decimals_verified,
        "observation_skew_seconds": observation_skew_seconds,
        "max_observation_skew_seconds": float(max_observation_skew_seconds),
        "observation_time_compatible": observation_time_compatible,
        "source_vault_balance_equals_destination_supply": balance_supply_equal,
        "current_backing_closure_verified": current_backing_closure_verified,
        "bridged_supply_verified": current_backing_closure_verified,
        "amount_raw": amount_raw,
        "amount": (
            _decimal_string(amount_raw, route_decimals)
            if amount_raw is not None
            else None
        ),
        "decimals": route_decimals,
        "supply_evidence": supply_evidence,
        "third_party_idl_semantics_promoted": False,
        "provider_tvl_label_promoted": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
        "evaluated_at": evaluated_at_epoch,
    }
    result["evidence_sha256"] = _canonical_sha256(result)
    return result


__all__ = [
    "CONTRACT",
    "DEFAULT_MAX_OBSERVATION_SKEW_SECONDS",
    "SOLANA_RPC_URL",
    "X1_RPC_URL",
    "WSOL_ROUTE_ID",
    "WSOL_SOURCE_MINT",
    "WSOL_X_DESTINATION_MINT",
    "WarpBridgedSupplyEvidenceError",
    "build_warp_bridged_supply_evidence",
    "capture_destination_mint_observation",
    "capture_source_vault_observation",
    "derive_mint_authority_pda",
    "derive_vault_pda",
]
