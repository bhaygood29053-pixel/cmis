from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from liquidity_scout.providers.x1.large_trade_provider_snapshot import (
    MAX_CANDIDATES,
    SCHEMA,
    capture_live_large_trade_provider_snapshot,
)


RUN_LIVE = os.getenv("RUN_LARGE_TRADE_PROVIDER_SNAPSHOT_534") == "1"
OUTPUT = os.getenv(
    "LARGE_TRADE_PROVIDER_SNAPSHOT_534_OUTPUT",
    str(
        Path(__file__).parent
        / "fixtures"
        / "live_534_large_trade_provider_snapshot.json"
    ),
)


@pytest.mark.skipif(
    not RUN_LIVE,
    reason="set RUN_LARGE_TRADE_PROVIDER_SNAPSHOT_534=1 for live #534 capture",
)
def test_live_capture_fresh_nonsecret_large_trade_provider_snapshot():
    snapshot = capture_live_large_trade_provider_snapshot(
        output_path=OUTPUT,
        limit=MAX_CANDIDATES,
    )

    assert snapshot["schema"] == SCHEMA
    assert 1 <= len(snapshot["candidates"]) <= MAX_CANDIDATES
    assert snapshot["candidate_limit"] == MAX_CANDIDATES
    assert snapshot["provider_scoped_candidate_search_only"] is True
    assert snapshot["global_x1_dex_search_claimed"] is False
    assert snapshot["source_independence_verified"] is False
    assert snapshot["provider_secret_included"] is False
    assert snapshot["execution_authorized"] is False

    for candidate in snapshot["candidates"]:
        pool = candidate["pool_address"]
        history = snapshot["trade_histories_by_pool"][pool]
        assert history["pool_address"] == pool
        assert history["contract"]["response_contract_verified"] is True
        assert history["contract"]["trade_row_shape_verified"] is True
        assert history["provider_secret_included"] is False
        assert history["execution_authorized"] is False

    rendered = json.dumps(snapshot, sort_keys=True, default=str)
    assert "Authorization" not in rendered
    assert "Bearer " not in rendered

    print("LIVE #534 LARGE-TRADE PROVIDER SNAPSHOT")
    print(rendered)
