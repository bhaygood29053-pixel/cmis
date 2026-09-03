"""Bounded raw capture of rare Warp program account families.

This module builds on the accepted zero-byte account inventory foundation.
It selects only the rare structural families accepted for follow-up discovery
and fetches their public on-chain account bytes through read-only RPC.

Account bytes are evidence for later layout review. They do not assign semantic
roles. Equality across chains also does not establish semantic equivalence.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
import hashlib
from typing import Any, Callable

import requests

from liquidity_scout.providers.x1.warp_onchain_inventory import (
    CONTRACT as INVENTORY_CONTRACT,
    DEFAULT_COMMITMENT,
    SOLANA_RPC_URL,
    WARP_PROGRAM_ID,
    X1_RPC_URL,
    inventory_warp_both_chains,
)


CONTRACT = "warp_rare_account_capture/v1"
RARE_ACCOUNT_SPACES = frozenset({170, 236, 321, 335})
MAX_CANDIDATES_PER_CHAIN = 16
PREFIX_BYTES = 32
SUFFIX_BYTES = 32


class WarpRareAccountCaptureError(RuntimeError):
    """Raised when rare Warp account evidence cannot be safely captured."""


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


def _rpc_request(
    method: str,
    params: list[Any],
    *,
    rpc_url: str,
    timeout: int = 30,
    post: Callable[..., Any] = requests.post,
) -> Any:
    """Perform one read-only JSON-RPC request without leaking URL credentials."""

    method = _text(method)
    rpc_url = _text(rpc_url)
    if not method:
        raise ValueError("RPC method is required")
    if not rpc_url:
        raise ValueError("RPC URL is required")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("timeout must be a positive integer")

    try:
        response = post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params,
            },
            headers={"content-type": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        raise WarpRareAccountCaptureError(
            f"{method} transport failed ({type(exc).__name__})"
        ) from None

    if not isinstance(body, Mapping):
        raise WarpRareAccountCaptureError(
            f"{method} returned a non-object JSON-RPC response"
        )
    if body.get("error") is not None:
        error = body.get("error")
        code = error.get("code") if isinstance(error, Mapping) else None
        raise WarpRareAccountCaptureError(
            f"{method} returned JSON-RPC error code {code!r}"
        )
    if "result" not in body:
        raise WarpRareAccountCaptureError(f"{method} response is missing result")
    return body.get("result")


def select_rare_account_candidates(
    inventory: Any,
    *,
    rare_spaces: frozenset[int] = RARE_ACCOUNT_SPACES,
    maximum: int = MAX_CANDIDATES_PER_CHAIN,
) -> list[dict[str, Any]]:
    """Select bounded rare-family accounts from an accepted structural inventory."""

    if not isinstance(inventory, Mapping):
        raise ValueError("inventory must be a mapping")
    if inventory.get("contract") != INVENTORY_CONTRACT:
        raise ValueError(
            f"inventory must use accepted contract {INVENTORY_CONTRACT}"
        )
    chain = _text(inventory.get("chain"))
    if chain not in {"solana", "x1"}:
        raise ValueError("inventory.chain must be solana or x1")
    if inventory.get("program_id") != WARP_PROGRAM_ID:
        raise ValueError("inventory must use the exact Warp program id")
    if inventory.get("response_integrity_verified") is not True:
        raise WarpRareAccountCaptureError(
            "inventory response integrity must be verified"
        )
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1:
        raise ValueError("maximum must be a positive integer")
    if not rare_spaces or any(
        isinstance(space, bool) or not isinstance(space, int) or space <= 0
        for space in rare_spaces
    ):
        raise ValueError("rare_spaces must contain positive integer byte lengths")

    accounts = inventory.get("accounts")
    if not isinstance(accounts, list):
        raise ValueError("inventory.accounts must be a list")

    selected: list[dict[str, Any]] = []
    for raw in accounts:
        if not isinstance(raw, Mapping):
            raise WarpRareAccountCaptureError(
                "inventory contains a malformed account row"
            )
        pubkey = _text(raw.get("pubkey"))
        owner = _text(raw.get("owner"))
        space = _nonnegative_int(raw.get("space"))
        owner_matches = raw.get("owner_matches_program")
        if not pubkey or owner != WARP_PROGRAM_ID or owner_matches is not True:
            raise WarpRareAccountCaptureError(
                "inventory contains an account without exact Warp ownership"
            )
        if space not in rare_spaces:
            continue

        selected.append(
            {
                "chain": chain,
                "pubkey": pubkey,
                "inventory_space": space,
                "inventory_owner": owner,
                "semantic_role": None,
                "semantic_role_verified": False,
            }
        )

    selected.sort(key=lambda item: (item["inventory_space"], item["pubkey"]))
    if len(selected) > maximum:
        raise WarpRareAccountCaptureError(
            f"rare candidate count {len(selected)} exceeds bounded maximum {maximum}"
        )
    if not selected:
        raise WarpRareAccountCaptureError(
            "inventory contains no selected rare account candidates"
        )
    return selected


def parse_account_info_result(
    result: Any,
    *,
    chain: str,
    pubkey: str,
    expected_space: int,
    include_raw_base64: bool = False,
) -> dict[str, Any]:
    """Normalize one exact account read and verify owner plus byte length."""

    chain = (_text(chain) or "").casefold()
    pubkey = _text(pubkey)
    if chain not in {"solana", "x1"}:
        raise ValueError("chain must be solana or x1")
    if not pubkey:
        raise ValueError("pubkey is required")
    if (
        isinstance(expected_space, bool)
        or not isinstance(expected_space, int)
        or expected_space <= 0
    ):
        raise ValueError("expected_space must be a positive integer")
    if expected_space not in RARE_ACCOUNT_SPACES:
        raise ValueError("expected_space is not an accepted rare family")
    if not isinstance(include_raw_base64, bool):
        raise ValueError("include_raw_base64 must be boolean")

    if not isinstance(result, Mapping):
        raise WarpRareAccountCaptureError(
            "getAccountInfo returned a malformed result"
        )
    context = result.get("context")
    if not isinstance(context, Mapping):
        raise WarpRareAccountCaptureError(
            "getAccountInfo result is missing context"
        )
    context_slot = _nonnegative_int(context.get("slot"))
    if context_slot is None:
        raise WarpRareAccountCaptureError(
            "getAccountInfo context slot is missing or invalid"
        )

    value = result.get("value")
    if not isinstance(value, Mapping):
        raise WarpRareAccountCaptureError(
            "getAccountInfo returned no account value"
        )

    owner = _text(value.get("owner"))
    if owner != WARP_PROGRAM_ID:
        raise WarpRareAccountCaptureError(
            "captured account owner does not equal the Warp program"
        )

    executable = value.get("executable")
    if not isinstance(executable, bool):
        raise WarpRareAccountCaptureError(
            "captured account executable flag is missing or invalid"
        )
    if executable is not False:
        raise WarpRareAccountCaptureError(
            "rare state capture requires a non-executable account"
        )

    lamports = _nonnegative_int(value.get("lamports"))
    if lamports is None:
        raise WarpRareAccountCaptureError(
            "captured account lamports are missing or invalid"
        )

    data = value.get("data")
    if (
        not isinstance(data, list)
        or len(data) != 2
        or not isinstance(data[0], str)
        or data[1] != "base64"
    ):
        raise WarpRareAccountCaptureError(
            "captured account data must be [base64, 'base64']"
        )

    try:
        raw_bytes = base64.b64decode(data[0], validate=True)
    except (binascii.Error, ValueError):
        raise WarpRareAccountCaptureError(
            "captured account data is invalid base64"
        ) from None

    if len(raw_bytes) != expected_space:
        raise WarpRareAccountCaptureError(
            "captured account byte length does not equal inventory space"
        )

    prefix = raw_bytes[:PREFIX_BYTES]
    suffix = raw_bytes[-SUFFIX_BYTES:] if raw_bytes else b""
    digest = hashlib.sha256(raw_bytes).hexdigest()

    return {
        "contract": CONTRACT,
        "chain": chain,
        "pubkey": pubkey,
        "program_id": WARP_PROGRAM_ID,
        "owner": owner,
        "owner_verified": True,
        "inventory_space": expected_space,
        "data_length": len(raw_bytes),
        "data_length_verified": True,
        "context_slot": context_slot,
        "lamports": lamports,
        "executable": executable,
        "non_executable_verified": True,
        "data_sha256": digest,
        "prefix_hex": prefix.hex(),
        "suffix_hex": suffix.hex(),
        "data_base64": data[0] if include_raw_base64 else None,
        "raw_material_retained": include_raw_base64,
        "semantic_role": None,
        "semantic_role_verified": False,
        "binary_layout_verified": False,
        "field_offsets_verified": False,
        "semantic_contract_accepted": False,
        "cmis_promotable": False,
        "read_only": True,
        "execution_authorized": False,
    }


def capture_rare_accounts_from_inventory(
    inventory: Any,
    *,
    rpc_url: str,
    commitment: str = DEFAULT_COMMITMENT,
    timeout: int = 30,
    requester: Callable[..., Any] = _rpc_request,
    include_raw_base64: bool = False,
) -> dict[str, Any]:
    """Fetch and normalize each bounded rare candidate through getAccountInfo."""

    rpc_url = _text(rpc_url)
    commitment = _text(commitment)
    if not rpc_url:
        raise ValueError("rpc_url is required")
    if not commitment:
        raise ValueError("commitment is required")

    candidates = select_rare_account_candidates(inventory)
    captures: list[dict[str, Any]] = []
    for candidate in candidates:
        result = requester(
            "getAccountInfo",
            [
                candidate["pubkey"],
                {
                    "encoding": "base64",
                    "commitment": commitment,
                },
            ],
            rpc_url=rpc_url,
            timeout=timeout,
        )
        capture = parse_account_info_result(
            result,
            chain=candidate["chain"],
            pubkey=candidate["pubkey"],
            expected_space=candidate["inventory_space"],
            include_raw_base64=include_raw_base64,
        )
        captures.append(capture)

    captures.sort(key=lambda item: (item["inventory_space"], item["pubkey"]))
    return {
        "contract": CONTRACT,
        "chain": inventory.get("chain"),
        "program_id": WARP_PROGRAM_ID,
        "candidate_count": len(candidates),
        "capture_count": len(captures),
        "rare_spaces": sorted(RARE_ACCOUNT_SPACES),
        "captures": captures,
        "all_owner_verified": all(
            item["owner_verified"] is True for item in captures
        ),
        "all_data_lengths_verified": all(
            item["data_length_verified"] is True for item in captures
        ),
        "all_non_executable_verified": all(
            item["non_executable_verified"] is True for item in captures
        ),
        "raw_material_retained": include_raw_base64,
        "account_role_verified": False,
        "binary_layout_verified": False,
        "semantic_contract_accepted": False,
        "cmis_promotable": False,
        "read_only": True,
        "execution_authorized": False,
    }


def compare_rare_account_captures(
    solana_capture: Any,
    x1_capture: Any,
) -> dict[str, Any]:
    """Compare exact pubkey overlaps without promoting account semantics."""

    if not isinstance(solana_capture, Mapping):
        raise ValueError("solana_capture must be a mapping")
    if not isinstance(x1_capture, Mapping):
        raise ValueError("x1_capture must be a mapping")
    if solana_capture.get("chain") != "solana":
        raise ValueError("solana_capture.chain must be solana")
    if x1_capture.get("chain") != "x1":
        raise ValueError("x1_capture.chain must be x1")

    def by_pubkey(capture: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
        rows = capture.get("captures")
        if not isinstance(rows, list):
            raise ValueError("capture.captures must be a list")
        result: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("capture row must be a mapping")
            pubkey = _text(row.get("pubkey"))
            if not pubkey:
                raise ValueError("capture row pubkey is required")
            if pubkey in result:
                raise ValueError("capture contains duplicate pubkeys")
            result[pubkey] = row
        return result

    solana_rows = by_pubkey(solana_capture)
    x1_rows = by_pubkey(x1_capture)
    overlaps: list[dict[str, Any]] = []
    for pubkey in sorted(set(solana_rows) & set(x1_rows)):
        solana_row = solana_rows[pubkey]
        x1_row = x1_rows[pubkey]
        overlaps.append(
            {
                "pubkey": pubkey,
                "solana_space": solana_row.get("inventory_space"),
                "x1_space": x1_row.get("inventory_space"),
                "same_space": (
                    solana_row.get("inventory_space")
                    == x1_row.get("inventory_space")
                ),
                "same_data_sha256": (
                    solana_row.get("data_sha256")
                    == x1_row.get("data_sha256")
                ),
                "same_prefix_hex": (
                    solana_row.get("prefix_hex")
                    == x1_row.get("prefix_hex")
                ),
                "same_suffix_hex": (
                    solana_row.get("suffix_hex")
                    == x1_row.get("suffix_hex")
                ),
                "semantic_role_equivalence_verified": False,
            }
        )

    return {
        "contract": CONTRACT,
        "program_id": WARP_PROGRAM_ID,
        "exact_pubkey_overlap_count": len(overlaps),
        "exact_pubkey_overlaps": overlaps,
        "same_bytes_imply_same_semantics": False,
        "cross_chain_role_equivalence_verified": False,
        "binary_layout_verified": False,
        "semantic_contract_accepted": False,
        "cmis_promotable": False,
        "read_only": True,
        "execution_authorized": False,
    }


def capture_warp_rare_both_chains(
    *,
    solana_rpc_url: str = SOLANA_RPC_URL,
    x1_rpc_url: str = X1_RPC_URL,
    commitment: str = DEFAULT_COMMITMENT,
    timeout: int = 30,
    requester: Callable[..., Any] = _rpc_request,
    inventory_requester: Callable[..., Any] | None = None,
    include_raw_base64: bool = False,
) -> dict[str, Any]:
    """Inventory then capture only rare Warp state accounts on both chains."""

    inventory_requester = inventory_requester or requester
    inventories = inventory_warp_both_chains(
        solana_rpc_url=solana_rpc_url,
        x1_rpc_url=x1_rpc_url,
        commitment=commitment,
        data_slice_length=0,
        timeout=timeout,
        requester=inventory_requester,
    )

    solana_capture = capture_rare_accounts_from_inventory(
        inventories["solana_inventory"],
        rpc_url=solana_rpc_url,
        commitment=commitment,
        timeout=timeout,
        requester=requester,
        include_raw_base64=include_raw_base64,
    )
    x1_capture = capture_rare_accounts_from_inventory(
        inventories["x1_inventory"],
        rpc_url=x1_rpc_url,
        commitment=commitment,
        timeout=timeout,
        requester=requester,
        include_raw_base64=include_raw_base64,
    )
    comparison = compare_rare_account_captures(solana_capture, x1_capture)

    return {
        "contract": CONTRACT,
        "program_id": WARP_PROGRAM_ID,
        "source_inventory_contract": INVENTORY_CONTRACT,
        "solana_capture": solana_capture,
        "x1_capture": x1_capture,
        "comparison": comparison,
        "account_role_verified": False,
        "binary_layout_verified": False,
        "semantic_contract_accepted": False,
        "cmis_promotable": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT",
    "MAX_CANDIDATES_PER_CHAIN",
    "PREFIX_BYTES",
    "RARE_ACCOUNT_SPACES",
    "SUFFIX_BYTES",
    "WarpRareAccountCaptureError",
    "capture_rare_accounts_from_inventory",
    "capture_warp_rare_both_chains",
    "compare_rare_account_captures",
    "parse_account_info_result",
    "select_rare_account_candidates",
]
