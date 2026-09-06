from __future__ import annotations

import json

import pytest

from liquidity_scout.providers.x1.large_trade_provider_snapshot import (
    CANDIDATE_POLICY,
    SCHEMA,
    build_large_trade_provider_snapshot,
    sanitize_trade_history_snapshot,
    select_large_trade_snapshot_candidates,
)


WXNT = "WrappedXNT"
ASSET_A = "AssetA"
ASSET_B = "AssetB"
ASSET_DUP = "AssetDup"


def pool(address, asset, *, volume, txs):
    return {
        "address": address,
        "baseToken": {"mint": WXNT},
        "quoteToken": {"mint": asset},
        "volume24h": volume,
        "txns24h": txs,
        "liquidity": "1000",
        "priceNative": "0.1",
    }


def history(address, rows=None):
    rows = [] if rows is None else rows
    return {
        "chain": "x1",
        "source": "X1.Ninja Developer API",
        "endpoint": f"/v1/trades/{address}",
        "pool_address": address,
        "observed_at": 1234,
        "contract": {
            "response_contract_verified": True,
            "trade_row_shape_verified": True,
            "returned_trade_count": len(rows),
            "provider_total_raw": len(rows),
            "provider_last_updated_raw": 1234,
            "top_level_keys": ["lastUpdated", "total", "trades"],
            "trade_row_keys": ["txHash"],
        },
        "raw_response": {
            "lastUpdated": 1234,
            "total": len(rows),
            "trades": rows,
        },
        "rate_limit": {
            "limit": "100",
            "remaining": "99",
            "reset": "999",
        },
        "semantics": {"trade_rows_verified": True},
    }


def trade(signature, address, *, maker="Wallet1", side="BUY"):
    return {
        "amountNative": "1",
        "amountToken": "10",
        "amountUsd": "2",
        "id": f"id-{signature}",
        "maker": maker,
        "poolAddress": address,
        "priceNative": "0.1",
        "priceUsd": "0.2",
        "slot": 100,
        "timestamp": 1234,
        "txHash": signature,
        "type": side,
        "unexpected": "must-not-survive",
    }


def test_candidate_selection_is_single_pool_active_and_deterministic():
    pools = [
        pool("PoolB", ASSET_B, volume="200", txs=8),
        pool("PoolA", ASSET_A, volume="300", txs=5),
        pool("Dup1", ASSET_DUP, volume="999", txs=99),
        pool("Dup2", ASSET_DUP, volume="888", txs=88),
        pool("Zero", "ZeroAsset", volume="0", txs=0),
        {
            "address": "NonWrapped",
            "baseToken": {"mint": "Other1"},
            "quoteToken": {"mint": "Other2"},
            "volume24h": "1000",
            "txns24h": 50,
        },
    ]

    candidates = select_large_trade_snapshot_candidates(
        pools,
        wrapped_xnt_mint=WXNT,
        limit=6,
    )

    assert [
        (row["asset_mint"], row["pool_address"])
        for row in candidates
    ] == [
        (ASSET_A, "PoolA"),
        (ASSET_B, "PoolB"),
    ]
    assert all("pool_row" in row for row in candidates)


def test_trade_history_sanitizer_drops_headers_and_unknown_fields():
    raw = history("PoolA", [trade("Sig1", "PoolA")])
    sanitized = sanitize_trade_history_snapshot(
        raw,
        expected_pool_address="PoolA",
    )

    assert sanitized["chain"] == "x1"
    assert sanitized["pool_address"] == "PoolA"
    assert sanitized["provider_secret_included"] is False
    assert sanitized["execution_authorized"] is False
    assert "rate_limit" not in sanitized
    row = sanitized["raw_response"]["trades"][0]
    assert row["txHash"] == "Sig1"
    assert "unexpected" not in row
    rendered = json.dumps(sanitized, sort_keys=True)
    assert "Authorization" not in rendered
    assert "Bearer " not in rendered


def test_snapshot_contains_only_selected_candidate_rows_and_histories():
    pools = [
        pool("PoolA", ASSET_A, volume="300", txs=5),
        pool("PoolB", ASSET_B, volume="200", txs=8),
    ]
    histories = {
        "PoolA": history("PoolA", [trade("SigA", "PoolA")]),
        "PoolB": history("PoolB", [trade("SigB", "PoolB")]),
    }

    snapshot = build_large_trade_provider_snapshot(
        pools=pools,
        xnt_price_usd="1.23",
        wrapped_xnt_mint=WXNT,
        trade_histories_by_pool=histories,
        captured_at=999,
        limit=2,
    )

    assert snapshot["schema"] == SCHEMA
    assert snapshot["candidate_policy"] == CANDIDATE_POLICY
    assert snapshot["candidate_limit"] == 2
    assert snapshot["catalog_pool_count"] == 2
    assert [row["pool_address"] for row in snapshot["candidates"]] == [
        "PoolA",
        "PoolB",
    ]
    assert set(snapshot["trade_histories_by_pool"]) == {"PoolA", "PoolB"}
    assert snapshot["provider_scoped_candidate_search_only"] is True
    assert snapshot["global_x1_dex_search_claimed"] is False
    assert snapshot["source_independence_verified"] is False
    assert snapshot["provider_secret_included"] is False
    assert snapshot["execution_authorized"] is False


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value.__setitem__("chain", "solana"),
        lambda value: value.__setitem__("pool_address", "WrongPool"),
        lambda value: value["contract"].__setitem__(
            "response_contract_verified", False
        ),
        lambda value: value["contract"].__setitem__(
            "trade_row_shape_verified", False
        ),
    ],
)
def test_sanitizer_fails_closed_on_contract_or_identity_drift(mutator):
    raw = history("PoolA", [trade("Sig1", "PoolA")])
    mutator(raw)
    with pytest.raises(ValueError):
        sanitize_trade_history_snapshot(
            raw,
            expected_pool_address="PoolA",
        )


def test_snapshot_requires_history_for_every_selected_candidate():
    pools = [pool("PoolA", ASSET_A, volume="300", txs=5)]
    with pytest.raises(ValueError, match="trade history missing"):
        build_large_trade_provider_snapshot(
            pools=pools,
            xnt_price_usd="1.23",
            wrapped_xnt_mint=WXNT,
            trade_histories_by_pool={},
            captured_at=999,
            limit=1,
        )
