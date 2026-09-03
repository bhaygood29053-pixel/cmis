"""Bounded semantics for the official Warp wallet-history response.

This adapter accepts only semantics directly supported by the connected
official History API plus previously accepted exact Warp route/config evidence.

Important:
- wallet identifiers are never returned;
- symbol text never becomes identity by itself;
- provider status "executed" is not enough to create a settled flow event;
- destination settlement time must come from separate canonical X1 RPC proof;
- wallet-scoped history never establishes route-wide coverage.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from liquidity_scout.services.cmis_bridge_route_evidence import (
    WARP_QUALIFICATION_CONTRACT,
)

CONTRACT = "warp_wallet_history_semantics/v1"
DESTINATION_SETTLEMENT_CONTRACT = "warp_destination_rpc_settlement/v1"
EXACT_RESPONSE_CANONICAL_SHA256 = (
    "e309a68509b631002c46526e772ac0b40d2381a21ff2bef46c7c56cbaa4dcca5"
)
SANITIZED_FIXTURE_CANONICAL_SHA256 = (
    "e4e94c4086cf92736d018367ac4edaee809b96cbda5387d600917ff4008e2195"
)
OBSERVED_PROVIDER_SOURCE = "sqlite"
OBSERVED_STATUSES = frozenset({"executed", "signing"})
CHAIN_ALIASES = {"sol": "solana", "x1": "x1"}


class WarpWalletHistorySemanticError(ValueError):
    """Raised when the response cannot be bound to one exact accepted route."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WarpWalletHistorySemanticError(f"{field} must be a mapping")
    return value


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise WarpWalletHistorySemanticError(f"{field} is required")
    return text


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise WarpWalletHistorySemanticError(f"{field} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise WarpWalletHistorySemanticError(f"{field} must be an integer") from exc
    if parsed < 0:
        raise WarpWalletHistorySemanticError(f"{field} must be nonnegative")
    return parsed


def _positive_int(value: Any, field: str) -> int:
    parsed = _nonnegative_int(value, field)
    if parsed <= 0:
        raise WarpWalletHistorySemanticError(f"{field} must be positive")
    return parsed


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sanitize_wallet_history_response(response: Any) -> dict[str, Any]:
    document = dict(_mapping(response, "response"))
    document["wallet"] = "<redacted>"
    transactions = document.get("transactions")
    if isinstance(transactions, list):
        sanitized = []
        for raw in transactions:
            if not isinstance(raw, Mapping):
                sanitized.append(raw)
                continue
            item = dict(raw)
            if "sender" in item:
                item["sender"] = "<redacted>"
            if "recipient" in item:
                item["recipient"] = "<redacted>"
            sanitized.append(item)
        document["transactions"] = sanitized
    return document


def _qualified_route(value: Any) -> dict[str, Any]:
    qualification = _mapping(value, "route_qualification")
    if qualification.get("contract") != WARP_QUALIFICATION_CONTRACT:
        raise WarpWalletHistorySemanticError(
            f"route_qualification must use {WARP_QUALIFICATION_CONTRACT}"
        )
    if qualification.get("warp_qualified") is not True:
        raise WarpWalletHistorySemanticError("route must be Warp-qualified")
    evidence = _mapping(qualification.get("route_evidence"), "route_evidence")
    if evidence.get("qualified") is not True:
        raise WarpWalletHistorySemanticError("route evidence must be qualified")

    source = _mapping(evidence.get("source"), "route source")
    destination = _mapping(evidence.get("destination"), "route destination")
    return {
        "route_id": _text(evidence.get("route_id"), "route_id"),
        "source": {
            "chain": _text(source.get("chain"), "source.chain").casefold(),
            "asset_id": _text(source.get("asset_id"), "source.asset_id"),
            "asset_id_kind": _text(
                source.get("asset_id_kind"), "source.asset_id_kind"
            ).casefold(),
        },
        "destination": {
            "chain": _text(destination.get("chain"), "destination.chain").casefold(),
            "asset_id": _text(destination.get("asset_id"), "destination.asset_id"),
            "asset_id_kind": _text(
                destination.get("asset_id_kind"), "destination.asset_id_kind"
            ).casefold(),
        },
        "route_evidence_id": evidence.get("evidence_id"),
    }


def _exact_config_token(
    config_response: Any,
    *,
    chain: str,
    mint: str,
) -> Mapping[str, Any]:
    document = _mapping(config_response, "config_response")
    block = _mapping(document.get(chain), f"config_response.{chain}")
    tokens = block.get("tokens")
    if not isinstance(tokens, list):
        raise WarpWalletHistorySemanticError(f"{chain}.tokens must be a list")
    matches = [
        item
        for item in tokens
        if isinstance(item, Mapping)
        and str(item.get("mint") or "").strip() == mint
    ]
    if len(matches) != 1:
        raise WarpWalletHistorySemanticError(
            f"exact config mint {mint} must resolve once on {chain}"
        )
    token = matches[0]
    _text(token.get("symbol"), f"{chain}.token.symbol")
    _positive_int(token.get("decimals"), f"{chain}.token.decimals")
    return token


def _positive_millisecond_timestamp(value: Any, field: str) -> tuple[int, float]:
    timestamp_ms = _positive_int(value, field)
    if timestamp_ms < 1_000_000_000_000:
        raise WarpWalletHistorySemanticError(
            f"{field} must be Unix milliseconds"
        )
    return timestamp_ms, timestamp_ms / 1000.0


def _destination_reference(raw: Mapping[str, Any]) -> dict[str, Any]:
    dest_tx_sig = str(raw.get("destTxSig") or "").strip()
    submission_tx_sig = str(raw.get("submissionTxSig") or "").strip()
    try:
        dest_slot = _nonnegative_int(raw.get("destSlot", 0), "destSlot")
        submission_slot = _nonnegative_int(
            raw.get("submissionSlot", 0), "submissionSlot"
        )
    except WarpWalletHistorySemanticError:
        dest_slot = 0
        submission_slot = 0

    return {
        "destination_tx_signature": dest_tx_sig or None,
        "submission_tx_signature": submission_tx_sig or None,
        "destination_slot": dest_slot or None,
        "submission_slot": submission_slot or None,
        "tx_signature_match": bool(
            dest_tx_sig
            and submission_tx_sig
            and dest_tx_sig == submission_tx_sig
        ),
        "slot_match": bool(
            dest_slot > 0
            and submission_slot > 0
            and dest_slot == submission_slot
        ),
    }


def analyze_warp_wallet_history_response(
    *,
    response: Any,
    route_qualification: Any,
    config_response: Any,
) -> dict[str, Any]:
    """Bind one wallet-scoped response to one exact accepted Warp route."""

    document = _mapping(response, "response")
    route = _qualified_route(route_qualification)

    source_chain = route["source"]["chain"]
    destination_chain = route["destination"]["chain"]
    if source_chain != "solana" or destination_chain != "x1":
        raise WarpWalletHistorySemanticError(
            "v1 accepts only observed Solana -> X1 wallet-history semantics"
        )
    if route["source"]["asset_id_kind"] != "mint":
        raise WarpWalletHistorySemanticError("source identity kind must be mint")
    if route["destination"]["asset_id_kind"] != "mint":
        raise WarpWalletHistorySemanticError("destination identity kind must be mint")

    source_token = _exact_config_token(
        config_response,
        chain=source_chain,
        mint=route["source"]["asset_id"],
    )
    destination_token = _exact_config_token(
        config_response,
        chain=destination_chain,
        mint=route["destination"]["asset_id"],
    )
    source_decimals = _positive_int(source_token.get("decimals"), "source decimals")
    destination_decimals = _positive_int(
        destination_token.get("decimals"), "destination decimals"
    )
    if source_decimals != destination_decimals:
        raise WarpWalletHistorySemanticError(
            "source/destination route decimals must match"
        )

    wallet = _text(document.get("wallet"), "wallet")
    provider_source = _text(document.get("source"), "source")
    if provider_source != OBSERVED_PROVIDER_SOURCE:
        raise WarpWalletHistorySemanticError(
            f"provider source must equal observed {OBSERVED_PROVIDER_SOURCE}"
        )

    transactions = document.get("transactions")
    if not isinstance(transactions, list):
        raise WarpWalletHistorySemanticError("transactions must be a list")
    count = _nonnegative_int(document.get("count"), "count")
    count_matches = count == len(transactions)

    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(transactions):
        if not isinstance(raw, Mapping):
            raise WarpWalletHistorySemanticError(
                f"transactions[{index}] must be a mapping"
            )

        tx_sig = _text(raw.get("txSig"), f"transactions[{index}].txSig")
        from_alias = _text(raw.get("from"), f"transactions[{index}].from").casefold()
        to_alias = _text(raw.get("to"), f"transactions[{index}].to").casefold()
        if CHAIN_ALIASES.get(from_alias) != source_chain:
            raise WarpWalletHistorySemanticError(
                f"transactions[{index}] source chain does not match exact route"
            )
        if CHAIN_ALIASES.get(to_alias) != destination_chain:
            raise WarpWalletHistorySemanticError(
                f"transactions[{index}] destination chain does not match exact route"
            )

        token_label = _text(raw.get("token"), f"transactions[{index}].token")
        if token_label != str(source_token["symbol"]):
            raise WarpWalletHistorySemanticError(
                f"transactions[{index}] token label does not match exact source mint"
            )

        amount_raw = _positive_int(
            raw.get("amount"), f"transactions[{index}].amount"
        )
        timestamp_ms, provider_timestamp = _positive_millisecond_timestamp(
            raw.get("timestamp"), f"transactions[{index}].timestamp"
        )
        status = _text(
            raw.get("status"), f"transactions[{index}].status"
        ).casefold()
        if status not in OBSERVED_STATUSES:
            raise WarpWalletHistorySemanticError(
                f"transactions[{index}] status is outside observed v1 semantics"
            )

        source_slot = _nonnegative_int(
            raw.get("sourceSlot"), f"transactions[{index}].sourceSlot"
        )
        slot_alias = _nonnegative_int(
            raw.get("slot"), f"transactions[{index}].slot"
        )
        signatures_collected = _nonnegative_int(
            raw.get("signaturesCollected"),
            f"transactions[{index}].signaturesCollected",
        )
        signatures_required = _positive_int(
            raw.get("signaturesRequired"),
            f"transactions[{index}].signaturesRequired",
        )
        destination = _destination_reference(raw)

        sender = str(raw.get("sender") or "").strip()
        recipient = str(raw.get("recipient") or "").strip()
        wallet_echo_consistent = bool(
            sender
            and recipient
            and sender == wallet
            and recipient == wallet
        )

        source_reference_consistent = bool(
            source_slot > 0 and slot_alias > 0 and source_slot == slot_alias
        )
        quorum_reached = signatures_collected >= signatures_required
        destination_reference_complete = bool(
            destination["tx_signature_match"]
            and destination["slot_match"]
        )
        provider_execution_evidence_present = bool(
            status == "executed"
            and source_reference_consistent
            and quorum_reached
            and destination_reference_complete
        )

        normalized.append(
            {
                "event_id": tx_sig,
                "source_tx_signature": tx_sig,
                "route_id": route["route_id"],
                "source": route["source"],
                "destination": route["destination"],
                "direction": "inflow",
                "token_label": token_label,
                "amount_raw": amount_raw,
                "decimals": source_decimals,
                "provider_status": status,
                "provider_timestamp_ms": timestamp_ms,
                "provider_timestamp": provider_timestamp,
                "provider_timestamp_role": (
                    "transaction_timestamp_not_destination_settlement_time"
                ),
                "source_slot": source_slot or None,
                "source_slot_alias": slot_alias or None,
                "source_reference_consistent": source_reference_consistent,
                "signatures_collected": signatures_collected,
                "signatures_required": signatures_required,
                "guardian_quorum_reached": quorum_reached,
                **destination,
                "wallet_echo_consistent": wallet_echo_consistent,
                "provider_execution_evidence_present": (
                    provider_execution_evidence_present
                ),
                "settlement_verified": False,
                "pairing_verified": False,
                "settled_at": None,
                "flow_event_eligible": False,
            }
        )

    sanitized = sanitize_wallet_history_response(document)
    return {
        "contract": CONTRACT,
        "provider": "warp_bridge",
        "route_id": route["route_id"],
        "route_evidence_id": route["route_evidence_id"],
        "source": route["source"],
        "destination": route["destination"],
        "source_token_symbol": str(source_token["symbol"]),
        "destination_token_symbol": str(destination_token["symbol"]),
        "decimals": source_decimals,
        "provider_storage_label": provider_source,
        "wallet_scope_present": True,
        "wallet_identifier_retained": False,
        "sender_recipient_identifiers_retained": False,
        "response_count": count,
        "response_count_matches_list": count_matches,
        "transactions": normalized,
        "exact_response_canonical_sha256": canonical_sha256(document),
        "sanitized_response_canonical_sha256": canonical_sha256(sanitized),
        "route_wide_coverage_verified": False,
        "pagination_coverage_verified": False,
        "source_independence_verified": False,
        "live_flow_normalization_authorized": False,
        "read_only": True,
        "execution_authorized": False,
    }


def build_verified_settled_flow_event(
    *,
    transaction_semantics: Any,
    destination_rpc_evidence: Any,
) -> dict[str, Any]:
    """Promote one executed provider record only after canonical X1 RPC proof."""

    transaction = _mapping(transaction_semantics, "transaction_semantics")
    rpc = _mapping(destination_rpc_evidence, "destination_rpc_evidence")

    if rpc.get("contract") != DESTINATION_SETTLEMENT_CONTRACT:
        raise WarpWalletHistorySemanticError(
            f"destination proof must use {DESTINATION_SETTLEMENT_CONTRACT}"
        )
    if transaction.get("provider_status") != "executed":
        raise WarpWalletHistorySemanticError(
            "only provider executed transactions can be settlement candidates"
        )
    if transaction.get("provider_execution_evidence_present") is not True:
        raise WarpWalletHistorySemanticError(
            "provider execution references are incomplete"
        )

    expected_sig = _text(
        transaction.get("destination_tx_signature"),
        "destination_tx_signature",
    )
    expected_slot = _positive_int(
        transaction.get("destination_slot"), "destination_slot"
    )
    if _text(rpc.get("transaction_signature"), "rpc transaction_signature") != expected_sig:
        raise WarpWalletHistorySemanticError(
            "RPC transaction signature does not match provider destination signature"
        )
    if _positive_int(rpc.get("slot"), "rpc slot") != expected_slot:
        raise WarpWalletHistorySemanticError(
            "RPC slot does not match provider destination slot"
        )
    required_true = (
        "transaction_found",
        "transaction_succeeded",
        "finalized",
        "block_time_verified",
    )
    for field in required_true:
        if rpc.get(field) is not True:
            raise WarpWalletHistorySemanticError(
                f"destination RPC evidence requires {field}=true"
            )
    block_time = rpc.get("block_time")
    if isinstance(block_time, bool):
        raise WarpWalletHistorySemanticError("block_time must be numeric")
    try:
        settled_at = float(block_time)
    except (TypeError, ValueError) as exc:
        raise WarpWalletHistorySemanticError("block_time must be numeric") from exc
    if settled_at <= 0:
        raise WarpWalletHistorySemanticError("block_time must be positive")

    transfer_core = {
        "route_id": transaction["route_id"],
        "source_tx_signature": transaction["source_tx_signature"],
        "destination_tx_signature": expected_sig,
        "destination_slot": expected_slot,
    }
    transfer_id = "warp_" + canonical_sha256(transfer_core)[:32]

    return {
        "event_id": transaction["event_id"],
        "transfer_id": transfer_id,
        "route_id": transaction["route_id"],
        "direction": transaction["direction"],
        "amount_raw": transaction["amount_raw"],
        "decimals": transaction["decimals"],
        "settled_at": settled_at,
        "source": transaction["source"],
        "destination": transaction["destination"],
        "lifecycle_state": "settled",
        "settlement_verified": True,
        "pairing_verified": True,
        "source_tx_signature": transaction["source_tx_signature"],
        "destination_tx_signature": expected_sig,
        "destination_slot": expected_slot,
        "settlement_source": "canonical_x1_rpc",
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT",
    "DESTINATION_SETTLEMENT_CONTRACT",
    "EXACT_RESPONSE_CANONICAL_SHA256",
    "OBSERVED_STATUSES",
    "SANITIZED_FIXTURE_CANONICAL_SHA256",
    "WarpWalletHistorySemanticError",
    "analyze_warp_wallet_history_response",
    "build_verified_settled_flow_event",
    "canonical_sha256",
    "sanitize_wallet_history_response",
]
