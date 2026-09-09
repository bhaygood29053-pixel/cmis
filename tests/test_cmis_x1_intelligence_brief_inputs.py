from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from liquidity_scout.services.cmis_contract import build_service_envelope
from liquidity_scout.services.cmis_x1_intelligence_brief_inputs import (
    CONTRACT_VERSION,
    X1IntelligenceBriefInputsError,
    build_x1_intelligence_brief_inputs,
)


MINT = "7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER"
START = "2026-09-09T00:00:00Z"
END = "2026-09-10T00:00:00Z"


def epoch(value):
    return int(
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(timezone.utc)
        .timestamp()
    )


def discovery_response(fact_time="2026-09-09T03:00:00Z"):
    fact = epoch(fact_time)
    first = {
        "content_id": "do_first",
        "mint": MINT,
        "observation_kind": "market_verified",
        "fact_time_unix": fact - 60,
        "fact_time_verified": True,
        "verification_state": "verified",
        "source_id": "x1_rpc",
        "execution_authorized": False,
    }
    recent = {
        "content_id": "do_recent",
        "mint": MINT,
        "observation_kind": "market_verified",
        "fact_time_unix": fact,
        "fact_time_verified": True,
        "verification_state": "verified",
        "source_id": "xdex",
        "execution_authorized": False,
    }
    response = build_service_envelope(
        "discovery_intelligence",
        "x1",
        "partial",
        asset={"mint": MINT},
        data={
            "contract_version": "discovery_intelligence/v1",
            "available": True,
            "mint": MINT,
            "verified_observation_count": 2,
            "first_verified_observation": first,
            "most_recent_verified_observation": recent,
            "coverage": {
                "start_fact_time_unix": fact - 60,
                "end_fact_time_unix": fact,
                "elapsed_observed_seconds": 60,
                "continuous_coverage_verified": False,
                "archive_completeness_verified": False,
            },
            "token_launch_time": None,
            "token_launch_time_verified": False,
        },
        observed_at=fact,
        warnings=[{"code": "discovery_history_is_sparse"}],
    )
    response["execution_authorized"] = False
    return response


def warning_response(fact_time="2026-09-09T08:00:00Z", active=True):
    level = "WATCH" if active else "CLEAR"
    response = build_service_envelope(
        "concentration_warning_intelligence",
        "x1",
        "ok",
        asset={"canonical_id": MINT},
        data={
            "contract_version": "concentration_warning_intelligence/v1",
            "warning_id": "cw_" + "1" * 64,
            "warning_level": level,
            "warning_active": active,
            "warning_level_is_risk_severity": False,
            "policy": {"metric": "absolute_delta_bps"},
            "persistence": {"mode": "two_distinct_compatible_observations"},
            "observations": [
                {"after_observed_at": "2026-09-09T07:00:00Z"},
                {"after_observed_at": fact_time},
            ],
            "evidence": {"receipt_ids": ["er_1"]},
            "limitations": ["watch_clear_are_not_risk_severity"],
            "risk_interpretation": None,
            "execution_authorized": False,
        },
        risk=None,
        observed_at=fact_time,
    )
    response["execution_authorized"] = False
    return response


def large_trade_response(times=None):
    times = times or ["2026-09-09T06:00:00Z", "2026-09-09T05:00:00Z"]
    results = []
    for index, value in enumerate(times, start=1):
        results.append({
            "rank": index,
            "transaction_signature": f"sig-{index}",
            "slot": 100 + index,
            "block_time": str(epoch(value)),
            "pool_address": f"pool-{index}",
            "direction": "BUY" if index == 1 else "SELL",
            "asset_mint": MINT,
            "asset_amount": str(1000 * index),
            "quote_mint": "quote-mint",
            "quote_amount": str(100 * index),
            "verified_usd_notional": str(500 * index),
            "usd_notional_verified": True,
            "wallet_address": f"wallet-{index}",
            "wallet_attribution_verified": True,
            "real_world_wallet_owner_verified": False,
            "trade_price_impact_evidence_id": None,
        })
    response = build_service_envelope(
        "large_trade_discovery",
        "x1",
        "ok",
        asset={"canonical_id": MINT, "mint": MINT},
        data={
            "contract_version": "large_trade_discovery/v1",
            "ranking_scope": "verified_provider_scoped_current_market_pool_set_exact_24h",
            "requested_window": {
                "start_epoch": str(epoch(START)),
                "end_epoch": str(epoch(END)),
                "duration_seconds": "86400",
            },
            "results": results,
            "evidence_boundaries": {
                "global_x1_dex_trade_ranking_authorized": False,
                "wallet_owner_identity_inference_authorized": False,
                "whale_insider_manipulator_label_authorized": False,
                "intent_inference_authorized": False,
                "coordinated_wallet_inference_authorized": False,
                "whole_market_price_impact_claim_authorized": False,
                "volume_causality_claim_authorized": False,
                "automatic_risk_conclusion_authorized": False,
                "trade_recommendation_authorized": False,
            },
            "execution_authorized": False,
        },
        risk=None,
        observed_at=str(epoch(END) - 1),
    )
    response["execution_authorized"] = False
    return response


def components():
    return [
        discovery_response(),
        warning_response(),
        large_trade_response(),
    ]


def build(**overrides):
    args = {
        "subjects": [MINT],
        "window_start": START,
        "window_end": END,
        "requested_services": [
            "discovery_intelligence",
            "concentration_warning_intelligence",
            "large_trade_discovery",
        ],
        "component_responses": components(),
    }
    args.update(overrides)
    return build_x1_intelligence_brief_inputs(**args)


def test_composes_bounded_brief_inputs_with_priority_and_coverage():
    result = build()

    assert result["contract_version"] == CONTRACT_VERSION
    assert result["chain"] == "x1"
    assert result["public_service_promoted"] is False
    assert result["scout_reliance_promoted"] is False
    assert result["execution_authorized"] is False
    assert result["priority_is_risk_severity"] is False
    assert result["proof_score_separate_from_risk"] is True
    assert result["complete_x1_ecosystem_coverage_verified"] is False

    items = result["items"]
    assert [item["priority"] for item in items] == [
        "persistent_warning",
        "large_verified_activity",
        "large_verified_activity",
        "new_verified_observation",
    ]
    assert items[0]["facts"]["warning_level"] == "WATCH"
    assert items[0]["risk"] is None
    assert items[1]["facts"]["real_world_wallet_owner_verified"] is False
    assert items[-1]["facts"]["token_launch_time_verified"] is False

    coverage = result["coverage"]
    assert coverage["requested_subject_count"] == 1
    assert coverage["resolved_subject_count"] == 1
    assert coverage["component_response_matrix_complete"] is True
    assert coverage["included_item_count"] == 4
    assert coverage["outside_window_item_count"] == 0
    assert coverage["complete_x1_ecosystem_coverage_verified"] is False
    assert coverage["window_end_exclusive"] is True


def test_exact_duplicate_component_response_is_collapsed_not_double_counted():
    values = components()
    values.append(deepcopy(values[0]))
    result = build(component_responses=values)

    assert result["coverage"]["duplicate_exact_component_responses_collapsed"] == 1
    assert result["coverage"]["included_item_count"] == 4


def test_conflicting_duplicate_component_response_fails_closed():
    values = components()
    conflict = deepcopy(values[0])
    conflict["data"]["most_recent_verified_observation"]["content_id"] = "changed"
    values.append(conflict)

    with pytest.raises(X1IntelligenceBriefInputsError, match="conflicting"):
        build(component_responses=values)


def test_missing_component_matrix_cell_fails_closed():
    values = components()[:-1]
    with pytest.raises(X1IntelligenceBriefInputsError, match="matrix is incomplete"):
        build(component_responses=values)


def test_window_is_start_inclusive_end_exclusive_and_never_claims_no_x1_activity():
    values = [
        discovery_response("2026-09-10T00:00:00Z"),
        warning_response("2026-09-09T00:00:00Z"),
        large_trade_response(["2026-09-09T23:59:59Z"]),
    ]
    result = build(component_responses=values)

    assert [item["source_service"] for item in result["items"]] == [
        "concentration_warning_intelligence",
        "large_trade_discovery",
    ]
    assert result["coverage"]["outside_window_item_count"] == 1
    assert result["coverage"]["complete_x1_ecosystem_coverage_verified"] is False


def test_bad_contract_chain_or_execution_authority_fails_closed():
    bad = components()
    bad[0]["data"]["contract_version"] = "discovery_intelligence/v2"
    with pytest.raises(X1IntelligenceBriefInputsError, match="contract mismatch"):
        build(component_responses=bad)

    bad = components()
    bad[0]["chain"] = "solana"
    with pytest.raises(X1IntelligenceBriefInputsError, match="X1 only"):
        build(component_responses=bad)

    bad = components()
    bad[0]["execution_authorized"] = True
    with pytest.raises(X1IntelligenceBriefInputsError, match="execution_authorized"):
        build(component_responses=bad)


def test_truth_boundary_upgrades_fail_closed():
    bad = components()
    bad[1]["data"]["warning_level_is_risk_severity"] = True
    with pytest.raises(X1IntelligenceBriefInputsError, match="risk severity"):
        build(component_responses=bad)

    bad = components()
    bad[2]["data"]["evidence_boundaries"][
        "whale_insider_manipulator_label_authorized"
    ] = True
    with pytest.raises(
        X1IntelligenceBriefInputsError,
        match="whale_insider_manipulator_label_authorized",
    ):
        build(component_responses=bad)

    bad = components()
    bad[0]["data"]["token_launch_time_verified"] = True
    with pytest.raises(X1IntelligenceBriefInputsError, match="launch time"):
        build(component_responses=bad)


def test_replay_is_deterministic():
    first = build()
    second = build()
    assert first == second
    assert first["brief_inputs_id"].startswith("xib_")


def test_window_must_be_bounded_to_one_day():
    with pytest.raises(X1IntelligenceBriefInputsError, match="<= 86400"):
        build(
            window_start="2026-09-08T00:00:00Z",
            window_end="2026-09-10T00:00:00Z",
        )
