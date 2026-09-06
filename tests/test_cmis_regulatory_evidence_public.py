import json
from pathlib import Path

from liquidity_scout.services.cmis_regulatory_evidence_public import (
    build_regulatory_evidence_response,
    validate_regulatory_evidence_public_record,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "regulatory"
    / "usdcx_genius_act_runtime_v1.json"
)
X1_USDCX_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"


def _record():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _validate(record=None, **overrides):
    kwargs = {
        "expected_jurisdiction": "US",
        "expected_framework": "GENIUS Act",
        "expected_asset_id": "USDC.X",
        "expected_chain_asset_id": X1_USDCX_MINT,
        "evaluated_at": "2026-09-06T16:00:00Z",
        "max_evidence_age_seconds": 86400,
    }
    kwargs.update(overrides)
    return validate_regulatory_evidence_public_record(
        _record() if record is None else record,
        **kwargs,
    )


def test_runtime_record_is_exact_mint_bound_and_fresh():
    result = _validate()
    assert result["asset"]["asset_id_kind"] == "mint"
    assert result["asset"]["chain_scoped_asset_id"] == X1_USDCX_MINT
    assert result["current_regulatory_state"]["rulemaking_status"] == "proposed_rule"
    assert result["_public_freshness"]["freshness_verified"] is True


def test_public_response_promotes_status_but_not_compliance():
    response = build_regulatory_evidence_response(
        _record(),
        expected_jurisdiction="US",
        expected_framework="GENIUS Act",
        expected_asset_id="USDC.X",
        expected_chain_asset_id=X1_USDCX_MINT,
        evaluated_at="2026-09-06T16:00:00Z",
    )
    assert response["status"] == "ok"
    assert response["data"]["public_service_promoted"] is True
    assert response["data"]["scout_reliance_promoted"] is True
    assert response["data"]["current_regulatory_state"]["rulemaking_status"] == "proposed_rule"
    assert response["data"]["compliance_conclusion"] is None
    assert response["data"]["compliance_conclusion_authorized"] is False
    assert response["execution_authorized"] is False


def test_proposed_rule_cannot_be_promoted_as_final():
    record = _record()
    record["current_regulatory_state"]["final_rule_verified"] = True
    response = build_regulatory_evidence_response(
        record,
        expected_jurisdiction="US",
        expected_framework="GENIUS Act",
        expected_asset_id="USDC.X",
        expected_chain_asset_id=X1_USDCX_MINT,
        evaluated_at="2026-09-06T16:00:00Z",
    )
    assert response["status"] == "error"
    assert "proposed rule cannot be promoted" in response["errors"][0]["message"]


def test_stale_current_regulatory_state_fails_closed():
    response = build_regulatory_evidence_response(
        _record(),
        expected_jurisdiction="US",
        expected_framework="GENIUS Act",
        expected_asset_id="USDC.X",
        expected_chain_asset_id=X1_USDCX_MINT,
        evaluated_at="2026-09-08T16:00:00Z",
        max_evidence_age_seconds=86400,
    )
    assert response["status"] == "error"
    assert "stale" in response["errors"][0]["message"]


def test_exact_x1_mint_mismatch_fails_closed():
    response = build_regulatory_evidence_response(
        _record(),
        expected_jurisdiction="US",
        expected_framework="GENIUS Act",
        expected_asset_id="USDC.X",
        expected_chain_asset_id="wrong-mint",
        evaluated_at="2026-09-06T16:00:00Z",
    )
    assert response["status"] == "error"
    assert "mint identity mismatch" in response["errors"][0]["message"]


def test_primary_regulator_provenance_is_required():
    record = _record()
    record["sources"] = [
        source
        for source in record["sources"]
        if source["authority_class"] != "primary_regulator"
    ]
    response = build_regulatory_evidence_response(
        record,
        expected_jurisdiction="US",
        expected_framework="GENIUS Act",
        expected_asset_id="USDC.X",
        expected_chain_asset_id=X1_USDCX_MINT,
        evaluated_at="2026-09-06T16:00:00Z",
    )
    assert response["status"] == "error"
    assert "primary-regulator provenance" in response["errors"][0]["message"]
