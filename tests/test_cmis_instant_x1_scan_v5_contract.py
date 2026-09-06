import pytest

from liquidity_scout.services.cmis_instant_x1_scan_v4 import (
    build_instant_x1_scan_v4_response,
)
from liquidity_scout.services.cmis_instant_x1_scan_v5 import (
    CONTRACT_VERSION,
    FRESHNESS_CONTRACT_VERSION,
    build_instant_x1_scan_v5_response,
)


def envelope(service, *, status="partial", data=None, confidence=None, risk=None):
    return {
        "service": service,
        "chain": "x1",
        "status": status,
        "asset": {"symbol": "OGX", "name": "OGX", "mint": "AssetMint"},
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
            "resolved_by": "exact_mint",
            "match_quality": "exact",
            "identity_key": "mint:AssetMint",
        },
        confidence={"complete": True},
    )
    market = envelope(
        "market_report",
        data={
            "price_usd": 1.0,
            "liquidity_usd": 725.7858651168269,
            "volume_24h_usd": 0,
            "transactions_24h": 0,
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
    tokenomics = envelope("tokenomics", data={})
    history = envelope(
        "historical_compare",
        data={
            "mode": "all_available",
            "coverage_scope": "cmis_stored_verified_observations",
            "available_metric_count": 0,
            "multi_point_metric_count": 0,
            "full_supported_pair_lifetime_verified": False,
            "continuous_pair_price_coverage_verified": False,
            "provider_range_complete_verified": False,
            "historical_quote_usd_equivalence_verified": False,
            "full_usd_lifetime_verified": False,
            "full_asset_lifetime_verified": False,
            "continuous_coverage_verified": False,
            "metrics": {},
        },
    )
    risk = envelope(
        "risk_check",
        risk={"recommendation": "WARN", "flags": [], "reasons": []},
    )
    return identity, market, tokenomics, history, risk


def freshness_v3():
    return {
        "contract_version": FRESHNESS_CONTRACT_VERSION,
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
                "value": "725.7858651168269",
                "unit": "USDC.X_nominal_quote_basis",
            },
            "independent_liquidity_usd": {
                "freshness_verified": True,
                "value": "725.7016666986146690586144687",
                "unit": "USD",
            },
            "volume_24h_usd": {"freshness_verified": True},
            "transactions_24h": {"freshness_verified": True},
        },
        "provider_nominal_liquidity_freshness_verified": True,
        "independent_liquidity_usd_freshness_verified": True,
        "limitations": [
            "provider_nominal_liquidity_is_not_independent_external_usd",
            "legacy_liquidity_usd_freshness_semantics_preserved_from_v2",
        ],
        "execution_authorized": False,
    }


def test_v5_preserves_v4_sections_and_projects_split_liquidity():
    args = fixtures()
    v4 = build_instant_x1_scan_v4_response(*args)
    v5 = build_instant_x1_scan_v5_response(
        *args,
        freshness_assessment=freshness_v3(),
    )

    assert v5["data"]["contract_version"] == CONTRACT_VERSION
    for section in ("identity", "tokenomics", "history", "risk", "holder_concentration"):
        assert v5["data"]["sections"][section] == v4["data"]["sections"][section]

    market = v5["data"]["sections"]["market"]
    assert market["liquidity_freshness_verified"] is False
    assert market["provider_nominal_liquidity"] == "725.7858651168269"
    assert market["provider_nominal_liquidity_unit"] == "USDC.X_nominal_quote_basis"
    assert market["provider_nominal_liquidity_freshness_verified"] is True
    assert market["independent_liquidity_usd"] == "725.7016666986146690586144687"
    assert market["independent_liquidity_usd_freshness_verified"] is True
    assert market["volume_24h_freshness_verified"] is True
    assert market["transactions_24h_freshness_verified"] is True
    assert v5["data"]["execution_authorized"] is False
    assert v5["freshness"]["contract_version"] == "cmis_response_freshness/v1"
    assert v5["freshness"]["scope"] == "instant_x1_scan.response"
    assert v5["freshness"]["state"] == "PARTIAL"
    assert v5["freshness"]["freshness_verified"] is False
    assert v5["freshness"]["details"] == market["freshness"]


def test_v5_without_v3_assessment_fails_closed_for_split_fields():
    v5 = build_instant_x1_scan_v5_response(*fixtures())
    market = v5["data"]["sections"]["market"]

    assert market["freshness"]["contract_version"] == FRESHNESS_CONTRACT_VERSION
    assert market["provider_nominal_liquidity"] is None
    assert market["provider_nominal_liquidity_freshness_verified"] is False
    assert market["independent_liquidity_usd"] is None
    assert market["independent_liquidity_usd_freshness_verified"] is False
    assert market["volume_24h_freshness_verified"] is False
    assert market["transactions_24h_freshness_verified"] is False
    assert v5["freshness"]["contract_version"] == "cmis_response_freshness/v1"
    assert v5["freshness"]["state"] == "NOT_VERIFIED"
    assert v5["freshness"]["freshness_verified"] is False
    assert v5["freshness"]["details"] == market["freshness"]
    assert "reason" not in v5["freshness"]


def test_v5_rejects_v2_or_execution_authorizing_freshness():
    wrong = freshness_v3()
    wrong["contract_version"] = "x1_current_market_freshness/v2"
    with pytest.raises(ValueError, match="requires x1_current_market_freshness/v3"):
        build_instant_x1_scan_v5_response(*fixtures(), freshness_assessment=wrong)

    unsafe = freshness_v3()
    unsafe["execution_authorized"] = True
    with pytest.raises(ValueError, match="may not authorize execution"):
        build_instant_x1_scan_v5_response(*fixtures(), freshness_assessment=unsafe)
