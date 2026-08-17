"""Read-only X1 RPC token-account balance transport.

This module fetches raw ``getTokenAccountBalance`` observations only. It does
not infer that an account is a pool vault, does not map a vault to a pool/mint,
and does not promote the returned amount into a CMIS reserve fact. Those
identity and semantic gates belong in a separately verified adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

import requests

from config import SETTINGS


CHAIN = "x1"
RPC_METHOD = "getTokenAccountBalance"
RPC_SOURCE = "X1 RPC"


class X1RPCBalanceError(RuntimeError):
    """Raised when the read-only RPC transport or response contract fails."""


def _text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty.")
    return text


def fetch_token_account_balance_raw(
    account: Any,
    *,
    rpc_url: Optional[str] = None,
    commitment: str = "confirmed",
    session=requests,
    timeout: int = 20,
) -> dict[str, Any]:
    """Fetch one token-account balance without assigning reserve semantics."""
    account_text = _text("account", account)
    url = _text("rpc_url", rpc_url if rpc_url is not None else SETTINGS.x1_rpc_url)
    commitment_text = _text("commitment", commitment)

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": RPC_METHOD,
        "params": [account_text, {"commitment": commitment_text}],
    }

    response = session.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    body = response.json()

    if not isinstance(body, Mapping):
        raise X1RPCBalanceError("X1 RPC token-balance response must be an object.")
    if body.get("error") is not None:
        raise X1RPCBalanceError(f"X1 RPC returned an error for {RPC_METHOD}.")

    result = body.get("result")
    if not isinstance(result, Mapping):
        raise X1RPCBalanceError("X1 RPC token-balance result is missing or malformed.")

    context = result.get("context")
    value = result.get("value")
    if not isinstance(context, Mapping) or not isinstance(value, Mapping):
        raise X1RPCBalanceError("X1 RPC token-balance context/value is malformed.")

    slot = context.get("slot")
    amount = value.get("amount")
    decimals = value.get("decimals")
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise X1RPCBalanceError("X1 RPC token-balance context slot is invalid.")
    if not isinstance(amount, str) or not amount.isdigit():
        raise X1RPCBalanceError("X1 RPC token-balance raw amount is invalid.")
    if isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0:
        raise X1RPCBalanceError("X1 RPC token-balance decimals are invalid.")

    return {
        "chain": CHAIN,
        "source": RPC_SOURCE,
        "method": RPC_METHOD,
        "rpc_url": url,
        "account": account_text,
        "commitment": commitment_text,
        "slot": slot,
        "amount": amount,
        "decimals": decimals,
        "ui_amount": value.get("uiAmount"),
        "ui_amount_string": value.get("uiAmountString"),
        "raw_response": dict(body),
        "identity_verified": False,
        "reserve_semantics_verified": False,
        "cmis_promotable": False,
    }


__all__ = [
    "CHAIN",
    "RPC_METHOD",
    "RPC_SOURCE",
    "X1RPCBalanceError",
    "fetch_token_account_balance_raw",
]
