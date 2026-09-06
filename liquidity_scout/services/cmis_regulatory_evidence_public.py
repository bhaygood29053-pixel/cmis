"""Public promotion wrapper for freshness-aware Regulatory Evidence v1.

CMIS #539 promotes only canonical CMIS-owned regulatory_evidence/v1 records
that preserve exact X1 asset identity, current regulator-state freshness, and
the non-compliance/non-execution boundary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from typing import Any

from liquidity_scout.services.cmis_contract import ERROR, OK, build_service_envelope
from liquidity_scout.services.cmis_regulatory_evidence import (
    CONTRACT_VERSION,
    SERVICE,
    RegulatoryEvidenceContractError,
    validate_regulatory_evidence_record,
)

SUPPORTED_CHAIN = "x1"
DEFAULT_MAX_EVIDENCE_AGE_SECONDS = 86400.0
CURRENT_RULEMAKING_STATUSES = frozenset({
    "proposed_rule",
    "final_rule",
    "effective",
    "unknown",
})


class RegulatoryEvidencePublicContractError(ValueError):
    """Raised when canonical regulatory evidence is unsafe to promote."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise RegulatoryEvidencePublicContractError(
            f"{field} must be normalized text"
        )
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise RegulatoryEvidencePublicContractError(f"{field} must be boolean")
    return value


def _positive_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise RegulatoryEvidencePublicContractError(f"{field} must be positive")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise RegulatoryEvidencePublicContractError(
            f"{field} must be positive"
        ) from exc
    if parsed <= 0:
        raise RegulatoryEvidencePublicContractError(f"{field} must be positive")
    return parsed


def _timestamp(value: Any, field: str) -> datetime:
    text = _text(value, field)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RegulatoryEvidencePublicContractError(
            f"{field} must be ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise RegulatoryEvidencePublicContractError(
            f"{field} must include timezone"
        )
    return parsed


def validate_regulatory_evidence_public_record(
    record: Mapping[str, Any],
    *,
    expected_jurisdiction: str,
    expected_framework: str,
    expected_asset_id: str,
    expected_chain_asset_id: str,
    evaluated_at: Any,
    max_evidence_age_seconds: Any = DEFAULT_MAX_EVIDENCE_AGE_SECONDS,
) -> dict[str, Any]:
    """Revalidate one canonical record for public X1 Scout reliance."""

    try:
        safe = validate_regulatory_evidence_record(
            record,
            expected_jurisdiction=_text(
                expected_jurisdiction, "expected_jurisdiction"
            ),
            expected_framework=_text(expected_framework, "expected_framework"),
            expected_asset=_text(expected_asset_id, "expected_asset_id"),
        )
    except RegulatoryEvidenceContractError as exc:
        raise RegulatoryEvidencePublicContractError(str(exc)) from exc

    asset = safe["asset"]
    if asset.get("chain") != SUPPORTED_CHAIN:
        raise RegulatoryEvidencePublicContractError(
            "promoted regulatory asset must be bound to X1"
        )
    if asset.get("asset_id_kind") != "mint":
        raise RegulatoryEvidencePublicContractError(
            "promoted X1 regulatory asset identity must use exact mint"
        )
    exact_chain_id = _text(
        asset.get("chain_scoped_asset_id"),
        "asset.chain_scoped_asset_id",
    )
    if exact_chain_id != _text(
        expected_chain_asset_id,
        "expected_chain_asset_id",
    ):
        raise RegulatoryEvidencePublicContractError(
            "exact X1 mint identity mismatch"
        )

    if asset.get("representation_type") in {"bridged", "wrapped"}:
        if asset.get("bridge_dependency") is not True:
            raise RegulatoryEvidencePublicContractError(
                "bridged/wrapped regulatory evidence must preserve bridge dependency"
            )
        if asset.get("custody_dependency") is not True:
            raise RegulatoryEvidencePublicContractError(
                "bridged/wrapped regulatory evidence must preserve custody dependency"
            )

    sources = safe.get("sources")
    if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)):
        raise RegulatoryEvidencePublicContractError(
            "sources must remain a sequence"
        )
    classes = {
        source.get("authority_class")
        for source in sources
        if isinstance(source, Mapping)
    }
    if "primary_law" not in classes:
        raise RegulatoryEvidencePublicContractError(
            "promoted evidence requires primary-law provenance"
        )
    if "primary_regulator" not in classes:
        raise RegulatoryEvidencePublicContractError(
            "promoted current regulatory state requires primary-regulator provenance"
        )

    state = safe.get("current_regulatory_state")
    if not isinstance(state, Mapping):
        raise RegulatoryEvidencePublicContractError(
            "current_regulatory_state must be a mapping"
        )
    status = _text(
        state.get("rulemaking_status"),
        "current_regulatory_state.rulemaking_status",
    )
    if status not in CURRENT_RULEMAKING_STATUSES:
        raise RegulatoryEvidencePublicContractError(
            "unsupported current rulemaking status"
        )

    final_rule_verified = _bool(
        state.get("final_rule_verified"),
        "current_regulatory_state.final_rule_verified",
    )
    effective_now_verified = _bool(
        state.get("effective_now_verified"),
        "current_regulatory_state.effective_now_verified",
    )

    if status == "proposed_rule" and (
        final_rule_verified is not False or effective_now_verified is not False
    ):
        raise RegulatoryEvidencePublicContractError(
            "proposed rule cannot be promoted as final or effective"
        )
    if status == "final_rule" and (
        final_rule_verified is not True or effective_now_verified is not False
    ):
        raise RegulatoryEvidencePublicContractError(
            "final-rule status requires final_rule_verified=true and effective_now_verified=false"
        )
    if status == "effective" and (
        final_rule_verified is not True or effective_now_verified is not True
    ):
        raise RegulatoryEvidencePublicContractError(
            "effective status requires both final-rule and effective-now verification"
        )
    if status == "unknown" and (
        final_rule_verified is not False or effective_now_verified is not False
    ):
        raise RegulatoryEvidencePublicContractError(
            "unknown rulemaking status cannot promote final/effective state"
        )

    status_as_of = _timestamp(
        state.get("status_as_of"),
        "current_regulatory_state.status_as_of",
    )
    evaluated = _timestamp(evaluated_at, "evaluated_at")
    max_age = _positive_number(
        max_evidence_age_seconds,
        "max_evidence_age_seconds",
    )
    age = (evaluated - status_as_of).total_seconds()
    if age < 0:
        raise RegulatoryEvidencePublicContractError(
            "current regulatory evidence fact time is in the future"
        )
    if age > max_age:
        raise RegulatoryEvidencePublicContractError(
            "current regulatory evidence is stale"
        )

    safe["_public_freshness"] = {
        "status_as_of": state["status_as_of"],
        "evaluated_at": (
            evaluated.isoformat().replace("+00:00", "Z")
        ),
        "age_seconds": age,
        "max_evidence_age_seconds": max_age,
        "freshness_verified": True,
    }
    return safe


def build_regulatory_evidence_response(
    record: Mapping[str, Any],
    *,
    expected_jurisdiction: str,
    expected_framework: str,
    expected_asset_id: str,
    expected_chain_asset_id: str,
    evaluated_at: Any,
    max_evidence_age_seconds: Any = DEFAULT_MAX_EVIDENCE_AGE_SECONDS,
) -> dict[str, Any]:
    try:
        safe = validate_regulatory_evidence_public_record(
            record,
            expected_jurisdiction=expected_jurisdiction,
            expected_framework=expected_framework,
            expected_asset_id=expected_asset_id,
            expected_chain_asset_id=expected_chain_asset_id,
            evaluated_at=evaluated_at,
            max_evidence_age_seconds=max_evidence_age_seconds,
        )
    except RegulatoryEvidencePublicContractError as exc:
        response = build_service_envelope(
            SERVICE,
            SUPPORTED_CHAIN,
            ERROR,
            data={
                "contract_version": CONTRACT_VERSION,
                "public_service_promoted": True,
                "scout_reliance_promoted": True,
                "compliance_conclusion_authorized": False,
                "execution_authorized": False,
            },
            risk=None,
            errors=[{
                "code": "regulatory_evidence_contract_violation",
                "message": str(exc),
            }],
        )
        response["execution_authorized"] = False
        return response

    freshness = safe.pop("_public_freshness")
    canonical = deepcopy(safe)
    state = deepcopy(canonical["current_regulatory_state"])

    response = build_service_envelope(
        SERVICE,
        SUPPORTED_CHAIN,
        OK,
        asset={
            "canonical_id": canonical["asset"]["chain_scoped_asset_id"],
            "mint": canonical["asset"]["chain_scoped_asset_id"],
        },
        data={
            "contract_version": CONTRACT_VERSION,
            "public_service_promoted": True,
            "scout_reliance_promoted": True,
            "read_only": True,
            "jurisdiction": canonical["jurisdiction"],
            "framework": canonical["framework"],
            "legal": deepcopy(canonical["legal"]),
            "current_regulatory_state": state,
            "asset": deepcopy(canonical["asset"]),
            "issuer": deepcopy(canonical["issuer"]),
            "applicability": canonical["applicability"],
            "freshness": freshness,
            "sources": deepcopy(canonical["sources"]),
            "limitations": deepcopy(canonical["limitations"]),
            "compliance_conclusion_authorized": False,
            "compliance_conclusion": None,
            "legal_advice_authorized": False,
            "execution_authorized": False,
        },
        risk=None,
        confidence={
            "canonical_regulatory_record_validated": True,
            "exact_x1_mint_identity_verified": True,
            "primary_law_provenance_present": True,
            "primary_regulator_provenance_present": True,
            "freshness_verified": True,
        },
        sources=[
            {
                "source": source["title"],
                "publisher": source["publisher"],
                "scope": source["authority_class"],
                "observed_at": source["retrieved_at"],
            }
            for source in canonical["sources"]
        ],
        observed_at=state["status_as_of"],
        warnings=[{
            "code": "regulatory_status_is_not_compliance",
            "message": (
                "Regulatory framework/status evidence does not establish issuer "
                "or asset legal compliance. Bridged representations retain "
                "separate bridge, custody, liquidity, and redemption dependencies."
            ),
        }],
        errors=[],
    )
    response["execution_authorized"] = False
    return response


__all__ = [
    "CURRENT_RULEMAKING_STATUSES",
    "DEFAULT_MAX_EVIDENCE_AGE_SECONDS",
    "RegulatoryEvidencePublicContractError",
    "SUPPORTED_CHAIN",
    "build_regulatory_evidence_response",
    "validate_regulatory_evidence_public_record",
]
