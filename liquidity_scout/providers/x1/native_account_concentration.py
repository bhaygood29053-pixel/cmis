"""Finalized native-XNT account concentration from X1 RPC.

This module is intentionally native-currency specific. It combines X1 RPC
`getLargestAccounts(filter=circulating)` with finalized native XNT circulating
supply from `getSupply`.

The counted entity is an X1 native account address. It is not a person, wallet
group, beneficial owner, token holder, or ownership identity.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.providers.x1.rpc import (
    DEFAULT_X1_RPC_URL,
    rpc_request,
)
from liquidity_scout.providers.x1.rpc_supply import (
    RPC_NETWORK_SUPPLY_SOURCE,
    get_network_supply_rpc,
)


CHAIN = "x1"
ASSET = "XNT"
SERVICE = "x1_native_account_concentration"
VERSION = "1.0"
RPC_METHOD = "getLargestAccounts"
RPC_SOURCE = "X1 RPC getLargestAccounts(finalized,circulating)"
BUCKETS = (1, 5, 10, 20)


class X1NativeAccountConcentrationError(RuntimeError):
    """Raised when native account concentration evidence fails closed."""


def _integer_text(name: str, value: Any) -> str:
    if isinstance(value, bool):
        raise X1NativeAccountConcentrationError(
            f"{name} must be a non-negative integer"
        )
    if isinstance(value, int):
        if value < 0:
            raise X1NativeAccountConcentrationError(
                f"{name} must be non-negative"
            )
        return str(value)
    text = str(value or "").strip()
    if not text or not text.isdigit():
        raise X1NativeAccountConcentrationError(
            f"{name} must be a non-negative integer"
        )
    return text.lstrip("0") or "0"


def _slot(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise X1NativeAccountConcentrationError(
            "getLargestAccounts context slot is invalid"
        )
    return value


def _address(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise X1NativeAccountConcentrationError(
            "getLargestAccounts address is missing"
        )
    return text


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator * 100.0 / denominator, 12)


def parse_native_largest_accounts_result(result: Any) -> dict[str, Any]:
    """Validate one finalized circulating-largest-accounts RPC result."""

    if not isinstance(result, Mapping):
        raise X1NativeAccountConcentrationError(
            "getLargestAccounts result must be an object"
        )
    context = result.get("context")
    values = result.get("value")
    if not isinstance(context, Mapping) or not isinstance(values, list):
        raise X1NativeAccountConcentrationError(
            "getLargestAccounts context/value is malformed"
        )

    slot = _slot(context.get("slot"))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, raw in enumerate(values):
        if not isinstance(raw, Mapping):
            raise X1NativeAccountConcentrationError(
                f"largest account row {index} is malformed"
            )
        address = _address(raw.get("address"))
        if address in seen:
            raise X1NativeAccountConcentrationError(
                "getLargestAccounts returned a duplicate address"
            )
        seen.add(address)
        amount = _integer_text(
            f"largest account row {index} lamports",
            raw.get("lamports"),
        )
        rows.append({"address": address, "base_units": amount})

    if not rows:
        raise X1NativeAccountConcentrationError(
            "getLargestAccounts returned no circulating accounts"
        )

    rows.sort(key=lambda row: (-int(row["base_units"]), row["address"]))
    return {
        "chain": CHAIN,
        "asset": ASSET,
        "slot": slot,
        "accounts": rows,
        "returned_account_count": len(rows),
        "commitment": "finalized",
        "filter": "circulating",
        "counted_entity": "native_xnt_account_address",
        "source": RPC_SOURCE,
    }


def get_native_largest_accounts_rpc(
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    retries: int = 4,
    timeout: int = 15,
    post=None,
    sleep=None,
) -> dict[str, Any]:
    """Fetch finalized circulating native-XNT largest-account evidence."""

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
        RPC_METHOD,
        [{"commitment": "finalized", "filter": "circulating"}],
        **kwargs,
    )
    return parse_native_largest_accounts_result(result)


def build_native_xnt_account_concentration(
    largest_accounts: Mapping[str, Any],
    network_supply: Mapping[str, Any],
    *,
    max_slot_span: int = 32,
) -> dict[str, Any]:
    """Bind largest native accounts to finalized circulating XNT supply."""

    if not isinstance(largest_accounts, Mapping):
        raise TypeError("largest_accounts must be a mapping")
    if not isinstance(network_supply, Mapping):
        raise TypeError("network_supply must be a mapping")
    if (
        isinstance(max_slot_span, bool)
        or not isinstance(max_slot_span, int)
        or max_slot_span < 0
    ):
        raise ValueError("max_slot_span must be a non-negative integer")

    if largest_accounts.get("chain") != CHAIN:
        raise X1NativeAccountConcentrationError(
            "largest-account evidence must be X1"
        )
    if largest_accounts.get("asset") != ASSET:
        raise X1NativeAccountConcentrationError(
            "largest-account evidence must be XNT"
        )
    if largest_accounts.get("filter") != "circulating":
        raise X1NativeAccountConcentrationError(
            "largest-account evidence must use circulating filter"
        )
    if largest_accounts.get("commitment") != "finalized":
        raise X1NativeAccountConcentrationError(
            "largest-account evidence must be finalized"
        )
    if largest_accounts.get("counted_entity") != "native_xnt_account_address":
        raise X1NativeAccountConcentrationError(
            "largest-account counted entity is invalid"
        )

    largest_slot = _slot(largest_accounts.get("slot"))
    accounts = largest_accounts.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        raise X1NativeAccountConcentrationError(
            "largest-account evidence is empty"
        )

    if network_supply.get("chain") != CHAIN:
        raise X1NativeAccountConcentrationError(
            "network-supply evidence must be X1"
        )
    if network_supply.get("asset") != ASSET:
        raise X1NativeAccountConcentrationError(
            "network-supply evidence must be XNT"
        )
    if network_supply.get("source") != RPC_NETWORK_SUPPLY_SOURCE:
        raise X1NativeAccountConcentrationError(
            "network-supply source is invalid"
        )
    if network_supply.get("commitment") != "finalized":
        raise X1NativeAccountConcentrationError(
            "network-supply evidence must be finalized"
        )

    supply_slot_raw = network_supply.get("context_slot")
    try:
        supply_slot = int(str(supply_slot_raw))
    except (TypeError, ValueError) as exc:
        raise X1NativeAccountConcentrationError(
            "network-supply context slot is invalid"
        ) from exc
    if supply_slot < 0:
        raise X1NativeAccountConcentrationError(
            "network-supply context slot is invalid"
        )

    circulating = int(
        _integer_text(
            "network circulating supply",
            network_supply.get("circulating_raw"),
        )
    )
    slot_span = abs(largest_slot - supply_slot)
    slot_scope_verified = slot_span <= max_slot_span

    rows = []
    for index, raw in enumerate(accounts):
        if not isinstance(raw, Mapping):
            raise X1NativeAccountConcentrationError(
                f"largest-account row {index} is malformed"
            )
        rows.append(
            {
                "address": _address(raw.get("address")),
                "base_units": _integer_text(
                    f"largest-account row {index} amount",
                    raw.get("base_units"),
                ),
            }
        )
    rows.sort(key=lambda row: (-int(row["base_units"]), row["address"]))

    buckets: dict[str, dict[str, Any]] = {}
    for count in BUCKETS:
        selected = rows[:count]
        total = sum(int(row["base_units"]) for row in selected)
        buckets[f"top_{count}"] = {
            "requested_account_count": count,
            "available_account_count": len(selected),
            "base_units": str(total),
            "percent_of_circulating_xnt": _pct(total, circulating),
        }

    concentration_verified = bool(
        slot_scope_verified
        and circulating > 0
        and len(rows) >= min(BUCKETS)
    )

    return {
        "service": SERVICE,
        "version": VERSION,
        "chain": CHAIN,
        "asset": ASSET,
        "status": "verified" if concentration_verified else "partial",
        "counted_entity": "native_xnt_account_address",
        "holder_count_state": "not_applicable",
        "holder_count_reason": "xnt_is_native_currency_not_spl_holder_population",
        "native_account_concentration_verified": concentration_verified,
        "largest_accounts_slot": largest_slot,
        "network_supply_slot": supply_slot,
        "slot_span": slot_span,
        "max_slot_span": max_slot_span,
        "slot_scope_verified": slot_scope_verified,
        "circulating_supply_base_units": str(circulating),
        "returned_largest_account_count": len(rows),
        "buckets": buckets,
        "beneficial_owner_identity_verified": False,
        "person_or_wallet_group_count_verified": False,
        "sources": [
            {"source": RPC_SOURCE, "role": "native_account_distribution"},
            {
                "source": RPC_NETWORK_SUPPLY_SOURCE,
                "role": "native_circulating_supply",
            },
        ],
        "cmis_promotable": concentration_verified,
        "execution_authorized": False,
        "warnings": [
            "native_account_addresses_are_not_beneficial_owner_identities",
            "largest_accounts_does_not_prove_total_native_account_count",
        ],
    }


def collect_native_xnt_account_concentration(
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    max_slot_span: int = 32,
) -> dict[str, Any]:
    """Collect and bind both finalized native-XNT RPC observations."""

    largest = get_native_largest_accounts_rpc(rpc_url=rpc_url)
    supply = get_network_supply_rpc(rpc_url=rpc_url)
    return build_native_xnt_account_concentration(
        largest,
        supply,
        max_slot_span=max_slot_span,
    )


__all__ = [
    "ASSET",
    "BUCKETS",
    "CHAIN",
    "RPC_METHOD",
    "RPC_SOURCE",
    "SERVICE",
    "VERSION",
    "X1NativeAccountConcentrationError",
    "build_native_xnt_account_concentration",
    "collect_native_xnt_account_concentration",
    "get_native_largest_accounts_rpc",
    "parse_native_largest_accounts_result",
]
