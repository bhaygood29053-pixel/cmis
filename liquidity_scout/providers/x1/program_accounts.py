"""Read-only X1 AMM program-account inventory for CMIS.

This module is intentionally observational. It enumerates accounts owned by the
recognized XDEX/XenDEX AMM programs through X1 RPC ``getProgramAccounts`` and
records deterministic response-integrity evidence. It does not assume an AMM
binary layout and does not promote any returned account to a pool merely because
it is program-owned.

The important boundary is explicit:

- ``getProgramAccounts`` can independently enumerate state accounts owned by a
  recognized program;
- CMIS still does not claim that the recognized program registry is globally
  exhaustive;
- CMIS still does not claim that every program-owned account is a liquidity
  pool until pool-state layout/identity is independently proven.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, rpc_request
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    XENDEX_AMM_PROGRAM_ID,
)

VERSION = "1.5.0"
RECOGNIZED_AMM_PROGRAM_IDS = (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    XENDEX_AMM_PROGRAM_ID,
)


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


def parse_program_accounts_result(
    result: Any,
    *,
    program_id: str,
) -> dict[str, Any]:
    """Parse one ``getProgramAccounts`` result without inferring pool roles."""

    program_id = _text(program_id)
    if not program_id:
        raise ValueError("program_id is required")

    rows = result
    context_slot = None
    if isinstance(result, Mapping) and "value" in result:
        rows = result.get("value")
        context = result.get("context")
        if isinstance(context, Mapping):
            context_slot = _nonnegative_int(context.get("slot"))

    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("getProgramAccounts returned no usable account list")

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
        space = _nonnegative_int(account.get("space"))
        lamports = _nonnegative_int(account.get("lamports"))
        executable = account.get("executable")
        rent_epoch = _nonnegative_int(account.get("rentEpoch"))
        owner_matches_program = owner == program_id
        if not owner_matches_program:
            owner_mismatch_count += 1

        size_counts[str(space) if space is not None else "unknown"] += 1
        accounts.append(
            {
                "pubkey": pubkey,
                "owner": owner,
                "owner_matches_program": owner_matches_program,
                "space": space,
                "lamports": lamports,
                "executable": executable if isinstance(executable, bool) else None,
                "rent_epoch": rent_epoch,
                "pool_role_promoted": False,
            }
        )

    response_integrity_verified = bool(
        malformed_row_count == 0
        and duplicate_pubkey_count == 0
        and owner_mismatch_count == 0
    )

    return {
        "program_id": program_id,
        "context_slot": context_slot,
        "returned_row_count": len(rows),
        "unique_account_count": len(accounts),
        "malformed_row_count": malformed_row_count,
        "duplicate_pubkey_count": duplicate_pubkey_count,
        "owner_mismatch_count": owner_mismatch_count,
        "account_size_counts": dict(sorted(size_counts.items())),
        "response_integrity_verified": response_integrity_verified,
        "program_account_enumeration_observed": True,
        "program_inventory_exhaustive_promoted": False,
        "pool_state_layout_verified": False,
        "accounts": accounts,
    }


def inventory_program_accounts(
    program_id: str,
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    commitment: str = "confirmed",
    data_slice_length: int = 0,
    requester: Callable[..., Any] = rpc_request,
) -> dict[str, Any]:
    """Enumerate one recognized program's owned accounts through X1 RPC.

    A zero-length data slice keeps the first inventory bounded while still
    returning each account identity and metadata. Later phases can sample full
    account bytes only after the inventory shape is known.
    """

    program_id = _text(program_id)
    rpc_url = _text(rpc_url)
    commitment = _text(commitment)
    if not program_id:
        raise ValueError("program_id is required")
    if not rpc_url:
        raise ValueError("rpc_url is required")
    if not commitment:
        raise ValueError("commitment is required")
    if isinstance(data_slice_length, bool) or not isinstance(data_slice_length, int):
        raise ValueError("data_slice_length must be an integer >= 0")
    if data_slice_length < 0 or data_slice_length > 256:
        raise ValueError("data_slice_length must be an integer between 0 and 256")

    config = {
        "encoding": "base64",
        "commitment": commitment,
        "dataSlice": {"offset": 0, "length": data_slice_length},
    }
    result = requester(
        "getProgramAccounts",
        [program_id, config],
        rpc_url=rpc_url,
    )
    parsed = parse_program_accounts_result(result, program_id=program_id)
    parsed.update(
        {
            "version": VERSION,
            "chain": "x1",
            "rpc_url": rpc_url,
            "rpc_method": "getProgramAccounts",
            "commitment": commitment,
            "data_slice_length": data_slice_length,
        }
    )
    return parsed


def inventory_recognized_amm_programs(
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    program_ids: Sequence[str] = RECOGNIZED_AMM_PROGRAM_IDS,
    commitment: str = "confirmed",
    data_slice_length: int = 0,
    requester: Callable[..., Any] = rpc_request,
) -> dict[str, Any]:
    """Inventory configured XDEX/XenDEX AMM programs without global promotion."""

    reports = []
    seen = set()
    for raw_program_id in program_ids:
        program_id = _text(raw_program_id)
        if not program_id or program_id in seen:
            continue
        seen.add(program_id)
        reports.append(
            inventory_program_accounts(
                program_id,
                rpc_url=rpc_url,
                commitment=commitment,
                data_slice_length=data_slice_length,
                requester=requester,
            )
        )

    all_responses_integrity_verified = bool(reports) and all(
        item.get("response_integrity_verified") is True for item in reports
    )
    account_pubkeys = sorted(
        {
            item.get("pubkey")
            for report in reports
            for item in report.get("accounts", [])
            if isinstance(item, Mapping) and _text(item.get("pubkey"))
        }
    )

    return {
        "service": "recognized_amm_program_account_inventory",
        "version": VERSION,
        "chain": "x1",
        "recognized_program_count": len(reports),
        "programs": reports,
        "summary": {
            "all_responses_integrity_verified": all_responses_integrity_verified,
            "unique_program_owned_account_count": len(account_pubkeys),
            "recognized_program_account_inventory_observed": bool(reports),
            "recognized_program_registry_globally_exhaustive": False,
            "pool_state_layout_verified": False,
            "global_onchain_pool_discovery_proven": False,
            "interpretation": (
                "X1 RPC can enumerate accounts owned by the configured recognized "
                "AMM programs. This phase does not yet prove that the AMM program "
                "registry is globally exhaustive or that every program-owned "
                "account is a liquidity-pool state account."
            ),
        },
        "account_pubkeys": account_pubkeys,
    }


__all__ = [
    "RECOGNIZED_AMM_PROGRAM_IDS",
    "VERSION",
    "inventory_program_accounts",
    "inventory_recognized_amm_programs",
    "parse_program_accounts_result",
]
