from copy import deepcopy

import pytest

from liquidity_scout.services.cmis_tokenized_equity_evidence_quality import (
    build_tokenized_equity_evidence_quality,
)
from liquidity_scout.services.cmis_tokenized_equity_intelligence import (
    CONTRACT_VERSION,
    MATERIALIZATION_CONTRACT_VERSION,
    SERVICE,
    TokenizedEquityIntelligenceContractError,
    build_tokenized_equity_intelligence_response,
    content_address_tokenized_equity_intelligence_materialization,
    validate_tokenized_equity_intelligence_materialization,
)
from liquidity_scout.services.cmis_tokenized_equity_intelligence_request import (
    REQUEST_CONTRACT_VERSION,
    TokenizedEquityIntelligenceRequestError,
    validate_tokenized_equity_intelligence_request,
)
from liquidity_scout.services.cmis_tokenized_equity_provenance import (
    build_tokenized_equity_provenance,
)

X1_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
SECURITY_ID = "US0000000001"


def raw_request(*, components=None, security=True):
    request = {
        "contract_version": REQUEST_CONTRACT_VERSION,
        "chain": "x1",
        "asset_mint": X1_MINT,
        "requested_components": components or ["provenance"],
    }
    if security:
        request.update({"security_id": SECURITY_ID, "security_id_kind": "isin"})
    return request


def provenance():
    return build_tokenized_equity_provenance(
        token={"chain": "x1", "asset_id": X1_MINT, "asset_id_kind": "mint"},
        underlying_security={"security_id": SECURITY_ID, "security_id_kind": "isin"},
        representation_type="tokenized_security_representation",
        issuer={"name": "Example Issuer"},
        evidence_ids=["reference-only"],
    )


def unresolved_materialization(*, components=None):
    request = raw_request(components=components or ["provenance", "rights"])
    requested = validate_tokenized_equity_intelligence_request(request)["requested_components"]
    base = {
        "contract_version": MATERIALIZATION_CONTRACT_VERSION,
        "chain": "x1",
        "request": request,
        "subject_resolution_state": "EVIDENCE_REQUIRED",
        "resolved_subject": None,
        "component_states": {name: "EVIDENCE_REQUIRED" for name in requested},
        "components": {},
        "evidence_quality": None,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "caller_fact_evidence_provider_material_accepted": False,
        "caller_proof_score_risk_legal_material_accepted": False,
        "live_x1_equity_deployment_verified": False,
        "live_robinhood_x1_route_verified": False,
        "execution_authorized": False,
    }
    return content_address_tokenized_equity_intelligence_materialization(base)


def resolved_provenance_materialization():
    request = raw_request(components=["provenance"])
    p = provenance()
    quality = build_tokenized_equity_evidence_quality(
        tokenized_equity_provenance=p,
    )
    base = {
        "contract_version": MATERIALIZATION_CONTRACT_VERSION,
        "chain": "x1",
        "request": request,
        "subject_resolution_state": "RESOLVED",
        "resolved_subject": {
            "chain": "x1",
            "asset_mint": X1_MINT,
            "asset_id_kind": "mint",
            "security_id": SECURITY_ID,
            "security_id_kind": "isin",
        },
        "component_states": {"provenance": "AVAILABLE"},
        "components": {"provenance": p},
        "evidence_quality": quality,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "caller_fact_evidence_provider_material_accepted": False,
        "caller_proof_score_risk_legal_material_accepted": False,
        "live_x1_equity_deployment_verified": False,
        "live_robinhood_x1_route_verified": False,
        "execution_authorized": False,
    }
    return content_address_tokenized_equity_intelligence_materialization(base)


def test_request_accepts_selectors_only_and_canonicalizes_component_order():
    safe = validate_tokenized_equity_intelligence_request(
        raw_request(components=["rights", "market_activity", "provenance"])
    )
    assert safe["requested_components"] == ["provenance", "rights", "market_activity"]
    assert safe["evidence_quality_implicitly_required"] is True
    assert safe["caller_fact_evidence_provider_material_supplied"] is False
    assert safe["execution_authorized"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence", {"pretend": True}),
        ("proof_score", 100),
        ("risk", {"level": "LOW"}),
        ("tokenized_equity_provenance", {"contract": "forged"}),
        ("bridge_route", {"live": True}),
        ("deployment_verified", True),
    ],
)
def test_request_rejects_caller_trust_material(field, value):
    request = raw_request()
    request[field] = value
    with pytest.raises(TokenizedEquityIntelligenceRequestError):
        validate_tokenized_equity_intelligence_request(request)


def test_request_requires_provenance_identity_foundation():
    with pytest.raises(TokenizedEquityIntelligenceRequestError, match="include provenance"):
        validate_tokenized_equity_intelligence_request(
            raw_request(components=["rights"])
        )


def test_request_requires_exact_x1_mint_and_security_selector_pair():
    bad = raw_request()
    bad["asset_mint"] = "AAPL"
    with pytest.raises(TokenizedEquityIntelligenceRequestError, match="exact 32-byte"):
        validate_tokenized_equity_intelligence_request(bad)
    incomplete = raw_request(security=False)
    incomplete["security_id"] = SECURITY_ID
    with pytest.raises(TokenizedEquityIntelligenceRequestError, match="supplied together"):
        validate_tokenized_equity_intelligence_request(incomplete)


def test_unresolved_subject_is_safe_partial_not_deployment_claim():
    material = unresolved_materialization()
    validated = validate_tokenized_equity_intelligence_materialization(material)
    assert validated["subject_resolution_state"] == "EVIDENCE_REQUIRED"
    response = build_tokenized_equity_intelligence_response(material)
    assert response["service"] == SERVICE
    assert response["status"] == "partial"
    assert response["data"]["contract_version"] == CONTRACT_VERSION
    assert response["data"]["resolved_subject"] is None
    assert response["data"]["live_x1_equity_deployment_verified"] is False
    assert response["public_service_promoted"] is True
    assert response["scout_reliance_promoted"] is True
    assert response["execution_authorized"] is False


def test_resolved_provenance_only_recomputes_evidence_quality_and_is_candidate_ok():
    material = resolved_provenance_materialization()
    validated = validate_tokenized_equity_intelligence_materialization(material)
    assert validated["resolved_subject"]["asset_mint"] == X1_MINT
    assert validated["evidence_quality"]["confidence_inputs"]["proof_score"] is None
    response = build_tokenized_equity_intelligence_response(material)
    assert response["status"] == "ok"
    assert response["data"]["component_states"] == {"provenance": "AVAILABLE"}
    assert response["data"]["proof_score_separate_from_risk"] is True
    assert response["confidence"]["proof_score_owned_by_protected_runtime"] is True
    assert response["runtime_capability_promoted"] is True
    assert response["execution_authorized"] is False


def test_materialization_id_is_content_addressed_and_tamper_evident():
    material = resolved_provenance_materialization()
    assert material["materialization_id"].startswith("tei_")
    tampered = deepcopy(material)
    tampered["component_states"]["provenance"] = "EVIDENCE_REQUIRED"
    with pytest.raises(TokenizedEquityIntelligenceContractError, match="identity mismatch"):
        validate_tokenized_equity_intelligence_materialization(tampered)


def test_materialization_rejects_unknown_hidden_fields():
    material = unresolved_materialization()
    material.pop("materialization_id")
    material["secret_provider_fact"] = {"adoption": True}
    material = content_address_tokenized_equity_intelligence_materialization(material)
    with pytest.raises(TokenizedEquityIntelligenceContractError, match="unsupported fields"):
        validate_tokenized_equity_intelligence_materialization(material)


def test_optional_security_selector_must_match_resolved_subject():
    material = resolved_provenance_materialization()
    material.pop("materialization_id")
    material["request"]["security_id"] = "US9999999999"
    material = content_address_tokenized_equity_intelligence_materialization(material)
    with pytest.raises(TokenizedEquityIntelligenceContractError, match="resolved security id"):
        validate_tokenized_equity_intelligence_materialization(material)


def test_precomputed_materialization_id_cannot_be_readdressed():
    material = unresolved_materialization()
    with pytest.raises(TokenizedEquityIntelligenceContractError, match="must not contain"):
        content_address_tokenized_equity_intelligence_materialization(material)
