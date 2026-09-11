from liquidity_scout.providers.x1.current_market_freshness import (
    V3_CONTRACT,
    evaluate_current_market_freshness_v3,
)
from liquidity_scout.providers.x1.instant_scan_freshness_policy import (
    accepted_instant_scan_freshness_policy,
)


PRIMARY_POOL = "pool-main"


def market():
    return {
        "data": {
            "price_usd": 1.0,
            "liquidity_usd": 725.7858651168269,
            "volume_24h_usd": 0,
            "transactions_24h": 0,
            "primary_pool": {
                "address": PRIMARY_POOL,
                "price_usd": 1.0,
            },
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


def stale_backfill():
    return {
        "provider_history_imported": True,
        "last_imported_observed_at": 800.0,
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


def split_liquidity(
    *,
    nominal=True,
    independent=True,
    independent_asset_usd="1.0",
    pool_address=PRIMARY_POOL,
):
    return {
        "contract_version": "x1_ninja_liquidity_freshness/v2",
        "provider_nominal_liquidity_freshness_verified": nominal,
        "independent_liquidity_usd_freshness_verified": independent,
        "provider_market_matches_nominal_basis": nominal,
        "provider_numerical_unit": "USDC.X_nominal_quote_basis",
        "provider_nominal_liquidity_value": "725.7858651168269",
        "independent_liquidity_usd_value": "725.7016666986146690586144687",
        "current_usdcx_usd_equivalence_verified": independent,
        "pool_results": [
            {
                "pool_address": pool_address,
                "reserve_mapping_verified": True,
                "provider_nominal_liquidity_freshness_verified": nominal,
                "independent_liquidity_usd_freshness_verified": independent,
                "unit_semantics": {
                    "contract_version": "x1_ninja_liquidity_unit_semantics/v1",
                    "independent_current_usd": {
                        "independent_asset_usd": independent_asset_usd,
                        "independent_usd_valuation_verified": independent,
                    },
                    "execution_authorized": False,
                },
            }
        ],
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
    assert result["independent_current_price_usd_freshness_verified"] is True
    assert result["execution_authorized"] is False


def test_v3_promotes_price_from_independent_fresh_chain_state_when_history_is_stale():
    result = evaluate_current_market_freshness_v3(
        market(),
        stale_backfill(),
        evaluated_at=1000,
        policy=accepted_instant_scan_freshness_policy(),
        liquidity_freshness_evidence=legacy_liquidity(False),
        liquidity_freshness_evidence_v2=split_liquidity(),
        rolling_activity_evidence=rolling(),
    )

    price = result["fields"]["price_usd"]
    assert price["freshness_verified"] is True
    assert price["provider_fact_time_verified"] is False
    assert price["current_value_reproduced_from_fresh_chain_state"] is True
    assert price["current_price_value"] == 1.0
    assert price["independent_current_usd_value"] == 1.0
    assert price["primary_pool_address"] == PRIMARY_POOL
    assert price["reason"] == "current_market_price_matches_independent_fresh_chain_state_valuation"
    assert result["independent_current_price_usd_freshness_verified"] is True
    assert "price_freshness_requires_timestamped_provider_price_match" not in result["limitations"]
    assert "provider_price_fact_time_not_implied_by_independent_chain_price_reproduction" in result["limitations"]


def test_v3_rejects_independent_chain_price_that_disagrees_with_provider_price():
    result = evaluate_current_market_freshness_v3(
        market(),
        stale_backfill(),
        evaluated_at=1000,
        policy=accepted_instant_scan_freshness_policy(),
        liquidity_freshness_evidence=legacy_liquidity(False),
        liquidity_freshness_evidence_v2=split_liquidity(
            independent_asset_usd="1.02"
        ),
        rolling_activity_evidence=rolling(),
    )

    assert result["fields"]["price_usd"]["freshness_verified"] is False
    assert result["independent_current_price_usd_freshness_verified"] is False
    evidence = result["independent_current_price_usd_evidence"]
    assert evidence["value_link_verified"] is False
    assert evidence["reason"] == "provider_price_does_not_match_independent_fresh_chain_state_valuation"
    assert "independent_current_price_usd_proof_incomplete" in result["limitations"]


def test_v3_rejects_independent_chain_price_for_wrong_primary_pool():
    result = evaluate_current_market_freshness_v3(
        market(),
        stale_backfill(),
        evaluated_at=1000,
        policy=accepted_instant_scan_freshness_policy(),
        liquidity_freshness_evidence=legacy_liquidity(False),
        liquidity_freshness_evidence_v2=split_liquidity(
            pool_address="different-pool"
        ),
        rolling_activity_evidence=rolling(),
    )

    assert result["fields"]["price_usd"]["freshness_verified"] is False
    assert result["independent_current_price_usd_freshness_verified"] is False
    assert result["independent_current_price_usd_evidence"]["primary_pool_address"] == PRIMARY_POOL


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
