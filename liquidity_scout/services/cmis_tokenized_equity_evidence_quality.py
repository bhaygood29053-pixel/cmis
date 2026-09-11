"""Evidence-receipt, freshness, and confidence inputs for Tokenized Equity / RWA.

This public CMIS foundation binds already-accepted RWA component outputs to one
exact token/security subject and derives deterministic content-addressed receipt
identities.  It does not compute the protected CMIS Proof Score, does not infer
missing facts, and does not turn retrieval time into fact freshness.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
from typing import Any

from liquidity_scout.services.cmis_cross_chain_equity_provenance import (
    CROSS_CHAIN_EQUITY_PROVENANCE_CONTRACT,
)
from liquidity_scout.services.cmis_tokenized_equity_market_activity import (
    REQUIRED_METRICS,
    TOKENIZED_EQUITY_MARKET_ACTIVITY_CONTRACT,
)
from liquidity_scout.services.cmis_tokenized_equity_provenance import (
    TOKENIZED_EQUITY_PROVENANCE_CONTRACT,
)
from liquidity_scout.services.cmis_tokenized_equity_rights import (
    REQUIRED_DIMENSIONS,
    TOKENIZED_EQUITY_RIGHTS_CONTRACT,
)

TOKENIZED_EQUITY_EVIDENCE_QUALITY_CONTRACT = "tokenized_equity_evidence_quality/v1"
DEFAULT_EXECUTION_AUTHORIZED = False
FRESHNESS_STATES = frozenset({"FRESH", "STALE", "UNKNOWN"})


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    return value


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _receipt_id(prefix: str, value: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


def _endpoint(value: Any, field: str) -> dict[str, str]:
    mapped = _mapping(value, field)
    return {
        "chain": _text(mapped.get("chain"), f"{field}.chain").casefold(),
        "asset_id": _text(mapped.get("asset_id"), f"{field}.asset_id"),
        "asset_id_kind": _text(
            mapped.get("asset_id_kind"), f"{field}.asset_id_kind"
        ).casefold(),
    }


def _security(value: Any, field: str) -> dict[str, str]:
    mapped = _mapping(value, field)
    return {
        "security_id": _text(mapped.get("security_id"), f"{field}.security_id"),
        "security_id_kind": _text(
            mapped.get("security_id_kind"), f"{field}.security_id_kind"
        ).casefold(),
    }


def _same_subject(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return left.get("token") == right.get("token") and left.get("security") == right.get("security")


def _bind_provenance(value: Any) -> tuple[dict[str, Any], Mapping[str, Any]]:
    component = _mapping(value, "tokenized_equity_provenance")
    if component.get("contract") != TOKENIZED_EQUITY_PROVENANCE_CONTRACT:
        raise ValueError("tokenized_equity_provenance must use accepted tokenized_equity_provenance/v1")
    if component.get("execution_authorized") is not False:
        raise ValueError("tokenized_equity_provenance must preserve execution_authorized=false")
    verification = _mapping(component.get("verification"), "tokenized_equity_provenance.verification")
    if verification.get("exact_token_identity_structurally_bound") is not True:
        raise ValueError("tokenized-equity token identity must be structurally bound")
    if verification.get("exact_underlying_security_id_structurally_bound") is not True:
        raise ValueError("tokenized-equity security identity must be structurally bound")
    subject = {
        "token": _endpoint(component.get("token"), "tokenized_equity_provenance.token"),
        "security": _security(component.get("underlying_security"), "tokenized_equity_provenance.underlying_security"),
    }
    return subject, component


def _component_subject(component: Mapping[str, Any], contract: str, field: str) -> dict[str, Any]:
    if component.get("execution_authorized") is not False:
        raise ValueError(f"{field} must preserve execution_authorized=false")
    if contract == TOKENIZED_EQUITY_RIGHTS_CONTRACT:
        nested = _mapping(component.get("provenance"), f"{field}.provenance")
        return {
            "token": _endpoint(nested.get("token"), f"{field}.provenance.token"),
            "security": _security(nested.get("underlying_security"), f"{field}.provenance.underlying_security"),
        }
    if contract == TOKENIZED_EQUITY_MARKET_ACTIVITY_CONTRACT:
        nested = _mapping(component.get("provenance"), f"{field}.provenance")
        return {
            "token": _endpoint(nested.get("token"), f"{field}.provenance.token"),
            "security": _security(nested.get("underlying_security"), f"{field}.provenance.underlying_security"),
        }
    if contract == CROSS_CHAIN_EQUITY_PROVENANCE_CONTRACT:
        return {
            "token": _endpoint(component.get("token"), f"{field}.token"),
            "security": _security(component.get("underlying_security"), f"{field}.underlying_security"),
        }
    raise ValueError(f"unsupported component contract: {contract}")


def _validate_component(value: Any, *, field: str, contract: str, subject: Mapping[str, Any]) -> Mapping[str, Any]:
    component = _mapping(value, field)
    if component.get("contract") != contract:
        raise ValueError(f"{field} must use accepted {contract}")
    if not _same_subject(subject, _component_subject(component, contract, field)):
        raise ValueError(f"{field} subject must exactly match tokenized-equity provenance")

    verification = _mapping(component.get("verification"), f"{field}.verification")
    if contract == TOKENIZED_EQUITY_RIGHTS_CONTRACT:
        dimensions = _mapping(component.get("dimensions"), f"{field}.dimensions")
        if set(dimensions) != set(REQUIRED_DIMENSIONS):
            raise ValueError(f"{field} must contain every accepted rights dimension exactly once")
        if verification.get("accepted_tokenized_equity_provenance_bound") is not True:
            raise ValueError(f"{field} must bind accepted tokenized-equity provenance")
    elif contract == TOKENIZED_EQUITY_MARKET_ACTIVITY_CONTRACT:
        metrics = _mapping(component.get("metrics"), f"{field}.metrics")
        if set(metrics) != set(REQUIRED_METRICS):
            raise ValueError(f"{field} must contain every accepted market metric exactly once")
        if verification.get("accepted_tokenized_equity_provenance_bound") is not True:
            raise ValueError(f"{field} must bind accepted tokenized-equity provenance")
        if verification.get("metric_semantics_kept_separate") is not True:
            raise ValueError(f"{field} must preserve separated metric semantics")
    elif contract == CROSS_CHAIN_EQUITY_PROVENANCE_CONTRACT:
        if verification.get("tokenized_equity_binding_verified") is not True:
            raise ValueError(f"{field} must bind accepted tokenized-equity provenance")
        if verification.get("all_route_evidence_qualified") is not True:
            raise ValueError(f"{field} route evidence must be qualified")
    return component


def _component_receipt(subject: Mapping[str, Any], component: Mapping[str, Any]) -> dict[str, Any]:
    base = {
        "subject": deepcopy(dict(subject)),
        "component_contract": component["contract"],
        "component_sha256": hashlib.sha256(_canonical_json(component).encode("utf-8")).hexdigest(),
        "freshness": {"state": "UNKNOWN", "reason": "component_digest_has_no_independent_fact_time_policy"},
        "risk_included": False,
        "legal_conclusion_included": False,
    }
    return {"receipt_id": _receipt_id("rwa_component", base), **base}


def _rights_receipts(subject: Mapping[str, Any], component: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    receipts: list[dict[str, Any]] = []
    unresolved: list[str] = []
    dimensions = _mapping(component.get("dimensions"), "tokenized_equity_rights.dimensions")
    for dimension in REQUIRED_DIMENSIONS:
        claim = _mapping(dimensions[dimension], f"rights.{dimension}")
        state = _text(claim.get("state"), f"rights.{dimension}.state").upper()
        evidence = claim.get("evidence")
        if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)):
            raise ValueError(f"rights.{dimension}.evidence must be a sequence")
        if not evidence:
            unresolved.append(f"rights.{dimension}")
            continue
        for index, raw in enumerate(evidence):
            item = _mapping(raw, f"rights.{dimension}.evidence[{index}]")
            source_class = _text(item.get("source_class"), f"rights.{dimension}.evidence[{index}].source_class")
            base = {
                "subject": deepcopy(dict(subject)),
                "component_contract": TOKENIZED_EQUITY_RIGHTS_CONTRACT,
                "claim_path": f"rights.{dimension}",
                "claim_state": state,
                "source": {
                    "source_class": source_class,
                    "source_url": _text(item.get("source_url"), f"rights.{dimension}.evidence[{index}].source_url"),
                    "document_id": _text(item.get("document_id"), f"rights.{dimension}.evidence[{index}].document_id"),
                    "section": _text(item.get("section"), f"rights.{dimension}.evidence[{index}].section"),
                    "content_sha256": _text(item.get("content_sha256"), f"rights.{dimension}.evidence[{index}].content_sha256"),
                },
                "fact_time": _text(item.get("fact_time"), f"rights.{dimension}.evidence[{index}].fact_time"),
                "retrieved_at": _text(item.get("retrieved_at"), f"rights.{dimension}.evidence[{index}].retrieved_at"),
                "freshness": {
                    "state": "UNKNOWN",
                    "reason": "rights_document_requires_current_validity_or_supersession_evidence",
                },
                "source_authority": (
                    "AUTHORITATIVE_FOR_COMPONENT_CLAIM"
                    if item.get("authoritative_for_decisive_state") is True
                    else "CONTEXT_ONLY"
                ),
                "risk_included": False,
                "legal_effect_adjudicated": False,
            }
            receipts.append({"receipt_id": _receipt_id("rwa_evidence", base), **base})
    return receipts, unresolved


def _market_receipts(subject: Mapping[str, Any], component: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    receipts: list[dict[str, Any]] = []
    unresolved: list[str] = []
    metrics = _mapping(component.get("metrics"), "tokenized_equity_market_activity.metrics")
    scope = deepcopy(component.get("scope"))
    for metric_name in REQUIRED_METRICS:
        metric = _mapping(metrics[metric_name], f"market.{metric_name}")
        state = _text(metric.get("state"), f"market.{metric_name}.state").upper()
        if state != "OBSERVED":
            unresolved.append(f"market.{metric_name}")
            continue
        freshness = _mapping(metric.get("freshness"), f"market.{metric_name}.freshness")
        freshness_state = _text(freshness.get("state"), f"market.{metric_name}.freshness.state").upper()
        if freshness_state not in FRESHNESS_STATES:
            raise ValueError(f"market.{metric_name} has unsupported freshness state")
        sources = metric.get("sources")
        if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)) or not sources:
            raise ValueError(f"market.{metric_name}.sources must be a non-empty sequence")
        fact_time = _text(metric.get("fact_time"), f"market.{metric_name}.fact_time")
        for index, raw in enumerate(sources):
            item = _mapping(raw, f"market.{metric_name}.sources[{index}]")
            base = {
                "subject": deepcopy(dict(subject)),
                "component_contract": TOKENIZED_EQUITY_MARKET_ACTIVITY_CONTRACT,
                "claim_path": f"market.{metric_name}",
                "claim_state": "OBSERVED",
                "claim_semantic": _text(metric.get("semantic"), f"market.{metric_name}.semantic"),
                "scope": deepcopy(scope),
                "source": {
                    "provider_id": _text(item.get("provider_id"), f"market.{metric_name}.sources[{index}].provider_id"),
                    "source_class": _text(item.get("source_class"), f"market.{metric_name}.sources[{index}].source_class"),
                    "source_url": _text(item.get("source_url"), f"market.{metric_name}.sources[{index}].source_url"),
                    "observation_id": _text(item.get("observation_id"), f"market.{metric_name}.sources[{index}].observation_id"),
                    "content_sha256": _text(item.get("content_sha256"), f"market.{metric_name}.sources[{index}].content_sha256"),
                    "transaction_id": item.get("transaction_id"),
                },
                "fact_time": fact_time,
                "retrieved_at": _text(item.get("retrieved_at"), f"market.{metric_name}.sources[{index}].retrieved_at"),
                "freshness": {
                    "state": freshness_state,
                    "reason": "inherited_from_accepted_market_fact_time_or_window_end_policy",
                },
                "source_authority": "ACCEPTED_MARKET_OBSERVATION_SOURCE",
                "risk_included": False,
                "legal_effect_adjudicated": False,
            }
            receipts.append({"receipt_id": _receipt_id("rwa_evidence", base), **base})
    return receipts, unresolved


def build_tokenized_equity_evidence_quality(
    *,
    tokenized_equity_provenance: Any,
    cross_chain_equity_provenance: Any = None,
    tokenized_equity_rights: Any = None,
    tokenized_equity_market_activity: Any = None,
) -> dict[str, Any]:
    """Bind accepted RWA component evidence without calculating Proof Score."""

    subject, provenance = _bind_provenance(tokenized_equity_provenance)
    components: list[Mapping[str, Any]] = [provenance]
    unresolved = [
        "provenance.source_evidence_content_addressing"
        if provenance.get("evidence_ids")
        else "provenance.source_evidence"
    ]

    cross = None
    if cross_chain_equity_provenance is not None:
        cross = _validate_component(
            cross_chain_equity_provenance,
            field="cross_chain_equity_provenance",
            contract=CROSS_CHAIN_EQUITY_PROVENANCE_CONTRACT,
            subject=subject,
        )
        components.append(cross)
        unresolved.append("cross_chain.route_evidence_fact_time_and_content_receipts")

    rights = None
    rights_receipts: list[dict[str, Any]] = []
    if tokenized_equity_rights is not None:
        rights = _validate_component(
            tokenized_equity_rights,
            field="tokenized_equity_rights",
            contract=TOKENIZED_EQUITY_RIGHTS_CONTRACT,
            subject=subject,
        )
        components.append(rights)
        rights_receipts, rights_unresolved = _rights_receipts(subject, rights)
        unresolved.extend(rights_unresolved)

    market = None
    market_receipts: list[dict[str, Any]] = []
    if tokenized_equity_market_activity is not None:
        market = _validate_component(
            tokenized_equity_market_activity,
            field="tokenized_equity_market_activity",
            contract=TOKENIZED_EQUITY_MARKET_ACTIVITY_CONTRACT,
            subject=subject,
        )
        components.append(market)
        market_receipts, market_unresolved = _market_receipts(subject, market)
        unresolved.extend(market_unresolved)

    component_receipts = [_component_receipt(subject, component) for component in components]
    evidence_receipts = rights_receipts + market_receipts
    receipt_ids = [item["receipt_id"] for item in evidence_receipts]
    if len(receipt_ids) != len(set(receipt_ids)):
        raise ValueError("derived evidence receipts are not unique")

    fresh = sum(item["freshness"]["state"] == "FRESH" for item in evidence_receipts)
    stale = sum(item["freshness"]["state"] == "STALE" for item in evidence_receipts)
    unknown = sum(item["freshness"]["state"] == "UNKNOWN" for item in evidence_receipts)
    authoritative = sum(item["source_authority"] == "AUTHORITATIVE_FOR_COMPONENT_CLAIM" for item in evidence_receipts)

    # The accepted component contracts currently do not expose a normalized,
    # independently verified same-fact conflict object. Do not manufacture
    # agreement from that absence; leave conflict status explicitly UNKNOWN.
    conflict_record = {
        "state": "UNKNOWN",
        "conflicts": [],
        "conflict_detection_complete": False,
        "absence_of_recorded_conflict_proves_agreement": False,
    }

    return {
        "contract": TOKENIZED_EQUITY_EVIDENCE_QUALITY_CONTRACT,
        "subject": subject,
        "component_receipts": component_receipts,
        "evidence_receipts": evidence_receipts,
        "freshness": {
            "policy": {
                "market_activity": "inherit_accepted_fact_time_or_window_end_policy",
                "rights": "unknown_without_current_validity_or_supersession_evidence",
                "structural_provenance": "unknown_without_temporal_source_evidence",
                "cross_chain_route": "unknown_without_route_fact_time_content_receipt",
                "retrieval_time_alone_proves_freshness": False,
            },
            "fresh_receipt_count": fresh,
            "stale_receipt_count": stale,
            "unknown_receipt_count": unknown,
        },
        "conflict_evidence": conflict_record,
        "unresolved_fields": sorted(set(unresolved)),
        "confidence_inputs": {
            "exact_subject_identity_verified": True,
            "accepted_component_binding_verified": True,
            "component_receipt_count": len(component_receipts),
            "evidence_receipt_count": len(evidence_receipts),
            "authoritative_rights_receipt_count": authoritative,
            "fresh_receipt_count": fresh,
            "stale_receipt_count": stale,
            "unknown_receipt_count": unknown,
            "source_independence_verified": False,
            "same_fact_agreement_verified": False,
            "proof_score": None,
            "proof_score_owned_by_protected_runtime": True,
            "risk_considered": False,
            "legal_effect_adjudicated": False,
        },
        "verification": {
            "content_addressed_component_receipts_derived": True,
            "content_addressed_evidence_receipts_derived": True,
            "fact_time_separate_from_retrieval_time": True,
            "missing_evidence_zero_filled": False,
            "global_agreement_inferred": False,
            "source_independence_inferred_from_distinct_labels": False,
            "live_x1_equity_deployment_verified": False,
            "live_robinhood_x1_route_verified": False,
        },
        "boundaries": {
            "caller_supplied_receipt_id_authorized": False,
            "caller_fact_or_evidence_substitution_for_promoted_runtime_authorized": False,
            "retrieval_time_equals_fact_time": False,
            "unknown_equals_false_or_zero": False,
            "missing_conflict_record_proves_agreement": False,
            "proof_score_equals_risk": False,
            "confidence_equals_legal_conclusion": False,
            "proof_score_calculation_authorized_in_public_foundation": False,
            "automatic_risk_conclusion_authorized": False,
            "legal_advice_authorized": False,
            "trade_recommendation_authorized": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": DEFAULT_EXECUTION_AUTHORIZED,
    }


__all__ = [
    "DEFAULT_EXECUTION_AUTHORIZED",
    "FRESHNESS_STATES",
    "TOKENIZED_EQUITY_EVIDENCE_QUALITY_CONTRACT",
    "build_tokenized_equity_evidence_quality",
]
