"""Read-only X1 RPC mint-filtered token-account enumeration probe.

This transport probes the Solana-compatible ``getProgramAccounts`` contract for
one explicit token program and mint. It validates every returned parsed token
account against the requested mint/program and exposes only an observed count
candidate.

A successful RPC response does *not* by itself prove that a public/provider RPC
returned an untruncated complete population. Consequently this module never
labels its count as total coverage and cannot directly satisfy the CMIS total
-token-account observation contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

import requests

from config import SETTINGS


CHAIN = "x1"
RPC_METHOD = "getProgramAccounts"
RPC_SOURCE = "X1 RPC"
MINT_OFFSET = 0


class X1RPCTokenAccountEnumerationError(RuntimeError):
    """Raised when the bounded read-only enumeration probe fails closed."""


def _text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty.")
    return text


def fetch_token_accounts_by_mint_raw(
    mint: Any,
    *,
    token_program_id: Any,
    rpc_url: Optional[str] = None,
    commitment: str = "confirmed",
    session=requests,
    timeout: int = 30,
) -> dict[str, Any]:
    """Probe one mint-filtered token-account population without claiming totality."""
    mint_text = _text("mint", mint)
    program_text = _text("token_program_id", token_program_id)
    url = _text("rpc_url", rpc_url if rpc_url is not None else SETTINGS.x1_rpc_url)
    commitment_text = _text("commitment", commitment)

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": RPC_METHOD,
        "params": [
            program_text,
            {
                "commitment": commitment_text,
                "encoding": "jsonParsed",
                "withContext": True,
                "filters": [
                    {
                        "memcmp": {
                            "offset": MINT_OFFSET,
                            "bytes": mint_text,
                        }
                    }
                ],
            },
        ],
    }

    try:
        response = session.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        raise X1RPCTokenAccountEnumerationError(
            "X1 RPC token-account enumeration request failed."
        ) from exc

    if not isinstance(body, Mapping):
        raise X1RPCTokenAccountEnumerationError(
            "X1 RPC token-account enumeration response must be an object."
        )
    if body.get("error") is not None:
        raise X1RPCTokenAccountEnumerationError(
            f"X1 RPC returned an error for {RPC_METHOD}."
        )

    result = body.get("result")
    if not isinstance(result, Mapping):
        raise X1RPCTokenAccountEnumerationError(
            "X1 RPC token-account enumeration result is missing or malformed."
        )
    context = result.get("context")
    values = result.get("value")
    if not isinstance(context, Mapping) or not isinstance(values, list):
        raise X1RPCTokenAccountEnumerationError(
            "X1 RPC token-account enumeration context/value is malformed."
        )

    slot = context.get("slot")
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise X1RPCTokenAccountEnumerationError(
            "X1 RPC token-account enumeration context slot is invalid."
        )

    accounts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(values):
        if not isinstance(item, Mapping):
            raise X1RPCTokenAccountEnumerationError(
                f"token account entry {index} is malformed."
            )
        pubkey = _text(f"value[{index}].pubkey", item.get("pubkey"))
        if pubkey in seen:
            raise X1RPCTokenAccountEnumerationError(
                "X1 RPC token-account enumeration contains duplicate accounts."
            )

        account = item.get("account")
        if not isinstance(account, Mapping):
            raise X1RPCTokenAccountEnumerationError(
                f"token account entry {index} account object is malformed."
            )
        owner_program = _text(
            f"value[{index}].account.owner", account.get("owner")
        )
        if owner_program != program_text:
            raise X1RPCTokenAccountEnumerationError(
                "X1 RPC returned an account owned by a different token program."
            )

        data = account.get("data")
        if not isinstance(data, Mapping):
            raise X1RPCTokenAccountEnumerationError(
                f"token account entry {index} parsed data is missing."
            )
        parsed = data.get("parsed")
        if not isinstance(parsed, Mapping) or parsed.get("type") != "account":
            raise X1RPCTokenAccountEnumerationError(
                f"token account entry {index} is not a parsed token account."
            )
        info = parsed.get("info")
        if not isinstance(info, Mapping):
            raise X1RPCTokenAccountEnumerationError(
                f"token account entry {index} parsed info is malformed."
            )
        returned_mint = _text(
            f"value[{index}].account.data.parsed.info.mint", info.get("mint")
        )
        if returned_mint != mint_text:
            raise X1RPCTokenAccountEnumerationError(
                "X1 RPC returned a token account for a different mint."
            )

        token_amount = info.get("tokenAmount")
        if not isinstance(token_amount, Mapping):
            raise X1RPCTokenAccountEnumerationError(
                f"token account entry {index} tokenAmount is malformed."
            )
        raw_amount = token_amount.get("amount")
        decimals = token_amount.get("decimals")
        if not isinstance(raw_amount, str) or not raw_amount.isdigit():
            raise X1RPCTokenAccountEnumerationError(
                f"token account entry {index} raw amount is invalid."
            )
        if (
            isinstance(decimals, bool)
            or not isinstance(decimals, int)
            or decimals < 0
        ):
            raise X1RPCTokenAccountEnumerationError(
                f"token account entry {index} decimals are invalid."
            )

        seen.add(pubkey)
        accounts.append(
            {
                "address": pubkey,
                "mint": returned_mint,
                "token_program_id": owner_program,
                "owner": info.get("owner"),
                "state": info.get("state"),
                "raw_amount": raw_amount,
                "decimals": decimals,
            }
        )

    return {
        "chain": CHAIN,
        "source": RPC_SOURCE,
        "method": RPC_METHOD,
        "mint": mint_text,
        "token_program_id": program_text,
        "commitment": commitment_text,
        "slot": slot,
        "mint_filter": {"offset": MINT_OFFSET, "bytes": mint_text},
        "encoding": "jsonParsed",
        "with_context": True,
        "accounts": accounts,
        "account_count_candidate": len(accounts),
        "returned_account_identity_verified": True,
        "token_account_semantics_verified": True,
        "enumeration_complete": False,
        "truncation_absent_verified": False,
        "coverage": "unverified",
        "total_count_eligible": False,
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
        "warnings": [
            "getProgramAccounts_success_does_not_prove_provider_truncation_absent",
            "token_accounts_are_not_unique_wallet_or_beneficial_owner_identities",
        ],
    }


__all__ = [
    "CHAIN",
    "MINT_OFFSET",
    "RPC_METHOD",
    "RPC_SOURCE",
    "X1RPCTokenAccountEnumerationError",
    "fetch_token_accounts_by_mint_raw",
]
