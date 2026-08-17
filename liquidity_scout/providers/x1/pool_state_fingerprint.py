"""Read-only X1 pool-state binary fingerprinting for CMIS v1.5.1.

This module samples full binary data only for already-known catalog pool accounts.
It does not scan every AMM program-owned account in full and it does not infer a
pool layout merely from account size.

The evidence boundary is explicit:
- program ownership and account-data integrity can be verified through X1 RPC;
- exact 32-byte public-key occurrences can be located deterministically;
- repeated offsets across independently known pools can later support a layout
  hypothesis;
- this phase never promotes ``pool_state_layout_verified`` on its own.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.program_accounts import (
    RECOGNIZED_AMM_PROGRAM_IDS,
)
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, rpc_request
from liquidity_scout.providers.x1.transaction_semantics import DEFAULT_QUOTE_MINTS

VERSION = "1.5.1"
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {char: index for index, char in enumerate(BASE58_ALPHABET)}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nonnegative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def decode_base58_pubkey(value: str) -> bytes:
    """Decode one base58 public key and require exactly 32 bytes."""

    text = _text(value)
    if not text:
        raise ValueError("public key is required")

    number = 0
    for char in text:
        digit = _BASE58_INDEX.get(char)
        if digit is None:
            raise ValueError(f"invalid base58 character: {char!r}")
        number = number * 58 + digit

    payload = (
        number.to_bytes((number.bit_length() + 7) // 8, "big")
        if number
        else b""
    )
    leading_zeros = len(text) - len(text.lstrip("1"))
    decoded = (b"\x00" * leading_zeros) + payload
    if len(decoded) != 32:
        raise ValueError(
            f"public key must decode to exactly 32 bytes; got {len(decoded)}"
        )
    return decoded


def find_pubkey_offsets(data: bytes, pubkey: str) -> list[int]:
    """Return every exact byte offset where a 32-byte public key occurs."""

    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("data must be bytes")
    needle = decode_base58_pubkey(pubkey)
    haystack = bytes(data)
    offsets: list[int] = []
    start = 0
    while True:
        index = haystack.find(needle, start)
        if index < 0:
            break
        offsets.append(index)
        start = index + 1
    return offsets


def parse_account_info_base64_result(
    result: Any,
    *,
    account: str,
) -> dict[str, Any]:
    """Parse one base64 ``getAccountInfo`` result with integrity evidence."""

    account = _text(account)
    if not account:
        raise ValueError("account is required")

    context_slot = None
    value = result
    if isinstance(result, Mapping) and "value" in result:
        value = result.get("value")
        context = result.get("context")
        if isinstance(context, Mapping):
            context_slot = _nonnegative_int(context.get("slot"))

    if value is None:
        return {
            "account": account,
            "account_exists": False,
            "context_slot": context_slot,
            "owner": None,
            "space": None,
            "data_length": None,
            "data_length_matches_space": False,
            "lamports": None,
            "executable": None,
            "rent_epoch": None,
            "data_sha256": None,
            "data": None,
            "response_integrity_verified": False,
        }

    if not isinstance(value, Mapping):
        raise ValueError("getAccountInfo returned no usable account object")

    owner = _text(value.get("owner"))
    space = _nonnegative_int(value.get("space"))
    lamports = _nonnegative_int(value.get("lamports"))
    executable = value.get("executable")
    rent_epoch = _nonnegative_int(value.get("rentEpoch"))

    raw_data = value.get("data")
    encoded = None
    encoding = None
    if (
        isinstance(raw_data, Sequence)
        and not isinstance(raw_data, (str, bytes, bytearray))
        and len(raw_data) >= 2
    ):
        encoded = raw_data[0]
        encoding = _text(raw_data[1])
    elif isinstance(raw_data, str):
        encoded = raw_data
        encoding = "base64"

    decoded = None
    if isinstance(encoded, str) and encoding == "base64":
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except Exception:
            decoded = None

    data_length = len(decoded) if isinstance(decoded, bytes) else None
    effective_space = space if space is not None else data_length
    data_length_matches_space = bool(
        decoded is not None
        and effective_space is not None
        and data_length == effective_space
    )
    integrity = bool(owner and decoded is not None and data_length_matches_space)

    return {
        "account": account,
        "account_exists": True,
        "context_slot": context_slot,
        "owner": owner,
        "space": effective_space,
        "reported_space": space,
        "data_length": data_length,
        "data_length_matches_space": data_length_matches_space,
        "lamports": lamports,
        "executable": executable if isinstance(executable, bool) else None,
        "rent_epoch": rent_epoch,
        "data_sha256": (
            hashlib.sha256(decoded).hexdigest()
            if isinstance(decoded, bytes)
            else None
        ),
        "data": decoded,
        "response_integrity_verified": integrity,
    }


def fetch_account_state(
    account: str,
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    commitment: str = "confirmed",
    requester: Callable[..., Any] = rpc_request,
) -> dict[str, Any]:
    """Fetch the complete binary state of one already-known account."""

    account = _text(account)
    rpc_url = _text(rpc_url)
    commitment = _text(commitment)
    if not account:
        raise ValueError("account is required")
    if not rpc_url:
        raise ValueError("rpc_url is required")
    if not commitment:
        raise ValueError("commitment is required")

    result = requester(
        "getAccountInfo",
        [
            account,
            {
                "encoding": "base64",
                "commitment": commitment,
            },
        ],
        rpc_url=rpc_url,
    )
    parsed = parse_account_info_base64_result(result, account=account)
    parsed.update(
        {
            "version": VERSION,
            "chain": "x1",
            "rpc_url": rpc_url,
            "rpc_method": "getAccountInfo",
            "commitment": commitment,
        }
    )
    return parsed


def fingerprint_known_pool_state(
    *,
    pool_address: str,
    asset_mint: str,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    quote_mints: Sequence[str] = DEFAULT_QUOTE_MINTS,
    recognized_program_ids: Sequence[str] = RECOGNIZED_AMM_PROGRAM_IDS,
    extra_identities: Mapping[str, str] | None = None,
    requester: Callable[..., Any] = rpc_request,
) -> dict[str, Any]:
    """Fingerprint one known pool account without promoting a binary layout."""

    pool_address = _text(pool_address)
    asset_mint = _text(asset_mint)
    if not pool_address:
        raise ValueError("pool_address is required")
    if not asset_mint:
        raise ValueError("asset_mint is required")

    account = fetch_account_state(
        pool_address,
        rpc_url=rpc_url,
        requester=requester,
    )
    data = account.pop("data", None)
    data = data if isinstance(data, bytes) else None

    recognized = {
        program_id
        for program_id in (_text(item) for item in recognized_program_ids)
        if program_id
    }
    owner = _text(account.get("owner"))
    owner_recognized = owner in recognized

    identities: dict[str, str] = {"asset_mint": asset_mint}
    for index, raw in enumerate(quote_mints):
        mint = _text(raw)
        if mint and mint != asset_mint:
            identities[f"quote_mint_{index + 1}"] = mint
    if isinstance(extra_identities, Mapping):
        for raw_name, raw_pubkey in extra_identities.items():
            name = _text(raw_name)
            pubkey = _text(raw_pubkey)
            if name and pubkey:
                identities[name] = pubkey

    occurrences: dict[str, dict[str, Any]] = {}
    invalid_identity_count = 0
    if data is not None:
        for name, pubkey in identities.items():
            try:
                offsets = find_pubkey_offsets(data, pubkey)
                valid = True
            except ValueError as exc:
                offsets = []
                valid = False
                invalid_identity_count += 1
                error = str(exc)
            row = {
                "pubkey": pubkey,
                "offsets": offsets,
                "occurrence_count": len(offsets),
                "identity_valid": valid,
            }
            if not valid:
                row["error"] = error
            occurrences[name] = row

    asset_offsets = (occurrences.get("asset_mint") or {}).get("offsets") or []
    quote_occurrence_count = sum(
        int(row.get("occurrence_count") or 0)
        for name, row in occurrences.items()
        if name.startswith("quote_mint_")
    )
    extra_occurrence_count = sum(
        int(row.get("occurrence_count") or 0)
        for name, row in occurrences.items()
        if name != "asset_mint" and not name.startswith("quote_mint_")
    )

    integrity = account.get("response_integrity_verified") is True
    identity_coupling_observed = bool(
        integrity
        and owner_recognized
        and len(asset_offsets) > 0
        and (quote_occurrence_count > 0 or extra_occurrence_count > 0)
    )

    public_account = {
        key: value
        for key, value in account.items()
        if key not in {"rpc_url"}
    }

    return {
        "service": "known_pool_state_fingerprint",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "asset_mint": asset_mint,
        "account": public_account,
        "recognized_program_owner": owner_recognized,
        "identity_occurrences": occurrences,
        "summary": {
            "account_exists": account.get("account_exists") is True,
            "response_integrity_verified": integrity,
            "recognized_program_owner": owner_recognized,
            "account_space": account.get("space"),
            "asset_mint_occurrence_count": len(asset_offsets),
            "quote_mint_occurrence_count": quote_occurrence_count,
            "extra_identity_occurrence_count": extra_occurrence_count,
            "invalid_identity_count": invalid_identity_count,
            "pool_state_identity_coupling_observed": identity_coupling_observed,
            "pool_state_layout_candidate_observed": identity_coupling_observed,
            "pool_state_layout_verified": False,
            "pool_role_promoted": False,
            "interpretation": (
                "Exact public-key byte occurrences are observational layout "
                "evidence for this already-known pool account. Stable repeated "
                "offsets across independently known pools are required before "
                "CMIS can verify a pool-state layout."
            ),
        },
        "errors": [],
    }


__all__ = [
    "BASE58_ALPHABET",
    "VERSION",
    "decode_base58_pubkey",
    "fetch_account_state",
    "find_pubkey_offsets",
    "fingerprint_known_pool_state",
    "parse_account_info_base64_result",
]
