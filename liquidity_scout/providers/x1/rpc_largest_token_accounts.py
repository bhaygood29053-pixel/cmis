"""Read-only X1 RPC largest-token-account transport.

This module collects ``getTokenLargestAccounts`` observations for one caller-
supplied mint. It preserves account-level balances and RPC context but does not
interpret the result as a holder count or holder distribution: token accounts
are not necessarily unique beneficial owners.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

import requests

from config import SETTINGS


CHAIN = "x1"
RPC_METHOD = "getTokenLargestAccounts"
RPC_SOURCE = "X1 RPC"


class X1RPCLargestTokenAccountsError(RuntimeError):
    """Raised when the read-only largest-token-accounts contract fails."""


def _text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty.")
    return text


def fetch_largest_token_accounts_raw(
    mint: Any,
    *,
    rpc_url: Optional[str] = None,
    commitment: str = "confirmed",
    session=requests,
    timeout: int = 20,
) -> dict[str, Any]:
    """Fetch largest token accounts without assigning holder semantics."""
    mint_text = _text("mint", mint)
    url = _text("rpc_url", rpc_url if rpc_url is not None else SETTINGS.x1_rpc_url)
    commitment_text = _text("commitment", commitment)

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": RPC_METHOD,
        "params": [mint_text, {"commitment": commitment_text}],
    }
    response = session.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    body = response.json()

    if not isinstance(body, Mapping):
        raise X1RPCLargestTokenAccountsError(
            "X1 RPC largest-accounts response must be an object."
        )
    if body.get("error") is not None:
        raise X1RPCLargestTokenAccountsError(
            f"X1 RPC returned an error for {RPC_METHOD}."
        )

    result = body.get("result")
    if not isinstance(result, Mapping):
        raise X1RPCLargestTokenAccountsError(
            "X1 RPC largest-accounts result is missing or malformed."
        )
    context = result.get("context")
    values = result.get("value")
    if not isinstance(context, Mapping) or not isinstance(values, list):
        raise X1RPCLargestTokenAccountsError(
            "X1 RPC largest-accounts context/value is malformed."
        )

    slot = context.get("slot")
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise X1RPCLargestTokenAccountsError(
            "X1 RPC largest-accounts context slot is invalid."
        )

    accounts: list[dict[str, Any]] = []
    seen: set[str] = set()
    expected_decimals: int | None = None
    previous_amount: int | None = None
    for index, item in enumerate(values):
        if not isinstance(item, Mapping):
            raise X1RPCLargestTokenAccountsError(
                f"largest account entry {index} is malformed."
            )
        address = _text(f"value[{index}].address", item.get("address"))
        amount = item.get("amount")
        decimals = item.get("decimals")
        if address in seen:
            raise X1RPCLargestTokenAccountsError(
                "X1 RPC largest-accounts response contains duplicate accounts."
            )
        if not isinstance(amount, str) or not amount.isdigit():
            raise X1RPCLargestTokenAccountsError(
                f"largest account entry {index} amount is invalid."
            )
        amount_int = int(amount)
        if previous_amount is not None and amount_int > previous_amount:
            raise X1RPCLargestTokenAccountsError(
                "X1 RPC largest-accounts response is not ordered by descending "
                "raw amount."
            )
        if isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0:
            raise X1RPCLargestTokenAccountsError(
                f"largest account entry {index} decimals are invalid."
            )
        if expected_decimals is None:
            expected_decimals = decimals
        elif decimals != expected_decimals:
            raise X1RPCLargestTokenAccountsError(
                "X1 RPC largest-accounts decimals are inconsistent."
            )
        previous_amount = amount_int
        seen.add(address)
        accounts.append(
            {
                "address": address,
                "amount": amount,
                "decimals": decimals,
                "ui_amount": item.get("uiAmount"),
                "ui_amount_string": item.get("uiAmountString"),
            }
        )

    return {
        "chain": CHAIN,
        "source": RPC_SOURCE,
        "method": RPC_METHOD,
        "rpc_url": url,
        "mint": mint_text,
        "commitment": commitment_text,
        "slot": slot,
        "accounts": accounts,
        "account_count_observed": len(accounts),
        "descending_amount_order_verified": True,
        "raw_response": dict(body),
        "holder_semantics_verified": False,
        "holder_coverage_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
        "warnings": [
            "largest_token_accounts_are_not_unique_holder_identities",
            "rpc_result_is_top_account_coverage_not_total_holder_coverage",
        ],
    }


__all__ = [
    "CHAIN",
    "RPC_METHOD",
    "RPC_SOURCE",
    "X1RPCLargestTokenAccountsError",
    "fetch_largest_token_accounts_raw",
]
