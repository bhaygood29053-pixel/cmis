from __future__ import annotations

from types import SimpleNamespace

import liquidity_scout.providers.x1.current_usdcx_usd_capture as capture_module
from liquidity_scout.providers.x1.current_usdcx_usd_capture import (
    capture_current_usdcx_usd_equivalence_evidence,
)
from liquidity_scout.providers.x1.current_usdcx_usd_equivalence import (
    SOLANA_USDC_MINT,
    X1_USDC_X_MINT,
)
from liquidity_scout.providers.x1.usdcx_destination_parity import WARP_USDC_ROUTE_ID
from liquidity_scout.providers.x1.warp_config_semantics import (
    WARP_CONFIG_SEMANTIC_CONTRACT_ID,
)


def _qualified_route():
    return {
        "route_id": WARP_USDC_ROUTE_ID,
        "semantic_contract_id": WARP_CONFIG_SEMANTIC_CONTRACT_ID,
        "route_status": "active",
        "source_is_native": True,
        "destination_is_native": False,
        "backing_model": "provider_config_native_source_to_non_native_destination",
        "source": {
            "chain": "solana",
            "asset_id": SOLANA_USDC_MINT,
            "asset_id_kind": "mint",
        },
        "destination": {
            "chain": "x1",
            "asset_id": X1_USDC_X_MINT,
            "asset_id_kind": "mint",
        },
    }


def test_config_fetch_completes_before_collected_at_timestamp(monkeypatch):
    state = {"fetched": False}
    config = {"fetchedAt": 100.25}

    def fetch_config():
        state["fetched"] = True
        return config

    def clock():
        assert state["fetched"], "clock was sampled before provider config fetch completed"
        return 100.5

    def build_route(*, config_response, collected_at, **_kwargs):
        assert config_response is config
        assert collected_at >= config_response["fetchedAt"]
        return _qualified_route()

    monkeypatch.setattr(
        capture_module,
        "build_warp_config_route_observation",
        build_route,
    )
    monkeypatch.setattr(
        capture_module,
        "build_warp_bridged_supply_evidence",
        lambda **_kwargs: {"backing": True},
    )
    monkeypatch.setattr(
        capture_module,
        "evaluate_usdcx_destination_parity",
        lambda _backing: {"parity": True},
    )
    monkeypatch.setattr(
        capture_module,
        "classify_pyth_freshness",
        lambda _price, policy: {"fresh": True, "policy": policy},
    )
    monkeypatch.setattr(
        capture_module,
        "accepted_pyth_freshness_policy",
        lambda: {"max_age": 60},
    )
    monkeypatch.setattr(
        capture_module,
        "evaluate_current_usdcx_usd_equivalence",
        lambda **_kwargs: {
            "current_usdcx_usd_equivalence_verified": True,
            "execution_authorized": False,
        },
    )

    provider = SimpleNamespace(
        get_price=lambda _mint: {
            "mint": SOLANA_USDC_MINT,
            "price": "1",
        }
    )

    result = capture_current_usdcx_usd_equivalence_evidence(
        clock=clock,
        official_config_fetcher=fetch_config,
        source_vault_capturer=lambda **_kwargs: {},
        destination_mint_capturer=lambda **_kwargs: {},
        pyth_provider=provider,
    )

    assert result["schema"] == "x1_current_usdcx_usd_equivalence_capture/v1"
    assert result["captured_at"] == 100.5
    assert result["equivalence"]["current_usdcx_usd_equivalence_verified"] is True
    assert result["execution_authorized"] is False
