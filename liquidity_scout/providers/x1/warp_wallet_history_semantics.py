"""Corroborative semantics for the official Warp wallet-history response.

The connected History API is wallet-scoped and therefore cannot establish
route-wide flow coverage. It is also not the canonical settled-event authority:
CMIS uses the accepted on-chain `warp_onchain_transfer_history/v1` path for
settled transfer truth.

This adapter preserves useful response semantics without retaining wallet
identifiers or upgrading provider labels/statuses into canonical flow facts.
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
CANONICAL_SETTLEMENT_SOURCE_CONTRACT = "warp_onchain_transfer_history/v1"
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
    """Raised when a wallet-history response cannot be safely contextualized."""


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


def _timestamp_ms(value: Any, field: str) -> tuple[int, float]:
    parsed = _positive_int(value, field)
    if parsed < 1_000_000_000_000:
        raise WarpWalletHistorySemanticError(f"{field} must be Unix milliseconds")
    return parsed, parsed / 1000.0


def analyze_warp_wallet_history_response(
    *,
    response: Any,
    route_qualification: Any,
    config_response: Any,
) -> dict[str, Any]:
    """Contextualize one official wallet-history response without promoting it."""

    document = _mapping(response, "response")
    route = _qualified_route(route_qualification)

    if route["source"]["chain"] != "solana" or route["destination"]["chain"] != "x1":
        raise WarpWalletHistorySemanticError(
            "v1 accepts only observed Solana -> X1 wallet-history direction"
        )
    if route["source"]["asset_id_kind"] != "mint":
        raise WarpWalletHistorySemanticError("source identity kind must be mint")
    if route["destination"]["asset_id_kind"] != "mint":
        raise WarpWalletHistorySemanticError("destination identity kind must be mint")

    source_token = _exact_config_token(
        config_response,
        chain="solana",
        mint=route["source"]["asset_id"],
    )
    destination_token = _exact_config_token(
        config_response,
        chain="x1",
        mint=route["destination"]["asset_id"],
    )
    source_decimals = _positive_int(source_token.get("decimals"), "source decimals")
    destination_decimals = _positive_int(
        destination_token.get("decimals"), "destination decimals"
    )
    if source_decimals != destination_decimals:
        raise WarpWalletHistorySemanticError("route decimals must match")

    wallet = _text(document.get("wallet"), "wallet")
    provider_source = _text(document.get("source"), "source")
    if provider_source != OBSERVED_PROVIDER_SOURCE:
        raise WarpWalletHistorySemanticError(
            f"provider source must equal observed {OBSERVED_PROVIDER_SOURCE}"
        )
    rows = document.get("transactions")
    if not isinstance(rows, list):
        raise WarpWalletHistorySemanticError("transactions must be a list")
    count = _nonnegative_int(document.get("count"), "count")

    normalized = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            raise WarpWalletHistorySemanticError(
                f"transactions[{index}] must be a mapping"
            )

        tx_sig = _text(raw.get("txSig"), f"transactions[{index}].txSig")
        from_alias = _text(raw.get("from"), f"transactions[{index}].from").casefold()
        to_alias = _text(raw.get("to"), f"transactions[{index}].to").casefold()
        if CHAIN_ALIASES.get(from_alias) != "solana":
            raise WarpWalletHistorySemanticError("row source chain is not Solana")
        if CHAIN_ALIASES.get(to_alias) != "x1":
            raise WarpWalletHistorySemanticError("row destination chain is not X1")

        token_label = _text(raw.get("token"), f"transactions[{index}].token")
        if token_label != str(source_token["symbol"]):
            raise WarpWalletHistorySemanticError(
                "provider token label does not match accepted route source symbol"
            )

        provider_amount_integer = _positive_int(
            raw.get("amount"), f"transactions[{index}].amount"
        )
        timestamp_ms, provider_timestamp = _timestamp_ms(
            raw.get("timestamp"), f"transactions[{index}].timestamp"
        )
        status = _text(raw.get("status"), f"transactions[{index}].status").casefold()
        if status not in OBSERVED_STATUSES:
            raise WarpWalletHistorySemanticError(
                "provider status is outside observed response semantics"
            )

        source_slot = _nonnegative_int(
            raw.get("sourceSlot"), f"transactions[{index}].sourceSlot"
        )
        slot_alias = _nonnegative_int(raw.get("slot"), f"transactions[{index}].slot")
        signatures_collected = _nonnegative_int(
            raw.get("signaturesCollected"),
            f"transactions[{index}].signaturesCollected",
        )
        signatures_required = _positive_int(
            raw.get("signaturesRequired"),
            f"transactions[{index}].signaturesRequired",
        )

        dest_sig = str(raw.get("destTxSig") or "").strip() or None
        submission_sig = str(raw.get("submissionTxSig") or "").strip() or None
        dest_slot = _nonnegative_int(raw.get("destSlot", 0), "destSlot") or None
        submission_slot = (
            _nonnegative_int(raw.get("submissionSlot", 0), "submissionSlot") or None
        )

        sender = str(raw.get("sender") or "").strip()
        recipient = str(raw.get("recipient") or "").strip()
        wallet_echo_consistent = bool(
            sender and recipient and sender == wallet and recipient == wallet
        )

        source_reference_consistent = bool(
            source_slot > 0 and slot_alias > 0 and source_slot == slot_alias
        )
        guardian_quorum_reached = signatures_collected >= signatures_required
        destination_reference_complete = bool(
            dest_sig
            and submission_sig
            and dest_sig == submission_sig
            and dest_slot
            and submission_slot
            and dest_slot == submission_slot
        )

        normalized.append(
            {
                "provider_tx_signature": tx_sig,
                "provider_from": from_alias,
                "provider_to": to_alias,
                "provider_token_label": token_label,
                "route_context_id": route["route_id"],
                "route_context_compatible": True,
                "row_exact_mint_identity_verified": False,
                "provider_amount_integer": provider_amount_integer,
                "provider_amount_unit_semantics_verified": False,
                "route_decimals_context": source_decimals,
                "provider_status": status,
                "provider_status_is_settlement_authority": False,
                "provider_timestamp_ms": timestamp_ms,
                "provider_timestamp": provider_timestamp,
                "provider_timestamp_is_settlement_time": False,
                "source_slot": source_slot or None,
                "slot_alias": slot_alias or None,
                "source_reference_consistent": source_reference_consistent,
                "signatures_collected": signatures_collected,
                "signatures_required": signatures_required,
                "guardian_quorum_reached": guardian_quorum_reached,
                "destination_tx_reference_present": bool(dest_sig),
                "destination_slot_reference_present": bool(dest_slot),
                "destination_reference_complete": destination_reference_complete,
                "wallet_echo_consistent": wallet_echo_consistent,
                "flow_event_normalization_authorized": False,
                "execution_authorized": False,
            }
        )

    sanitized = sanitize_wallet_history_response(document)
    return {
        "contract": CONTRACT,
        "provider": "warp_bridge",
        "route_context_id": route["route_id"],
        "route_evidence_id": route["route_evidence_id"],
        "source": route["source"],
        "destination": route["destination"],
        "source_token_symbol": str(source_token["symbol"]),
        "destination_token_symbol": str(destination_token["symbol"]),
        "route_decimals_context": source_decimals,
        "provider_storage_label": provider_source,
        "response_count": count,
        "response_count_matches_list": count == len(rows),
        "transactions": normalized,
        "exact_response_canonical_sha256": canonical_sha256(document),
        "sanitized_response_canonical_sha256": canonical_sha256(sanitized),
        "wallet_identifier_retained": False,
        "sender_recipient_identifiers_retained": False,
        "corroboration_only": True,
        "canonical_settlement_source_contract": (
            CANONICAL_SETTLEMENT_SOURCE_CONTRACT
        ),
        "route_wide_coverage_verified": False,
        "pagination_coverage_verified": False,
        "source_independence_verified": False,
        "flow_event_normalization_authorized": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CANONICAL_SETTLEMENT_SOURCE_CONTRACT",
    "CONTRACT",
    "EXACT_RESPONSE_CANONICAL_SHA256",
    "OBSERVED_STATUSES",
    "SANITIZED_FIXTURE_CANONICAL_SHA256",
    "WarpWalletHistorySemanticError",
    "analyze_warp_wallet_history_response",
    "canonical_sha256",
    "sanitize_wallet_history_response",
]
