"""Fresh non-secret X1.Ninja snapshot for protected Large-Trade handoff proof.

Issue #534 keeps the provider credential and transport in public CMIS while
exporting only public provider facts needed by the protected #40 proof.

The snapshot is intentionally narrow:
- active wrapped-XNT exact single-pool candidate rows;
- bounded X1.Ninja trade-history rows for those candidate pools;
- capture metadata and explicit safety boundaries.

No credential, Authorization header, cookies, request headers, or session state
is retained.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import json
import time
from typing import Any


SCHEMA = "cmis_large_trade_provider_snapshot_534/v1"
CANDIDATE_POLICY = (
    "current_x1_ninja_wrapped_xnt_exact_single_pool_assets;"
    "positive_provider_24h_activity;"
    "provider_volume_desc_then_tx_desc_then_pool_then_mint"
)
MAX_CANDIDATES = 6

_TRADE_FIELDS = (
    "amountNative",
    "amountToken",
    "amountUsd",
    "id",
    "maker",
    "poolAddress",
    "priceNative",
    "priceUsd",
    "slot",
    "timestamp",
    "txHash",
    "type",
)


def _text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _token_mint(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    return _text(value.get("mint") or value.get("address"))


def _pool_address(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    return _text(
        value.get("address")
        or value.get("poolAddress")
        or value.get("pool_address")
    )


def _provider_volume_24h(pool: Mapping[str, Any]) -> float:
    raw = (
        pool.get("volume24h")
        if pool.get("volume24h") is not None
        else pool.get("volume_24h")
    )
    parsed = _number(raw)
    return parsed if parsed is not None and parsed > 0 else 0.0


def _provider_transactions_24h(pool: Mapping[str, Any]) -> int:
    raw = (
        pool.get("txns24h")
        if pool.get("txns24h") is not None
        else pool.get("transactions24h")
    )
    parsed = _number(raw)
    if parsed is None or parsed <= 0:
        return 0
    return int(parsed)


def select_large_trade_snapshot_candidates(
    pools: Sequence[Mapping[str, Any]],
    *,
    wrapped_xnt_mint: str,
    limit: int = MAX_CANDIDATES,
) -> list[dict[str, Any]]:
    """Select deterministic active exact single-pool wrapped-XNT assets."""

    if (
        not isinstance(pools, Sequence)
        or isinstance(pools, (str, bytes, bytearray))
    ):
        raise TypeError("pools must be a sequence")
    wrapped = _text(wrapped_xnt_mint)
    if not wrapped:
        raise ValueError("wrapped_xnt_mint is required")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("limit must be an integer from 1 to 20")

    by_asset: dict[str, list[Mapping[str, Any]]] = {}
    for pool in pools:
        if not isinstance(pool, Mapping):
            continue
        address = _pool_address(pool)
        base = _token_mint(pool.get("baseToken"))
        quote = _token_mint(pool.get("quoteToken"))
        if not address or not base or not quote:
            continue
        if base == wrapped and quote != wrapped:
            asset = quote
        elif quote == wrapped and base != wrapped:
            asset = base
        else:
            continue
        by_asset.setdefault(asset, []).append(pool)

    candidates: list[dict[str, Any]] = []
    for asset, rows in by_asset.items():
        if len(rows) != 1:
            continue
        pool = rows[0]
        volume = _provider_volume_24h(pool)
        txs = _provider_transactions_24h(pool)
        if volume <= 0 or txs <= 0:
            continue
        address = _pool_address(pool)
        if not address:
            continue
        candidates.append({
            "asset_mint": asset,
            "pool_address": address,
            "provider_volume_24h_raw_numeric": volume,
            "provider_transactions_24h_raw_numeric": txs,
            "pool_row": deepcopy(dict(pool)),
        })

    candidates.sort(
        key=lambda row: (
            -row["provider_volume_24h_raw_numeric"],
            -row["provider_transactions_24h_raw_numeric"],
            row["pool_address"],
            row["asset_mint"],
        )
    )
    return candidates[:limit]


def sanitize_trade_history_snapshot(
    history: Mapping[str, Any],
    *,
    expected_pool_address: str,
) -> dict[str, Any]:
    """Retain only accepted public provider trade-history facts."""

    if not isinstance(history, Mapping):
        raise TypeError("trade history must be a mapping")
    pool_address = _text(expected_pool_address)
    if not pool_address:
        raise ValueError("expected_pool_address is required")
    if history.get("chain") != "x1":
        raise ValueError("trade history chain must be x1")
    if _text(history.get("pool_address")) != pool_address:
        raise ValueError("trade history pool identity mismatch")

    contract = history.get("contract")
    if not isinstance(contract, Mapping):
        raise ValueError("trade history contract metadata is required")
    if contract.get("response_contract_verified") is not True:
        raise ValueError("trade history response contract must be verified")
    if contract.get("trade_row_shape_verified") is not True:
        raise ValueError("trade history row shape must be verified")

    raw = history.get("raw_response")
    if not isinstance(raw, Mapping):
        raise ValueError("trade history raw_response is required")
    trades = raw.get("trades")
    if not isinstance(trades, list):
        raise ValueError("trade history trades must be a list")

    sanitized_rows = []
    for row in trades:
        if not isinstance(row, Mapping):
            raise ValueError("trade history rows must be objects")
        sanitized_rows.append({
            field: deepcopy(row.get(field))
            for field in _TRADE_FIELDS
        })

    return {
        "chain": "x1",
        "source": history.get("source"),
        "endpoint": history.get("endpoint"),
        "pool_address": pool_address,
        "observed_at": history.get("observed_at"),
        "contract": {
            "response_contract_verified": True,
            "trade_row_shape_verified": True,
            "returned_trade_count": contract.get("returned_trade_count"),
            "provider_total_raw": contract.get("provider_total_raw"),
            "provider_last_updated_raw": contract.get(
                "provider_last_updated_raw"
            ),
        },
        "raw_response": {
            "lastUpdated": raw.get("lastUpdated"),
            "total": raw.get("total"),
            "trades": sanitized_rows,
        },
        "semantics": {
            "trade_rows_verified": True,
            "side_classification_verified": False,
            "token_amount_units_verified": False,
            "usd_value_source_verified": False,
            "lp_event_semantics_verified": False,
            "transaction_signature_verified": False,
            "finality_verified": False,
            "pagination_or_range_verified": False,
        },
        "provider_secret_included": False,
        "execution_authorized": False,
    }


def build_large_trade_provider_snapshot(
    *,
    pools: Sequence[Mapping[str, Any]],
    xnt_price_usd: Any,
    wrapped_xnt_mint: str,
    trade_histories_by_pool: Mapping[str, Mapping[str, Any]],
    captured_at: Any,
    limit: int = MAX_CANDIDATES,
) -> dict[str, Any]:
    """Build the sanitized public/provider snapshot consumed by protected #40."""

    candidates = select_large_trade_snapshot_candidates(
        pools,
        wrapped_xnt_mint=wrapped_xnt_mint,
        limit=limit,
    )
    if not candidates:
        raise ValueError("no active exact single-pool wrapped-XNT candidates")

    histories: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        address = candidate["pool_address"]
        raw_history = trade_histories_by_pool.get(address)
        if not isinstance(raw_history, Mapping):
            raise ValueError(
                f"trade history missing for candidate pool {address}"
            )
        histories[address] = sanitize_trade_history_snapshot(
            raw_history,
            expected_pool_address=address,
        )

    snapshot = {
        "schema": SCHEMA,
        "issue": 534,
        "captured_at": captured_at,
        "wrapped_xnt_mint": _text(wrapped_xnt_mint),
        "xnt_price_usd": deepcopy(xnt_price_usd),
        "candidate_policy": CANDIDATE_POLICY,
        "candidate_limit": limit,
        "catalog_pool_count": len(pools),
        "candidates": candidates,
        "trade_histories_by_pool": histories,
        "provider_scoped_candidate_search_only": True,
        "global_x1_dex_search_claimed": False,
        "source_independence_verified": False,
        "provider_secret_included": False,
        "execution_authorized": False,
    }

    rendered = json.dumps(snapshot, sort_keys=True, default=str)
    if "Bearer " in rendered or "Authorization" in rendered:
        raise ValueError("snapshot unexpectedly contains provider authorization material")
    return snapshot


def capture_live_large_trade_provider_snapshot(
    *,
    output_path: str,
    limit: int = MAX_CANDIDATES,
    clock=time.time,
) -> dict[str, Any]:
    """Capture a fresh snapshot using accepted public X1.Ninja transports."""

    from liquidity_scout.providers.x1.market import fetch_all_pools
    from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw
    from liquidity_scout.providers.x1.transaction_semantics import WXNT_MINT

    pools, xnt_price = fetch_all_pools(sleep_seconds=0)
    candidates = select_large_trade_snapshot_candidates(
        pools,
        wrapped_xnt_mint=WXNT_MINT,
        limit=limit,
    )
    if not candidates:
        raise ValueError("live X1.Ninja catalog has no eligible candidates")

    histories = {}
    for candidate in candidates:
        address = candidate["pool_address"]
        histories[address] = fetch_pool_trades_raw(address)

    snapshot = build_large_trade_provider_snapshot(
        pools=pools,
        xnt_price_usd=xnt_price,
        wrapped_xnt_mint=WXNT_MINT,
        trade_histories_by_pool=histories,
        captured_at=clock(),
        limit=limit,
    )
    path = _text(output_path)
    if not path:
        raise ValueError("output_path is required")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True, default=str) + "\n")
    return snapshot


__all__ = [
    "CANDIDATE_POLICY",
    "MAX_CANDIDATES",
    "SCHEMA",
    "build_large_trade_provider_snapshot",
    "capture_live_large_trade_provider_snapshot",
    "sanitize_trade_history_snapshot",
    "select_large_trade_snapshot_candidates",
]
