"""Public contract for bounded X1 direct wallet-relationship intelligence.

This module validates one protected
x1_direct_wallet_transfer_materialization/v1 record and projects only the
verified direct-transfer facts into the normal CMIS service envelope. Merely
shipping this module does not register a runtime service, advertise a capability,
or authorize X1 Scout reliance.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from liquidity_scout.services.cmis_contract import OK, build_service_envelope


SERVICE = "wallet_relationship_intelligence"
CONTRACT_VERSION = "wallet_relationship_intelligence/v1"
UPSTREAM_CONTRACT_VERSION = "x1_direct_wallet_transfer_materialization/v1"
RELATIONSHIP_SCHEMA = "cmis_wallet_relationship_evidence.v1"
RELATIONSHIP_KIND = "observed_direct_interaction"
INTERACTION_TYPE = "verified_token_transfer"
SUPPORTED_CHAIN = "x1"
SOURCE = "X1 RPC"
VERIFICATION_METHOD = "x1_rpc_jsonparsed_spl_transfer_v1"
EVIDENCE_SCOPE = "exact_finalized_x1_transaction"

_RELATIONSHIP_ID_RE = re.compile(r"^wr_[0-9a-f]{64}$")
_OBSERVATION_ID_RE = re.compile(r"^wa_[0-9a-f]{64}$")
_REQUIRED_FALSE_RELATIONSHIP_FIELDS = (
    "ownership_inference_added",
    "beneficial_ownership_inference_added",
    "behavioral_interpretation_added",
    "intent_interpretation_added",
    "complete_history_claimed",
    "complete_graph_coverage_claimed",
    "provider_assertion_promoted",
    "public_service_promoted",
    "scout_reliance_promoted",
    "cmis_promotable",
    "execution_authorized",
)
_REQUIRED_FALSE_MATERIALIZATION_FIELDS = (
    "public_service_promoted",
    "scout_reliance_promoted",
    "ownership_inference_added",
    "beneficial_ownership_inference_added",
    "behavioral_interpretation_added",
    "intent_interpretation_added",
    "execution_authorized",
)


class WalletRelationshipIntelligenceContractError(ValueError):
    """Raised when protected direct-transfer material violates the public contract."""


def _mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WalletRelationshipIntelligenceContractError(f"{name} must be a mapping")
    return value


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise WalletRelationshipIntelligenceContractError(
            f"{name} must be normalized non-empty text"
        )
    return value


def _canonical_utc(name: str, value: Any) -> str:
    text = _text(name, value)
    if not text.endswith("Z"):
        raise WalletRelationshipIntelligenceContractError(
            f"{name} must be canonical UTC ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise WalletRelationshipIntelligenceContractError(
            f"{name} must be canonical UTC ending in Z"
        ) from exc
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != text:
        raise WalletRelationshipIntelligenceContractError(
            f"{name} must be canonical UTC ending in Z"
        )
    return text


def _nonnegative_int_or_none(name: str, value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WalletRelationshipIntelligenceContractError(
            f"{name} must be a non-negative integer or null"
        )
    return value


def _positive_raw_amount(name: str, value: Any) -> str:
    text = _text(name, value)
    if not text.isdigit() or int(text) <= 0:
        raise WalletRelationshipIntelligenceContractError(
            f"{name} must be a positive canonical raw-integer string"
        )
    if str(int(text)) != text:
        raise WalletRelationshipIntelligenceContractError(
            f"{name} must be a positive canonical raw-integer string"
        )
    return text


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise WalletRelationshipIntelligenceContractError(
            "wallet relationship material must be canonical JSON-compatible data"
        ) from exc


def _expected_relationship_id(record: Mapping[str, Any]) -> str:
    material = deepcopy(dict(record))
    material.pop("relationship_evidence_id", None)
    digest = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()
    return f"wr_{digest}"


def validate_wallet_relationship_materialization(value: Any) -> dict[str, Any]:
    """Validate protected materialization without recomputing chain facts."""

    supplied = deepcopy(dict(_mapping("materialization", value)))

    if supplied.get("contract_version") != UPSTREAM_CONTRACT_VERSION:
        raise WalletRelationshipIntelligenceContractError(
            f"materialization must use {UPSTREAM_CONTRACT_VERSION}"
        )
    if supplied.get("chain") != SUPPORTED_CHAIN:
        raise WalletRelationshipIntelligenceContractError(
            "wallet relationship intelligence v1 accepts X1 evidence only"
        )

    signature = _text("transaction_signature", supplied.get("transaction_signature"))
    asset_mint = _text("asset_mint", supplied.get("asset_mint"))
    sender = _text("sender_wallet", supplied.get("sender_wallet"))
    recipient = _text("recipient_wallet", supplied.get("recipient_wallet"))
    if sender == recipient:
        raise WalletRelationshipIntelligenceContractError(
            "sender_wallet and recipient_wallet must be distinct"
        )
    instruction_type = supplied.get("instruction_type")
    if instruction_type not in {"transfer", "transferChecked"}:
        raise WalletRelationshipIntelligenceContractError(
            "instruction_type must be transfer or transferChecked"
        )
    _text("source_token_account", supplied.get("source_token_account"))
    _text("destination_token_account", supplied.get("destination_token_account"))
    amount_raw = _positive_raw_amount("amount_raw", supplied.get("amount_raw"))
    decimals = supplied.get("decimals")
    if isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0:
        raise WalletRelationshipIntelligenceContractError(
            "decimals must be a non-negative integer"
        )
    observed_at = _canonical_utc("observed_at", supplied.get("observed_at"))
    block_slot = _nonnegative_int_or_none("block_slot", supplied.get("block_slot"))

    for field in _REQUIRED_FALSE_MATERIALIZATION_FIELDS:
        if supplied.get(field) is not False:
            raise WalletRelationshipIntelligenceContractError(
                f"protected materialization must keep {field}=false"
            )
    if supplied.get("risk_interpretation") is not None:
        raise WalletRelationshipIntelligenceContractError(
            "protected materialization risk_interpretation must remain null"
        )

    observation = _mapping(
        "wallet_activity_observation", supplied.get("wallet_activity_observation")
    )
    observation_id = observation.get("observation_id")
    if not isinstance(observation_id, str) or not _OBSERVATION_ID_RE.fullmatch(
        observation_id
    ):
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation id must be canonical wa_ content id"
        )
    if observation.get("chain") != SUPPORTED_CHAIN:
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation chain mismatch"
        )
    if observation.get("wallet") != sender:
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation sender mismatch"
        )
    if observation.get("counterparty") != recipient:
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation recipient mismatch"
        )
    if observation.get("activity_type") != "TRANSFER_OUT":
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation must preserve TRANSFER_OUT"
        )
    if observation.get("asset_id") != asset_mint:
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation asset mismatch"
        )
    if observation.get("transaction_signature") != signature:
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation transaction mismatch"
        )
    if observation.get("observed_at") != observed_at:
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation fact-time mismatch"
        )
    if observation.get("block_slot") != block_slot:
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation block-slot mismatch"
        )
    if observation.get("asset_amount") != amount_raw:
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation amount mismatch"
        )
    if observation.get("asset_unit") != "raw-token-units":
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation unit mismatch"
        )
    if observation.get("source") != SOURCE:
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation source must be X1 RPC"
        )
    if observation.get("verification_method") != VERIFICATION_METHOD:
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation verification method mismatch"
        )
    if observation.get("evidence_scope") != EVIDENCE_SCOPE:
        raise WalletRelationshipIntelligenceContractError(
            "wallet activity observation evidence scope mismatch"
        )
    verification = _mapping(
        "wallet_activity_observation.verification", observation.get("verification")
    )
    for field in (
        "wallet_identity_verified",
        "asset_identity_verified",
        "transaction_identity_verified",
        "amount_verified",
        "transfer_direction_verified",
        "token_account_ownership_verified",
        "counterparty_verified",
    ):
        if verification.get(field) is not True:
            raise WalletRelationshipIntelligenceContractError(
                f"wallet activity observation requires {field}=true"
            )

    relationship = _mapping(
        "relationship_evidence", supplied.get("relationship_evidence")
    )
    relationship_id = relationship.get("relationship_evidence_id")
    if not isinstance(relationship_id, str) or not _RELATIONSHIP_ID_RE.fullmatch(
        relationship_id
    ):
        raise WalletRelationshipIntelligenceContractError(
            "relationship_evidence_id must be canonical wr_ content id"
        )
    if relationship_id != _expected_relationship_id(relationship):
        raise WalletRelationshipIntelligenceContractError(
            "relationship_evidence_id does not bind canonical relationship material"
        )
    expected_equal = {
        "schema": RELATIONSHIP_SCHEMA,
        "relationship_kind": RELATIONSHIP_KIND,
        "interaction_type": INTERACTION_TYPE,
        "chain": SUPPORTED_CHAIN,
        "asset_id": asset_mint,
        "sender": sender,
        "recipient": recipient,
        "transaction_signature": signature,
        "observed_at": observed_at,
        "block_slot": block_slot,
        "asset_amount": amount_raw,
        "asset_unit": "raw-token-units",
        "source": SOURCE,
        "verification_method": VERIFICATION_METHOD,
        "evidence_scope": EVIDENCE_SCOPE,
    }
    for field, expected in expected_equal.items():
        if relationship.get(field) != expected:
            raise WalletRelationshipIntelligenceContractError(
                f"relationship evidence {field} mismatch"
            )

    evidence = _mapping("relationship_evidence.evidence", relationship.get("evidence"))
    if evidence.get("wallet_activity_observation_id") != observation_id:
        raise WalletRelationshipIntelligenceContractError(
            "relationship evidence must bind the preserved wallet activity observation"
        )
    for field in (
        "wallet_activity_revalidated",
        "wallet_identity_verified",
        "counterparty_verified",
        "asset_identity_verified",
        "transaction_identity_verified",
        "transfer_direction_verified",
    ):
        if evidence.get(field) is not True:
            raise WalletRelationshipIntelligenceContractError(
                f"relationship evidence requires {field}=true"
            )
    if evidence.get("evidence_receipt_binding_available") is not False:
        raise WalletRelationshipIntelligenceContractError(
            "wallet relationship foundation must not invent Evidence Receipt binding"
        )
    if evidence.get("evidence_receipt_ids") != []:
        raise WalletRelationshipIntelligenceContractError(
            "wallet relationship foundation must not invent Evidence Receipt ids"
        )
    if evidence.get("proof_score_binding_available") is not False:
        raise WalletRelationshipIntelligenceContractError(
            "wallet relationship foundation must not invent Proof Score binding"
        )
    if evidence.get("proof_score_records") != []:
        raise WalletRelationshipIntelligenceContractError(
            "wallet relationship foundation must not invent Proof Score records"
        )

    for field in _REQUIRED_FALSE_RELATIONSHIP_FIELDS:
        if relationship.get(field) is not False:
            raise WalletRelationshipIntelligenceContractError(
                f"relationship evidence must keep {field}=false"
            )
    if relationship.get("risk_interpretation") is not None:
        raise WalletRelationshipIntelligenceContractError(
            "relationship evidence risk_interpretation must remain null"
        )
    if relationship.get("proof_strength_separate_from_risk") is not True:
        raise WalletRelationshipIntelligenceContractError(
            "relationship evidence must keep Proof Score separate from risk"
        )

    limitations = relationship.get("limitations")
    if not isinstance(limitations, list) or not limitations:
        raise WalletRelationshipIntelligenceContractError(
            "relationship evidence limitations must be a non-empty list"
        )
    required_limitations = {
        "observed_direct_interaction_only",
        "ownership_not_inferred",
        "beneficial_ownership_not_inferred",
        "behavior_intent_and_risk_not_inferred",
        "complete_wallet_history_not_proven",
        "complete_relationship_graph_not_proven",
        "missing_amounts_are_not_zero_filled",
    }
    if not required_limitations.issubset(set(limitations)):
        raise WalletRelationshipIntelligenceContractError(
            "relationship evidence is missing required truth-boundary limitations"
        )
    return supplied


def build_wallet_relationship_intelligence_response(
    materialization: Any,
) -> dict[str, Any]:
    """Project one verified direct interaction into a public CMIS envelope."""

    validated = validate_wallet_relationship_materialization(materialization)
    relationship = validated["relationship_evidence"]

    data = {
        "contract_version": CONTRACT_VERSION,
        "relationship_kind": relationship["relationship_kind"],
        "interaction_type": relationship["interaction_type"],
        "asset_mint": validated["asset_mint"],
        "sender_wallet": validated["sender_wallet"],
        "recipient_wallet": validated["recipient_wallet"],
        "transaction_signature": validated["transaction_signature"],
        "observed_at": validated["observed_at"],
        "block_slot": validated["block_slot"],
        "amount_raw": validated["amount_raw"],
        "decimals": validated["decimals"],
        "source_token_account": validated["source_token_account"],
        "destination_token_account": validated["destination_token_account"],
        "relationship_evidence_id": relationship["relationship_evidence_id"],
        "wallet_activity_observation_id": relationship["evidence"][
            "wallet_activity_observation_id"
        ],
        "evidence_scope": relationship["evidence_scope"],
        "evidence_receipt_binding_available": False,
        "proof_score_binding_available": False,
        "proof_strength_separate_from_risk": True,
        "ownership_inference_added": False,
        "beneficial_ownership_inference_added": False,
        "behavioral_interpretation_added": False,
        "intent_interpretation_added": False,
        "risk_interpretation": None,
        "complete_history_claimed": False,
        "complete_graph_coverage_claimed": False,
        "execution_authorized": False,
        "limitations": list(relationship["limitations"]),
    }

    return build_service_envelope(
        SERVICE,
        SUPPORTED_CHAIN,
        OK,
        asset={"id": validated["asset_mint"], "id_kind": "mint"},
        data=data,
        risk=None,
        confidence={
            "proof_score_available": False,
            "proof_score_separate_from_risk": True,
            "basis": "deterministically_revalidated_direct_transfer_evidence",
        },
        sources=[
            {
                "source": SOURCE,
                "verification_method": VERIFICATION_METHOD,
                "transaction_signature": validated["transaction_signature"],
            }
        ],
        observed_at=validated["observed_at"],
        freshness={
            "freshness_state": "NOT_APPLICABLE",
            "reason": "historical_finalized_transaction_fact",
        },
        warnings=list(relationship["limitations"]),
        errors=[],
    )


__all__ = [
    "CONTRACT_VERSION",
    "INTERACTION_TYPE",
    "RELATIONSHIP_KIND",
    "SERVICE",
    "SUPPORTED_CHAIN",
    "UPSTREAM_CONTRACT_VERSION",
    "WalletRelationshipIntelligenceContractError",
    "build_wallet_relationship_intelligence_response",
    "validate_wallet_relationship_materialization",
]
