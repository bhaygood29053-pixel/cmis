import pytest

from liquidity_scout.providers.x1.xdex_history_current_end import (
    FRESHNESS_BOUND_SECONDS,
    evaluate_xdex_history_current_end,
)


BASE = "BASE"
QUOTE = "QUOTE"


def bar(ts, close="1"):
    return {"t": ts, "c": close}


def evaluate(rows, *, start=60, end=120, now=239, base=BASE, quote=QUOTE):
    return evaluate_xdex_history_current_end(
        base_mint=base,
        quote_mint=quote,
        requested_time_from=start,
        requested_closed_bar_start=end,
        provider_rows=rows,
        evaluation_time=now,
    )


def test_complete_tail_within_120_second_bound_verifies_current_end_only():
    result = evaluate([bar(60), bar(120)])

    assert result["freshness_bound_seconds"] == FRESHNESS_BOUND_SECONDS == 120
    assert result["age_seconds"] == 119
    assert result["exact_pair_identity_bound"] is True
    assert result["tail_continuity_verified"] is True
    assert result["latest_expected_closed_bar_verified"] is True
    assert result["freshness_verified"] is True
    assert result["current_end_coverage_verified"] is True
    assert result["provider_range_complete_verified"] is False
    assert result["continuous_coverage_verified"] is False
    assert result["full_asset_lifetime_verified"] is False


def test_exact_120_second_boundary_is_accepted():
    result = evaluate([bar(60), bar(120)], now=240)
    assert result["age_seconds"] == 120
    assert result["current_end_coverage_verified"] is True


def test_age_over_120_seconds_fails_closed():
    result = evaluate([bar(60), bar(120)], now=241)
    assert result["freshness_verified"] is False
    assert result["current_end_coverage_verified"] is False


def test_missing_tail_timestamp_fails_closed():
    result = evaluate([bar(60)], end=120, now=180)
    assert result["missing_timestamp_count"] == 1
    assert result["tail_continuity_verified"] is False
    assert result["current_end_coverage_verified"] is False


def test_out_of_scope_timestamp_fails_closed():
    result = evaluate([bar(0), bar(60), bar(120)], start=60, end=120, now=180)
    assert result["unexpected_timestamp_count"] == 1
    assert result["rows_within_closed_scope"] is False
    assert result["current_end_coverage_verified"] is False


def test_conflicting_duplicate_fails_closed():
    result = evaluate([bar(60), bar(120, "1"), bar(120, "2")], now=180)
    assert result["conflicting_duplicate_timestamp_count"] == 1
    assert result["current_end_coverage_verified"] is False


def test_pair_identity_is_required():
    result = evaluate([bar(60), bar(120)], base="", now=180)
    assert result["exact_pair_identity_bound"] is False
    assert result["current_end_coverage_verified"] is False


def test_non_list_provider_rows_fail_closed():
    result = evaluate(None, now=180)
    assert result["provider_rows_valid"] is False
    assert result["current_end_coverage_verified"] is False


def test_unaligned_requested_bounds_are_rejected():
    with pytest.raises(ValueError):
        evaluate_xdex_history_current_end(
            base_mint=BASE,
            quote_mint=QUOTE,
            requested_time_from=61,
            requested_closed_bar_start=120,
            provider_rows=[bar(120)],
            evaluation_time=180,
        )
