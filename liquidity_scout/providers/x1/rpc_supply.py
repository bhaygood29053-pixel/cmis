"""Finalized native X1 supply facts collected directly from X1 RPC.

The official X1 Explorer source uses ``getSupply`` with finalized commitment and
``excludeNonCirculatingAccountsList=true`` for native supply.  This provider
primitive mirrors that read-only RPC contract while deliberately preserving the
returned amounts as raw base-unit integers.

No XNT decimal scaling is performed here.  A separate live cross-check against
the official ``api.x1.xyz`` network-supply endpoints must verify the unit
relationship before CMIS may compare or combine the two sources numerically.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .rpc import DEFAULT_X1_RPC_URL, X1RPCProvider, rpc_request


CHAIN = "x1"
ASSET = "XNT"
RPC_NETWORK_SUPPLY_SOURCE = "X1 RPC getSupply(finalized)"


class X1RPCSupplyError(RuntimeError):
    """Raised when a getSupply result cannot be trusted structurally."""


def _nonnegative_integer_text(name: str, value: Any) -> str:
    if isinstance(value, bool):
        raise X1RPCSupplyError(f"X1 RPC getSupply {name} must be a non-negative integer.")

    if isinstance(value, int):
        if value < 0:
            raise X1RPCSupplyError(f"X1 RPC getSupply {name} must be non-negative.")
        return str(value)

    text = str(value or "").strip()
    if not text or not text.isdigit():
        raise X1RPCSupplyError(f"X1 RPC getSupply {name} must be a non-negative integer.")
    return text.lstrip("0") or "0"


def _optional_nonnegative_integer(name: str, value: Any):
    if value is None:
        return None
    return _nonnegative_integer_text(name, value)


def parse_network_supply_result(result: Any) -> dict[str, Any]:
    """Validate the Solana-compatible X1 ``getSupply`` response structure.

    Values remain raw base units.  ``total``, ``circulating`` and
    ``nonCirculating`` are required because the official X1 Explorer consumes
    those three fields directly.
    """

    if not isinstance(result, Mapping):
        raise X1RPCSupplyError("X1 RPC getSupply result must be a JSON object.")

    value = result.get("value")
    if not isinstance(value, Mapping):
        raise X1RPCSupplyError("X1 RPC getSupply result is missing a value object.")

    missing = [
        field
        for field in ("total", "circulating", "nonCirculating")
        if field not in value
    ]
    if missing:
        raise X1RPCSupplyError(
            "X1 RPC getSupply value is missing field(s): " + ", ".join(missing)
        )

    context = result.get("context")
    context_slot = None
    if isinstance(context, Mapping) and "slot" in context:
        context_slot = _optional_nonnegative_integer("context.slot", context.get("slot"))

    return {
        "chain": CHAIN,
        "asset": ASSET,
        "total_raw": _nonnegative_integer_text("total", value.get("total")),
        "circulating_raw": _nonnegative_integer_text(
            "circulating", value.get("circulating")
        ),
        "non_circulating_raw": _nonnegative_integer_text(
            "nonCirculating", value.get("nonCirculating")
        ),
        "context_slot": context_slot,
        "commitment": "finalized",
        "representation": "rpc_base_units",
        "units_verified_against_network_supply_api": False,
        "source": RPC_NETWORK_SUPPLY_SOURCE,
    }


def get_network_supply_rpc(
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    retries: int = 4,
    timeout: int = 15,
    post=None,
    sleep=None,
) -> dict[str, Any]:
    """Return finalized native X1 supply from X1 RPC without scaling it."""

    kwargs = {
        "rpc_url": rpc_url,
        "retries": retries,
        "timeout": timeout,
    }
    if post is not None:
        kwargs["post"] = post
    if sleep is not None:
        kwargs["sleep"] = sleep

    result = rpc_request(
        "getSupply",
        [{"commitment": "finalized", "excludeNonCirculatingAccountsList": True}],
        **kwargs,
    )
    return parse_network_supply_result(result)


class X1RPCSupplyProvider:
    """Small facade for finalized native-network supply over X1 RPC."""

    chain = CHAIN
    asset = ASSET
    source = RPC_NETWORK_SUPPLY_SOURCE

    def __init__(self, rpc_provider: X1RPCProvider | None = None):
        self.rpc_provider = rpc_provider or X1RPCProvider()

    def get_supply(self) -> dict[str, Any]:
        result = self.rpc_provider.request(
            "getSupply",
            [{"commitment": "finalized", "excludeNonCirculatingAccountsList": True}],
        )
        return parse_network_supply_result(result)


__all__ = [
    "ASSET",
    "CHAIN",
    "RPC_NETWORK_SUPPLY_SOURCE",
    "X1RPCSupplyError",
    "X1RPCSupplyProvider",
    "get_network_supply_rpc",
    "parse_network_supply_result",
]
