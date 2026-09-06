"""Deterministic regulatory-evidence contract foundation.

Issue #536 establishes a non-promoted, read-only regulatory evidence schema.
It validates source identity, legal status, effective-date semantics, asset
representation identity, and explicit authority boundaries. It does not decide
legal compliance and it does not authorize execution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import date, datetime
from typing import Any

SERVICE = "regulatory_evidence"
CONTRACT_VERSION = "regulatory_evidence/v1"

LEGAL_STATUSES = frozenset({
    "enacted",
    "proposed_rule",
    "final_rule",
    "effective",
    "superseded",
    "repealed",
    "unknown",
})
APPLICABILITY_STATES = frozenset({
    "APPLICABLE",
    "NOT_APPLICABLE",
    "UNKNOWN",
    "INSUFFICIENT_EVIDENCE",
})
REPRESENTATION_TYPES = frozenset({"native", "bridged", "wrapped", "unknown"})
AUTHORITY_CLASSES = frozenset({"primary_law", "primary_regulator"})


class RegulatoryEvidenceContractError(ValueError):
    """Raised when regulatory evidence violates the v1 contract."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise RegulatoryEvidenceContractError(f"{field} must be normalized text")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise RegulatoryEvidenceContractError(f"{field} must be boolean")
    return value


def _date(value: Any, field: str) -> str:
    value = _text(value, field)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise RegulatoryEvidenceContractError(
            f"{field} must be ISO date YYYY-MM-DD"
        ) from exc
    return value


def _timestamp(value: Any, field: str) -> str:
    value = _text(value, field)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RegulatoryEvidenceContractError(
            f"{field} must be ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise RegulatoryEvidenceContractError(f"{field} must include timezone")
    return value


def _validate_source(source: Mapping[str, Any], index: int) -> dict[str, Any]:
    safe = deepcopy(dict(source))
    authority_class = _text(safe.get("authority_class"), f"sources[{index}].authority_class")
    if authority_class not in AUTHORITY_CLASSES:
        raise RegulatoryEvidenceContractError(
            f"sources[{index}].authority_class is not accepted"
        )
    url = _text(safe.get("url"), f"sources[{index}].url")
    if not url.startswith("https://"):
        raise RegulatoryEvidenceContractError(
            f"sources[{index}].url must use https"
        )
    _text(safe.get("publisher"), f"sources[{index}].publisher")
    _text(safe.get("title"), f"sources[{index}].title")
    if safe.get("published_on") is not None:
        _date(safe["published_on"], f"sources[{index}].published_on")
    _timestamp(safe.get("retrieved_at"), f"sources[{index}].retrieved_at")
    return safe


def validate_regulatory_evidence_record(
    record: Mapping[str, Any],
    *,
    expected_jurisdiction: str | None = None,
    expected_framework: str | None = None,
    expected_asset: str | None = None,
) -> dict[str, Any]:
    """Validate a canonical regulatory_evidence/v1 record.

    v1 is intentionally descriptive. A valid record may state applicability,
    source-backed legal status, and asset/issuer/bridge relationships, but it
    must not contain an authorized legal-compliance conclusion.
    """
    if not isinstance(record, Mapping):
        raise RegulatoryEvidenceContractError("record must be a mapping")
    safe = deepcopy(dict(record))

    if safe.get("service") != SERVICE or safe.get("contract") != CONTRACT_VERSION:
        raise RegulatoryEvidenceContractError(
            f"record must use {SERVICE} / {CONTRACT_VERSION}"
        )

    jurisdiction = _text(safe.get("jurisdiction"), "jurisdiction")
    framework = _text(safe.get("framework"), "framework")
    if expected_jurisdiction is not None and jurisdiction != expected_jurisdiction:
        raise RegulatoryEvidenceContractError("jurisdiction identity mismatch")
    if expected_framework is not None and framework != expected_framework:
        raise RegulatoryEvidenceContractError("framework identity mismatch")

    legal = safe.get("legal")
    if not isinstance(legal, Mapping):
        raise RegulatoryEvidenceContractError("legal must be a mapping")
    _text(legal.get("law_id"), "legal.law_id")
    _date(legal.get("enacted_on"), "legal.enacted_on")
    legal_status = _text(legal.get("status"), "legal.status")
    if legal_status not in LEGAL_STATUSES:
        raise RegulatoryEvidenceContractError("legal.status is not accepted")

    effective = legal.get("effective_date_rule")
    if not isinstance(effective, Mapping):
        raise RegulatoryEvidenceContractError(
            "legal.effective_date_rule must be a mapping"
        )
    rule_type = _text(effective.get("type"), "legal.effective_date_rule.type")
    if rule_type not in {"fixed", "earlier_of"}:
        raise RegulatoryEvidenceContractError(
            "effective-date rule type must be fixed or earlier_of"
        )
    _date(effective.get("fixed_date"), "legal.effective_date_rule.fixed_date")
    if rule_type == "earlier_of":
        days = effective.get("days_after_final_rules")
        if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
            raise RegulatoryEvidenceContractError(
                "days_after_final_rules must be a positive integer"
            )

    sources = safe.get("sources")
    if (
        not isinstance(sources, Sequence)
        or isinstance(sources, (str, bytes))
        or not sources
    ):
        raise RegulatoryEvidenceContractError(
            "sources must be a non-empty sequence"
        )
    safe["sources"] = [
        _validate_source(source, index)
        if isinstance(source, Mapping)
        else (_ for _ in ()).throw(
            RegulatoryEvidenceContractError(
                f"sources[{index}] must be a mapping"
            )
        )
        for index, source in enumerate(sources)
    ]

    asset = safe.get("asset")
    if not isinstance(asset, Mapping):
        raise RegulatoryEvidenceContractError("asset must be a mapping")
    asset_id = _text(asset.get("asset_id"), "asset.asset_id")
    if expected_asset is not None and asset_id != expected_asset:
        raise RegulatoryEvidenceContractError("asset identity mismatch")
    representation_type = _text(
        asset.get("representation_type"), "asset.representation_type"
    )
    if representation_type not in REPRESENTATION_TYPES:
        raise RegulatoryEvidenceContractError(
            "asset.representation_type is not accepted"
        )
    bridge_dependency = _bool(
        asset.get("bridge_dependency"), "asset.bridge_dependency"
    )
    _bool(asset.get("custody_dependency"), "asset.custody_dependency")

    if representation_type in {"bridged", "wrapped"}:
        _text(asset.get("underlying_asset"), "asset.underlying_asset")
        if bridge_dependency is not True:
            raise RegulatoryEvidenceContractError(
                "bridged/wrapped assets must preserve bridge_dependency=true"
            )
    elif representation_type == "native" and bridge_dependency is not False:
        raise RegulatoryEvidenceContractError(
            "native assets must preserve bridge_dependency=false"
        )

    issuer = safe.get("issuer")
    if not isinstance(issuer, Mapping):
        raise RegulatoryEvidenceContractError("issuer must be a mapping")
    _text(issuer.get("name"), "issuer.name")
    issuer_status = _text(issuer.get("identity_status"), "issuer.identity_status")
    if issuer_status not in {"VERIFIED", "PROVIDER_REPORTED", "UNKNOWN"}:
        raise RegulatoryEvidenceContractError(
            "issuer.identity_status is not accepted"
        )

    applicability = _text(safe.get("applicability"), "applicability")
    if applicability not in APPLICABILITY_STATES:
        raise RegulatoryEvidenceContractError(
            "applicability state is not accepted"
        )

    _timestamp(safe.get("retrieved_at"), "retrieved_at")

    if safe.get("read_only") is not True:
        raise RegulatoryEvidenceContractError("read_only must be true")
    if safe.get("execution_authorized") is not False:
        raise RegulatoryEvidenceContractError(
            "execution_authorized must remain false"
        )
    if safe.get("compliance_conclusion_authorized") is not False:
        raise RegulatoryEvidenceContractError(
            "compliance_conclusion_authorized must remain false"
        )
    if safe.get("compliance_conclusion") is not None:
        raise RegulatoryEvidenceContractError(
            "v1 must not emit a compliance conclusion"
        )

    limitations = safe.get("limitations")
    if (
        not isinstance(limitations, Sequence)
        or isinstance(limitations, (str, bytes))
        or not limitations
    ):
        raise RegulatoryEvidenceContractError(
            "limitations must be a non-empty sequence"
        )
    for index, item in enumerate(limitations):
        _text(item, f"limitations[{index}]")

    return safe


__all__ = [
    "APPLICABILITY_STATES",
    "AUTHORITY_CLASSES",
    "CONTRACT_VERSION",
    "LEGAL_STATUSES",
    "REPRESENTATION_TYPES",
    "RegulatoryEvidenceContractError",
    "SERVICE",
    "validate_regulatory_evidence_record",
]
