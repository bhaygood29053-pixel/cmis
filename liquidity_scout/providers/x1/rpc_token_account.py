"""Read-only X1 RPC token-account identity transport.

This module calls ``getAccountInfo`` with ``jsonParsed`` encoding and preserves
only directly observed token-account identity fields. It does not decide that
an account belongs to a pool, does not compare the observed mint/authority to
an expected identity, and never promotes the observation into a CMIS reserve
fact by itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

import requests

from config import SETTINGS


CHAIN = "x1"
RPC_METHOD = "getAccountInfo"
RPC_SOURCE = "X1 RPC"
ENCODING = "jsonParsed"


class X1RPCTokenAccountError(RuntimeError):
    """Raised when the read-only token-account identity contract fails."""


def _text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty.")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def fetch_token_account_identity_raw(
    account: Any,
    *,
    rpc_url: Optional[str] = None,
    commitment: str = "confirmed",
    session=requests,
    timeout: int = 20,
) -> dict[str, Any]:
    """Fetch parsed token-account mint/authority without assigning pool semantics."""
    account_text = _text("account", account)
    url = _text("rpc_url", rpc_url if rpc_url is not None else SETTINGS.x1_rpc_url)
    commitment_text = _text("commitment", commitment)

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": RPC_METHOD,
        "params": [
            account_text,
            {
                "encoding": ENCODING,
                "commitment": commitment_text,
            },
        ],
    }

    response = session.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    body = response.json()

    if not isinstance(body, Mapping):
        raise X1RPCTokenAccountError("X1 RPC account-info response must be an object.")
    if body.get("error") is not None:
        raise X1RPCTokenAccountError(f"X1 RPC returned an error for {RPC_METHOD}.")

    result = body.get("result")
    if not isinstance(result, Mapping):
        raise X1RPCTokenAccountError("X1 RPC account-info result is missing or malformed.")

    context = result.get("context")
    value = result.get("value")
    if not isinstance(context, Mapping) or not isinstance(value, Mapping):
        raise X1RPCTokenAccountError("X1 RPC account-info context/value is malformed.")

    slot = context.get("slot")
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise X1RPCTokenAccountError("X1 RPC account-info context slot is invalid.")

    data = value.get("data")
    if not isinstance(data, Mapping):
        raise X1RPCTokenAccountError("X1 RPC parsed account data is missing or malformed.")
    parsed = data.get("parsed")
    if not isinstance(parsed, Mapping):
        raise X1RPCTokenAccountError("X1 RPC parsed token-account payload is missing.")
    info = parsed.get("info")
    if not isinstance(info, Mapping):
        raise X1RPCTokenAccountError("X1 RPC parsed token-account info is missing.")

    mint = _optional_text(info.get("mint"))
    authority = _optional_text(info.get("owner"))
    if mint is None:
        raise X1RPCTokenAccountError("X1 RPC parsed token-account mint is missing.")
    if authority is None:
        raise X1RPCTokenAccountError("X1 RPC parsed token-account authority is missing.")

    return {
        "chain": CHAIN,
        "source": RPC_SOURCE,
        "method": RPC_METHOD,
        "rpc_url": url,
        "account": account_text,
        "commitment": commitment_text,
        "encoding": ENCODING,
        "slot": slot,
        "mint": mint,
        "authority": authority,
        "token_state": _optional_text(info.get("state")),
        "parsed_program": _optional_text(data.get("program")),
        "parsed_type": _optional_text(parsed.get("type")),
        "account_program_owner": _optional_text(value.get("owner")),
        "raw_response": dict(body),
        "token_account_fields_parsed": True,
        "expected_identity_verified": False,
        "pool_vault_identity_verified": False,
        "cmis_promotable": False,
    }


__all__ = [
    "CHAIN",
    "ENCODING",
    "RPC_METHOD",
    "RPC_SOURCE",
    "X1RPCTokenAccountError",
    "fetch_token_account_identity_raw",
]
