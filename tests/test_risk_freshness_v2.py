from liquidity_scout.services.risk import (
    CURRENT_MARKET_FRESHNESS_V2_CONTRACT,
    build_risk_check,
)


def _market():
    return {
        "symbol": "TST",
        "mint": "Mint",
        "liquidity_usd": 500,
        "volume_24h_usd": 20,
        "transactions_24h": 4,
        "completeness": {
            "liquidity": True,
            "volume_24h": True,
            "transactions_24h": True,
        },
    }


def _freshness():
    return {
        "contract_version": CURRENT_MARKET_FRESHNESS_V2_CONTRACT,
        "freshness_state": "PARTIAL",
        "evaluated_at": 1000,
        "verified_field_count": 2,
        "total_field_count": 4,
        "current_market_freshness_verified": False,
        "fields": {
            "price_usd": {"freshness_verified": True, "reason": "ok"},
            "liquidity_usd": {"freshness_verified": True, "reason": "ok"},
            "volume_24h_usd": {"freshness_verified": False, "reason": "pending"},
            "transactions_24h": {"freshness_verified": False, "reason": "pending"},
        },
    }


def test_risk_accepts_v2_and_preserves_field_scoped_warning():
    result = build_risk_check(_market(), freshness_report=_freshness())
    freshness = result["components"]["freshness"]
    assert freshness["evidence"]["contract_version"] == CURRENT_MARKET_FRESHNESS_V2_CONTRACT
    assert "price_freshness_unverified" not in freshness["flags"]
    assert "liquidity_freshness_unverified" not in freshness["flags"]
    assert "volume_24h_freshness_unverified" in freshness["flags"]
    assert "transactions_24h_freshness_unverified" in freshness["flags"]


def test_risk_rejects_unknown_freshness_contract():
    bad = _freshness()
    bad["contract_version"] = "x1_current_market_freshness/v999"
    try:
        build_risk_check(_market(), freshness_report=bad)
    except ValueError as exc:
        assert "accepted X1 current-market freshness contract" in str(exc)
    else:
        raise AssertionError("unknown freshness contract must fail closed")
