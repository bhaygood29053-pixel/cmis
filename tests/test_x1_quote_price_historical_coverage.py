from liquidity_scout.services.x1_quote_price_historical_coverage import (
    evaluate_x1_quote_price_historical_coverage,
)


BASE = "BASE"
QUOTE = "QUOTE"


def lifetime():
    return {
        "base_mint": BASE,
        "quote_mint": QUOTE,
        "supported_lifetime_range_complete_verified": True,
        "provider_range_complete_verified": True,
        "archive_exhaustion_verified": True,
        "price_bar_continuity_verified": True,
        "global_provider_archive_complete_verified": False,
    }


def test_pair_lifetime_can_verify_while_usd_lifetime_stays_partial():
    result = evaluate_x1_quote_price_historical_coverage(
        supported_lifetime_range=lifetime(),
        exact_pair_quote_identity_verified=True,
        canonical_fact_timestamps_verified=True,
        historical_quote_usd_equivalence_verified=False,
    )

    assert result["pair_lifetime_status"] == "verified"
    assert result["full_supported_pair_lifetime_verified"] is True
    assert result["continuous_pair_price_coverage_verified"] is True
    assert result["provider_range_complete_verified"] is True

    assert result["usd_lifetime_status"] == "partial"
    assert result["historical_quote_usd_equivalence_verified"] is False
    assert result["full_usd_lifetime_verified"] is False
    assert result["full_asset_lifetime_verified"] is False
    assert result["continuous_coverage_verified"] is False
    assert result["missing_pair_gates"] == []
    assert result["missing_usd_gates"] == [
        "historical_quote_usd_equivalence"
    ]


def test_usd_lifetime_promotes_only_with_quote_usd_equivalence():
    result = evaluate_x1_quote_price_historical_coverage(
        supported_lifetime_range=lifetime(),
        exact_pair_quote_identity_verified=True,
        canonical_fact_timestamps_verified=True,
        historical_quote_usd_equivalence_verified=True,
    )

    assert result["full_supported_pair_lifetime_verified"] is True
    assert result["full_usd_lifetime_verified"] is True
    assert result["full_asset_lifetime_verified"] is True
    assert result["continuous_coverage_verified"] is True
    assert result["missing_usd_gates"] == []


def test_range_failure_blocks_both_claims():
    candidate = lifetime()
    candidate["provider_range_complete_verified"] = False

    result = evaluate_x1_quote_price_historical_coverage(
        supported_lifetime_range=candidate,
        exact_pair_quote_identity_verified=True,
        canonical_fact_timestamps_verified=True,
    )

    assert result["full_supported_pair_lifetime_verified"] is False
    assert result["full_usd_lifetime_verified"] is False
    assert "supported_pair_lifetime_range" in result["missing_pair_gates"]


def test_identity_failure_blocks_pair_lifetime():
    result = evaluate_x1_quote_price_historical_coverage(
        supported_lifetime_range=lifetime(),
        exact_pair_quote_identity_verified=False,
        canonical_fact_timestamps_verified=True,
    )

    assert result["full_supported_pair_lifetime_verified"] is False
    assert "exact_pair_quote_identity" in result["missing_pair_gates"]


def test_timestamp_failure_blocks_pair_lifetime():
    result = evaluate_x1_quote_price_historical_coverage(
        supported_lifetime_range=lifetime(),
        exact_pair_quote_identity_verified=True,
        canonical_fact_timestamps_verified=False,
    )

    assert result["full_supported_pair_lifetime_verified"] is False
    assert "canonical_fact_timestamps" in result["missing_pair_gates"]


def test_global_archive_claim_is_not_required_or_promoted():
    result = evaluate_x1_quote_price_historical_coverage(
        supported_lifetime_range=lifetime(),
        exact_pair_quote_identity_verified=True,
        canonical_fact_timestamps_verified=True,
    )
    assert result["full_supported_pair_lifetime_verified"] is True
    assert "global_provider_archive_completeness_not_claimed" in result["limitations"]
