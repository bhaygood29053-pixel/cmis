from liquidity_scout.services.cmis_instant_x1_scan import (
    CONTRACT_VERSION,
    build_instant_x1_scan_response,
)


def envelope(service, *, status="partial", data=None, confidence=None, risk=None):
    return {
        "service": service,
        "chain": "x1",
        "status": status,
        "asset": {"symbol": "XNT", "name": "XNT", "mint": "WrappedXNT"},
        "data": dict(data or {}),
        "risk": risk,
        "confidence": dict(confidence or {}),
        "sources": [{"source": "test", "role": service}],
        "warnings": [],
        "errors": [],
        "observed_at": 1_788_288_243,
    }


def test_scan_v3_projects_bounded_provider_history_without_lifetime_promotion():
    identity = envelope(
        "asset_lookup",
        status="ok",
        data={
            "resolved_by": "native",
            "match_quality": "native",
            "identity_key": "native:xnt",
        },
        confidence={"complete": True},
    )
    market = envelope(
        "market_report",
        data={
            "price_usd": 0.39,
            "liquidity_usd": 106000.0,
            "volume_24h_usd": 12000.0,
            "transactions_24h": 5000,
            "completeness": {
                "price": True,
                "liquidity": True,
                "volume_24h": True,
                "transactions_24h": True,
                "holders": False,
            },
        },
        confidence={"core_market_complete": True},
    )
    tokenomics = envelope(
        "tokenomics",
        data={
            "current_total_supply": "1070000000",
            "supply_verified": True,
            "mint_authority": None,
            "mint_authority_verified": True,
            "mint_authority_state": "not_applicable",
            "freeze_authority": None,
            "freeze_authority_verified": True,
            "freeze_authority_state": "not_applicable",
            "circulating_supply": "14000000",
            "circulating_supply_verified": True,
        },
    )
    history = envelope(
        "historical_compare",
        data={
            "mode": "all_available",
            "coverage_scope": "cmis_stored_verified_observations",
            "first_verified_observed_at": 1_725_000_000,
            "last_verified_observed_at": 1_726_000_000,
            "coverage_seconds": 1_000_000,
            "available_metric_count": 1,
            "multi_point_metric_count": 1,
            "asset_lifetime_start_verified": False,
            "full_asset_lifetime_verified": False,
            "continuous_coverage_verified": False,
            "provider_history_imported": True,
            "provider_price_history": {
                "available": True,
                "usable_observation_count": 24,
                "first_observed_at": 1_725_000_000,
                "last_observed_at": 1_725_900_000,
            },
            "provider_history_backfill": {
                "status": "partial",
                "provider_history_imported": True,
                "stored_verified_provider_observation_count": 24,
                "full_asset_lifetime_verified": False,
                "continuous_coverage_verified": False,
            },
            "coverage": {
                "market": {"status": "partial"},
                "onchain": {
                    "status": "not_requested",
                    "reason": "onchain_coverage_not_requested",
                },
            },
            "metrics": {
                "price": {
                    "status": "ok",
                    "observation_count": 25,
                    "coverage_seconds": 1_000_000,
                    "observed_gap_count": 0,
                    "largest_observed_gap_seconds": 300,
                    "gap_threshold_seconds": 129600,
                    "provider_backfill_observation_count": 24,
                    "provider_history_imported": True,
                    "continuous_coverage_verified": False,
                }
            },
        },
    )
    risk = envelope(
        "risk_check",
        risk={
            "recommendation": "WARN",
            "flags": ["token_activity_unavailable"],
            "reasons": ["Verified bounded token activity evidence was not supplied."],
            "confidence": {},
            "score": None,
            "score_verified": False,
            "score_reason": "risk_score_not_calibrated",
            "policy": {},
        },
    )

    freshness = {
        "contract_version": "x1_current_market_freshness/v1",
        "freshness_state": "PARTIAL",
        "collection_freshness_verified": True,
        "current_market_freshness_verified": False,
        "fields": {
            "price_usd": {"freshness_verified": True},
            "liquidity_usd": {"freshness_verified": False},
            "volume_24h_usd": {"freshness_verified": False},
            "transactions_24h": {"freshness_verified": False},
        },
    }
    response = build_instant_x1_scan_response(
        identity,
        market,
        tokenomics,
        history,
        risk,
        freshness_assessment=freshness,
    )

    assert CONTRACT_VERSION == "instant_x1_scan/v3"
    section = response["data"]["sections"]["history"]
    assert (
        section["coverage_scope"]
        == "cmis_verified_observations_with_bounded_provider_price_backfill"
    )
    assert section["provider_history_imported"] is True
    assert section["metrics"]["price"]["observation_count"] == 25
    assert section["metrics"]["price"]["provider_backfill_observation_count"] == 24
    assert section["metrics"]["price"]["observed_gap_count"] == 0
    assert section["full_asset_lifetime_verified"] is False
    assert section["continuous_coverage_verified"] is False

    market_section = response["data"]["sections"]["market"]
    assert market_section["price_freshness_verified"] is True
    assert market_section["liquidity_freshness_verified"] is False
    assert market_section["volume_24h_freshness_verified"] is False
    assert market_section["transactions_24h_freshness_verified"] is False
    assert market_section["freshness"]["freshness_state"] == "PARTIAL"

    limitations = set(response["data"]["limitations"])
    assert "provider_price_backfill_is_price_only" in limitations
    assert "provider_source_independence_not_verified" in limitations
    assert "provider_archive_completeness_not_verified" in limitations
    assert "current_market_freshness_is_field_scoped" in limitations
    assert "price_freshness_uses_timestamped_provider_backfill" in limitations
    assert "liquidity_volume_transaction_fact_time_not_verified" in limitations
    assert "collection_time_is_not_provider_fact_time" in limitations
    assert "history_does_not_imply_complete_asset_lifetime" in limitations
    assert "continuous_coverage_requires_separate_archive_completeness_proof" in limitations
    assert response["data"]["execution_authorized"] is False


def test_scan_v3_projects_verified_pair_lifetime_without_usd_overclaim():
    identity = envelope(
        "asset_lookup",
        status="ok",
        data={"resolved_by": "native"},
        confidence={"complete": True},
    )
    market = envelope(
        "market_report",
        data={
            "completeness": {
                "price": True,
                "liquidity": True,
                "volume_24h": True,
                "transactions_24h": True,
                "holders": False,
            }
        },
        confidence={"core_market_complete": True},
    )
    tokenomics = envelope(
        "tokenomics",
        data={
            "supply_verified": True,
            "mint_authority_verified": True,
            "freeze_authority_verified": True,
        },
    )
    history = envelope(
        "historical_compare",
        data={
            "mode": "all_available",
            "coverage_scope": "cmis_stored_verified_observations",
            "available_metric_count": 1,
            "multi_point_metric_count": 1,
            "full_supported_pair_lifetime_verified": True,
            "continuous_pair_price_coverage_verified": True,
            "provider_range_complete_verified": True,
            "historical_quote_usd_equivalence_verified": False,
            "full_usd_lifetime_verified": False,
            "full_asset_lifetime_verified": False,
            "continuous_coverage_verified": False,
            "price_lifetime_coverage": {
                "base_mint": "WrappedXNT",
                "quote_mint": "USDCX",
                "full_supported_pair_lifetime_verified": True,
            },
            "metrics": {"price": {"status": "ok"}},
        },
    )
    risk = envelope(
        "risk_check",
        risk={"recommendation": "WARN", "flags": [], "reasons": []},
    )

    response = build_instant_x1_scan_response(
        identity,
        market,
        tokenomics,
        history,
        risk,
    )

    section = response["data"]["sections"]["history"]
    assert section["price_coverage_scope"] == "full_supported_pair_lifetime"
    assert section["full_supported_pair_lifetime_verified"] is True
    assert section["continuous_pair_price_coverage_verified"] is True
    assert section["provider_range_complete_verified"] is True
    assert section["historical_quote_usd_equivalence_verified"] is False
    assert section["full_usd_lifetime_verified"] is False
    assert section["full_asset_lifetime_verified"] is False

    limitations = set(response["data"]["limitations"])
    assert "historical_quote_usd_equivalence_not_verified" in limitations
    assert (
        "full_supported_pair_lifetime_price_does_not_imply_other_metric_lifetimes"
        in limitations
    )
    assert "provider_archive_completeness_not_verified" not in limitations
    assert "history_does_not_imply_complete_asset_lifetime" not in limitations
    assert response["data"]["execution_authorized"] is False
