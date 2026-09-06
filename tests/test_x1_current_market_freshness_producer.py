from __future__ import annotations

from liquidity_scout.providers.x1.current_market_freshness_producer import (
    SCHEMA,
    produce_x1_current_market_freshness_evidence,
)


MINT = "Asset11111111111111111111111111111111111111"
POOL = "Pool111111111111111111111111111111111111111"


def market():
    return {
        "chain": "x1",
        "status": "ok",
        "asset": {"mint": MINT},
        "data": {
            "mint": MINT,
            "liquidity_usd": "100",
            "volume_24h_usd": "5",
            "transactions_24h": 1,
            "contributing_pools": [{"address": POOL}],
            "completeness": {
                "liquidity": True,
                "volume_24h": True,
                "transactions_24h": True,
            },
        },
    }


def scope(ok=True):
    return {
        "contract_version": "x1_ninja_current_pool_scope/v1",
        "chain": "x1",
        "asset_mint": MINT,
        "market_contributing_pool_addresses": [POOL],
        "current_catalog_exact_mint_pool_addresses": [POOL],
        "provider_scoped_pool_universe_verified": ok,
        "global_xdex_pool_universe_verified": False,
        "execution_authorized": False,
    }


def liquidity(*, execution=False):
    return {
        "contract_version": "x1_ninja_liquidity_freshness/v1",
        "chain": "x1",
        "liquidity_freshness_verified": True,
        "execution_authorized": execution,
    }


def rolling(*, volume=True, transactions=True):
    return {
        "contract_version": "x1_rolling_24h_market_activity/v1",
        "chain": "x1",
        "volume_24h_freshness_verified": volume,
        "transactions_24h_freshness_verified": transactions,
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }


def identity(**_kwargs):
    return {
        "chain": "x1",
        "pool_address": POOL,
        "asset_mint": MINT,
        "identity_verified": True,
        "execution_authorized": False,
    }


def common_kwargs():
    return {
        "clock": lambda: 1000.0,
        "catalog_fetcher": lambda **_kwargs: ([{"address": POOL}], 1.0),
        "scope_evaluator": lambda **_kwargs: scope(True),
        "snapshot_collector": lambda **_kwargs: {"pools": []},
        "current_usdcx_capturer": lambda: {"equivalence": {}},
        "liquidity_evaluator": lambda **_kwargs: liquidity(),
        "identity_capturer": identity,
    }


def test_full_liquidity_and_zero_rolling_success_skips_historical_context():
    calls = {"context": 0}

    def window(**_kwargs):
        return {"transactions": []}

    def context(**_kwargs):
        calls["context"] += 1
        raise AssertionError("zero activity must not build historical USD context")

    result = produce_x1_current_market_freshness_evidence(
        market(),
        **common_kwargs(),
        window_reconstructor=window,
        rolling_evaluator=lambda **_kwargs: rolling(volume=True, transactions=True),
        historical_context_builder=context,
    )

    assert result["schema"] == SCHEMA
    assert result["liquidity_freshness_verified"] is True
    assert result["volume_24h_freshness_verified"] is True
    assert result["transactions_24h_freshness_verified"] is True
    assert calls["context"] == 0
    assert result["execution_authorized"] is False


def test_nonzero_rolling_builds_one_shared_historical_context_and_values_again():
    calls = {"window": 0, "context": 0, "resolver": 0}

    def window(**kwargs):
        calls["window"] += 1
        if "usd_quote_resolver" in kwargs:
            return {
                "valued": True,
                "transactions": [
                    {"classification": "EXACT_POOL_SWAP", "block_time": 900}
                ],
            }
        return {
            "valued": False,
            "transactions": [
                {"classification": "EXACT_POOL_SWAP", "block_time": 900}
            ],
        }

    def context(**kwargs):
        calls["context"] += 1
        assert kwargs["oldest_fact_time"] == 900
        return {"execution_authorized": False}

    def resolver_builder(_context):
        calls["resolver"] += 1
        return lambda **_kwargs: {"historical_usd_value_verified": True}

    def rolling_eval(**kwargs):
        valued = all(window.get("valued") for window in kwargs["pool_windows"])
        return rolling(volume=valued, transactions=True)

    result = produce_x1_current_market_freshness_evidence(
        market(),
        **common_kwargs(),
        window_reconstructor=window,
        rolling_evaluator=rolling_eval,
        historical_context_builder=context,
        historical_resolver_builder=resolver_builder,
    )

    assert calls == {"window": 2, "context": 1, "resolver": 1}
    assert result["volume_24h_freshness_verified"] is True
    assert result["transactions_24h_freshness_verified"] is True


def test_historical_usd_failure_preserves_transaction_freshness():
    def window(**_kwargs):
        return {
            "valued": False,
            "transactions": [
                {"classification": "EXACT_POOL_SWAP", "block_time": 900}
            ],
        }

    def fail_context(**_kwargs):
        raise RuntimeError("historical provider unavailable")

    def rolling_eval(**kwargs):
        assert all(not window.get("valued") for window in kwargs["pool_windows"])
        return rolling(volume=False, transactions=True)

    result = produce_x1_current_market_freshness_evidence(
        market(),
        **common_kwargs(),
        window_reconstructor=window,
        rolling_evaluator=rolling_eval,
        historical_context_builder=fail_context,
    )

    assert result["liquidity_freshness_verified"] is True
    assert result["transactions_24h_freshness_verified"] is True
    assert result["volume_24h_freshness_verified"] is False
    assert any(
        item.startswith("historical_usd_production_failed:RuntimeError:")
        for item in result["failures"]
    )


def test_exact_scope_failure_stops_before_expensive_proof():
    kwargs = common_kwargs()
    kwargs["scope_evaluator"] = lambda **_kwargs: scope(False)

    result = produce_x1_current_market_freshness_evidence(
        market(),
        **kwargs,
        window_reconstructor=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not reconstruct an unverified scope")
        ),
        rolling_evaluator=lambda **_kwargs: rolling(),
    )

    assert result["liquidity_freshness_evidence"] is None
    assert result["rolling_activity_evidence"] is None
    assert "provider_scoped_pool_universe_unverified" in result["failures"]


def test_execution_authorizing_liquidity_evidence_is_rejected_but_rolling_can_continue():
    kwargs = common_kwargs()
    kwargs["liquidity_evaluator"] = lambda **_kwargs: liquidity(execution=True)

    result = produce_x1_current_market_freshness_evidence(
        market(),
        **kwargs,
        window_reconstructor=lambda **_kwargs: {"transactions": []},
        rolling_evaluator=lambda **_kwargs: rolling(volume=True, transactions=True),
    )

    assert result["liquidity_freshness_evidence"] is None
    assert result["liquidity_freshness_verified"] is False
    assert result["transactions_24h_freshness_verified"] is True
    assert result["volume_24h_freshness_verified"] is True
    assert any(
        item.startswith("liquidity_production_failed:ValueError:")
        for item in result["failures"]
    )
    assert result["execution_authorized"] is False
