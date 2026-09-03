from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from liquidity_scout.services.cmis_concentration_warning_intelligence import (
    CONTRACT_VERSION,
    DELIVERY_MODE,
    SERVICE,
    build_concentration_warning_intelligence_response,
    validate_concentration_warning,
)


ID1 = "ie_" + "1" * 64
ID2 = "ie_" + "2" * 64


def _proof(receipt_id):
    return {
        "receipt_id": receipt_id,
        "proof_strength": "STRONG",
        "proof_percent": 100,
        "method": "verified_evidence_ratio_v1",
    }


def _warning(*, level="WATCH"):
    active = level == "WATCH"
    first_receipt = "er-first"
    second_receipt = "er-second"
    first_satisfied = True
    second_satisfied = active

    material = {
        "schema": "cmis_persistent_concentration_warning.v1",
        "chain": "x1",
        "asset_id": "mint-1",
        "evaluated_at": "2026-09-02T20:15:00Z",
        "policy": {
            "policy_id": "x1-concentration-watch",
            "policy_version": "1.0.0",
            "metric": "absolute_delta_bps",
            "unit": "basis_points",
            "absolute_delta_threshold_bps": "100",
            "comparator": "GTE",
            "comparison_symbol": ">=",
            "hidden_default_threshold": False,
        },
        "freshness_policy": {
            "max_latest_age_seconds": 300,
            "latest_age_seconds": "300",
            "latest_evidence_freshness_verified": True,
            "receipt_freshness_verified": True,
        },
        "persistence": {
            "mode": "two_distinct_compatible_observations",
            "required_observations": 2,
            "satisfied_observations": 2 if active else 1,
            "evaluated_evidence_ids": [ID1, ID2],
            "condition_satisfying_evidence_ids": (
                [ID1, ID2] if active else [ID1]
            ),
            "triggering_evidence_ids": [ID1, ID2] if active else [],
            "duplicate_evidence_can_inflate_count": False,
            "strict_order_verified": True,
            "compatibility_verified": True,
            "window_seconds": "600",
            "max_window_seconds": 600,
        },
        "observations": [
            {
                "intelligence_evidence_id": ID1,
                "after_observed_at": "2026-09-02T20:00:00Z",
                "source": "X1.Ninja",
                "scope": "observed_top_token_accounts",
                "requested_account_limit": 20,
                "observed_account_count": 20,
                "direction": "INCREASE",
                "delta_bps": "125",
                "absolute_delta_bps": "125",
                "threshold_status": "EXCEEDS_THRESHOLD",
                "condition_satisfied": first_satisfied,
                "receipt_ids": [first_receipt],
                "proof_records": [_proof(first_receipt)],
                "freshness_verified": True,
            },
            {
                "intelligence_evidence_id": ID2,
                "after_observed_at": "2026-09-02T20:10:00Z",
                "source": "X1.Ninja",
                "scope": "observed_top_token_accounts",
                "requested_account_limit": 20,
                "observed_account_count": 20,
                "direction": "INCREASE",
                "delta_bps": "125" if active else "25",
                "absolute_delta_bps": "125" if active else "25",
                "threshold_status": (
                    "EXCEEDS_THRESHOLD" if active else "WITHIN_THRESHOLD"
                ),
                "condition_satisfied": second_satisfied,
                "receipt_ids": [second_receipt],
                "proof_records": [_proof(second_receipt)],
                "freshness_verified": True,
            },
        ],
        "evidence": {
            "intelligence_evidence_ids": [ID1, ID2],
            "receipt_ids": [first_receipt, second_receipt],
            "proof_lineage": [
                {
                    "intelligence_evidence_id": ID1,
                    "receipt_ids": [first_receipt],
                    "proof_records": [_proof(first_receipt)],
                },
                {
                    "intelligence_evidence_id": ID2,
                    "receipt_ids": [second_receipt],
                    "proof_records": [_proof(second_receipt)],
                },
            ],
            "freshness_verified": True,
            "unresolved_fields": [],
        },
        "warning_active": active,
        "warning_level": level,
        "warning_level_is_risk_severity": False,
        "risk_interpretation": None,
        "risk_interpretation_verified": False,
        "behavioral_interpretation_verified": False,
        "ownership_interpretation_verified": False,
        "proof_strength_separate_from_risk": True,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "delivery_authorized": False,
        "execution_authorized": False,
        "limitations": [
            "warning_is_deterministic_policy_evaluation_not_a_market_fact",
            "watch_is_not_risk_severity",
            "warning_delivery_is_not_authorized",
            "warning_does_not_authorize_execution_or_value_movement",
        ],
    }
    digest = hashlib.sha256(
        json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return {"warning_id": f"cw_{digest}", **material}


def test_watch_warning_is_exposed_as_pull_only_promoted_service():
    warning = _warning(level="WATCH")
    response = build_concentration_warning_intelligence_response(warning)

    assert response["service"] == SERVICE
    assert response["chain"] == "x1"
    assert response["status"] == "ok"
    assert response["risk"] is None
    assert response["observed_at"] == "2026-09-02T20:10:00Z"
    assert response["execution_authorized"] is False

    data = response["data"]
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["delivery_mode"] == DELIVERY_MODE == "pull_only"
    assert data["push_delivery_authorized"] is False
    assert data["public_service_promoted"] is True
    assert data["scout_reliance_promoted"] is True
    assert data["warning_level"] == "WATCH"
    assert data["warning_active"] is True
    assert data["warning_level_is_risk_severity"] is False
    assert data["risk_interpretation"] is None
    assert data["proof_strength_separate_from_risk"] is True
    assert data["canonical_warning"] == warning
    assert data["canonical_warning"]["public_service_promoted"] is False
    assert data["canonical_warning"]["scout_reliance_promoted"] is False
    assert data["canonical_warning"]["delivery_authorized"] is False
    assert data["canonical_warning"]["execution_authorized"] is False


def test_clear_warning_is_valid_success_not_error_or_risk():
    response = build_concentration_warning_intelligence_response(
        _warning(level="CLEAR")
    )
    assert response["status"] == "ok"
    assert response["data"]["warning_level"] == "CLEAR"
    assert response["data"]["warning_active"] is False
    assert response["data"]["persistence"]["satisfied_observations"] == 1
    assert response["data"]["persistence"]["triggering_evidence_ids"] == []
    assert response["risk"] is None


def test_validator_returns_exact_canonical_warning_copy():
    warning = _warning()
    validated = validate_concentration_warning(warning)
    assert validated == warning
    assert validated is not warning


def test_tampered_warning_identity_fails_public_contract():
    warning = _warning()
    warning["warning_level"] = "CLEAR"
    response = build_concentration_warning_intelligence_response(warning)
    assert response["status"] == "error"
    assert response["errors"][0]["code"] == (
        "concentration_warning_intelligence_contract_violation"
    )


def test_duplicate_or_replayed_evidence_is_rejected():
    warning = _warning()
    warning["persistence"]["evaluated_evidence_ids"] = [ID1, ID1]
    response = build_concentration_warning_intelligence_response(warning)
    assert response["status"] == "error"
    assert "distinct" in response["errors"][0]["message"]


def test_broken_proof_lineage_is_rejected():
    warning = _warning()
    warning["observations"][1]["proof_records"][0]["receipt_id"] = "other"
    response = build_concentration_warning_intelligence_response(warning)
    assert response["status"] == "error"
    assert "receipt_id" in response["errors"][0]["message"]


def test_protected_warning_cannot_self_promote_before_public_wrapper():
    warning = _warning()
    warning["public_service_promoted"] = True
    response = build_concentration_warning_intelligence_response(warning)
    assert response["status"] == "error"
    assert "public_service_promoted=false" in response["errors"][0]["message"]


def test_watch_requires_both_observations_to_satisfy_and_trigger():
    warning = _warning()
    warning["persistence"]["condition_satisfying_evidence_ids"] = [ID1]
    warning["persistence"]["satisfied_observations"] = 1
    warning["persistence"]["triggering_evidence_ids"] = [ID1]
    response = build_concentration_warning_intelligence_response(warning)
    assert response["status"] == "error"
    assert "WATCH requires both" in response["errors"][0]["message"]


def test_push_delivery_and_execution_never_promote():
    response = build_concentration_warning_intelligence_response(_warning())
    assert response["data"]["delivery_mode"] == "pull_only"
    assert response["data"]["push_delivery_authorized"] is False
    assert response["data"]["execution_authorized"] is False
    assert response["execution_authorized"] is False
    assert response["data"]["behavioral_interpretation_verified"] is False
    assert response["data"]["ownership_interpretation_verified"] is False
