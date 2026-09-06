from decimal import Decimal

import liquidity_scout.providers.x1.liquidity_freshness_v2 as module
from liquidity_scout.providers.x1.liquidity_freshness_v2 import (
    VERSION,
    evaluate_x1_ninja_liquidity_freshness_v2,
)


POOL = "8ztGiYGDvQA8bMoyaFgBNvNWgDraYpMeU3E63kaEHBWG"
ASSET = "7k79DrpoyY1GkD2m14WCwwew1yQsixkZzJhbCzLHdUKu"
XNT = "So11111111111111111111111111111111111111112"


def _legacy(**overrides):
    value = {
        "contract_version": "x1_ninja_liquidity_freshness/v1",
        "chain": "x1",
        "status": "partial",
        "contributing_pool_count": 1,
        "rpc_freshness": {
            "slot_bracket_verified": True,
            "rpc_block_time_fresh": True,
        },
        "xnt_usd_basis": {
            "reference_pool_identity_verified": True,
            "reference_reserves_verified": True,
            "usdcx_per_xnt": "0.3517496668516706787549193935",
            "fresh_usdc_usd": "0.99988399",
        },
        "pool_results": [
            {
                "pool_address": POOL,
                "mint_0": XNT,
                "mint_1": ASSET,
                "rpc_xnt_reserve": "1031.679534501",
                "rpc_asset_reserve": "202234331.244878089",
                "provider_liquidity_usd": "725.7858651168269",
                "pooledBase_rpc_comparison": {"within_tolerance": True},
                "pooledQuote_rpc_comparison": {"within_tolerance": True},
                "liquidity_freshness_verified": False,
                "rejection_reasons": [
                    "provider_liquidity_does_not_match_current_rpc_valuation"
                ],
            }
        ],
        "liquidity_freshness_verified": False,
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }
    value.update(overrides)
    return value


def _scope(**overrides):
    value = {
        "contract_version": "x1_ninja_current_pool_scope/v1",
        "chain": "x1",
        "asset_mint": ASSET,
        "provider_scoped_pool_universe_verified": True,
        "global_xdex_pool_universe_verified": False,
        "market_contributing_pool_addresses": [POOL],
        "current_catalog_exact_mint_pool_addresses": [POOL],
        "execution_authorized": False,
    }
    value.update(overrides)
    return value


def _market(liquidity="725.7858651168269"):
    return {
        "chain": "x1",
        "asset": {"mint": ASSET},
        "data": {
            "liquidity_usd": liquidity,
            "completeness": {"liquidity": True},
            "contributing_pools": [{"address": POOL}],
            "lp_count": 1,
        },
    }


def _snapshot(**overrides):
    value = {
        "provider_xnt_price_usd": "0.3517496668516707",
        "pools": [
            {
                "pool_address": POOL,
                "status": "ok",
                "provider": {
                    "liquidity": "725.7858651168269",
                },
            }
        ],
    }
    value.update(overrides)
    return value


def _equivalence(ok=True):
    return {
        "current_usdcx_usd_equivalence_verified": ok,
        "execution_authorized": False,
    }


def test_live_513_v2_splits_provider_nominal_from_independent_usd(monkeypatch):
    monkeypatch.setattr(
        module,
        "evaluate_x1_ninja_liquidity_freshness",
        lambda **_kwargs: _legacy(),
    )

    result = evaluate_x1_ninja_liquidity_freshness_v2(
        market_envelope=_market(),
        snapshot=_snapshot(),
        current_usdcx_usd_equivalence=_equivalence(),
        pool_scope_evidence=_scope(),
        evaluated_at=1788679689,
    )

    assert result["contract_version"] == VERSION
    assert result["status"] == "verified"
    assert result["provider_numerical_unit"] == "USDC.X_nominal_quote_basis"
    assert result["provider_nominal_liquidity_freshness_verified"] is True
    assert result["independent_liquidity_usd_freshness_verified"] is True
    assert result["legacy_liquidity_freshness_verified"] is False

    assert Decimal(result["derived_provider_nominal_liquidity_sum"]) == Decimal(
        "725.7858651168269159802816414"
    )
    assert Decimal(result["independent_liquidity_usd_value"]) == Decimal(
        "725.70166669861466905861446883876072040898180513"
    )
    assert (
        Decimal(result["independent_liquidity_usd_value"])
        != Decimal(result["provider_nominal_liquidity_value"])
    )

    per_pool = result["pool_results"][0]
    assert per_pool["provider_nominal_liquidity_freshness_verified"] is True
    assert per_pool["independent_liquidity_usd_freshness_verified"] is True
    assert (
        per_pool["unit_semantics"]["independent_current_usd"][
            "provider_vs_independent_usd"
        ]["within_tolerance"]
        is False
    )
    assert result["stable_name_implies_one_usd"] is False
    assert result["provider_price_reused_as_independent_usd_proof"] is False
    assert result["provider_fact_time_verified"] is False
    assert result["source_independence_verified"] is False
    assert result["execution_authorized"] is False


def test_v2_fails_provider_nominal_when_market_value_does_not_match(monkeypatch):
    monkeypatch.setattr(
        module,
        "evaluate_x1_ninja_liquidity_freshness",
        lambda **_kwargs: _legacy(),
    )

    result = evaluate_x1_ninja_liquidity_freshness_v2(
        market_envelope=_market("800"),
        snapshot=_snapshot(),
        current_usdcx_usd_equivalence=_equivalence(),
        pool_scope_evidence=_scope(),
        evaluated_at=1788679689,
    )

    assert result["provider_nominal_liquidity_freshness_verified"] is False
    assert result["independent_liquidity_usd_freshness_verified"] is True
    assert "provider_nominal_liquidity_freshness_unverified" in result["failures"]


def test_v2_fails_independent_usd_without_current_equivalence(monkeypatch):
    monkeypatch.setattr(
        module,
        "evaluate_x1_ninja_liquidity_freshness",
        lambda **_kwargs: _legacy(),
    )

    result = evaluate_x1_ninja_liquidity_freshness_v2(
        market_envelope=_market(),
        snapshot=_snapshot(),
        current_usdcx_usd_equivalence=_equivalence(False),
        pool_scope_evidence=_scope(),
        evaluated_at=1788679689,
    )

    assert result["provider_nominal_liquidity_freshness_verified"] is True
    assert result["independent_liquidity_usd_freshness_verified"] is False
    assert "current_usdcx_usd_equivalence_unverified" in result["failures"]


def test_v2_fails_both_when_rpc_bracket_is_not_fresh(monkeypatch):
    legacy = _legacy(
        rpc_freshness={
            "slot_bracket_verified": True,
            "rpc_block_time_fresh": False,
        }
    )
    monkeypatch.setattr(
        module,
        "evaluate_x1_ninja_liquidity_freshness",
        lambda **_kwargs: legacy,
    )

    result = evaluate_x1_ninja_liquidity_freshness_v2(
        market_envelope=_market(),
        snapshot=_snapshot(),
        current_usdcx_usd_equivalence=_equivalence(),
        pool_scope_evidence=_scope(),
        evaluated_at=1788679689,
    )

    assert result["provider_nominal_liquidity_freshness_verified"] is False
    assert result["independent_liquidity_usd_freshness_verified"] is False
    assert "rpc_current_state_freshness_unverified" in result["failures"]


def test_v2_fails_closed_without_same_snapshot_provider_xnt_reference(monkeypatch):
    monkeypatch.setattr(
        module,
        "evaluate_x1_ninja_liquidity_freshness",
        lambda **_kwargs: _legacy(),
    )

    result = evaluate_x1_ninja_liquidity_freshness_v2(
        market_envelope=_market(),
        snapshot=_snapshot(provider_xnt_price_usd=None),
        current_usdcx_usd_equivalence=_equivalence(),
        pool_scope_evidence=_scope(),
        evaluated_at=1788679689,
    )

    assert result["provider_nominal_liquidity_freshness_verified"] is False
    assert "provider_xnt_reference_unavailable" in " ".join(result["failures"])
    assert result["execution_authorized"] is False
