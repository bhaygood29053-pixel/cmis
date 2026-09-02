from copy import deepcopy

from liquidity_scout.providers.x1.xdex_supported_lifetime_range import (
    evaluate_xdex_supported_lifetime_range,
)


BASE = "BASE"
QUOTE = "QUOTE"
START = 120
INTERVAL = 60
FORWARD_END = 600


def archive():
    return {
        "base_mint": BASE,
        "quote_mint": QUOTE,
        "archive_start_exhaustion_verified": True,
        "archive_exhaustion_verified": True,
        "first_provider_observation": START,
        "lifetime_start_anchor": {
            "kind": "first_verified_supported_market_interval",
            "verified": True,
            "observed_at": START,
            "interval_seconds": INTERVAL,
        },
    }


def continuity():
    expected = ((FORWARD_END - START) // INTERVAL) + 1
    return {
        "base_mint": BASE,
        "quote_mint": QUOTE,
        "time_from": START,
        "time_to": FORWARD_END,
        "interval_seconds": INTERVAL,
        "expected_timestamp_count": expected,
        "total_unique_timestamp_count": expected,
        "missing_timestamp_count": 0,
        "unexpected_timestamp_count": 0,
        "conflicting_duplicate_timestamp_count": 0,
        "observed_gap_count": 0,
        "largest_observed_gap_seconds": 0,
        "scan_end_reached": True,
        "all_windows_verified": True,
        "bounded_continuity_verified": True,
    }


def current_end():
    return {
        "base_mint": BASE,
        "quote_mint": QUOTE,
        "exact_pair_identity_bound": True,
        "requested_time_from": FORWARD_END - 60,
        "provider_latest_observed_at": FORWARD_END + 300,
        "interval_seconds": INTERVAL,
        "tail_continuity_verified": True,
        "latest_expected_closed_bar_verified": True,
        "canonical_fact_timestamp_verified": True,
        "freshness_verified": True,
        "current_end_coverage_verified": True,
    }


def evaluate(a=None, c=None, e=None):
    return evaluate_xdex_supported_lifetime_range(
        archive_start=a or archive(),
        continuity=c or continuity(),
        current_end=e or current_end(),
    )


def test_exact_supported_lifetime_range_promotes_range_only():
    result = evaluate()
    assert result["supported_lifetime_range_complete_verified"] is True
    assert result["provider_range_complete_verified"] is True
    assert result["archive_exhaustion_verified"] is True
    assert result["price_bar_continuity_verified"] is True
    assert result["global_provider_archive_complete_verified"] is False
    assert result["continuous_coverage_verified"] is False
    assert result["historical_quote_usd_equivalence_verified"] is False
    assert result["full_asset_lifetime_verified"] is False


def test_pair_mismatch_fails_closed():
    end = current_end()
    end["quote_mint"] = "OTHER"
    result = evaluate(e=end)
    assert result["gates"]["exact_pair_identity_verified"] is False
    assert result["provider_range_complete_verified"] is False


def test_archive_start_must_be_verified():
    start = archive()
    start["archive_start_exhaustion_verified"] = False
    result = evaluate(a=start)
    assert result["gates"]["archive_start_verified"] is False
    assert result["provider_range_complete_verified"] is False


def test_forward_scan_must_start_at_anchor():
    forward = continuity()
    forward["time_from"] = START + INTERVAL
    result = evaluate(c=forward)
    assert result["gates"]["forward_continuity_verified"] is False
    assert result["provider_range_complete_verified"] is False


def test_forward_counts_must_match_exactly():
    forward = continuity()
    forward["total_unique_timestamp_count"] -= 1
    result = evaluate(c=forward)
    assert result["gates"]["forward_continuity_verified"] is False
    assert result["provider_range_complete_verified"] is False


def test_forward_gap_fails_closed():
    forward = continuity()
    forward["observed_gap_count"] = 1
    forward["largest_observed_gap_seconds"] = 60
    result = evaluate(c=forward)
    assert result["gates"]["forward_continuity_verified"] is False
    assert result["provider_range_complete_verified"] is False


def test_current_end_must_be_fresh_and_complete():
    end = current_end()
    end["freshness_verified"] = False
    end["current_end_coverage_verified"] = False
    result = evaluate(e=end)
    assert result["gates"]["current_end_verified"] is False
    assert result["provider_range_complete_verified"] is False


def test_seam_gap_fails_closed():
    end = current_end()
    end["requested_time_from"] = FORWARD_END + 2 * INTERVAL
    result = evaluate(e=end)
    assert result["gates"]["forward_to_current_seam_verified"] is False
    assert result["provider_range_complete_verified"] is False


def test_interval_mismatch_fails_closed():
    end = current_end()
    end["interval_seconds"] = 300
    result = evaluate(e=end)
    assert result["gates"]["current_end_verified"] is False
    assert result["provider_range_complete_verified"] is False
