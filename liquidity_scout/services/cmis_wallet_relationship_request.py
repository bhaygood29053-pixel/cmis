"""Public caller-selector contract for future X1 wallet relationship runtime.

The caller may choose one exact finalized X1 transaction to verify plus the
exact mint/sender/recipient identities. The caller may not supply transfer facts,
parsed transaction material, wallet-activity/relationship records, provider
assertions, evidence quality, ownership labels, risk, or execution authority.

Runtime/capability promotion remains CMIS #631 and is blocked on protected
materialization acceptance (#633 / cmis-core PR #51 / private Actions #52).
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from liquidity_scout.services.cmis_x1_asset_identity import (
    is_exact_x1_public_key,
)


REQUEST_CONTRACT_VERSION = "wallet_relationship_intelligence_request/v1"
SUPPORTED_CHAIN = "x1"

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {char: index for index, char in enumerate(_BASE58_ALPHABET)}

_ALLOWED_KEYS = frozenset(
    {
        "contract_version",
        "chain",
        "transaction_signature",
        "asset_mint",
        "sender_wallet",
        "recipient_wallet",
    }
)
_FORBIDDEN_CALLER_KEYS = frozenset(
    {
        "transaction",
        "transaction_result",
        "parsed_transaction",
        "instruction",
        "instructions",
        "instruction_type",
        "source_token_account",
        "destination_token_account",
        "token_account_owner",
        "amount",
        "amount_raw",
        "decimals",
        "direction",
        "transfer_direction",
        "wallet_activity_observation",
        "wallet_activity_observation_id",
        "relationship_evidence",
        "relationship_evidence_id",
        "relationship_summary",
        "wa_id",
        "wr_id",
        "wrs_id",
        "provider",
        "provider_facts",
        "provider_trust",
        "source",
        "sources",
        "evidence",
        "evidence_receipt",
        "evidence_receipts",
        "proof_score",
        "proof_scores",
        "ownership",
        "ownership_label",
        "beneficial_ownership",
        "beneficial_owner",
        "real_world_identity",
        "whale",
        "insider",
        "bot",
        "market_maker",
        "coordination",
        "manipulation",
        "fraud",
        "scam",
        "intent",
        "causality",
        "risk",
        "risk_interpretation",
        "complete_history_claimed",
        "complete_graph_coverage_claimed",
        "public_service_promoted",
        "scout_reliance_promoted",
        "execution_authorized",
    }
)


class WalletRelationshipRequestError(ValueError):
    """Raised when a caller attempts to widen the wallet relationship trust root."""


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WalletRelationshipRequestError("request must be a mapping")
    return value


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise WalletRelationshipRequestError(
            f"{name} must be normalized non-empty text"
        )
    return value


def _decode_base58(value: str) -> bytes | None:
    number = 0
    for char in value:
        digit = _BASE58_INDEX.get(char)
        if digit is None:
            return None
        number = (number * 58) + digit
    leading_zeroes = len(value) - len(value.lstrip("1"))
    payload = (
        b""
        if number == 0
        else number.to_bytes((number.bit_length() + 7) // 8, "big")
    )
    return (b"\x00" * leading_zeroes) + payload


def _signature(value: Any) -> str:
    text = _text("transaction_signature", value)
    decoded = _decode_base58(text)
    if decoded is None or len(decoded) != 64:
        raise WalletRelationshipRequestError(
            "transaction_signature must be an exact 64-byte base58 transaction signature"
        )
    return text


def _pubkey(name: str, value: Any) -> str:
    text = _text(name, value)
    if not is_exact_x1_public_key(text):
        raise WalletRelationshipRequestError(
            f"{name} must be an exact 32-byte base58 X1 public key"
        )
    return text


def validate_wallet_relationship_request(value: Any) -> dict[str, Any]:
    """Validate only caller-controlled selectors for future #631 runtime."""

    request = deepcopy(dict(_mapping(value)))

    forbidden_present = sorted(_FORBIDDEN_CALLER_KEYS.intersection(request))
    if forbidden_present:
        raise WalletRelationshipRequestError(
            "caller may not supply CMIS-owned wallet relationship facts/authority fields: "
            + ", ".join(forbidden_present)
        )

    unknown = sorted(set(request) - _ALLOWED_KEYS)
    if unknown:
        raise WalletRelationshipRequestError(
            "unsupported wallet relationship request fields: " + ", ".join(unknown)
        )

    if request.get("contract_version") != REQUEST_CONTRACT_VERSION:
        raise WalletRelationshipRequestError(
            f"request contract must be {REQUEST_CONTRACT_VERSION}"
        )
    if request.get("chain") != SUPPORTED_CHAIN:
        raise WalletRelationshipRequestError(
            "wallet relationship request must use chain=x1"
        )

    signature = _signature(request.get("transaction_signature"))
    asset_mint = _pubkey("asset_mint", request.get("asset_mint"))
    sender = _pubkey("sender_wallet", request.get("sender_wallet"))
    recipient = _pubkey("recipient_wallet", request.get("recipient_wallet"))
    if sender == recipient:
        raise WalletRelationshipRequestError(
            "sender_wallet and recipient_wallet must be distinct exact X1 identities"
        )

    return {
        "contract_version": REQUEST_CONTRACT_VERSION,
        "chain": SUPPORTED_CHAIN,
        "transaction_signature": signature,
        "asset_mint": asset_mint,
        "sender_wallet": sender,
        "recipient_wallet": recipient,
        "runtime_transaction_caller_supplied": False,
        "runtime_parsed_transfer_caller_supplied": False,
        "runtime_wallet_activity_caller_supplied": False,
        "runtime_relationship_evidence_caller_supplied": False,
        "runtime_provider_facts_caller_supplied": False,
        "runtime_evidence_quality_caller_supplied": False,
        "runtime_ownership_behavior_intent_risk_caller_supplied": False,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "complete_history_claimed": False,
        "complete_graph_coverage_claimed": False,
        "execution_authorized": False,
    }


__all__ = [
    "REQUEST_CONTRACT_VERSION",
    "SUPPORTED_CHAIN",
    "WalletRelationshipRequestError",
    "validate_wallet_relationship_request",
]
