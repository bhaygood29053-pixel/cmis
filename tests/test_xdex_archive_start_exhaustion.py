from liquidity_scout.providers.x1.xdex_archive_start_exhaustion import (
    SCHEMA,
    evaluate_xdex_archive_start_exhaustion,
)


BASE = "BASE"
QUOTE = "QUOTE"
ANCHOR_START = 1000
INTERVAL = 60
OPEN_TIME = 1028


def anchor(**overrides):
    value = {
        "kind": "first_verified_supported_market_interval",
        "verified": True,
        "observed_at": ANCHOR_START,
        "interval_seconds": INTERVAL,
        "market_open_at": OPEN_TIME,
        "open_time_semantics_verified": True,
    }
    value.update(overrides)
    return value


def bar(ts, close=1.0):
    return {"t": ts, "c": close}


def evidence_windows():
    pre = {
        "time_from": 700,
        "time_to": 999,
        "rows": [],
    }
    post_rows = [bar(1000), bar(1060), bar(1120)]
    post = {
        "time_from": 1000,
        "time_to": 1200,
        "rows": post_rows,
    }
    crossing = {
        "time_from": 700,
        "time_to": 1200,
        "rows": list(post_rows),
    }
    repeat = {
        "time_from": 700,
        "time_to": 1200,
        "rows": list(post_rows),
    }
    return pre, crossing, post, repeat


def evaluate(*, anchor_value=None, pre=None, crossing=None, post=None, repeat=None):
    d_pre, d_crossing, d_post, d_repeat = evidence_windows()
    return evaluate_xdex_archive_start_exhaustion(
        anchor() if anchor_value is None else anchor_value,
        base_mint=BASE,
        quote_mint=QUOTE,
        pre_window=d_pre if pre is None else pre,
        crossing_window=d_crossing if crossing is None else crossing,
        post_window=d_post if post is None else post,
        repeat_crossing_window=d_repeat if repeat is None else repeat,
    )


def test_exact_boundary_proof_promotes_archive_start_only():
    result = evaluate()

    assert result["schema"] == SCHEMA
    assert result["archive_start_exhaustion_verified"] is True
    assert result["archive_exhaustion_verified"] is True
    assert result["provider_range_complete_verified"] is False
    assert result["continuous_coverage_verified"] is False
    assert result["full_asset_lifetime_verified"] is False
    assert all(result["gates"].values())


def test_unverified_lifetime_anchor_fails_closed():
    result = evaluate(anchor_value=anchor(verified=False))

    assert result["gates"]["lifetime_start_anchor_verified"] is False
    assert result["archive_exhaustion_verified"] is False


def test_pre_anchor_row_fails_closed():
    pre, crossing, post, repeat = evidence_windows()
    pre["rows"] = [bar(940)]
    crossing["rows"] = [bar(940), *crossing["rows"]]
    repeat["rows"] = list(crossing["rows"])

    result = evaluate(pre=pre, crossing=crossing, post=post, repeat=repeat)

    assert result["gates"]["pre_anchor_empty_verified"] is False
    assert result["archive_exhaustion_verified"] is False


def test_split_partition_mismatch_fails_closed():
    pre, crossing, post, repeat = evidence_windows()
    crossing["rows"] = [bar(1000), bar(1060)]

    result = evaluate(pre=pre, crossing=crossing, post=post, repeat=repeat)

    assert result["gates"]["split_partition_exact_verified"] is False
    assert result["archive_exhaustion_verified"] is False


def test_repeat_instability_fails_closed():
    pre, crossing, post, repeat = evidence_windows()
    repeat["rows"] = [bar(1000), bar(1060), bar(1120, close=2.0)]

    result = evaluate(pre=pre, crossing=crossing, post=post, repeat=repeat)

    assert result["gates"]["repeated_request_stable_verified"] is False
    assert result["archive_exhaustion_verified"] is False


def test_wrong_first_boundary_row_fails_closed():
    pre, crossing, post, repeat = evidence_windows()
    post["rows"] = [bar(1060), bar(1120)]
    crossing["rows"] = list(post["rows"])
    repeat["rows"] = list(post["rows"])

    result = evaluate(pre=pre, crossing=crossing, post=post, repeat=repeat)

    assert result["gates"]["first_boundary_row_verified"] is False
    assert result["archive_exhaustion_verified"] is False


def test_first_interval_gap_fails_closed_without_claiming_continuity():
    pre, crossing, post, repeat = evidence_windows()
    post["rows"] = [bar(1000), bar(1120), bar(1180)]
    crossing["rows"] = list(post["rows"])
    repeat["rows"] = list(post["rows"])

    result = evaluate(pre=pre, crossing=crossing, post=post, repeat=repeat)

    assert result["gates"]["first_two_intervals_verified"] is False
    assert result["archive_exhaustion_verified"] is False
    assert result["continuous_coverage_verified"] is False


def test_out_of_scope_row_fails_closed():
    pre, crossing, post, repeat = evidence_windows()
    post["rows"] = [bar(999), bar(1000), bar(1060)]
    crossing["rows"] = [bar(1000), bar(1060)]
    repeat["rows"] = [bar(1000), bar(1060)]

    result = evaluate(pre=pre, crossing=crossing, post=post, repeat=repeat)

    assert result["gates"]["all_window_scopes_verified"] is False
    assert result["archive_exhaustion_verified"] is False
