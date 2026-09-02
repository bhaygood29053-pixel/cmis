import struct

from liquidity_scout.providers.x1.xdex_pool_open_time_semantics import (
    OPEN_TIME_OFFSET,
    POOL_STATE_LEN,
    XDEX_PROGRAM_ID,
    evaluate_xdex_pool_open_time_semantics,
)


ASSET = "So11111111111111111111111111111111111111112"
QUOTE = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
OPEN_TIME = 1767392668
FIRST_BAR = 1767392640


def account_state(*, owner=XDEX_PROGRAM_ID, size=POOL_STATE_LEN, open_time=OPEN_TIME):
    data = bytearray(size)
    if size >= OPEN_TIME_OFFSET + 8:
        struct.pack_into("<Q", data, OPEN_TIME_OFFSET, open_time)
    if size >= OPEN_TIME_OFFSET + 16:
        struct.pack_into("<Q", data, OPEN_TIME_OFFSET + 8, 363)
    return {
        "response_integrity_verified": True,
        "owner": owner,
        "space": size,
        "data": bytes(data),
    }


def structural_report(*, mint_0=ASSET, mint_1=QUOTE, verified=True):
    return {
        "summary": {
            "pool_state_structural_role_verified": verified,
        },
        "decoded_state": {
            "mint_0": mint_0,
            "mint_1": mint_1,
        },
    }


def provider_first_bar(first=FIRST_BAR):
    return {"first_observed_at": first}


def test_exact_live_shape_promotes_bounded_open_time_semantics_and_anchor():
    result = evaluate_xdex_pool_open_time_semantics(
        account_state(),
        structural_report(),
        provider_first_bar(),
        asset_mint=ASSET,
        quote_mint=QUOTE,
    )

    assert result["open_time"] == OPEN_TIME
    assert result["open_time_semantics_verified"] is True
    assert result["provider_first_bar_covers_swap_open"] is True
    assert result["lifetime_start_anchor_verified"] is True
    assert result["lifetime_start_anchor"] == {
        "kind": "first_verified_supported_market_interval",
        "verified": True,
        "observed_at": FIRST_BAR,
        "interval_seconds": 60,
        "market_open_at": OPEN_TIME,
        "open_time_semantics_verified": True,
    }
    assert result["full_asset_lifetime_verified"] is False
    assert result["continuous_coverage_verified"] is False


def test_wrong_program_fails_closed():
    result = evaluate_xdex_pool_open_time_semantics(
        account_state(owner="wrong"),
        structural_report(),
        provider_first_bar(),
        asset_mint=ASSET,
        quote_mint=QUOTE,
    )
    assert result["program_identity_verified"] is False
    assert result["open_time_semantics_verified"] is False
    assert result["lifetime_start_anchor_verified"] is False


def test_wrong_pool_state_size_fails_closed():
    result = evaluate_xdex_pool_open_time_semantics(
        account_state(size=500),
        structural_report(),
        provider_first_bar(),
        asset_mint=ASSET,
        quote_mint=QUOTE,
    )
    assert result["pool_state_length_verified"] is False
    assert result["open_time_semantics_verified"] is False


def test_wrong_pair_identity_fails_closed():
    result = evaluate_xdex_pool_open_time_semantics(
        account_state(),
        structural_report(mint_1="OTHER"),
        provider_first_bar(),
        asset_mint=ASSET,
        quote_mint=QUOTE,
    )
    assert result["exact_pair_identity_verified"] is False
    assert result["open_time_semantics_verified"] is False


def test_open_time_semantics_can_verify_without_first_bar_anchor():
    result = evaluate_xdex_pool_open_time_semantics(
        account_state(),
        structural_report(),
        provider_first_bar(FIRST_BAR - 60),
        asset_mint=ASSET,
        quote_mint=QUOTE,
    )
    assert result["open_time_semantics_verified"] is True
    assert result["provider_first_bar_covers_swap_open"] is False
    assert result["lifetime_start_anchor_verified"] is False


def test_implausible_open_time_fails_semantic_promotion():
    result = evaluate_xdex_pool_open_time_semantics(
        account_state(open_time=363),
        structural_report(),
        provider_first_bar(),
        asset_mint=ASSET,
        quote_mint=QUOTE,
    )
    assert result["open_time_semantics_verified"] is False
    assert result["lifetime_start_anchor_verified"] is False
