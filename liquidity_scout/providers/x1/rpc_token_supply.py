"""Read-only X1 RPC token-supply transport.

This module collects one ``getTokenSupply`` observation for a caller-supplied
mint. The RPC method exposes mint supply, not circulating supply, beneficial-
owner count, holder count, or distribution semantics. Those remain separate
CMIS facts and must not be inferred here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

import requests

from config import SETTINGS


CHAIN = "x1"
RPC_METHOD = "getTokenSupply"
RPC_SOURCE = "X1 RPC"


class X1RPCTokenSupplyError(RuntimeError):
    """Raised when the read-only token-supply RPC contract fails."""


def _text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty.")
    return text


def fetch_token_supply_raw(
    mint: Any,
    *,
    rpc_url: Optional[str] = None,
    commitment: str = "confirmed",
    session=requests,
    timeout: int = 20,
) -> dict[str, Any]:
    """Fetch total mint supply without assigning circulating-supply semantics."""
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
        raise X1RPCTokenSupplyError("X1 RPC token-supply response must be an object.")
    if body.get("error") is not None:
        raise X1RPCTokenSupplyError(f"X1 RPC returned an error for {RPC_METHOD}.")

    result = body.get("result")
    if not isinstance(result, Mapping):
        raise X1RPCTokenSupplyError("X1 RPC token-supply result is missing or malformed.")
    context = result.get("context")
    value = result.get("value")
    if not isinstance(context, Mapping) or not isinstance(value, Mapping):
        raise X1RPCTokenSupplyError("X1 RPC token-supply context/value is malformed.")

    slot = context.get("slot")
    amount = value.get("amount")
    decimals = value.get("decimals")
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise X1RPCTokenSupplyError("X1 RPC token-supply context slot is invalid.")
    if not isinstance(amount, str) or not amount.isdigit():
        raise X1RPCTokenSupplyError("X1 RPC token-supply raw amount is invalid.")
    if isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0:
        raise X1RPCTokenSupplyError("X1 RPC token-supply decimals are invalid.")

    return {
        "chain": CHAIN,
        "source": RPC_SOURCE,
        "method": RPC_METHOD,
        "rpc_url": url,
        "mint": mint_text,
        "commitment": commitment_text,
        "slot": slot,
        "amount": amount,
        "decimals": decimals,
        "ui_amount": value.get("uiAmount"),
        "ui_amount_string": value.get("uiAmountString"),
        "raw_response": dict(body),
        "mint_supply_observed": True,
        "circulating_supply_verified": False,
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
        "warnings": [
            "rpc_token_supply_is_total_mint_supply_not_circulating_supply",
            "token_supply_does_not_establish_holder_or_beneficial_owner_semantics",
        ],
    }


__all__ = [
    "CHAIN",
    "RPC_METHOD",
    "RPC_SOURCE",
    "X1RPCTokenSupplyError",
    "fetch_token_supply_raw",
]
