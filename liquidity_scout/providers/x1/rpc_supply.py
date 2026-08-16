"""Finalized native X1 supply facts collected directly from X1 RPC.

The official X1 Explorer source uses ``getSupply`` with finalized commitment and
``excludeNonCirculatingAccountsList=true`` for native supply. This provider
primitive mirrors that read-only RPC contract.

X1 Labs' ``x1-sdk`` retains the upstream ``solana-native-token`` naming and
publishes ``LAMPORTS_PER_SOL = 1_000_000_000`` in ``native-token/src/lib.rs``.
CMIS records that as the X1 Solana-compatible native base-unit scale while
keeping the provenance explicit; it does not imply that the public X1 asset is
named SOL. CMIS canonical identity remains XNT.

The separate ``api.x1.xyz`` network-supply endpoints currently expose whole
integer XNT observations. Their exact rounding rule is not yet verified, so a
cross-source comparison must preserve that uncertainty instead of demanding
bit-for-bit equality with finalized RPC base units.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .rpc import DEFAULT_X1_RPC_URL, X1RPCProvider, rpc_request


CHAIN = "x1"
ASSET = "XNT"
RPC_NETWORK_SUPPLY_SOURCE = "X1 RPC getSupply(finalized)"
X1_NATIVE_BASE_UNITS_PER_XNT = 1_000_000_000
X1_NATIVE_UNIT_SOURCE = (
    "x1-labs/x1-sdk native-token LAMPORTS_PER_SOL=1_000_000_000"
)


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


def base_units_to_xnt_text(value: Any) -> str:
    """Convert X1 native base units to an exact decimal XNT string.

    This uses integer arithmetic only. The 1e9 scale is sourced from the
    official X1 Labs SDK's Solana-compatible native-token crate; no floating
    point rounding is introduced at this provider boundary.
    """

    raw = _nonnegative_integer_text("native base units", value)
    whole, fractional = divmod(int(raw), X1_NATIVE_BASE_UNITS_PER_XNT)
    if fractional == 0:
        return str(whole)
    fraction_text = f"{fractional:09d}".rstrip("0")
    return f"{whole}.{fraction_text}"


def parse_network_supply_result(result: Any) -> dict[str, Any]:
    """Validate the Solana-compatible X1 ``getSupply`` response structure."""

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

    total_raw = _nonnegative_integer_text("total", value.get("total"))
    circulating_raw = _nonnegative_integer_text(
        "circulating", value.get("circulating")
    )
    non_circulating_raw = _nonnegative_integer_text(
        "nonCirculating", value.get("nonCirculating")
    )

    return {
        "chain": CHAIN,
        "asset": ASSET,
        "total_raw": total_raw,
        "circulating_raw": circulating_raw,
        "non_circulating_raw": non_circulating_raw,
        "total_xnt": base_units_to_xnt_text(total_raw),
        "circulating_xnt": base_units_to_xnt_text(circulating_raw),
        "non_circulating_xnt": base_units_to_xnt_text(non_circulating_raw),
        "context_slot": context_slot,
        "commitment": "finalized",
        "representation": "rpc_base_units",
        "base_units_per_xnt": X1_NATIVE_BASE_UNITS_PER_XNT,
        "unit_source": X1_NATIVE_UNIT_SOURCE,
        "units_verified_by_x1_sdk": True,
        "api_x1_xyz_rounding_verified": False,
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
    """Return finalized native X1 supply with exact XNT conversion."""

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
    "X1_NATIVE_BASE_UNITS_PER_XNT",
    "X1_NATIVE_UNIT_SOURCE",
    "X1RPCSupplyError",
    "X1RPCSupplyProvider",
    "base_units_to_xnt_text",
    "get_network_supply_rpc",
    "parse_network_supply_result",
]
