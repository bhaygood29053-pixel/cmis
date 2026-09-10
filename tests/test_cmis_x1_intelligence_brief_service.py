from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest
from liquidity_scout.services.cmis_x1_intelligence_brief_service import (
    SERVICE,
    X1IntelligenceBriefServiceContractError,
    build_x1_intelligence_brief_service_response,
)


MINT = "7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER"


def brief():
    return {
        "brief_inputs_id": "xib_test",
        "contract_version": "x1_intelligence_brief_inputs/v1",
        "chain": "x1",
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "subjects": [MINT],
        "requested_services": [
            "concentration_warning_intelligence",
            "discovery_intelligence",
            "large_trade_discovery",
        ],
        "window": {
            "start": "2026-09-09T00:00:00Z",
            "end": "2026-09-10T00:00:00Z",
            "end_exclusive": True,
            "duration_seconds": 86400,
        },
        "items": [],
        "component_evaluations": [],
        "coverage": {
            "requested_subject_count": 1,
            "resolved_subject_count": 1,
            "requested_service_count": 3,
            "input_service_classes_requested": [
                "concentration_warning_intelligence",
                "discovery_intelligence",
                "large_trade_discovery",
            ],
            "input_service_classes_evaluated": [
                "concentration_warning_intelligence",
                "discovery_intelligence",
                "large_trade_discovery",
            ],
            "partial_service_classes": [],
            "unavailable_service_classes": ["large_trade_discovery"],
            "error_or_ambiguous_service_classes": [
                "concentration_warning_intelligence",
                "discovery_intelligence",
            ],
            "component_response_matrix_complete": True,
            "duplicate_exact_component_responses_collapsed": 0,
            "included_item_count": 0,
            "outside_window_item_count": 0,
            "window_start": "2026-09-09T00:00:00Z",
            "window_end": "2026-09-10T00:00:00Z",
            "window_end_exclusive": True,
            "earliest_included_fact_time": None,
            "latest_included_fact_time": None,
            "complete_x1_ecosystem_coverage_verified": False,
        },
        "priority_is_risk_severity": False,
        "proof_score_separate_from_risk": True,
        "missing_evidence_zero_filled": False,
        "complete_x1_ecosystem_coverage_verified": False,
        "execution_authorized": False,
    }


def test_wraps_non_promoted_brief_in_promoted_read_only_service_envelope():
    source = brief()
    before = deepcopy(source)

    response = build_x1_intelligence_brief_service_response(source)

    assert response["service"] == SERVICE
    assert response["chain"] == "x1"
    assert response["status"] == "partial"
    assert response["asset"] == {}
    assert response["data"] == source
    assert response["risk"] is None
    assert response["confidence"]["proof_score_separate_from_risk"] is True
    assert (
        response["confidence"]["complete_x1_ecosystem_coverage_verified"]
        is False
    )
    assert response["freshness"]["state"] == "UNKNOWN"
    assert response["freshness"]["freshness_verified"] is None
    assert response["observed_at"] is None
    assert response["read_only"] is True
    assert response["public_service_promoted"] is True
    assert response["scout_reliance_promoted"] is True
    assert response["runtime_capability_promoted"] is True
    assert response["complete_x1_ecosystem_coverage_verified"] is False
    assert response["execution_authorized"] is False
    assert response["data"]["public_service_promoted"] is False
    assert response["data"]["scout_reliance_promoted"] is False
    assert source == before


def test_empty_bounded_brief_never_becomes_global_no_activity_claim():
    response = build_x1_intelligence_brief_service_response(brief())
    codes = {item["code"] for item in response["warnings"]}

    assert "bounded_x1_intelligence_brief_scope" in codes
    assert "empty_bounded_brief_is_not_global_no_activity" in codes
    assert response["data"]["complete_x1_ecosystem_coverage_verified"] is False


def test_top_level_freshness_is_not_inferred_from_item_fact_time():
    source = brief()
    source["items"] = [
        {
            "brief_item_id": "xbi_test",
            "subject_mint": MINT,
            "source_service": "large_trade_discovery",
            "source_contract_version": "large_trade_discovery/v1",
            "priority": "large_verified_activity",
            "priority_rank": 30,
            "fact_time": "2026-09-09T23:59:59Z",
            "event_key": "sig",
            "facts": {},
            "source_status": "ok",
            "source_observed_at": "2026-09-09T23:59:59Z",
            "source_freshness": {"state": "VERIFIED"},
            "source_confidence": {},
            "source_sources": [],
            "source_warnings": [],
            "source_errors": [],
            "risk": None,
            "proof_strength_separate_from_risk": True,
            "priority_is_risk_severity": False,
            "complete_x1_ecosystem_coverage_verified": False,
            "execution_authorized": False,
        }
    ]
    source["coverage"]["included_item_count"] = 1

    response = build_x1_intelligence_brief_service_response(source)

    assert response["freshness"]["state"] == "UNKNOWN"
    assert response["freshness"]["observed_at"] is None
    assert response["data"]["items"][0]["source_freshness"]["state"] == "VERIFIED"


@pytest.mark.parametrize(
    "field",
    [
        "public_service_promoted",
        "scout_reliance_promoted",
        "complete_x1_ecosystem_coverage_verified",
        "execution_authorized",
    ],
)
def test_authority_or_coverage_upgrade_fails_closed(field):
    source = brief()
    source[field] = True

    with pytest.raises(
        X1IntelligenceBriefServiceContractError,
        match=field,
    ):
        build_x1_intelligence_brief_service_response(source)


def test_incomplete_component_matrix_fails_closed():
    source = brief()
    source["coverage"]["component_response_matrix_complete"] = False

    with pytest.raises(
        X1IntelligenceBriefServiceContractError,
        match="complete subject/service response matrix",
    ):
        build_x1_intelligence_brief_service_response(source)


def test_promotion_branch_registers_public_runtime_capability_candidate():
    tree = ast.parse(
        Path("liquidity_scout/cmis/capabilities.py").read_text(encoding="utf-8")
    )
    runtime_services = None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name)
            and target.id == "PUBLIC_RUNTIME_SERVICES"
            for target in node.targets
        ):
            runtime_services = ast.literal_eval(node.value)
            break
    assert runtime_services is not None
    assert SERVICE in runtime_services
