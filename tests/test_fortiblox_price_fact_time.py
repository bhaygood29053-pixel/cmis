from copy import deepcopy

import pytest

from liquidity_scout.providers.x1.fortiblox_price_fact_time import (
    CONTRACT_VERSION,
    DISPROVEN,
    EVIDENCE_INCOMPLETE,
    PROVEN,
    analyze_fortiblox_price_fact_time,
)

MINT_A = "Token111111111111111111111111111111111111111"
MINT_B = "Token222222222222222222222222222222222222222"


def snap(collected, updated, a=1.0, b=2.0):
    return {
        "collected_at_ms": collected,
        "provider_updated_at_ms": updated,
        "tokens": [
            {"mint": MINT_A, "price_usd": a},
            {"mint": MINT_B, "price_usd": b},
        ],
    }


def test_same_updated_at_with_price_change_disproves_price_fact_time_binding():
    result = analyze_fortiblox_price_fact_time(
        [
            snap(1_788_970_000_000, 1_788_969_999_000, a=1.0),
            snap(1_788_970_005_000, 1_788_969_999_000, a=1.1),
        ]
    )
    assert result["contract_version"] == CONTRACT_VERSION
    assert result["conclusion"] == DISPROVEN
    assert result["contradictions"][0]["changed_mints"] == [MINT_A]
    assert result["current_fact_corroboration_authorized"] is False
    assert result["execution_authorized"] is False


def test_coupled_changes_without_semantic_proof_remain_evidence_incomplete():
    result = analyze_fortiblox_price_fact_time(
        [
            snap(1_788_970_000_000, 1_788_969_999_000, a=1.0),
            snap(1_788_970_005_000, 1_788_970_004_000, a=1.1),
            snap(1_788_970_010_000, 1_788_970_009_000, a=1.2),
        ]
    )
    assert result["conclusion"] == EVIDENCE_INCOMPLETE
    assert result["price_change_pair_count"] == 2
    assert result["price_changes_coupled_to_updated_at_change_count"] == 2
    assert result["timestamp_unit_verified"] is False
    assert result["clock_semantics_verified"] is False
    assert result["source_independence_verified"] is False
    assert result["volume_freshness_verified"] is False


def test_explicit_field_semantics_plus_live_changes_can_reach_proven_state():
    result = analyze_fortiblox_price_fact_time(
        [
            snap(1_788_970_000_000, 1_788_969_999_000, a=1.0),
            snap(1_788_970_005_000, 1_788_970_004_000, a=1.1),
        ],
        explicit_provider_field_semantics_verified=True,
    )
    assert result["conclusion"] == PROVEN
    assert result["price_field_timestamp_semantics_verified"] is True
    assert result["current_fact_corroboration_authorized"] is True
    assert result["cmis_verified"] is False
    assert result["public_service_promoted"] is False
    assert result["scout_reliance_promoted"] is False
    assert result["execution_authorized"] is False


def test_static_prices_do_not_prove_binding_even_when_updated_at_moves():
    result = analyze_fortiblox_price_fact_time(
        [
            snap(1_788_970_000_000, 1_788_969_999_000),
            snap(1_788_970_005_000, 1_788_970_004_000),
        ]
    )
    assert result["conclusion"] == EVIDENCE_INCOMPLETE
    assert result["price_change_pair_count"] == 0


def test_timestamp_shape_is_observation_not_verified_semantics():
    result = analyze_fortiblox_price_fact_time(
        [
            snap(1_788_970_000_000, 1_788_969_999_000),
            snap(1_788_970_005_000, 1_788_970_004_000),
        ]
    )
    assert result["updated_at_millisecond_shape_observed"] is True
    assert result["updated_at_clock_near_collection_observed"] is True
    assert result["timestamp_unit_verified"] is False
    assert result["clock_semantics_verified"] is False


def test_duplicate_mint_fails_closed():
    value = snap(1_788_970_000_000, 1_788_969_999_000)
    value["tokens"].append(deepcopy(value["tokens"][0]))
    with pytest.raises(ValueError, match="duplicate mint"):
        analyze_fortiblox_price_fact_time([value, snap(1_788_970_005_000, 1_788_970_004_000)])


def test_requires_multiple_snapshots():
    with pytest.raises(ValueError, match="at least two snapshots"):
        analyze_fortiblox_price_fact_time([snap(1_788_970_000_000, 1_788_969_999_000)])
