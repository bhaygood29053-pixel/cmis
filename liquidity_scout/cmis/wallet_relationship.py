"""Deterministic direct wallet-relationship evidence for CMIS.

This module builds only observed direct transfer relationships from canonical,
revalidated CMIS wallet-activity observations. It does not infer ownership,
beneficial ownership, behavior, intent, risk, or complete graph/history coverage,
and it does not authorize public-service promotion, Scout reliance, or execution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Callable

from liquidity_scout.cmis.wallet_activity import summarize_wallet_activity


SCHEMA_VERSION = 1
SCHEMA = "cmis_wallet_relationship_evidence.v1"
SUMMARY_SCHEMA = "cmis_wallet_relationship_summary.v1"
RELATIONSHIP_KIND = "observed_direct_interaction"
INTERACTION_TYPE = "verified_token_transfer"
_RELATIONSHIP_ID_RE = re.compile(r"^wr_[0-9a-f]{64}$")
_SUMMARY_ID_RE = re.compile(r"^wrs_[0-9a-f]{64}$")
_OBSERVATION_ID_RE = re.compile(r"^wa_[0-9a-f]{64}$")
_TRANSFER_TYPES = frozenset({"TRANSFER_IN", "TRANSFER_OUT"})
_STANDARD_LIMITATIONS = (
    "observed_direct_interaction_only",
    "ownership_not_inferred",
    "beneficial_ownership_not_inferred",
    "behavior_intent_and_risk_not_inferred",
    "complete_wallet_history_not_proven",
    "complete_relationship_graph_not_proven",
    "missing_amounts_are_not_zero_filled",
    "wallet_activity_source_does_not_embed_evidence_receipt_or_proof_score",
)


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _content_id(prefix: str, value: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


def _normalize_observation_id(value: Any) -> str:
    if not isinstance(value, str) or not _OBSERVATION_ID_RE.fullmatch(value):
        raise ValueError("wallet_activity_observation_id must be a canonical wa_ content id")
    return value


def _resolve_wallet_activity(
    wallet_activity_observation_id: Any,
    *,
    observation_resolver: Callable[[str], Any] | None,
) -> dict[str, Any]:
    observation_id = _normalize_observation_id(wallet_activity_observation_id)
    if not callable(observation_resolver):
        raise ValueError("a trusted internal wallet-activity observation resolver is required")
    try:
        resolved = observation_resolver(observation_id)
    except Exception as exc:
        raise ValueError(
            "trusted internal wallet-activity observation resolution failed: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    if resolved is None:
        raise ValueError("the requested CMIS wallet-activity observation was not found")
    if not isinstance(resolved, Mapping):
        raise ValueError("resolved CMIS wallet-activity observation must be a mapping")

    # Reuse the accepted public wallet-activity aggregation boundary to force a
    # complete deterministic rebuild of the observation before relationship use.
    summary = summarize_wallet_activity(
        chain=resolved.get("chain"),
        wallet=resolved.get("wallet"),
        observations=[resolved],
    )
    observations = summary.get("observations")
    if not isinstance(observations, list) or len(observations) != 1:
        raise ValueError("resolved CMIS wallet-activity observation could not be revalidated")
    record = observations[0]
    if record.get("observation_id") != observation_id:
        raise ValueError(
            "resolved CMIS wallet-activity observation does not match the requested id"
        )
    return record


def _relationship_parties(record: Mapping[str, Any]) -> tuple[str, str]:
    activity_type = record.get("activity_type")
    if activity_type not in _TRANSFER_TYPES:
        raise ValueError(
            "wallet relationship evidence accepts only verified TRANSFER_IN/TRANSFER_OUT facts"
        )
    verification = record.get("verification")
    if not isinstance(verification, Mapping):
        raise ValueError("wallet activity verification object is required")
    if verification.get("transfer_direction_verified") is not True:
        raise ValueError("direct wallet relationship requires verified transfer direction")
    if verification.get("counterparty_verified") is not True:
        raise ValueError("direct wallet relationship requires verified counterparty identity")

    wallet = record.get("wallet")
    counterparty = record.get("counterparty")
    if not isinstance(wallet, str) or not wallet:
        raise ValueError("direct wallet relationship requires exact wallet identity")
    if not isinstance(counterparty, str) or not counterparty:
        raise ValueError("direct wallet relationship requires exact counterparty identity")

    if activity_type == "TRANSFER_OUT":
        return wallet, counterparty
    return counterparty, wallet


def _boundary_fields() -> dict[str, Any]:
    return {
        "ownership_inference_added": False,
        "beneficial_ownership_inference_added": False,
        "behavioral_interpretation_added": False,
        "intent_interpretation_added": False,
        "risk_interpretation": None,
        "proof_strength_separate_from_risk": True,
        "complete_history_claimed": False,
        "complete_graph_coverage_claimed": False,
        "provider_assertion_promoted": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def build_direct_wallet_relationship(
    wallet_activity_observation_id: Any,
    *,
    observation_resolver: Callable[[str], Any] | None,
) -> dict[str, Any]:
    """Build one direct transfer relationship from revalidated CMIS evidence."""

    record = _resolve_wallet_activity(
        wallet_activity_observation_id,
        observation_resolver=observation_resolver,
    )
    sender, recipient = _relationship_parties(record)
    verification = record["verification"]

    limitations = sorted(
        set(record.get("limitations") or []).union(_STANDARD_LIMITATIONS)
    )
    evidence = {
        "wallet_activity_observation_id": record["observation_id"],
        "wallet_activity_revalidated": True,
        "wallet_identity_verified": verification.get("wallet_identity_verified") is True,
        "counterparty_verified": verification.get("counterparty_verified") is True,
        "asset_identity_verified": verification.get("asset_identity_verified") is True,
        "transaction_identity_verified": (
            verification.get("transaction_identity_verified") is True
        ),
        "transfer_direction_verified": (
            verification.get("transfer_direction_verified") is True
        ),
        # The accepted wallet-activity primitive does not embed Evidence Receipt
        # or Proof Score records. Keep that absence explicit instead of inventing
        # replacement proof objects or accepting caller-supplied ones.
        "evidence_receipt_binding_available": False,
        "evidence_receipt_ids": [],
        "proof_score_binding_available": False,
        "proof_score_records": [],
    }

    base = {
        "schema_version": SCHEMA_VERSION,
        "schema": SCHEMA,
        "relationship_kind": RELATIONSHIP_KIND,
        "interaction_type": INTERACTION_TYPE,
        "chain": record["chain"],
        "asset_id": record["asset_id"],
        "sender": sender,
        "recipient": recipient,
        "transaction_signature": record["transaction_signature"],
        "observed_at": record["observed_at"],
        "block_slot": record.get("block_slot"),
        "asset_amount": record.get("asset_amount"),
        "asset_unit": record.get("asset_unit"),
        "source": record["source"],
        "verification_method": record["verification_method"],
        "evidence_scope": record["evidence_scope"],
        "evidence": evidence,
        "limitations": limitations,
        **_boundary_fields(),
    }
    return {"relationship_evidence_id": _content_id("wr", base), **base}


def validate_direct_wallet_relationship(
    value: Any,
    *,
    observation_resolver: Callable[[str], Any] | None,
) -> dict[str, Any]:
    """Rebuild and require exact equality with canonical relationship evidence."""

    if not isinstance(value, Mapping):
        raise TypeError("wallet relationship evidence must be a mapping")
    supplied = deepcopy(dict(value))
    relationship_id = supplied.get("relationship_evidence_id")
    if not isinstance(relationship_id, str) or not _RELATIONSHIP_ID_RE.fullmatch(
        relationship_id
    ):
        raise ValueError("relationship_evidence_id must be a canonical wr_ content id")
    evidence = supplied.get("evidence")
    observation_id = (
        evidence.get("wallet_activity_observation_id")
        if isinstance(evidence, Mapping)
        else None
    )
    rebuilt = build_direct_wallet_relationship(
        observation_id,
        observation_resolver=observation_resolver,
    )
    if supplied != rebuilt:
        raise ValueError(
            "wallet relationship evidence does not match its deterministic canonical record"
        )
    return rebuilt


def _compatibility_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        record["chain"],
        record["asset_id"],
        record["sender"],
        record["recipient"],
        record["source"],
        record["verification_method"],
        record["evidence_scope"],
    )


def _interaction_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    # Without a separately verified transfer-index contract, CMIS cannot prove
    # multiple same-pair/same-asset transfers inside one transaction are distinct.
    # Count at most one direct interaction per transaction for this first slice.
    return (
        record["chain"],
        record["asset_id"],
        record["sender"],
        record["recipient"],
        record["transaction_signature"],
    )


def _duplicate_material(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        record.get("observed_at"),
        record.get("block_slot"),
        record.get("asset_amount"),
        record.get("asset_unit"),
    )


def summarize_direct_wallet_relationships(
    wallet_activity_observation_ids: Sequence[Any],
    *,
    observation_resolver: Callable[[str], Any] | None,
) -> dict[str, Any]:
    """Aggregate compatible direct relationships without inferring ownership."""

    if isinstance(wallet_activity_observation_ids, (str, bytes, bytearray)) or not isinstance(
        wallet_activity_observation_ids, Sequence
    ):
        raise TypeError(
            "wallet_activity_observation_ids must be a sequence of canonical wa_ ids"
        )
    if not wallet_activity_observation_ids:
        raise ValueError("at least one wallet-activity observation id is required")

    relationship_records: list[dict[str, Any]] = []
    seen_relationship_ids: set[str] = set()
    for observation_id in wallet_activity_observation_ids:
        relationship = build_direct_wallet_relationship(
            observation_id,
            observation_resolver=observation_resolver,
        )
        relationship_id = relationship["relationship_evidence_id"]
        if relationship_id in seen_relationship_ids:
            continue
        seen_relationship_ids.add(relationship_id)
        relationship_records.append(relationship)

    first_key = _compatibility_key(relationship_records[0])
    for record in relationship_records[1:]:
        if _compatibility_key(record) != first_key:
            raise ValueError(
                "wallet relationship evidence has incompatible "
                "chain/asset/direction/source/method/scope"
            )

    units = {
        record["asset_unit"]
        for record in relationship_records
        if record.get("asset_unit") is not None
    }
    if len(units) > 1:
        raise ValueError("wallet relationship evidence has incompatible asset units")

    interactions: dict[tuple[Any, ...], dict[str, Any]] = {}
    interaction_evidence: dict[tuple[Any, ...], list[str]] = {}
    for record in relationship_records:
        key = _interaction_key(record)
        existing = interactions.get(key)
        if existing is None:
            interactions[key] = record
            interaction_evidence[key] = [record["relationship_evidence_id"]]
            continue
        if _duplicate_material(existing) != _duplicate_material(record):
            raise ValueError(
                "duplicate wallet relationship evidence disagrees on material transfer facts"
            )
        interaction_evidence[key].append(record["relationship_evidence_id"])

    unique_interactions = sorted(
        interactions.values(),
        key=lambda item: (
            item["observed_at"],
            item["transaction_signature"],
            item["relationship_evidence_id"],
        ),
    )
    first = unique_interactions[0]
    relationship_ids = sorted(seen_relationship_ids)
    observation_ids = sorted(
        record["evidence"]["wallet_activity_observation_id"]
        for record in relationship_records
    )
    transaction_signatures = sorted(
        {record["transaction_signature"] for record in unique_interactions}
    )
    amount_observation_count = sum(
        1 for record in unique_interactions if record.get("asset_amount") is not None
    )

    base = {
        "schema_version": SCHEMA_VERSION,
        "schema": SUMMARY_SCHEMA,
        "relationship_kind": RELATIONSHIP_KIND,
        "interaction_type": INTERACTION_TYPE,
        "chain": first["chain"],
        "asset_id": first["asset_id"],
        "sender": first["sender"],
        "recipient": first["recipient"],
        "source": first["source"],
        "verification_method": first["verification_method"],
        "evidence_scope": first["evidence_scope"],
        "first_observed_interaction": unique_interactions[0]["observed_at"],
        "last_observed_interaction": unique_interactions[-1]["observed_at"],
        "verified_direct_interaction_count": len(unique_interactions),
        "relationship_evidence_count": len(relationship_records),
        "duplicate_relationship_evidence_collapsed": (
            len(relationship_records) - len(unique_interactions)
        ),
        "transaction_signatures": transaction_signatures,
        "relationship_evidence_ids": relationship_ids,
        "wallet_activity_observation_ids": observation_ids,
        "asset_unit": next(iter(units)) if units else None,
        "amount_observation_count": amount_observation_count,
        "missing_amount_observation_count": (
            len(unique_interactions) - amount_observation_count
        ),
        "interaction_evidence": [
            {
                "transaction_signature": record["transaction_signature"],
                "relationship_evidence_ids": sorted(
                    interaction_evidence[_interaction_key(record)]
                ),
            }
            for record in unique_interactions
        ],
        "limitations": sorted(
            set(_STANDARD_LIMITATIONS).union(
                {
                    "bounded_compatible_evidence_set_only",
                    "transaction_scoped_deduplication_without_transfer_index_claim",
                }
            )
        ),
        **_boundary_fields(),
    }
    return {"relationship_summary_id": _content_id("wrs", base), **base}


def validate_direct_wallet_relationship_summary(
    value: Any,
    *,
    observation_resolver: Callable[[str], Any] | None,
) -> dict[str, Any]:
    """Rebuild and require exact equality with a canonical bounded summary."""

    if not isinstance(value, Mapping):
        raise TypeError("wallet relationship summary must be a mapping")
    supplied = deepcopy(dict(value))
    summary_id = supplied.get("relationship_summary_id")
    if not isinstance(summary_id, str) or not _SUMMARY_ID_RE.fullmatch(summary_id):
        raise ValueError("relationship_summary_id must be a canonical wrs_ content id")
    observation_ids = supplied.get("wallet_activity_observation_ids")
    rebuilt = summarize_direct_wallet_relationships(
        observation_ids,
        observation_resolver=observation_resolver,
    )
    if supplied != rebuilt:
        raise ValueError(
            "wallet relationship summary does not match its deterministic canonical record"
        )
    return rebuilt


__all__ = [
    "INTERACTION_TYPE",
    "RELATIONSHIP_KIND",
    "SCHEMA",
    "SCHEMA_VERSION",
    "SUMMARY_SCHEMA",
    "build_direct_wallet_relationship",
    "summarize_direct_wallet_relationships",
    "validate_direct_wallet_relationship",
    "validate_direct_wallet_relationship_summary",
]
