import pytest

from liquidity_scout.providers.x1.xdex_forward_bar_continuity import (
    SCHEMA,
    scan_xdex_forward_bar_continuity,
)


BASE = "BASE"
QUOTE = "QUOTE"


def bar(ts, close=1.0):
    return {"t": ts, "c": close}


def complete_fetcher(_base, _quote, *, time_from, time_to):
    return [bar(ts) for ts in range(time_from, time_to + 60, 60)]


def test_complete_multiwindow_scan_promotes_bounded_continuity_only():
    result = scan_xdex_forward_bar_continuity(
        BASE,
        QUOTE,
        time_from=0,
        time_to=540,
        interval_seconds=60,
        window_intervals=4,
        fetcher=complete_fetcher,
    )

    assert result["schema"] == SCHEMA
    assert result["expected_timestamp_count"] == 10
    assert result["expected_window_count"] == 3
    assert result["requested_window_count"] == 3
    assert result["missing_timestamp_count"] == 0
    assert result["bounded_continuity_verified"] is True
    assert result["continuous_coverage_verified"] is False
    assert result["provider_range_complete_verified"] is False
    assert result["full_asset_lifetime_verified"] is False


def test_missing_timestamp_fails_closed_and_reports_gap():
    def fetcher(_base, _quote, *, time_from, time_to):
        rows = complete_fetcher(_base, _quote, time_from=time_from, time_to=time_to)
        return [row for row in rows if row["t"] != 120]

    result = scan_xdex_forward_bar_continuity(
        BASE,
        QUOTE,
        time_from=0,
        time_to=300,
        window_intervals=10,
        fetcher=fetcher,
    )

    assert result["bounded_continuity_verified"] is False
    assert result["missing_timestamp_count"] == 1
    assert result["missing_timestamp_sample"] == [120]
    assert result["observed_gap_count"] == 1
    assert result["largest_observed_gap_seconds"] == 60


def test_out_of_range_timestamp_fails_closed():
    def fetcher(_base, _quote, *, time_from, time_to):
        return [bar(time_from - 60), *complete_fetcher(
            _base, _quote, time_from=time_from, time_to=time_to
        )]

    result = scan_xdex_forward_bar_continuity(
        BASE,
        QUOTE,
        time_from=0,
        time_to=180,
        window_intervals=10,
        fetcher=fetcher,
    )

    assert result["bounded_continuity_verified"] is False
    assert result["unexpected_timestamp_count"] == 1


def test_off_grid_timestamp_fails_closed():
    def fetcher(_base, _quote, *, time_from, time_to):
        rows = complete_fetcher(_base, _quote, time_from=time_from, time_to=time_to)
        rows.append(bar(time_from + 1))
        return rows

    result = scan_xdex_forward_bar_continuity(
        BASE,
        QUOTE,
        time_from=0,
        time_to=180,
        window_intervals=10,
        fetcher=fetcher,
    )

    assert result["bounded_continuity_verified"] is False
    assert result["unexpected_timestamp_count"] == 1


def test_conflicting_duplicate_fails_closed():
    def fetcher(_base, _quote, *, time_from, time_to):
        rows = complete_fetcher(_base, _quote, time_from=time_from, time_to=time_to)
        rows.append(bar(time_from, close=2.0))
        return rows

    result = scan_xdex_forward_bar_continuity(
        BASE,
        QUOTE,
        time_from=0,
        time_to=180,
        window_intervals=10,
        fetcher=fetcher,
    )

    assert result["bounded_continuity_verified"] is False
    assert result["conflicting_duplicate_timestamp_count"] == 1


def test_identical_duplicate_does_not_change_unique_count_but_fails_expected_shape():
    def fetcher(_base, _quote, *, time_from, time_to):
        rows = complete_fetcher(_base, _quote, time_from=time_from, time_to=time_to)
        rows.append(dict(rows[0]))
        return rows

    result = scan_xdex_forward_bar_continuity(
        BASE,
        QUOTE,
        time_from=0,
        time_to=180,
        window_intervals=10,
        fetcher=fetcher,
    )

    assert result["duplicate_timestamp_count"] == 1
    assert result["total_unique_timestamp_count"] == 4
    # Identical duplicates do not invalidate continuity because every expected
    # timestamp is still uniquely represented and there is no conflict.
    assert result["bounded_continuity_verified"] is True


def test_max_window_bound_prevents_false_continuity():
    result = scan_xdex_forward_bar_continuity(
        BASE,
        QUOTE,
        time_from=0,
        time_to=540,
        window_intervals=2,
        max_windows=2,
        fetcher=complete_fetcher,
    )

    assert result["scan_end_reached"] is False
    assert result["bounded_continuity_verified"] is False
    assert "requested_end_not_reached" in result["limitations"]


def test_provider_failure_fails_closed():
    def fetcher(*_args, **_kwargs):
        raise RuntimeError("boom")

    result = scan_xdex_forward_bar_continuity(
        BASE,
        QUOTE,
        time_from=0,
        time_to=180,
        fetcher=fetcher,
    )

    assert result["bounded_continuity_verified"] is False
    assert result["failure_reason"].startswith("provider_request_failed:")


def test_unaligned_bounds_are_rejected():
    with pytest.raises(ValueError):
        scan_xdex_forward_bar_continuity(
            BASE,
            QUOTE,
            time_from=1,
            time_to=180,
            fetcher=complete_fetcher,
        )
