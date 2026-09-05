from liquidity_scout.providers.x1.current_market_freshness import (
    V1_CONTRACT,
    V2_CONTRACT,
    evaluate_current_market_freshness,
    evaluate_current_market_freshness_v2,
)
from liquidity_scout.providers.x1.instant_scan_freshness_policy import (
    accepted_instant_scan_freshness_policy,
)


def market():
    return {
        "data": {
            "price_usd": 1.0,
            "liquidity_usd": 500.0,
            "volume_24h_usd": 20.0,
            "transactions_24h": 4,
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


def liquidity(ok=True):
    return {
        "contract_version": "x1_ninja_liquidity_freshness/v1",
        "liquidity_freshness_verified": ok,
        "current_value_reproduced_from_fresh_chain_state": ok,
        "all_contributing_pools_corroborated": ok,
        "current_usdcx_usd_equivalence_verified": ok,
        "execution_authorized": False,
    }


def rolling(*, volume=False, transactions=False):
    return {
        "contract_version": "x1_rolling_24h_market_activity/v1",
        "volume_24h_freshness_verified": volume,
        "volume_24h_window_coverage_verified": volume,
        "volume_24h_semantics_verified": volume,
        "transactions_24h_freshness_verified": transactions,
        "transactions_24h_window_coverage_verified": transactions,
        "transactions_24h_semantics_verified": transactions,
        "execution_authorized": False,
    }


def test_v1_remains_unchanged_and_liquidity_unverified():
    result = evaluate_current_market_freshness(
        market(),
        backfill(),
        evaluated_at=1000,
        policy=accepted_instant_scan_freshness_policy(),
    )
    assert result["contract_version"] == V1_CONTRACT
    assert result["fields"]["price_usd"]["freshness_verified"] is True
    assert result["fields"]["liquidity_usd"]["freshness_verified"] is False


def test_v2_promotes_liquidity_only_from_exact_accepted_evidence():
    result = evaluate_current_market_freshness_v2(
        market(),
        backfill(),
        evaluated_at=1000,
        policy=accepted_instant_scan_freshness_policy(),
        chain_corroboration={"contract_version": "x1_rpc_market_corroboration/v1"},
        liquidity_freshness_evidence=liquidity(True),
    )
    assert result["contract_version"] == V2_CONTRACT
    assert result["freshness_state"] == "PARTIAL"
    assert result["verified_field_count"] == 2
    assert result["fields"]["price_usd"]["freshness_verified"] is True
    assert result["fields"]["liquidity_usd"]["freshness_verified"] is True
    assert result["fields"]["liquidity_usd"]["provider_fact_time_verified"] is False
    assert result["fields"]["volume_24h_usd"]["freshness_verified"] is False
    assert result["fields"]["transactions_24h"]["freshness_verified"] is False
    assert result["current_market_freshness_verified"] is False


def test_v2_does_not_trust_wrong_liquidity_contract():
    evidence = liquidity(True)
    evidence["contract_version"] = "made_up/v1"
    result = evaluate_current_market_freshness_v2(
        market(),
        backfill(),
        evaluated_at=1000,
        policy=accepted_instant_scan_freshness_policy(),
        liquidity_freshness_evidence=evidence,
    )
    assert result["fields"]["liquidity_usd"]["freshness_verified"] is False


def test_v2_can_promote_all_fields_only_when_rolling_contract_also_passes():
    result = evaluate_current_market_freshness_v2(
        market(),
        backfill(),
        evaluated_at=1000,
        policy=accepted_instant_scan_freshness_policy(),
        liquidity_freshness_evidence=liquidity(True),
        rolling_activity_evidence=rolling(volume=True, transactions=True),
    )
    assert result["freshness_state"] == "VERIFIED"
    assert result["verified_field_count"] == 4
    assert result["current_market_freshness_verified"] is True


def test_v2_rolling_volume_and_transactions_fail_independently():
    result = evaluate_current_market_freshness_v2(
        market(),
        backfill(),
        evaluated_at=1000,
        policy=accepted_instant_scan_freshness_policy(),
        liquidity_freshness_evidence=liquidity(True),
        rolling_activity_evidence=rolling(volume=True, transactions=False),
    )
    assert result["fields"]["volume_24h_usd"]["freshness_verified"] is True
    assert result["fields"]["transactions_24h"]["freshness_verified"] is False
    assert result["current_market_freshness_verified"] is False
