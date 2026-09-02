from liquidity_scout.services.x1_price_historical_coverage import (
    POLICY_ID,
    evaluate_x1_price_historical_coverage,
)


def complete_proof():
    return {
        "lifetime_start_anchor": {
            "kind": "first_verified_supported_market_observation",
            "verified": True,
            "observed_at": 100,
        },
        "archive": {
            "provider_range_complete_verified": True,
            "archive_exhaustion_verified": True,
        },
        "identity": {
            "exact_pair_quote_identity_verified": True,
        },
        "timestamps": {
            "canonical_fact_timestamps_verified": True,
        },
        "cadence": {
            "policy_verified": True,
            "expected_interval_seconds": 60,
            "maximum_allowed_gap_seconds": 60,
            "observed_gap_count": 0,
            "largest_observed_gap_seconds": 60,
            "bounded_continuity_verified": True,
        },
        "current_end": {
            "verified": True,
            "observed_at": 220,
            "age_seconds": 10,
            "freshness_bound_seconds": 60,
        },
        "quote": {
            "historical_quote_usd_equivalence_verified": True,
        },
    }


def test_complete_explicit_proof_promotes_price_lifetime_and_continuity():
    result = evaluate_x1_price_historical_coverage(
        complete_proof(),
        metric_profile={
            "first_observed_at": 100,
            "last_observed_at": 220,
        },
    )

    assert result["policy_id"] == POLICY_ID
    assert result["status"] == "verified"
    assert result["promotion_eligible"] is True
    assert result["asset_lifetime_start_verified"] is True
    assert result["full_asset_lifetime_verified"] is True
    assert result["continuous_coverage_verified"] is True
    assert result["missing_gates"] == []


def test_gap_free_sample_without_archive_proof_does_not_promote():
    proof = complete_proof()
    proof["archive"]["provider_range_complete_verified"] = False
    proof["archive"]["archive_exhaustion_verified"] = False

    result = evaluate_x1_price_historical_coverage(
        proof,
        metric_profile={
            "first_observed_at": 100,
            "last_observed_at": 220,
        },
    )

    assert result["promotion_eligible"] is False
    assert result["full_asset_lifetime_verified"] is False
    assert result["continuous_coverage_verified"] is False
    assert "provider_range_complete_verified" in result["missing_gates"]
    assert "archive_exhaustion_verified" in result["missing_gates"]


def test_anchor_must_bind_to_exposed_first_observation():
    proof = complete_proof()

    result = evaluate_x1_price_historical_coverage(
        proof,
        metric_profile={
            "first_observed_at": 160,
            "last_observed_at": 220,
        },
    )

    assert result["asset_lifetime_start_verified"] is False
    assert result["full_asset_lifetime_verified"] is False
    assert "lifetime_start_anchor_verified" in result["missing_gates"]


def test_stale_current_end_fails_closed():
    proof = complete_proof()
    proof["current_end"]["age_seconds"] = 61

    result = evaluate_x1_price_historical_coverage(
        proof,
        metric_profile={
            "first_observed_at": 100,
            "last_observed_at": 220,
        },
    )

    assert result["full_asset_lifetime_verified"] is False
    assert result["continuous_coverage_verified"] is False
    assert "current_end_coverage_verified" in result["missing_gates"]


def test_unproven_historical_quote_usd_equivalence_blocks_usd_price_lifetime():
    proof = complete_proof()
    proof["quote"]["historical_quote_usd_equivalence_verified"] = False

    result = evaluate_x1_price_historical_coverage(
        proof,
        metric_profile={
            "first_observed_at": 100,
            "last_observed_at": 220,
        },
    )

    assert result["full_asset_lifetime_verified"] is False
    assert "historical_quote_usd_equivalence_verified" in result["missing_gates"]
