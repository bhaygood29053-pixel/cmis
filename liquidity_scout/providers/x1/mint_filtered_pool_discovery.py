"""Read-only X1 mint-filtered AMM program-state discovery for CMIS v1.5.3.

This module applies an already-verified program-owner/account-size mint layout to
X1 RPC ``getProgramAccounts`` filters. It enumerates program-owned accounts whose
binary state contains a target mint at one of the supplied byte offsets.

The output is intentionally narrower than "pool discovery": a matching account
is only a program-state account in the verified family until a later phase
proves that every matching family member is in fact a liquidity-pool state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.pool_state_fingerprint import decode_base58_pubkey
from liquidity_scout.providers.x1.program_accounts import parse_program_accounts_result
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, rpc_request

VERSION = "1.5.3"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _normalize_offsets(values: Sequence[int]) -> tuple[int, ...]:
    offsets: list[int] = []
    seen = set()
    for raw in values:
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            raise ValueError("mint offsets must be non-negative integers")
        if raw in seen:
            continue
        seen.add(raw)
        offsets.append(raw)
    if len(offsets) < 2:
        raise ValueError("at least two distinct mint offsets are required")
    return tuple(offsets)


def discover_program_state_accounts_for_mint(
    *,
    mint: str,
    program_id: str,
    account_space: int,
    mint_offsets: Sequence[int],
    rpc_url: str = DEFAULT_X1_RPC_URL,
    commitment: str = "confirmed",
    requester: Callable[..., Any] = rpc_request,
) -> dict[str, Any]:
    """Enumerate one verified program/size family for a target mint.

    One ``getProgramAccounts`` query is issued per verified mint offset with both
    ``dataSize`` and ``memcmp`` filters. Results are unioned by account pubkey and
    retain which offsets matched. No returned account is promoted to a pool.
    """

    mint = _text(mint)
    program_id = _text(program_id)
    rpc_url = _text(rpc_url)
    commitment = _text(commitment)
    if not mint:
        raise ValueError("mint is required")
    decode_base58_pubkey(mint)
    if not program_id:
        raise ValueError("program_id is required")
    decode_base58_pubkey(program_id)
    if not rpc_url:
        raise ValueError("rpc_url is required")
    if not commitment:
        raise ValueError("commitment is required")

    account_space = _positive_int(account_space, name="account_space")
    offsets = _normalize_offsets(mint_offsets)

    query_reports: list[dict[str, Any]] = []
    union: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []

    for offset in offsets:
        config = {
            "encoding": "base64",
            "commitment": commitment,
            "dataSlice": {"offset": 0, "length": 0},
            "filters": [
                {"dataSize": account_space},
                {"memcmp": {"offset": offset, "bytes": mint}},
            ],
        }

        try:
            result = requester(
                "getProgramAccounts",
                [program_id, config],
                rpc_url=rpc_url,
            )
            parsed = parse_program_accounts_result(result, program_id=program_id)
            returned = parsed.get("accounts") or []
            space_mismatch_count = sum(
                1
                for row in returned
                if isinstance(row, Mapping) and row.get("space") != account_space
            )
            query_integrity = bool(
                parsed.get("response_integrity_verified") is True
                and space_mismatch_count == 0
            )

            for raw in returned:
                if not isinstance(raw, Mapping):
                    continue
                pubkey = _text(raw.get("pubkey"))
                if not pubkey:
                    continue
                row = union.setdefault(
                    pubkey,
                    {
                        "pubkey": pubkey,
                        "owner": _text(raw.get("owner")),
                        "space": raw.get("space"),
                        "owner_matches_program": raw.get("owner_matches_program") is True,
                        "matched_mint_offsets": [],
                        "pool_role_promoted": False,
                    },
                )
                if offset not in row["matched_mint_offsets"]:
                    row["matched_mint_offsets"].append(offset)

            query_reports.append(
                {
                    "offset": offset,
                    "returned_row_count": parsed.get("returned_row_count"),
                    "unique_account_count": parsed.get("unique_account_count"),
                    "space_mismatch_count": space_mismatch_count,
                    "response_integrity_verified": query_integrity,
                }
            )
        except Exception as exc:
            query_reports.append(
                {
                    "offset": offset,
                    "returned_row_count": None,
                    "unique_account_count": None,
                    "space_mismatch_count": None,
                    "response_integrity_verified": False,
                }
            )
            errors.append(
                {
                    "offset": offset,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    accounts = sorted(union.values(), key=lambda row: row["pubkey"])
    for row in accounts:
        row["matched_mint_offsets"].sort()

    all_queries_integrity_verified = bool(query_reports) and all(
        row.get("response_integrity_verified") is True for row in query_reports
    )
    every_union_account_matches_family = bool(accounts) and all(
        row.get("owner_matches_program") is True and row.get("space") == account_space
        for row in accounts
    )

    return {
        "service": "mint_filtered_program_state_discovery",
        "version": VERSION,
        "chain": "x1",
        "mint": mint,
        "program_id": program_id,
        "account_space": account_space,
        "mint_offsets": list(offsets),
        "rpc_method": "getProgramAccounts",
        "filter_queries": query_reports,
        "accounts": accounts,
        "summary": {
            "filter_query_count": len(query_reports),
            "all_filter_queries_integrity_verified": all_queries_integrity_verified,
            "unique_matching_program_state_account_count": len(accounts),
            "every_matching_account_owner_and_size_verified": (
                every_union_account_matches_family
            ),
            "targeted_program_family_mint_filter_observed": bool(
                all_queries_integrity_verified
            ),
            "every_matching_account_is_pool_verified": False,
            "recognized_program_registry_globally_exhaustive": False,
            "global_onchain_pool_discovery_proven": False,
            "interpretation": (
                "RPC filters enumerate program-owned accounts in the supplied "
                "owner/size family that contain the target mint at verified mint "
                "offsets. Matching accounts are not promoted to liquidity pools."
            ),
        },
        "errors": errors,
    }


__all__ = ["VERSION", "discover_program_state_accounts_for_mint"]
