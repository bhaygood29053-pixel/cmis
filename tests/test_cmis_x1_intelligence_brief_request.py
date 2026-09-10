from __future__ import annotations

from copy import deepcopy

import pytest

from liquidity_scout.services.cmis_x1_intelligence_brief_request import (
    REQUEST_CONTRACT_VERSION,
    X1IntelligenceBriefRequestError,
    validate_x1_intelligence_brief_request,
)


MINT = "7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER"


def request():
    return {
        "contract_version": REQUEST_CONTRACT_VERSION,
        "chain": "x1",
        "subjects": [MINT],
        "window_start": "2026-09-09T00:00:00Z",
        "window_end": "2026-09-10T00:00:00Z",
        "requested_services": [
            "concentration_warning_intelligence",
            "large_trade_discovery",
            "discovery_intelligence",
        ],
    }


def test_accepts_only_exact_bounded_selectors():
    result = validate_x1_intelligence_brief_request(request())

    assert result["contract_version"] == REQUEST_CONTRACT_VERSION
    assert result["chain"] == "x1"
    assert result["subjects"] == [MINT]
    assert result["requested_services"] == [
        "concentration_warning_intelligence",
        "discovery_intelligence",
        "large_trade_discovery",
    ]
    assert result["read_only"] is True
    assert result["public_service_promoted"] is False
    assert result["scout_reliance_promoted"] is False
    assert result["execution_authorized"] is False
    assert result["runtime_component_responses_caller_supplied"] is False
    assert result["runtime_evidence_caller_supplied"] is False
    assert result["runtime_priority_caller_supplied"] is False
    assert result["runtime_fact_time_caller_supplied"] is False
    assert result["runtime_risk_caller_supplied"] is False
    assert result["runtime_provider_facts_caller_supplied"] is False


@pytest.mark.parametrize(
    "field",
    [
        "component_responses",
        "evidence",
        "proof_score",
        "priority",
        "fact_time",
        "risk",
        "provider_facts",
        "coverage",
        "public_service_promoted",
        "scout_reliance_promoted",
        "execution_authorized",
    ],
)
def test_caller_cannot_inject_cmis_owned_fact_or_authority_fields(field):
    value = request()
    value[field] = {} if field not in {
        "priority",
        "fact_time",
        "public_service_promoted",
        "scout_reliance_promoted",
        "execution_authorized",
    } else "caller-value"

    with pytest.raises(
        X1IntelligenceBriefRequestError,
        match="caller may not supply CMIS-owned",
    ):
        validate_x1_intelligence_brief_request(value)


def test_unknown_request_fields_fail_closed():
    value = request()
    value["mode"] = "make_it_bullish"

    with pytest.raises(
        X1IntelligenceBriefRequestError,
        match="unsupported X1 Intelligence Brief request fields",
    ):
        validate_x1_intelligence_brief_request(value)


def test_chain_and_exact_mint_are_fail_closed():
    value = request()
    value["chain"] = "solana"
    with pytest.raises(X1IntelligenceBriefRequestError, match="chain=x1"):
        validate_x1_intelligence_brief_request(value)

    value = request()
    value["subjects"] = ["AGI"]
    with pytest.raises(
        X1IntelligenceBriefRequestError,
        match="exact X1 mint identity",
    ):
        validate_x1_intelligence_brief_request(value)


def test_subjects_and_services_must_be_unique():
    value = request()
    value["subjects"] = [MINT, MINT]
    with pytest.raises(X1IntelligenceBriefRequestError, match="subjects must be unique"):
        validate_x1_intelligence_brief_request(value)

    value = request()
    value["requested_services"] = [
        "discovery_intelligence",
        "discovery_intelligence",
    ]
    with pytest.raises(
        X1IntelligenceBriefRequestError,
        match="requested_services must be unique",
    ):
        validate_x1_intelligence_brief_request(value)


def test_only_accepted_component_services_are_selectable():
    value = request()
    value["requested_services"] = ["burn_intelligence"]

    with pytest.raises(
        X1IntelligenceBriefRequestError,
        match="unsupported brief component services",
    ):
        validate_x1_intelligence_brief_request(value)


def test_window_is_canonical_bounded_and_positive():
    value = request()
    value["window_end"] = "2026-09-10T00:00:01Z"
    with pytest.raises(
        X1IntelligenceBriefRequestError,
        match="<= 86400",
    ):
        validate_x1_intelligence_brief_request(value)

    value = request()
    value["window_end"] = value["window_start"]
    with pytest.raises(
        X1IntelligenceBriefRequestError,
        match=">0",
    ):
        validate_x1_intelligence_brief_request(value)

    value = request()
    value["window_start"] = "2026-09-09T00:00:00+00:00"
    with pytest.raises(
        X1IntelligenceBriefRequestError,
        match="canonical UTC",
    ):
        validate_x1_intelligence_brief_request(value)


def test_request_projection_does_not_mutate_caller_input():
    value = request()
    before = deepcopy(value)
    validate_x1_intelligence_brief_request(value)
    assert value == before
