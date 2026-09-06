from liquidity_scout.providers.x1.current_market_freshness import (
    V3_CONTRACT,
    evaluate_current_market_freshness_v3,
)
from liquidity_scout.providers.x1.instant_scan_freshness_policy import (
    accepted_instant_scan_freshness_policy,
)


def market():
    return {
        "data": {
            "price_usd": 1.0,
            "liquidity_usd": 725.7858651168269,
            "volume_24h_usd": 0,
            "transactions_24h": 0,
            "completeness": {
                "price": True,
                "liquidity": True,
                "volume_24h": True,
                "transactions_24h": True,
            },
            "provenance": {"catalog_last_refresh_unix": 995.0},
        }
    }


def backfill():
    return {
        "provider_history_imported": True,
        "last_imported_observed_at": 990.0,
        "last_imported_price_usd": 1.0,
    }


def legacy_liquidity(ok=False):
    return {
        "contract_version": "x1_ninja_liquidity_freshness/v1",
        "liquidity_freshness_verified": ok,
        "current_value_reproduced_from_fresh_chain_state": ok,
        "all_contributing_pools_corroborated": ok,
        "current_usdcx_usd_equivalence_verified": True,
        "execution_authorized": False,
    }


def split_liquidity(*, nominal=True, independent=True):
    return {
        "contract_version": "x1_ninja_liquidity_freshness/v2",
        "provider_nominal_liquidity_freshness_verified": nominal,
        "independent_liquidity_usd_freshness_verified": independent,
        "provider_market_matches_nominal_basis": nominal,
        "provider_numerical_unit": "USDC.X_nominal_quote_basis",
        "provider_nominal_liquidity_value": "725.7858651168269",
        "independent_liquidity_usd_value": "725.7016666986146690586144687",
        "current_usdcx_usd_equivalence_verified": independent,
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }


def rolling():
    return {
        "contract_version": "x1_rolling_24h_market_activity/v1",
        "volume_24h_freshness_verified": True,
        "volume_24h_window_coverage_verified": True,
        "volume_24h_semantics_verified": True,
        "transactions_24h_freshness_verified": True,
        "transactions_24h_window_coverage_verified": True,
        "transactions_24h_semantics_verified": True,
        "execution_authorized": False,
    }


def test_v3_projects_split_liquidity_without_relabeling_legacy_liquidity():
    result = evaluate_current_market_freshness_v3(
        market(),
        backfill(),
        evaluated_at=1000,
        policy=accepted_instant_scan_freshness_policy(),
        liquidity_freshness_evidence=legacy_liquidity(False),
        liquidity_freshness_evidence_v2=split_liquidity(),
        rolling_activity_evidence=rolling(),
    )

    assert result["contract_version"] == V3_CONTRACT
    assert result["fields"]["liquidity_usd"]["freshness_verified"] is False
    assert result["fields"]["provider_nominal_liquidity"]["freshness_verified"] is True
    assert result["fields"]["provider_nominal_liquidity"]["unit"] == "USDC.X_nominal_quote_basis"
    assert result["fields"]["independent_liquidity_usd"]["freshness_verified"] is True
    assert result["fields"]["independent_liquidity_usd"]["unit"] == "USD"
    assert result["fields"]["volume_24h_usd"]["freshness_verified"] is True
    assert result["fields"]["transactions_24h"]["freshness_verified"] is True
    assert result["provider_nominal_liquidity_freshness_verified"] is True
    assert result["independent_liquidity_usd_freshness_verified"] is True
    assert result["execution_authorized"] is False


def test_v3_rejects_wrong_split_contract_without_affecting_rolling():
    split = split_liquidity()
    split["contract_version"] = "made_up/v9"
    result = evaluate_current_market_freshness_v3(
        market(),
        backfill(),
        evaluated_at=1000,
        policy=accepted_instant_scan_freshness_policy(),
        liquidity_freshness_evidence=legacy_liquidity(False),
        liquidity_freshness_evidence_v2=split,
        rolling_activity_evidence=rolling(),
    )
    assert result["fields"]["provider_nominal_liquidity"]["freshness_verified"] is False
    assert result["fields"]["independent_liquidity_usd"]["freshness_verified"] is False
    assert result["fields"]["volume_24h_usd"]["freshness_verified"] is True
    assert result["fields"]["transactions_24h"]["freshness_verified"] is True
