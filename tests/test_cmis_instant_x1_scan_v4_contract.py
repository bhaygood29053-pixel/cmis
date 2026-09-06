from __future__ import annotations

import pytest

from liquidity_scout.services.cmis_instant_x1_scan_v3 import (
    build_instant_x1_scan_v3_response,
)
from liquidity_scout.services.cmis_instant_x1_scan_v4 import (
    CONTRACT_VERSION,
    FRESHNESS_CONTRACT_VERSION,
    build_instant_x1_scan_v4_response,
)
from tests.test_cmis_instant_x1_scan_v3_contract import fixtures


def _freshness_v2(*, price=True, liquidity=True, volume=True, transactions=True):
    verified = [price, liquidity, volume, transactions]
    count = sum(1 for value in verified if value)
    return {
        "contract_version": "x1_current_market_freshness/v2",
        "scope": "instant_x1_scan.current_market",
        "freshness_state": (
            "VERIFIED" if count == 4 else ("PARTIAL" if count else "NOT_VERIFIED")
        ),
        "current_market_freshness_verified": count == 4,
        "verified_field_count": count,
        "total_field_count": 4,
        "fields": {
            "price_usd": {
                "freshness_verified": price,
                "reason": "timestamped_provider_price_matches_current_market_price",
            },
            "liquidity_usd": {
                "freshness_verified": liquidity,
                "reason": "aggregate_liquidity_reproduced_from_fresh_chain_state",
            },
            "volume_24h_usd": {
                "freshness_verified": volume,
                "reason": "exact_24h_chain_window_volume_matches_provider",
            },
            "transactions_24h": {
                "freshness_verified": transactions,
                "reason": "exact_24h_chain_window_transaction_count_matches_provider",
            },
        },
        "provider_price_fact_time_verified": price,
        "liquidity_freshness_evidence": {},
        "rolling_activity_evidence": {
            "contract_version": "x1_rolling_24h_market_activity/v1",
            "volume_24h_freshness_verified": volume,
            "transactions_24h_freshness_verified": transactions,
            "provider_fact_time_verified": False,
            "source_independence_verified": False,
            "execution_authorized": False,
        },
        "limitations": [
            "collection_time_is_not_provider_fact_time",
            "source_independence_separate_from_freshness",
        ],
        "execution_authorized": False,
    }


def test_v4_preserves_v3_non_freshness_sections_and_authority():
    args = fixtures()
    v3 = build_instant_x1_scan_v3_response(*args)
    v4 = build_instant_x1_scan_v4_response(
        *args,
        freshness_assessment=_freshness_v2(),
    )

    assert CONTRACT_VERSION == "instant_x1_scan/v4"
    assert FRESHNESS_CONTRACT_VERSION == "x1_current_market_freshness/v2"
    assert v4["data"]["contract_version"] == CONTRACT_VERSION
    for section in ("identity", "tokenomics", "history", "risk", "holder_concentration"):
        assert v4["data"]["sections"][section] == v3["data"]["sections"][section]
    assert v4["data"]["execution_authorized"] is False


def test_v4_projects_verified_v2_rolling_fields_without_fact_time_promotion():
    v4 = build_instant_x1_scan_v4_response(
        *fixtures(),
        freshness_assessment=_freshness_v2(),
    )
    market = v4["data"]["sections"]["market"]

    assert market["price_freshness_verified"] is True
    assert market["liquidity_freshness_verified"] is True
    assert market["volume_24h_freshness_verified"] is True
    assert market["transactions_24h_freshness_verified"] is True
    assert (
        market["freshness"]["rolling_activity_evidence"]["provider_fact_time_verified"]
        is False
    )
    assert (
        market["freshness"]["rolling_activity_evidence"]["source_independence_verified"]
        is False
    )
    assert "provider_fact_time_not_promoted_by_chain_reconstruction" in v4["data"]["limitations"]
    assert "source_independence_separate_from_freshness" in v4["data"]["limitations"]


def test_v4_without_v2_assessment_fails_closed():
    v4 = build_instant_x1_scan_v4_response(*fixtures())
    market = v4["data"]["sections"]["market"]

    assert market["freshness"]["contract_version"] == FRESHNESS_CONTRACT_VERSION
    assert market["freshness"]["freshness_state"] == "NOT_VERIFIED"
    assert market["price_freshness_verified"] is False
    assert market["liquidity_freshness_verified"] is False
    assert market["volume_24h_freshness_verified"] is False
    assert market["transactions_24h_freshness_verified"] is False


def test_v4_rejects_v1_or_execution_authorizing_freshness():
    v1 = _freshness_v2()
    v1["contract_version"] = "x1_current_market_freshness/v1"
    with pytest.raises(ValueError, match="requires x1_current_market_freshness/v2"):
        build_instant_x1_scan_v4_response(*fixtures(), freshness_assessment=v1)

    unsafe = _freshness_v2()
    unsafe["execution_authorized"] = True
    with pytest.raises(ValueError, match="may not authorize execution"):
        build_instant_x1_scan_v4_response(*fixtures(), freshness_assessment=unsafe)
