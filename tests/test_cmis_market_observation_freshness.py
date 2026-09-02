from liquidity_scout.providers.x1.market import DEFAULT_REFRESH_SECONDS
from liquidity_scout.services.cmis_market_freshness import (
    MAX_AGE_SECONDS,
    evaluate_market_observation_freshness,
)


def test_fresh_observation_passes():
    result = evaluate_market_observation_freshness(1000, evaluated_at=1010)

    assert result["classification"] == "fresh"
    assert result["age_seconds"] == 10
    assert result["observation_freshness_verified"] is True
    assert result["provider_fact_time_verified"] is False


def test_stale_observation_fails():
    result = evaluate_market_observation_freshness(
        1000,
        evaluated_at=1000 + MAX_AGE_SECONDS + 1,
    )

    assert result["classification"] == "stale"
    assert result["observation_freshness_verified"] is False


def test_future_observation_fails_closed():
    result = evaluate_market_observation_freshness(1010, evaluated_at=1000)

    assert result["classification"] == "future"
    assert result["observation_freshness_verified"] is False


def test_x1_catalog_refresh_policy_alignment():
    assert DEFAULT_REFRESH_SECONDS == 50
    assert MAX_AGE_SECONDS == 60
    assert MAX_AGE_SECONDS - DEFAULT_REFRESH_SECONDS == 10
