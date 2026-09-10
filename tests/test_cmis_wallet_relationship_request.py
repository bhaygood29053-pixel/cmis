from __future__ import annotations

from copy import deepcopy

import pytest

from liquidity_scout.services.cmis_wallet_relationship_request import (
    REQUEST_CONTRACT_VERSION,
    WalletRelationshipRequestError,
    validate_wallet_relationship_request,
)


SIGNATURE = (
    "2AXDGYSE4f2sz7tvMMzyHvUfcoJmxudvdhBcmiUSo6ijwfYmfZYsKRxboQMPh3R4"
    "kUhXRVdtSXFXMheka4Rc4P2"
)
MINT = "7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER"
SENDER = "8qbHbw2BbbTHBW1sbeqakYXVKRQM8Ne7pLK7m6CVfeR"
RECIPIENT = "CktRuQ2mttgRGkXJtyksdKHjUdc2C4TgDzyB98oEzy8"


def request():
    return {
        "contract_version": REQUEST_CONTRACT_VERSION,
        "chain": "x1",
        "transaction_signature": SIGNATURE,
        "asset_mint": MINT,
        "sender_wallet": SENDER,
        "recipient_wallet": RECIPIENT,
    }


def test_accepts_only_exact_selector_set_and_marks_caller_trust_material_absent():
    source = request()
    before = deepcopy(source)

    result = validate_wallet_relationship_request(source)

    assert result["contract_version"] == REQUEST_CONTRACT_VERSION
    assert result["chain"] == "x1"
    assert result["transaction_signature"] == SIGNATURE
    assert result["asset_mint"] == MINT
    assert result["sender_wallet"] == SENDER
    assert result["recipient_wallet"] == RECIPIENT
    assert result["runtime_transaction_caller_supplied"] is False
    assert result["runtime_parsed_transfer_caller_supplied"] is False
    assert result["runtime_wallet_activity_caller_supplied"] is False
    assert result["runtime_relationship_evidence_caller_supplied"] is False
    assert result["runtime_provider_facts_caller_supplied"] is False
    assert result["runtime_evidence_quality_caller_supplied"] is False
    assert (
        result["runtime_ownership_behavior_intent_risk_caller_supplied"]
        is False
    )
    assert result["read_only"] is True
    assert result["public_service_promoted"] is False
    assert result["scout_reliance_promoted"] is False
    assert result["complete_history_claimed"] is False
    assert result["complete_graph_coverage_claimed"] is False
    assert result["execution_authorized"] is False
    assert source == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("transaction", {}),
        ("parsed_transaction", {}),
        ("instruction", {}),
        ("amount_raw", "1000"),
        ("transfer_direction", "TRANSFER_OUT"),
        ("wallet_activity_observation", {}),
        ("wallet_activity_observation_id", "wa_fake"),
        ("relationship_evidence", {}),
        ("relationship_evidence_id", "wr_fake"),
        ("provider", "trusted"),
        ("evidence_receipt", {}),
        ("proof_score", {}),
        ("ownership", True),
        ("beneficial_owner", "entity"),
        ("whale", True),
        ("insider", True),
        ("bot", True),
        ("coordination", True),
        ("manipulation", True),
        ("intent", "accumulate"),
        ("causality", "price_move"),
        ("risk", {"score": 99}),
        ("complete_history_claimed", True),
        ("complete_graph_coverage_claimed", True),
        ("execution_authorized", True),
    ],
)
def test_rejects_caller_supplied_fact_evidence_behavior_or_authority(field, value):
    value_request = request()
    value_request[field] = value

    with pytest.raises(
        WalletRelationshipRequestError,
        match="caller may not supply CMIS-owned wallet relationship facts/authority fields",
    ):
        validate_wallet_relationship_request(value_request)


def test_rejects_unknown_fields():
    value = request()
    value["extra"] = "nope"

    with pytest.raises(WalletRelationshipRequestError, match="unsupported"):
        validate_wallet_relationship_request(value)


def test_requires_exact_request_contract_and_x1_chain():
    value = request()
    value["contract_version"] = "wallet_relationship_intelligence_request/v2"
    with pytest.raises(WalletRelationshipRequestError, match="request contract"):
        validate_wallet_relationship_request(value)

    value = request()
    value["chain"] = "solana"
    with pytest.raises(WalletRelationshipRequestError, match="chain=x1"):
        validate_wallet_relationship_request(value)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("transaction_signature", "sig-1", "64-byte base58"),
        ("asset_mint", "mint-1", "32-byte base58"),
        ("sender_wallet", "wallet-a", "32-byte base58"),
        ("recipient_wallet", "wallet-b", "32-byte base58"),
    ],
)
def test_requires_exact_transaction_and_public_key_identity(field, value, match):
    invalid = request()
    invalid[field] = value

    with pytest.raises(WalletRelationshipRequestError, match=match):
        validate_wallet_relationship_request(invalid)


def test_sender_and_recipient_must_be_distinct():
    value = request()
    value["recipient_wallet"] = SENDER

    with pytest.raises(WalletRelationshipRequestError, match="must be distinct"):
        validate_wallet_relationship_request(value)
