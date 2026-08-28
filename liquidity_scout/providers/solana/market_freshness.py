"""Deterministic Solana market-freshness evidence classification.

This module never selects a current price. It keeps CMIS collection time,
provider fact time, Solana block identity, and freshness policy as separate
proof dimensions.

Accepted provider-owned semantics:
- Jupiter Price V3 blockId is the Solana block/slot when the price was computed.
- Jupiter createdAt is token creation metadata, not price observation time.
- The accepted DEX Screener token-pairs schema exposes pairCreatedAt but no
  documented market-fact update timestamp.

No freshness thresholds live here. Until a separately accepted policy provides
explicit max-age/future-skew provenance, freshness_verified and
current_price_promotable remain false.
"""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

from liquidity_scout.providers.solana.jupiter_freshness_policy import (
    accepted_solana_jupiter_freshness_policy,
    classify_solana_jupiter_freshness,
)

CHAIN = "solana"
JUPITER_SOURCE = "jupiter_price_v3"
DEXSCREENER_SOURCE = "dexscreener_token_pairs_v1"
RPC_SOURCE = "solana_rpc"
VERSION = "solana_market_freshness/v1"

JUPITER_BLOCK_ID_PROVENANCE = (
    "https://developers.jup.ag/docs/guides/how-to-get-token-price"
)
DEXSCREENER_SCHEMA_PROVENANCE = "https://docs.dexscreener.com/api/reference"
SOLANA_BLOCK_TIME_PROVENANCE = "https://solana.com/docs/rpc/http/getblocktime"


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _timestamp(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        return None
    return parsed


def _collection_evidence(record: Mapping[str, Any]) -> dict[str, Any]:
    started = _timestamp(record.get("collection_started_at_unix"))
    completed = _timestamp(record.get("collection_completed_at_unix"))
    verified = (
        record.get("collection_time_verified") is True
        and started is not None
        and completed is not None
        and completed >= started
    )
    return {
        "collection_started_at_unix": started,
        "collection_completed_at_unix": completed,
        "collection_time_verified": verified,
    }


def build_solana_market_freshness_evidence(
    jupiter: Mapping[str, Any],
    dexscreener: Mapping[str, Any],
    *,
    block_time_record: Mapping[str, Any] | None = None,
    reference_slot_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return bounded freshness evidence without applying a freshness policy."""

    if not isinstance(jupiter, Mapping) or not isinstance(dexscreener, Mapping):
        raise TypeError("Solana freshness inputs must be mappings")

    limitations: list[str] = []

    jupiter_collection = _collection_evidence(jupiter)
    dex_collection = _collection_evidence(dexscreener)

    mint = _text(jupiter.get("mint"))
    identity_verified = bool(
        jupiter.get("chain") == CHAIN
        and dexscreener.get("chain") == CHAIN
        and jupiter.get("source") == JUPITER_SOURCE
        and dexscreener.get("source") == DEXSCREENER_SOURCE
        and mint is not None
        and _text(dexscreener.get("mint")) == mint
    )

    block_id = _nonnegative_int(jupiter.get("block_id"))
    block_id_semantics_verified = bool(
        identity_verified
        and jupiter.get("price_available") is True
        and block_id is not None
    )

    block_time_unix: int | None = None
    block_time_verified = False
    if isinstance(block_time_record, Mapping):
        candidate = _nonnegative_int(block_time_record.get("block_time_unix"))
        block_time_verified = bool(
            block_id_semantics_verified
            and block_time_record.get("chain") == CHAIN
            and block_time_record.get("source") == RPC_SOURCE
            and block_time_record.get("method") == "getBlockTime"
            and block_time_record.get("block_time_verified") is True
            and block_time_record.get("block_id") == block_id
            and candidate is not None
        )
        if block_time_verified:
            block_time_unix = candidate

    reference_slot: int | None = None
    reference_slot_verified = False
    reference_commitment = None
    if isinstance(reference_slot_record, Mapping):
        candidate_slot = _nonnegative_int(reference_slot_record.get("slot"))
        reference_commitment = _text(reference_slot_record.get("commitment"))
        reference_slot_verified = bool(
            reference_slot_record.get("chain") == CHAIN
            and reference_slot_record.get("source") == RPC_SOURCE
            and reference_slot_record.get("method") == "getSlot"
            and reference_slot_record.get("slot_verified") is True
            and candidate_slot is not None
            and reference_commitment is not None
        )
        if reference_slot_verified:
            reference_slot = candidate_slot

    block_at_or_before_reference_slot = (
        bool(
            block_id is not None
            and reference_slot is not None
            and block_id <= reference_slot
        )
        if reference_slot_verified
        else False
    )

    chain_block_identity_verified = bool(
        block_id_semantics_verified and block_time_verified
    )

    finality_verified = False
    if chain_block_identity_verified:
        limitations.append("jupiter_block_finality_not_proven_by_get_block_time")

    if not reference_slot_verified:
        limitations.append("solana_reference_slot_unavailable")
    elif not block_at_or_before_reference_slot:
        limitations.append("jupiter_block_after_reference_slot")

    provider_fact_time_verified = chain_block_identity_verified
    fact_age_seconds_candidate: float | None = None
    fact_age_computable = False
    if (
        provider_fact_time_verified
        and jupiter_collection["collection_time_verified"] is True
        and block_time_unix is not None
    ):
        completed = jupiter_collection["collection_completed_at_unix"]
        assert completed is not None
        if float(block_time_unix) <= completed:
            fact_age_seconds_candidate = completed - float(block_time_unix)
            fact_age_computable = True
        else:
            limitations.append("jupiter_block_time_after_collection_clock")

    dex_provider_fact_time_verified = False
    limitations.append("dexscreener_market_fact_timestamp_unavailable")

    evidence = {
        "service": "solana_market_freshness",
        "version": VERSION,
        "chain": CHAIN,
        "mint": mint,
        "identity_verified": identity_verified,
        "jupiter": {
            **jupiter_collection,
            "block_id": block_id,
            "block_id_semantics_verified": block_id_semantics_verified,
            "block_id_semantics_provenance": JUPITER_BLOCK_ID_PROVENANCE,
            "token_created_at_used_for_freshness": False,
            "chain_block_identity_verified": chain_block_identity_verified,
            "block_time_unix": block_time_unix,
            "block_time_verified": block_time_verified,
            "block_time_provenance": SOLANA_BLOCK_TIME_PROVENANCE,
            "reference_slot": reference_slot,
            "reference_slot_verified": reference_slot_verified,
            "reference_commitment": reference_commitment,
            "block_at_or_before_reference_slot": block_at_or_before_reference_slot,
            "finality_verified": finality_verified,
            "provider_fact_time_unix": (
                block_time_unix if provider_fact_time_verified else None
            ),
            "provider_fact_time_verified": provider_fact_time_verified,
            "fact_age_seconds_candidate": fact_age_seconds_candidate,
            "fact_age_computable": fact_age_computable,
        },
        "dexscreener": {
            **dex_collection,
            "pair_created_at_used_for_freshness": False,
            "market_fact_timestamp_field": None,
            "market_fact_timestamp_semantics_verified": False,
            "provider_fact_time_unix": None,
            "provider_fact_time_verified": dex_provider_fact_time_verified,
            "schema_provenance": DEXSCREENER_SCHEMA_PROVENANCE,
        },
        "cross_source_time_identity_verified": False,
        "freshness_policy_complete": False,
        "freshness_verified": False,
        "current_price_promotable": False,
        "max_age_seconds": None,
        "max_future_skew_seconds": None,
        "limitations": list(dict.fromkeys(limitations)),
    }

    jupiter_policy_result = classify_solana_jupiter_freshness(
        evidence,
        policy=accepted_solana_jupiter_freshness_policy(),
    )
    evidence["jupiter_freshness"] = jupiter_policy_result
    evidence["freshness_policy_complete"] = (
        jupiter_policy_result["policy"]["policy_complete"] is True
    )
    evidence["max_age_seconds"] = jupiter_policy_result["policy"]["max_age_seconds"]
    evidence["max_future_skew_seconds"] = (
        jupiter_policy_result["policy"]["max_future_skew_seconds"]
    )
    # The shared market freshness flag remains false because DEX Screener still
    # lacks a verified market-fact timestamp and cross-source time identity.
    evidence["freshness_verified"] = False
    evidence["current_price_promotable"] = False
    return evidence


__all__ = [
    "CHAIN",
    "DEXSCREENER_SCHEMA_PROVENANCE",
    "JUPITER_BLOCK_ID_PROVENANCE",
    "SOLANA_BLOCK_TIME_PROVENANCE",
    "VERSION",
    "build_solana_market_freshness_evidence",
]
