import pytest

from liquidity_scout.providers.x1.xdex_history_current_end import (
    FRESHNESS_BOUND_SECONDS,
    evaluate_xdex_history_current_end,
)


def bar(ts, close="1"):
    return {"t": ts, "c": close}


def test_latest_closed_bar_within_120_second_bound_verifies_current_end_only():
    result = evaluate_xdex_history_current_end(
        requested_closed_bar_start=120,
        provider_rows=[bar(60), bar(120)],
        evaluation_time=239,
    )

    assert result["freshness_bound_seconds"] == FRESHNESS_BOUND_SECONDS == 120
    assert result["age_seconds"] == 119
    assert result["latest_expected_closed_bar_verified"] is True
    assert result["freshness_verified"] is True
    assert result["current_end_coverage_verified"] is True
    assert result["provider_range_complete_verified"] is False
    assert result["continuous_coverage_verified"] is False
    assert result["full_asset_lifetime_verified"] is False


def test_exact_120_second_boundary_is_accepted():
    result = evaluate_xdex_history_current_end(
        requested_closed_bar_start=120,
        provider_rows=[bar(120)],
        evaluation_time=240,
    )
    assert result["age_seconds"] == 120
    assert result["current_end_coverage_verified"] is True


def test_age_over_120_seconds_fails_closed():
    result = evaluate_xdex_history_current_end(
        requested_closed_bar_start=120,
        provider_rows=[bar(120)],
        evaluation_time=241,
    )
    assert result["age_seconds"] == 121
    assert result["freshness_verified"] is False
    assert result["current_end_coverage_verified"] is False


def test_provider_must_reach_exact_requested_closed_bar():
    result = evaluate_xdex_history_current_end(
        requested_closed_bar_start=180,
        provider_rows=[bar(60), bar(120)],
        evaluation_time=200,
    )
    assert result["latest_expected_closed_bar_verified"] is False
    assert result["current_end_coverage_verified"] is False


def test_future_provider_timestamp_is_rejected_by_scope():
    result = evaluate_xdex_history_current_end(
        requested_closed_bar_start=120,
        provider_rows=[bar(120), bar(180)],
        evaluation_time=181,
    )
    assert result["rows_within_closed_scope"] is False
    assert result["current_end_coverage_verified"] is False


def test_conflicting_duplicate_fails_closed():
    result = evaluate_xdex_history_current_end(
        requested_closed_bar_start=120,
        provider_rows=[bar(120, "1"), bar(120, "2")],
        evaluation_time=180,
    )
    assert result["conflicting_duplicate_timestamp_count"] == 1
    assert result["current_end_coverage_verified"] is False


def test_non_list_provider_rows_fail_closed():
    result = evaluate_xdex_history_current_end(
        requested_closed_bar_start=120,
        provider_rows=None,
        evaluation_time=180,
    )
    assert result["provider_rows_valid"] is False
    assert result["current_end_coverage_verified"] is False


def test_unaligned_requested_bar_is_rejected():
    with pytest.raises(ValueError):
        evaluate_xdex_history_current_end(
            requested_closed_bar_start=121,
            provider_rows=[bar(120)],
            evaluation_time=180,
        )
