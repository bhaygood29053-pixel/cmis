"""Read-only Warp program-account inventory across Solana and X1.

This discovery slice intentionally does not decode Warp account bytes or assign
semantic roles.  It inventories accounts owned by the exact Warp program using
Solana-compatible `getProgramAccounts`, records structural metadata, and
produces deterministic fingerprints for later semantic discovery.

No account is promoted to "config", "guardian", "route", "vault", or any
other role merely because it is program-owned or has a particular size.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
from typing import Any, Callable

import requests


CONTRACT = "warp_onchain_account_inventory/v1"
WARP_PROGRAM_ID = "6JbPTuxVuoTgyQeXFb9MH8C8nUY8NBbLP1Lu4B13JfMD"
X1_RPC_URL = "https://rpc.mainnet.x1.xyz"
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
DEFAULT_COMMITMENT = "confirmed"
MAX_DATA_SLICE_LENGTH = 256


class WarpOnchainInventoryError(RuntimeError):
    """Raised when a Warp read-only inventory cannot be safely established."""


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


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _rpc_request(
    method: str,
    params: list[Any],
    *,
    rpc_url: str,
    timeout: int = 30,
    post: Callable[..., Any] = requests.post,
) -> Any:
    """Perform one bounded, read-only Solana-compatible JSON-RPC request."""

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
        raise WarpOnchainInventoryError(
            f"{method} transport failed ({type(exc).__name__})"
        ) from None

    if not isinstance(body, Mapping):
        raise WarpOnchainInventoryError(f"{method} returned a non-object response")
    if body.get("error") is not None:
        error = body.get("error")
        code = error.get("code") if isinstance(error, Mapping) else None
        raise WarpOnchainInventoryError(
            f"{method} returned JSON-RPC error code {code!r}"
        )
    if "result" not in body:
        raise WarpOnchainInventoryError(f"{method} response is missing result")
    return body.get("result")


def parse_program_accounts_result(
    result: Any,
    *,
    chain: str,
    program_id: str = WARP_PROGRAM_ID,
) -> dict[str, Any]:
    """Parse one getProgramAccounts result without assigning account semantics."""

    chain = (_text(chain) or "").casefold()
    program_id = _text(program_id)
    if chain not in {"solana", "x1"}:
        raise ValueError("chain must be solana or x1")
    if not program_id:
        raise ValueError("program_id is required")

    rows = result
    context_slot = None
    if isinstance(result, Mapping) and "value" in result:
        rows = result.get("value")
        context = result.get("context")
        if isinstance(context, Mapping):
            context_slot = _nonnegative_int(context.get("slot"))

    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise WarpOnchainInventoryError(
            "getProgramAccounts returned no usable account list"
        )

    accounts: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_pubkey_count = 0
    malformed_row_count = 0
    owner_mismatch_count = 0
    size_counts: Counter[str] = Counter()

    for raw in rows:
        if not isinstance(raw, Mapping):
            malformed_row_count += 1
            continue

        pubkey = _text(raw.get("pubkey"))
        account = raw.get("account")
        if not pubkey or not isinstance(account, Mapping):
            malformed_row_count += 1
            continue

        if pubkey in seen:
            duplicate_pubkey_count += 1
            continue
        seen.add(pubkey)

        owner = _text(account.get("owner"))
        lamports = _nonnegative_int(account.get("lamports"))
        executable = account.get("executable")
        rent_epoch = _nonnegative_int(account.get("rentEpoch"))
        space = _nonnegative_int(account.get("space"))

        # Some Solana-compatible providers omit account.space when a dataSlice is
        # used.  If full base64 data was nevertheless supplied, only its encoded
        # shape is retained here; this slice never decodes account bytes.
        data = account.get("data")
        data_encoding = None
        encoded_data_length = None
        if isinstance(data, list) and len(data) == 2:
            if isinstance(data[0], str):
                encoded_data_length = len(data[0])
            if isinstance(data[1], str):
                data_encoding = data[1]

        if owner != program_id:
            owner_mismatch_count += 1

        size_counts[str(space) if space is not None else "unknown"] += 1
        accounts.append(
            {
                "pubkey": pubkey,
                "owner": owner,
                "owner_matches_program": owner == program_id,
                "space": space,
                "lamports": lamports,
                "executable": executable if isinstance(executable, bool) else None,
                "rent_epoch": rent_epoch,
                "data_encoding": data_encoding,
                "encoded_data_length": encoded_data_length,
                "semantic_role": None,
                "semantic_role_verified": False,
            }
        )

    accounts.sort(key=lambda item: item["pubkey"])

    response_integrity_verified = bool(
        malformed_row_count == 0
        and duplicate_pubkey_count == 0
        and owner_mismatch_count == 0
    )

    fingerprint_payload = [
        {
            "pubkey": item["pubkey"],
            "owner": item["owner"],
            "space": item["space"],
            "lamports": item["lamports"],
            "executable": item["executable"],
            "rent_epoch": item["rent_epoch"],
        }
        for item in accounts
    ]
    structural_fingerprint_payload = [
        {
            "pubkey": item["pubkey"],
            "owner": item["owner"],
            "space": item["space"],
            "executable": item["executable"],
        }
        for item in accounts
    ]

    return {
        "contract": CONTRACT,
        "chain": chain,
        "program_id": program_id,
        "rpc_method": "getProgramAccounts",
        "context_slot": context_slot,
        "returned_row_count": len(rows),
        "unique_account_count": len(accounts),
        "malformed_row_count": malformed_row_count,
        "duplicate_pubkey_count": duplicate_pubkey_count,
        "owner_mismatch_count": owner_mismatch_count,
        "account_size_counts": dict(sorted(size_counts.items())),
        "response_integrity_verified": response_integrity_verified,
        "inventory_sha256": _canonical_sha256(fingerprint_payload),
        "structural_inventory_sha256": _canonical_sha256(
            structural_fingerprint_payload
        ),
        "accounts": accounts,
        "account_binary_layout_verified": False,
        "config_account_identity_verified": False,
        "guardian_account_identity_verified": False,
        "route_semantics_verified": False,
        "semantic_contract_accepted": False,
        "cmis_promotable": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


def inventory_warp_program_accounts(
    *,
    chain: str,
    rpc_url: str | None = None,
    program_id: str = WARP_PROGRAM_ID,
    commitment: str = DEFAULT_COMMITMENT,
    data_slice_length: int = 0,
    timeout: int = 30,
    requester: Callable[..., Any] = _rpc_request,
) -> dict[str, Any]:
    """Inventory Warp-owned accounts on one chain with a bounded data slice."""

    chain = (_text(chain) or "").casefold()
    if chain not in {"solana", "x1"}:
        raise ValueError("chain must be solana or x1")
    program_id = _text(program_id)
    commitment = _text(commitment)
    if not program_id:
        raise ValueError("program_id is required")
    if not commitment:
        raise ValueError("commitment is required")
    if isinstance(data_slice_length, bool) or not isinstance(data_slice_length, int):
        raise ValueError("data_slice_length must be an integer")
    if data_slice_length < 0 or data_slice_length > MAX_DATA_SLICE_LENGTH:
        raise ValueError(
            f"data_slice_length must be between 0 and {MAX_DATA_SLICE_LENGTH}"
        )

    default_url = SOLANA_RPC_URL if chain == "solana" else X1_RPC_URL
    resolved_rpc_url = _text(rpc_url) or default_url

    config = {
        "encoding": "base64",
        "commitment": commitment,
        "dataSlice": {"offset": 0, "length": data_slice_length},
        "withContext": True,
    }

    result = requester(
        "getProgramAccounts",
        [program_id, config],
        rpc_url=resolved_rpc_url,
        timeout=timeout,
    )
    parsed = parse_program_accounts_result(
        result,
        chain=chain,
        program_id=program_id,
    )
    parsed.update(
        {
            "rpc_url": resolved_rpc_url,
            "commitment": commitment,
            "data_slice_length": data_slice_length,
        }
    )
    return parsed


def compare_warp_inventories(
    solana_inventory: Any,
    x1_inventory: Any,
) -> dict[str, Any]:
    """Compare account inventories without inferring semantic equivalence."""

    if not isinstance(solana_inventory, Mapping):
        raise ValueError("solana_inventory must be a mapping")
    if not isinstance(x1_inventory, Mapping):
        raise ValueError("x1_inventory must be a mapping")
    if solana_inventory.get("chain") != "solana":
        raise ValueError("solana_inventory.chain must be solana")
    if x1_inventory.get("chain") != "x1":
        raise ValueError("x1_inventory.chain must be x1")
    if solana_inventory.get("program_id") != WARP_PROGRAM_ID:
        raise ValueError("solana inventory must use the exact Warp program id")
    if x1_inventory.get("program_id") != WARP_PROGRAM_ID:
        raise ValueError("x1 inventory must use the exact Warp program id")

    def pubkeys(inventory: Mapping[str, Any]) -> set[str]:
        result: set[str] = set()
        accounts = inventory.get("accounts")
        if not isinstance(accounts, list):
            raise ValueError("inventory.accounts must be a list")
        for item in accounts:
            if not isinstance(item, Mapping):
                raise ValueError("inventory account must be a mapping")
            pubkey = _text(item.get("pubkey"))
            if not pubkey:
                raise ValueError("inventory account pubkey is required")
            result.add(pubkey)
        return result

    solana_pubkeys = pubkeys(solana_inventory)
    x1_pubkeys = pubkeys(x1_inventory)
    overlap = sorted(solana_pubkeys & x1_pubkeys)

    core = {
        "contract": CONTRACT,
        "program_id": WARP_PROGRAM_ID,
        "solana": {
            "unique_account_count": solana_inventory.get("unique_account_count"),
            "account_size_counts": solana_inventory.get("account_size_counts"),
            "inventory_sha256": solana_inventory.get("inventory_sha256"),
            "structural_inventory_sha256": solana_inventory.get(
                "structural_inventory_sha256"
            ),
            "context_slot": solana_inventory.get("context_slot"),
            "response_integrity_verified": solana_inventory.get(
                "response_integrity_verified"
            ),
        },
        "x1": {
            "unique_account_count": x1_inventory.get("unique_account_count"),
            "account_size_counts": x1_inventory.get("account_size_counts"),
            "inventory_sha256": x1_inventory.get("inventory_sha256"),
            "structural_inventory_sha256": x1_inventory.get(
                "structural_inventory_sha256"
            ),
            "context_slot": x1_inventory.get("context_slot"),
            "response_integrity_verified": x1_inventory.get(
                "response_integrity_verified"
            ),
        },
        "exact_pubkey_overlap": overlap,
        "exact_pubkey_overlap_count": len(overlap),
    }

    return {
        **core,
        "comparison_sha256": _canonical_sha256(core),
        "same_size_implies_same_role": False,
        "cross_chain_role_equivalence_verified": False,
        "account_binary_layout_verified": False,
        "semantic_contract_accepted": False,
        "cmis_promotable": False,
        "read_only": True,
        "execution_authorized": False,
    }


def inventory_warp_both_chains(
    *,
    solana_rpc_url: str = SOLANA_RPC_URL,
    x1_rpc_url: str = X1_RPC_URL,
    commitment: str = DEFAULT_COMMITMENT,
    data_slice_length: int = 0,
    timeout: int = 30,
    requester: Callable[..., Any] = _rpc_request,
) -> dict[str, Any]:
    """Run the same bounded Warp inventory independently on Solana and X1."""

    solana = inventory_warp_program_accounts(
        chain="solana",
        rpc_url=solana_rpc_url,
        commitment=commitment,
        data_slice_length=data_slice_length,
        timeout=timeout,
        requester=requester,
    )
    x1 = inventory_warp_program_accounts(
        chain="x1",
        rpc_url=x1_rpc_url,
        commitment=commitment,
        data_slice_length=data_slice_length,
        timeout=timeout,
        requester=requester,
    )
    comparison = compare_warp_inventories(solana, x1)

    return {
        "contract": CONTRACT,
        "program_id": WARP_PROGRAM_ID,
        "solana_inventory": solana,
        "x1_inventory": x1,
        "comparison": comparison,
        "next_step": (
            "Classify stable account-size families and capture bounded account bytes "
            "only after separate review; do not assign semantic roles from size alone."
        ),
        "semantic_contract_accepted": False,
        "cmis_promotable": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT",
    "DEFAULT_COMMITMENT",
    "MAX_DATA_SLICE_LENGTH",
    "SOLANA_RPC_URL",
    "WARP_PROGRAM_ID",
    "X1_RPC_URL",
    "WarpOnchainInventoryError",
    "compare_warp_inventories",
    "inventory_warp_both_chains",
    "inventory_warp_program_accounts",
    "parse_program_accounts_result",
]
