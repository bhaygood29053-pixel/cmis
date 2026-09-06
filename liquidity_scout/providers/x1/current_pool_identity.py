"""Exact current X1 pool identity for rolling freshness reconstruction."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from liquidity_scout.providers.x1.ninja_price_fact_time import (
    collect_ninja_price_fact_time_snapshot,
)
from liquidity_scout.providers.x1.rpc import get_token_account_info


CONTRACT_VERSION = "x1_current_pool_identity/v1"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def capture_x1_current_pool_identity(
    *,
    pool_address: Any,
    asset_mint: Any,
    snapshot: Mapping[str, Any] | None = None,
    snapshot_collector: Callable[..., Mapping[str, Any]] = (
        collect_ninja_price_fact_time_snapshot
    ),
    token_account_reader: Callable[[str], Mapping[str, Any]] = get_token_account_info,
) -> dict[str, Any]:
    """Bind one current pool to exact mints, vaults, and shared authority."""

    address = _text(pool_address)
    mint = _text(asset_mint)
    if not address or not mint:
        raise ValueError("pool_address and asset_mint are required")

    evidence = (
        dict(snapshot)
        if isinstance(snapshot, Mapping)
        else dict(snapshot_collector(pool_addresses=[address]))
    )
    rows = [
        row
        for row in evidence.get("pools") or []
        if isinstance(row, Mapping) and _text(row.get("pool_address")) == address
    ]
    if len(rows) != 1 or rows[0].get("status") != "ok":
        raise ValueError("current pool RPC snapshot unavailable")

    rpc = rows[0].get("rpc")
    if not isinstance(rpc, Mapping) or rpc.get("rpc_reserve_ratio_verified") is not True:
        raise ValueError("current pool RPC identity unavailable")

    mint_0 = _text(rpc.get("mint_0"))
    mint_1 = _text(rpc.get("mint_1"))
    vault_0 = _text(rpc.get("vault_0"))
    vault_1 = _text(rpc.get("vault_1"))
    if not all([mint_0, mint_1, vault_0, vault_1]):
        raise ValueError("decoded pool mint/vault identity incomplete")

    v0 = token_account_reader(vault_0)
    v1 = token_account_reader(vault_1)
    if not (
        isinstance(v0, Mapping)
        and isinstance(v1, Mapping)
        and v0.get("identity_verified") is True
        and v1.get("identity_verified") is True
    ):
        raise ValueError("current vault token-account identity unavailable")

    owner_0 = _text(v0.get("token_authority"))
    owner_1 = _text(v1.get("token_authority"))
    if not owner_0 or owner_0 != owner_1:
        raise ValueError("current vault shared authority unverified")

    if mint_0 == mint:
        asset_vault = vault_0
        counter_mint = mint_1
        counter_vault = vault_1
    elif mint_1 == mint:
        asset_vault = vault_1
        counter_mint = mint_0
        counter_vault = vault_0
    else:
        raise ValueError("decoded pool does not contain selected asset mint")

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": "x1",
        "pool_address": address,
        "asset_mint": mint,
        "asset_vault": asset_vault,
        "counter_mint": counter_mint,
        "counter_vault": counter_vault,
        "shared_owner": owner_0,
        "identity_verified": True,
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }


__all__ = ["CONTRACT_VERSION", "capture_x1_current_pool_identity"]
