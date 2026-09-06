from copy import deepcopy

from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)
from liquidity_scout.services.cmis_instant_x1_scan_v5 import (
    build_instant_x1_scan_v5_response,
)
from liquidity_scout.services.cmis_instant_x1_scan_v6 import (
    CONTRACT_VERSION,
    HISTORY_ADEQUACY_CONTRACT_VERSION,
    build_instant_x1_scan_v6_response,
)


def envelope(service, *, status="partial", asset=None, data=None, confidence=None, risk=None):
    return {
        "service": service,
        "chain": "x1",
        "status": status,
        "asset": dict(asset or {"symbol": "XNT", "name": "XNT", "mint": None}),
        "data": dict(data or {}),
        "risk": risk,
        "confidence": dict(confidence or {}),
        "sources": [{"source": "test", "role": service}],
        "warnings": [],
        "errors": [],
        "observed_at": 1000.0,
    }


def fixtures():
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
        asset={"symbol": "XNT", "name": "XNT", "mint": WRAPPED_XNT_MINT},
        data={
            "price_usd": 1.0,
            "liquidity_usd": 100000.0,
            "volume_24h_usd": 10000.0,
            "transactions_24h": 500,
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
            "supply_verified": True,
            "mint_authority_verified": True,
            "freeze_authority_verified": True,
        },
    )
    history = envelope(
        "historical_compare",
        data={
            "mode": "all_available",
            "coverage_scope": "cmis_verified_observations_with_bounded_provider_price_backfill",
            "available_metric_count": 1,
            "multi_point_metric_count": 1,
            "provider_history_imported": True,
            "full_supported_pair_lifetime_verified": True,
            "continuous_pair_price_coverage_verified": True,
            "provider_range_complete_verified": True,
            "historical_quote_usd_equivalence_verified": False,
            "full_usd_lifetime_verified": False,
            "full_asset_lifetime_verified": False,
            "continuous_coverage_verified": False,
            "price_lifetime_coverage": {
                "asset_identity_bound": True,
                "base_mint": WRAPPED_XNT_MINT,
                "quote_mint": USDC_X_MINT,
                "full_supported_pair_lifetime_verified": True,
                "continuous_pair_price_coverage_verified": True,
                "provider_range_complete_verified": True,
                "historical_quote_usd_equivalence_verified": False,
                "full_usd_lifetime_verified": False,
                "global_provider_archive_complete_verified": False,
            },
            "metrics": {
                "price": {
                    "status": "ok",
                    "observation_count": 348864,
                    "current_verified": True,
                }
            },
        },
    )
    risk = envelope(
        "risk_check",
        risk={"recommendation": "WARN", "flags": [], "reasons": []},
    )
    return identity, market, tokenomics, history, risk


def freshness():
    return {
        "contract_version": "x1_current_market_freshness/v3",
        "scope": "instant_x1_scan.current_market",
        "freshness_state": "PARTIAL",
        "current_market_freshness_verified": False,
        "verified_field_count": 4,
        "total_field_count": 6,
        "fields": {
            "price_usd": {"freshness_verified": False},
            "liquidity_usd": {"freshness_verified": False},
            "provider_nominal_liquidity": {
                "freshness_verified": True,
                "value": "100000",
                "unit": "USDC.X_nominal_quote_basis",
            },
            "independent_liquidity_usd": {
                "freshness_verified": True,
                "value": "99990",
                "unit": "USD",
            },
            "volume_24h_usd": {"freshness_verified": True},
            "transactions_24h": {"freshness_verified": True},
        },
        "execution_authorized": False,
    }


def native_distribution():
    return {
        "native_account_concentration_verified": True,
        "cmis_promotable": True,
        "counted_entity": "native_xnt_account_address",
        "slot_scope_verified": True,
        "largest_accounts_slot": 100,
        "network_supply_slot": 109,
        "slot_span": 9,
        "circulating_supply_base_units": "1000000",
        "buckets": {
            "top_20": {
                "percent_of_circulating_xnt": 21.65,
                "available_account_count": 20,
            }
        },
        "beneficial_owner_identity_verified": False,
        "person_or_wallet_group_count_verified": False,
        "sources": [],
    }


def test_v6_verifies_native_xnt_scan_history_without_stronger_overclaims():
    args = fixtures()
    result = build_instant_x1_scan_v6_response(
        *args,
        freshness_assessment=freshness(),
        native_distribution=native_distribution(),
    )

    assert result["data"]["contract_version"] == CONTRACT_VERSION
    completion = result["data"]["sections"]["history"]["scan_completion"]
    assert completion["contract_version"] == HISTORY_ADEQUACY_CONTRACT_VERSION
    assert completion["status"] == "VERIFIED"
    assert completion["required_history_scope"] == "supported_pair_price_lifetime"
    assert completion["history_completion_verified"] is True
    assert all(completion["checks"].values())
    assert completion["same_fact_corroboration"]["state"] == "BOUNDED_PROVIDER_CLOSE_CORROBORATION"
    assert completion["same_fact_corroboration"]["source_independence_implied"] is False
    assert completion["source_independence_verified"] is False
    assert completion["source_independence_required_for_scan_completion"] is False
    assert completion["historical_quote_usd_equivalence_verified"] is False
    assert completion["full_usd_lifetime_verified"] is False
    assert completion["full_usd_lifetime_required_for_scan_completion"] is False
    assert completion["global_provider_archive_complete_verified"] is False
    assert completion["global_archive_completeness_required_for_scan_completion"] is False
    assert completion["non_price_metric_lifetimes_verified"] is False
    assert completion["non_price_metric_lifetimes_required_for_scan_completion"] is False
    assert completion["execution_authorized"] is False
    assert "provider_source_independence_not_verified" in result["data"]["limitations"]
    assert result["freshness"]["contract_version"] == "cmis_response_freshness/v1"
    assert result["freshness"]["scope"] == "instant_x1_scan.response"
    assert result["freshness"]["state"] == "PARTIAL"
    assert result["freshness"]["freshness_verified"] is False
    assert result["freshness"]["details"] == result["data"]["sections"]["market"]["freshness"]


def test_v6_preserves_v5_sections_except_added_history_completion():
    args = fixtures()
    v5 = build_instant_x1_scan_v5_response(
        *args,
        freshness_assessment=freshness(),
        native_distribution=native_distribution(),
    )
    before = deepcopy(v5)
    v6 = build_instant_x1_scan_v6_response(
        *args,
        freshness_assessment=freshness(),
        native_distribution=native_distribution(),
    )

    assert v5 == before
    for section in ("identity", "market", "tokenomics", "holder_concentration", "risk", "evidence"):
        assert v6["data"]["sections"][section] == v5["data"]["sections"][section]
    v6_history = deepcopy(v6["data"]["sections"]["history"])
    v6_history.pop("scan_completion")
    assert v6_history == v5["data"]["sections"]["history"]


def test_v6_fails_closed_when_pair_lifetime_gate_is_missing():
    args = list(fixtures())
    history = deepcopy(args[3])
    history["data"]["continuous_pair_price_coverage_verified"] = False
    args[3] = history

    result = build_instant_x1_scan_v6_response(
        *args,
        freshness_assessment=freshness(),
        native_distribution=native_distribution(),
    )
    completion = result["data"]["sections"]["history"]["scan_completion"]
    assert completion["status"] == "NOT_VERIFIED"
    assert completion["history_completion_verified"] is False
    assert completion["checks"]["continuous_pair_price_coverage_verified"] is False


def test_v6_fails_closed_on_non_native_identity_even_with_xnt_named_history():
    args = list(fixtures())
    identity = deepcopy(args[0])
    identity["data"]["identity_key"] = "mint:" + WRAPPED_XNT_MINT
    identity["asset"]["mint"] = WRAPPED_XNT_MINT
    args[0] = identity

    result = build_instant_x1_scan_v6_response(
        *args,
        freshness_assessment=freshness(),
    )
    completion = result["data"]["sections"]["history"]["scan_completion"]
    assert completion["history_completion_verified"] is False
    assert completion["checks"]["native_xnt_identity_verified"] is False


def test_v6_fails_closed_on_pair_identity_mismatch():
    args = list(fixtures())
    history = deepcopy(args[3])
    history["data"]["price_lifetime_coverage"]["quote_mint"] = "OtherQuoteMint"
    args[3] = history

    result = build_instant_x1_scan_v6_response(
        *args,
        freshness_assessment=freshness(),
        native_distribution=native_distribution(),
    )
    completion = result["data"]["sections"]["history"]["scan_completion"]
    assert completion["history_completion_verified"] is False
    assert completion["checks"]["exact_xnt_usdcx_pair_identity_bound"] is False
