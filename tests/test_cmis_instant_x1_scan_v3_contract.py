from __future__ import annotations

from copy import deepcopy

from liquidity_scout.services.cmis_instant_x1_scan import build_instant_x1_scan_response
from liquidity_scout.services.cmis_instant_x1_scan_v3 import (
    CONTRACT_VERSION,
    build_instant_x1_scan_v3_response,
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
    return identity, market, tokenomics, history, risk


def test_v3_preserves_v2_fact_history_risk_and_authority_sections():
    args = fixtures()
    v2 = build_instant_x1_scan_response(*args)
    original = deepcopy(v2)
    freshness = {
        "contract_version": "x1_current_market_freshness/v1",
        "freshness_state": "PARTIAL",
        "fields": {
            "price_usd": {"freshness_verified": True},
            "liquidity_usd": {"freshness_verified": False},
            "volume_24h_usd": {"freshness_verified": False},
            "transactions_24h": {"freshness_verified": False},
        },
    }

    v3 = build_instant_x1_scan_v3_response(*args, freshness_assessment=freshness)

    assert v2 == original
    assert CONTRACT_VERSION == "instant_x1_scan/v3"
    assert v3["data"]["contract_version"] == CONTRACT_VERSION
    assert v3["data"]["sections"]["identity"] == v2["data"]["sections"]["identity"]
    assert v3["data"]["sections"]["tokenomics"] == v2["data"]["sections"]["tokenomics"]
    assert v3["data"]["sections"]["history"] == v2["data"]["sections"]["history"]
    assert v3["data"]["sections"]["risk"] == v2["data"]["sections"]["risk"]
    assert v3["data"]["sections"]["history"]["full_supported_pair_lifetime_verified"] is True
    assert v3["data"]["sections"]["history"]["full_usd_lifetime_verified"] is False
    assert v3["data"]["execution_authorized"] is False


def test_v3_projects_field_scoped_freshness_only_into_market_section():
    args = fixtures()
    freshness = {
        "contract_version": "x1_current_market_freshness/v1",
        "freshness_state": "PARTIAL",
        "fields": {
            "price_usd": {"freshness_verified": True},
            "liquidity_usd": {"freshness_verified": False},
            "volume_24h_usd": {"freshness_verified": False},
            "transactions_24h": {"freshness_verified": False},
        },
    }
    v3 = build_instant_x1_scan_v3_response(*args, freshness_assessment=freshness)
    market = v3["data"]["sections"]["market"]

    assert market["freshness"] == freshness
    assert market["price_freshness_verified"] is True
    assert market["liquidity_freshness_verified"] is False
    assert market["volume_24h_freshness_verified"] is False
    assert market["transactions_24h_freshness_verified"] is False


def test_v3_without_assessment_fails_closed_to_not_verified_freshness():
    v3 = build_instant_x1_scan_v3_response(*fixtures())
    market = v3["data"]["sections"]["market"]
    assert market["freshness"]["freshness_state"] == "NOT_VERIFIED"
    assert market["price_freshness_verified"] is False
    assert market["liquidity_freshness_verified"] is False
    assert market["volume_24h_freshness_verified"] is False
    assert market["transactions_24h_freshness_verified"] is False


def test_v3_preserves_verified_native_xnt_distribution():
    args = fixtures()
    freshness = {
        "contract_version": "x1_current_market_freshness/v1",
        "scope": "instant_x1_scan.current_market",
        "freshness_state": "NOT_VERIFIED",
        "collection_freshness_verified": False,
        "provider_price_fact_time_verified": False,
        "current_market_freshness_verified": False,
        "verified_field_count": 0,
        "total_field_count": 4,
        "fields": {
            "price_usd": {
                "freshness_verified": False,
                "reason": "not_verified",
            },
            "liquidity_usd": {
                "freshness_verified": False,
                "reason": "not_verified",
            },
            "volume_24h_usd": {
                "freshness_verified": False,
                "reason": "not_verified",
            },
            "transactions_24h": {
                "freshness_verified": False,
                "reason": "not_verified",
            },
        },
        "limitations": [],
    }
    distribution = {
        "native_account_concentration_verified": True,
        "cmis_promotable": True,
        "counted_entity": "native_xnt_account_address",
        "slot_scope_verified": True,
        "largest_accounts_slot": 100,
        "network_supply_slot": 110,
        "slot_span": 10,
        "circulating_supply_base_units": "1000",
        "buckets": {
            "top_20": {
                "percent_of_circulating_xnt": 22.8,
                "available_account_count": 20,
            }
        },
        "sources": [],
    }

    v3 = build_instant_x1_scan_v3_response(
        *args,
        freshness_assessment=freshness,
        native_distribution=distribution,
    )

    holder = v3["data"]["sections"]["holder_concentration"]
    assert holder["holders_state"] == "not_applicable"
    assert holder["top_account_concentration"]["verified"] is True
    assert holder["top_account_concentration"]["value"] == 22.8
    assert (
        "holder_count_requires_existing_verified_holder_semantics"
        not in v3["data"]["limitations"]
    )
