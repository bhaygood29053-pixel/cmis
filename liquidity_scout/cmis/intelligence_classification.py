"""Deterministic descriptive classification over accepted CMIS intelligence evidence.

This module establishes a classification boundary without introducing behavioral,
ownership, intent, fraud, manipulation, or risk interpretation. The first narrow
classifier resolves one CMIS-owned Phase 12 ``top_account_concentration_change``
evidence bundle by its exact content id, revalidates the complete evidence bundle,
and derives only a descriptive direction label from the already-verified numeric
fact.

Classification is not public-service promotion, Scout reliance, risk, policy, or
execution authority. In particular, explicit concentration-threshold policy
assessment remains a separate contract and is not used here.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Callable

from liquidity_scout.cmis.intelligence_evidence_ledger import (
    ACCEPTED_CONCLUSION_TYPE,
    normalize_intelligence_evidence_id,
    validate_concentration_change_intelligence_evidence,
)


SCHEMA_VERSION = 1
SCHEMA = "cmis_intelligence_classification.v1"
CLASSIFICATION_TYPE = "top_account_concentration_direction"
CLASSIFICATION_KIND = "descriptive"
RULESET_ID = "top_account_concentration_direction/v1"
_CLASSIFICATION_ID_RE = re.compile(r"^icl_[0-9a-f]{64}$")
_LABEL_BY_DIRECTION = {
    "INCREASE": "CONCENTRATION_INCREASED",
    "DECREASE": "CONCENTRATION_DECREASED",
    "NO_CHANGE": "CONCENTRATION_UNCHANGED",
}


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _content_id(value: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
    return f"icl_{digest}"


def _resolve_evidence(
    intelligence_evidence_id: Any,
    *,
    evidence_resolver: Callable[[str], Any] | None,
) -> dict[str, Any]:
    evidence_id = normalize_intelligence_evidence_id(intelligence_evidence_id)
    if not callable(evidence_resolver):
        raise ValueError("a trusted internal intelligence evidence resolver is required")
    try:
        resolved = evidence_resolver(evidence_id)
    except Exception as exc:
        raise ValueError(
            "trusted internal intelligence evidence resolution failed: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    if resolved is None:
        raise ValueError("the requested CMIS intelligence evidence was not found")

    rebuilt = validate_concentration_change_intelligence_evidence(resolved)
    if rebuilt["intelligence_evidence_id"] != evidence_id:
        raise ValueError("resolved CMIS intelligence evidence does not match the requested id")
    return rebuilt


def _evidence_summary(evidence: Mapping[str, Any]) -> dict[str, Any]:
    receipt_ids: list[str] = []
    proof_records: list[dict[str, Any]] = []
    for bundle in evidence.get("evidence_bundles", []):
        if not isinstance(bundle, Mapping):
            raise ValueError("canonical intelligence evidence bundle is malformed")
        receipt = bundle.get("evidence_receipt")
        proof = bundle.get("proof_score")
        if not isinstance(receipt, Mapping) or not isinstance(proof, Mapping):
            raise ValueError("canonical intelligence evidence proof bundle is malformed")
        receipt_id = receipt.get("receipt_id")
        if not isinstance(receipt_id, str):
            raise ValueError("canonical intelligence evidence receipt id is missing")
        receipt_ids.append(receipt_id)
        proof_records.append(
            {
                "receipt_id": receipt_id,
                "proof_strength": proof.get("proof_strength"),
                "proof_percent": proof.get("proof_percent"),
                "method": proof.get("method"),
            }
        )
    return {
        "receipt_ids": receipt_ids,
        "proof_records": proof_records,
    }


def build_concentration_direction_classification(
    intelligence_evidence_id: Any,
    *,
    evidence_resolver: Callable[[str], Any] | None,
) -> dict[str, Any]:
    """Build the first deterministic descriptive intelligence classification.

    No caller-supplied classification label is accepted. The label is derived
    only from the direction field after the complete evidence-bound conclusion
    has been deterministically rebuilt and revalidated.
    """

    evidence = _resolve_evidence(
        intelligence_evidence_id,
        evidence_resolver=evidence_resolver,
    )
    if evidence.get("conclusion_type") != ACCEPTED_CONCLUSION_TYPE:
        raise ValueError(
            "classification accepts only top_account_concentration_change evidence"
        )
    conclusion = evidence.get("conclusion")
    if not isinstance(conclusion, Mapping):
        raise ValueError("canonical intelligence evidence conclusion is missing")

    direction = conclusion.get("direction")
    label = _LABEL_BY_DIRECTION.get(direction)
    if label is None:
        raise ValueError("validated concentration direction is unsupported")

    summary = _evidence_summary(evidence)
    binding = evidence.get("binding")
    if not isinstance(binding, Mapping):
        raise ValueError("canonical intelligence evidence binding is missing")

    base = {
        "schema_version": SCHEMA_VERSION,
        "schema": SCHEMA,
        "classification_type": CLASSIFICATION_TYPE,
        "classification_kind": CLASSIFICATION_KIND,
        "ruleset_id": RULESET_ID,
        "label": label,
        "basis": {
            "conclusion_type": ACCEPTED_CONCLUSION_TYPE,
            "conclusion_fingerprint": evidence.get("conclusion_fingerprint"),
            "deterministic_fact_revalidated": True,
            "policy_evaluation_used": False,
            "hidden_threshold_used": False,
        },
        "subject": {
            "chain": conclusion.get("chain"),
            "asset_id": conclusion.get("asset_id"),
            "source": conclusion.get("source"),
            "scope": conclusion.get("scope"),
            "requested_account_limit": conclusion.get("requested_account_limit"),
            "observed_account_count": conclusion.get("observed_account_count"),
        },
        "observation_window": {
            "start": conclusion.get("before_observed_at"),
            "end": conclusion.get("after_observed_at"),
        },
        "fact": {
            "direction": direction,
            "before_share_exact": deepcopy(conclusion.get("before_share_exact")),
            "after_share_exact": deepcopy(conclusion.get("after_share_exact")),
            "delta_share_exact": deepcopy(conclusion.get("delta_share_exact")),
            "delta_bps": conclusion.get("delta_bps"),
        },
        "evidence": {
            "intelligence_evidence_id": evidence["intelligence_evidence_id"],
            "receipt_ids": summary["receipt_ids"],
            "proof_records": summary["proof_records"],
            "independent_verification_present": binding.get(
                "independent_verification_present"
            ),
            "chain_verified": binding.get("chain_verified"),
            "source_coverage_verified": binding.get("source_coverage_verified"),
            "asset_coverage_verified": binding.get("asset_coverage_verified"),
        },
        "risk_interpretation": None,
        "proof_strength_separate_from_risk": True,
        "behavioral_interpretation_added": False,
        "ownership_interpretation_added": False,
        "provider_assertion_promoted": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }
    return {"classification_id": _content_id(base), **base}


def validate_concentration_direction_classification(
    value: Any,
    *,
    evidence_resolver: Callable[[str], Any] | None,
) -> dict[str, Any]:
    """Rebuild and require exact equality with the deterministic classification."""

    if not isinstance(value, Mapping):
        raise TypeError("intelligence classification must be a mapping")
    supplied = deepcopy(dict(value))
    classification_id = supplied.get("classification_id")
    if not isinstance(classification_id, str) or not _CLASSIFICATION_ID_RE.fullmatch(
        classification_id
    ):
        raise ValueError("classification_id must be a canonical icl_ content id")
    evidence = supplied.get("evidence")
    evidence_id = evidence.get("intelligence_evidence_id") if isinstance(evidence, Mapping) else None
    rebuilt = build_concentration_direction_classification(
        evidence_id,
        evidence_resolver=evidence_resolver,
    )
    if supplied != rebuilt:
        raise ValueError(
            "intelligence classification does not match its deterministic canonical classification"
        )
    return rebuilt


__all__ = [
    "CLASSIFICATION_KIND",
    "CLASSIFICATION_TYPE",
    "RULESET_ID",
    "SCHEMA",
    "SCHEMA_VERSION",
    "build_concentration_direction_classification",
    "validate_concentration_direction_classification",
]
