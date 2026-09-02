import pytest

from liquidity_scout.providers.x1.xdex_price_history_range import (
    SCHEMA,
    discover_xdex_price_history_range,
)


BASE = "BASE"
QUOTE = "QUOTE"


def bar(ts, close=1.0):
    return {"t": ts, "c": close}


def complete_fetcher(_base, _quote, *, time_from, time_to):
    rows = {
        (300, 400): [bar(300), bar(360)],
        (200, 300): [bar(240), bar(300)],
        (100, 200): [],
    }
    return rows[(time_from, time_to)]


def test_full_sweep_does_not_promote_without_range_semantics_proof():
    result = discover_xdex_price_history_range(
        BASE,
        QUOTE,
        search_floor=100,
        search_end=400,
        window_seconds=100,
        fetcher=complete_fetcher,
        provider_range_semantics_verified=False,
        search_floor_precedes_supported_market_lifetime_verified=True,
    )

    assert result["schema"] == SCHEMA
    assert result["search_floor_reached"] is True
    assert result["range_sweep_complete"] is True
    assert result["earliest_provider_observation_candidate"] == 240
    assert result["provider_range_complete_verified"] is False
    assert result["archive_exhaustion_verified"] is False
    assert (
        "xdex_requested_range_exhaustiveness_semantics_not_verified"
        in result["limitations"]
    )


def test_verified_range_semantics_and_verified_floor_allow_archive_promotion():
    result = discover_xdex_price_history_range(
        BASE,
        QUOTE,
        search_floor=100,
        search_end=400,
        window_seconds=100,
        fetcher=complete_fetcher,
        provider_range_semantics_verified=True,
        search_floor_precedes_supported_market_lifetime_verified=True,
    )

    assert result["status"] == "verified"
    assert result["provider_range_complete_verified"] is True
    assert result["archive_exhaustion_verified"] is True
    assert result["discovered_unique_timestamp_count"] == 3
    assert result["empty_window_count"] == 1


def test_verified_route_semantics_are_insufficient_without_verified_lower_bound():
    result = discover_xdex_price_history_range(
        BASE,
        QUOTE,
        search_floor=100,
        search_end=400,
        window_seconds=100,
        fetcher=complete_fetcher,
        provider_range_semantics_verified=True,
        search_floor_precedes_supported_market_lifetime_verified=False,
    )

    assert result["range_sweep_complete"] is True
    assert result["provider_range_complete_verified"] is False
    assert (
        "search_floor_pre_market_lower_bound_not_verified"
        in result["limitations"]
    )


def test_provider_row_outside_requested_window_fails_closed():
    def bad_fetcher(_base, _quote, *, time_from, time_to):
        return [bar(time_from - 1)]

    result = discover_xdex_price_history_range(
        BASE,
        QUOTE,
        search_floor=100,
        search_end=400,
        window_seconds=100,
        fetcher=bad_fetcher,
        provider_range_semantics_verified=True,
        search_floor_precedes_supported_market_lifetime_verified=True,
    )

    assert result["range_sweep_complete"] is False
    assert result["provider_range_complete_verified"] is False
    assert (
        result["failure_reason"]
        == "provider_rows_outside_or_conflicting_requested_range"
    )


def test_max_window_bound_prevents_false_exhaustion():
    result = discover_xdex_price_history_range(
        BASE,
        QUOTE,
        search_floor=100,
        search_end=400,
        window_seconds=100,
        max_windows=2,
        fetcher=complete_fetcher,
        provider_range_semantics_verified=True,
        search_floor_precedes_supported_market_lifetime_verified=True,
    )

    assert result["search_floor_reached"] is False
    assert result["range_sweep_complete"] is False
    assert result["provider_range_complete_verified"] is False
    assert "search_floor_not_reached" in result["limitations"]


def test_invalid_bounds_are_rejected():
    with pytest.raises(ValueError):
        discover_xdex_price_history_range(
            BASE,
            QUOTE,
            search_floor=400,
            search_end=100,
            window_seconds=100,
        )
