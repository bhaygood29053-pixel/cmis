"""Public CMIS X1 Concentration Warning Intelligence v1 contract.

This service validates and exposes one canonical protected
cmis_persistent_concentration_warning.v1 object. It does not recompute
concentration, persistence, freshness, Evidence Receipts, or Proof Scores.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Any

from liquidity_scout.services.cmis_contract import ERROR, OK, build_service_envelope


SERVICE = "concentration_warning_intelligence"
CONTRACT_VERSION = "concentration_warning_intelligence/v1"
SUPPORTED_CHAIN = "x1"
DELIVERY_MODE = "pull_only"
WARNING_SCHEMA = "cmis_persistent_concentration_warning.v1"
PERSISTENCE_MODE = "two_distinct_compatible_observations"
_WARNING_ID_RE = re.compile(r"^cw_[0-9a-f]{64}$")
_EVIDENCE_ID_RE = re.compile(r"^ie_[0-9a-f]{64}$")
_SUPPORTED_LEVELS = frozenset({"WATCH", "CLEAR"})
_SUPPORTED_COMPARATORS = frozenset({"GT", "GTE"})


class ConcentrationWarningIntelligenceContractError(ValueError):
    """Raised when a protected warning violates the public service contract."""


def _mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConcentrationWarningIntelligenceContractError(f"{name} must be a mapping")
    return value


def _list(name: str, value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise ConcentrationWarningIntelligenceContractError(f"{name} must be a list")
    return value


def _normalized_text(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ConcentrationWarningIntelligenceContractError(
            f"{name} must be normalized non-empty text"
        )
    text = value.strip()
    if not text or text != value:
        raise ConcentrationWarningIntelligenceContractError(
            f"{name} must be normalized non-empty text"
        )
    return text


def _canonical_utc(name: str, value: Any) -> datetime:
    text = _normalized_text(name, value)
    if not text.endswith("Z"):
        raise ConcentrationWarningIntelligenceContractError(
            f"{name} must be canonical UTC ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ConcentrationWarningIntelligenceContractError(
            f"{name} must be canonical UTC ending in Z"
        ) from exc
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != text:
        raise ConcentrationWarningIntelligenceContractError(
            f"{name} must be canonical UTC ending in Z"
        )
    return parsed


def _nonnegative_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConcentrationWarningIntelligenceContractError(
            f"{name} must be a non-negative integer"
        )
    return value


def _canonical_nonnegative_decimal(name: str, value: Any) -> Decimal:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ConcentrationWarningIntelligenceContractError(
            f"{name} must be a canonical non-negative decimal string"
        )
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ConcentrationWarningIntelligenceContractError(
            f"{name} must be a canonical non-negative decimal string"
        ) from exc
    if not result.is_finite() or result < 0:
        raise ConcentrationWarningIntelligenceContractError(
            f"{name} must be a canonical non-negative decimal string"
        )
    canonical = format(result, "f")
    if "." in canonical:
        canonical = canonical.rstrip("0").rstrip(".")
    canonical = "0" if canonical in {"", "-0"} else canonical
    if canonical != value:
        raise ConcentrationWarningIntelligenceContractError(
            f"{name} must be a canonical non-negative decimal string"
        )
    return result


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
        raise ConcentrationWarningIntelligenceContractError(
            "warning material must be canonical JSON-compatible data"
        ) from exc


def _expected_warning_id(warning: Mapping[str, Any]) -> str:
    material = deepcopy(dict(warning))
    material.pop("warning_id", None)
    digest = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()
    return f"cw_{digest}"


def _validate_evidence_ids(value: Any, *, name: str) -> list[str]:
    ids = _list(name, value)
    if len(ids) != 2:
        raise ConcentrationWarningIntelligenceContractError(
            f"{name} must contain exactly two evidence ids"
        )
    for evidence_id in ids:
        if not isinstance(evidence_id, str) or not _EVIDENCE_ID_RE.fullmatch(evidence_id):
            raise ConcentrationWarningIntelligenceContractError(
                f"{name} contains a non-canonical intelligence evidence id"
            )
    if ids[0] == ids[1]:
        raise ConcentrationWarningIntelligenceContractError(
            f"{name} must contain distinct intelligence evidence ids"
        )
    return list(ids)


def _validate_proof_record(value: Any, *, receipt_ids: list[str]) -> None:
    record = _mapping("proof record", value)
    if record.get("receipt_id") not in receipt_ids:
        raise ConcentrationWarningIntelligenceContractError(
            "proof record receipt_id must bind to preserved receipt lineage"
        )
    if record.get("proof_strength") not in {"STRONG", "MODERATE", "WEAK"}:
        raise ConcentrationWarningIntelligenceContractError(
            "proof record proof_strength is invalid"
        )
    percent = record.get("proof_percent")
    if isinstance(percent, bool) or not isinstance(percent, (int, float)):
        raise ConcentrationWarningIntelligenceContractError(
            "proof record proof_percent is invalid"
        )
    method = record.get("method")
    if not isinstance(method, str) or not method.strip():
        raise ConcentrationWarningIntelligenceContractError(
            "proof record method is required"
        )


def validate_concentration_warning(warning: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one canonical Issue #396 warning without recomputing its facts."""

    if not isinstance(warning, Mapping):
        raise ConcentrationWarningIntelligenceContractError(
            "concentration warning must be a mapping"
        )
    supplied = deepcopy(dict(warning))

    warning_id = supplied.get("warning_id")
    if not isinstance(warning_id, str) or not _WARNING_ID_RE.fullmatch(warning_id):
        raise ConcentrationWarningIntelligenceContractError(
            "warning_id must be a canonical cw_ content id"
        )
    if supplied.get("schema") != WARNING_SCHEMA:
        raise ConcentrationWarningIntelligenceContractError(
            f"warning must use {WARNING_SCHEMA}"
        )
    if supplied.get("chain") != SUPPORTED_CHAIN:
        raise ConcentrationWarningIntelligenceContractError(
            "concentration warning intelligence v1 accepts X1 warnings only"
        )
    asset_id = _normalized_text("asset_id", supplied.get("asset_id"))
    _canonical_utc("evaluated_at", supplied.get("evaluated_at"))

    policy = _mapping("policy", supplied.get("policy"))
    if policy.get("metric") != "absolute_delta_bps":
        raise ConcentrationWarningIntelligenceContractError(
            "warning policy metric must be absolute_delta_bps"
        )
    if policy.get("unit") != "basis_points":
        raise ConcentrationWarningIntelligenceContractError(
            "warning policy unit must be basis_points"
        )
    comparator = policy.get("comparator")
    if comparator not in _SUPPORTED_COMPARATORS:
        raise ConcentrationWarningIntelligenceContractError(
            "warning comparator must be GT or GTE"
        )
    expected_symbol = ">" if comparator == "GT" else ">="
    if policy.get("comparison_symbol") != expected_symbol:
        raise ConcentrationWarningIntelligenceContractError(
            "warning comparison_symbol does not match comparator"
        )
    if policy.get("hidden_default_threshold") is not False:
        raise ConcentrationWarningIntelligenceContractError(
            "warning must not use a hidden threshold default"
        )
    _normalized_text("policy.policy_id", policy.get("policy_id"))
    _normalized_text("policy.policy_version", policy.get("policy_version"))
    if policy.get("absolute_delta_threshold_bps") is None:
        raise ConcentrationWarningIntelligenceContractError(
            "warning threshold value is required"
        )

    freshness = _mapping("freshness_policy", supplied.get("freshness_policy"))
    max_latest_age = _nonnegative_int(
        "freshness_policy.max_latest_age_seconds",
        freshness.get("max_latest_age_seconds"),
    )
    latest_age = _canonical_nonnegative_decimal(
        "freshness_policy.latest_age_seconds",
        freshness.get("latest_age_seconds"),
    )
    if latest_age > Decimal(max_latest_age):
        raise ConcentrationWarningIntelligenceContractError(
            "latest evidence age exceeds its accepted freshness bound"
        )
    if freshness.get("latest_evidence_freshness_verified") is not True:
        raise ConcentrationWarningIntelligenceContractError(
            "latest evidence freshness must be verified"
        )
    if freshness.get("receipt_freshness_verified") is not True:
        raise ConcentrationWarningIntelligenceContractError(
            "Evidence Receipt freshness must be verified"
        )

    persistence = _mapping("persistence", supplied.get("persistence"))
    if persistence.get("mode") != PERSISTENCE_MODE:
        raise ConcentrationWarningIntelligenceContractError(
            "unsupported warning persistence mode"
        )
    if persistence.get("required_observations") != 2:
        raise ConcentrationWarningIntelligenceContractError(
            "warning requires exactly two observations"
        )
    evaluated_ids = _validate_evidence_ids(
        persistence.get("evaluated_evidence_ids"),
        name="persistence.evaluated_evidence_ids",
    )
    satisfying_ids = _list(
        "persistence.condition_satisfying_evidence_ids",
        persistence.get("condition_satisfying_evidence_ids"),
    )
    if len(satisfying_ids) != len(set(satisfying_ids)):
        raise ConcentrationWarningIntelligenceContractError(
            "condition-satisfying evidence ids must be unique"
        )
    if any(item not in evaluated_ids for item in satisfying_ids):
        raise ConcentrationWarningIntelligenceContractError(
            "condition-satisfying evidence ids must be evaluated evidence ids"
        )
    if persistence.get("satisfied_observations") != len(satisfying_ids):
        raise ConcentrationWarningIntelligenceContractError(
            "satisfied_observations does not match satisfying evidence ids"
        )
    triggering_ids = _list(
        "persistence.triggering_evidence_ids",
        persistence.get("triggering_evidence_ids"),
    )
    if persistence.get("duplicate_evidence_can_inflate_count") is not False:
        raise ConcentrationWarningIntelligenceContractError(
            "duplicate evidence must not inflate persistence"
        )
    if persistence.get("strict_order_verified") is not True:
        raise ConcentrationWarningIntelligenceContractError(
            "warning fact-time ordering must be verified"
        )
    if persistence.get("compatibility_verified") is not True:
        raise ConcentrationWarningIntelligenceContractError(
            "warning observation compatibility must be verified"
        )
    max_window = _nonnegative_int(
        "persistence.max_window_seconds",
        persistence.get("max_window_seconds"),
    )
    window = _canonical_nonnegative_decimal(
        "persistence.window_seconds",
        persistence.get("window_seconds"),
    )
    if window > Decimal(max_window):
        raise ConcentrationWarningIntelligenceContractError(
            "warning persistence window exceeds its accepted bound"
        )

    observations = _list("observations", supplied.get("observations"))
    if len(observations) != 2:
        raise ConcentrationWarningIntelligenceContractError(
            "warning must preserve exactly two observations"
        )
    for index, observation in enumerate(observations):
        record = _mapping(f"observations[{index}]", observation)
        if record.get("intelligence_evidence_id") != evaluated_ids[index]:
            raise ConcentrationWarningIntelligenceContractError(
                "observation evidence order must match persistence evidence order"
            )
        _canonical_utc(
            f"observations[{index}].after_observed_at",
            record.get("after_observed_at"),
        )
        if record.get("freshness_verified") is not True:
            raise ConcentrationWarningIntelligenceContractError(
                "each warning observation must preserve verified freshness"
            )
        receipts = _list(
            f"observations[{index}].receipt_ids",
            record.get("receipt_ids"),
        )
        if not receipts or any(
            not isinstance(item, str) or not item.strip() for item in receipts
        ):
            raise ConcentrationWarningIntelligenceContractError(
                "each observation must preserve Evidence Receipt ids"
            )
        proof_records = _list(
            f"observations[{index}].proof_records",
            record.get("proof_records"),
        )
        if len(proof_records) != len(receipts):
            raise ConcentrationWarningIntelligenceContractError(
                "each observation must preserve complete Proof Score lineage"
            )
        for proof in proof_records:
            _validate_proof_record(proof, receipt_ids=receipts)

    first_time = _canonical_utc(
        "observations[0].after_observed_at",
        _mapping("observations[0]", observations[0]).get("after_observed_at"),
    )
    second_time = _canonical_utc(
        "observations[1].after_observed_at",
        _mapping("observations[1]", observations[1]).get("after_observed_at"),
    )
    if second_time <= first_time:
        raise ConcentrationWarningIntelligenceContractError(
            "warning observations must remain in strict increasing fact-time order"
        )

    evidence = _mapping("evidence", supplied.get("evidence"))
    evidence_ids = _validate_evidence_ids(
        evidence.get("intelligence_evidence_ids"),
        name="evidence.intelligence_evidence_ids",
    )
    if evidence_ids != evaluated_ids:
        raise ConcentrationWarningIntelligenceContractError(
            "warning evidence ids must match persistence evidence ids"
        )
    if evidence.get("freshness_verified") is not True:
        raise ConcentrationWarningIntelligenceContractError(
            "warning evidence freshness must be verified"
        )
    unresolved = _list(
        "evidence.unresolved_fields",
        evidence.get("unresolved_fields"),
    )
    if unresolved:
        raise ConcentrationWarningIntelligenceContractError(
            "warning evidence must not retain unresolved fields"
        )
    receipt_ids = _list("evidence.receipt_ids", evidence.get("receipt_ids"))
    if not receipt_ids or any(
        not isinstance(item, str) or not item.strip() for item in receipt_ids
    ):
        raise ConcentrationWarningIntelligenceContractError(
            "warning must preserve aggregate Evidence Receipt ids"
        )
    proof_lineage = _list("evidence.proof_lineage", evidence.get("proof_lineage"))
    if len(proof_lineage) != 2:
        raise ConcentrationWarningIntelligenceContractError(
            "warning must preserve two proof-lineage records"
        )
    for index, lineage in enumerate(proof_lineage):
        line = _mapping(f"evidence.proof_lineage[{index}]", lineage)
        if line.get("intelligence_evidence_id") != evaluated_ids[index]:
            raise ConcentrationWarningIntelligenceContractError(
                "proof lineage evidence order must match evaluated evidence order"
            )
        line_receipts = _list(
            f"evidence.proof_lineage[{index}].receipt_ids",
            line.get("receipt_ids"),
        )
        line_proofs = _list(
            f"evidence.proof_lineage[{index}].proof_records",
            line.get("proof_records"),
        )
        if len(line_proofs) != len(line_receipts):
            raise ConcentrationWarningIntelligenceContractError(
                "warning proof lineage is incomplete"
            )
        for proof in line_proofs:
            _validate_proof_record(proof, receipt_ids=line_receipts)

    warning_active = supplied.get("warning_active")
    if not isinstance(warning_active, bool):
        raise ConcentrationWarningIntelligenceContractError(
            "warning_active must be boolean"
        )
    warning_level = supplied.get("warning_level")
    if warning_level not in _SUPPORTED_LEVELS:
        raise ConcentrationWarningIntelligenceContractError(
            "warning_level must be WATCH or CLEAR"
        )
    if warning_active is not (warning_level == "WATCH"):
        raise ConcentrationWarningIntelligenceContractError(
            "warning_active must match warning_level"
        )
    if warning_active:
        if satisfying_ids != evaluated_ids or triggering_ids != evaluated_ids:
            raise ConcentrationWarningIntelligenceContractError(
                "WATCH requires both evaluated observations to satisfy and trigger"
            )
    elif triggering_ids:
        raise ConcentrationWarningIntelligenceContractError(
            "CLEAR must not expose triggering evidence ids"
        )

    required_false = (
        "warning_level_is_risk_severity",
        "risk_interpretation_verified",
        "behavioral_interpretation_verified",
        "ownership_interpretation_verified",
        "public_service_promoted",
        "scout_reliance_promoted",
        "cmis_promotable",
        "delivery_authorized",
        "execution_authorized",
    )
    for field in required_false:
        if supplied.get(field) is not False:
            raise ConcentrationWarningIntelligenceContractError(
                f"canonical protected warning must keep {field}=false"
            )
    if supplied.get("risk_interpretation") is not None:
        raise ConcentrationWarningIntelligenceContractError(
            "canonical protected warning risk_interpretation must remain null"
        )
    if supplied.get("proof_strength_separate_from_risk") is not True:
        raise ConcentrationWarningIntelligenceContractError(
            "Proof Score must remain separate from risk"
        )
    limitations = _list("limitations", supplied.get("limitations"))
    if not limitations or any(not isinstance(item, str) for item in limitations):
        raise ConcentrationWarningIntelligenceContractError(
            "warning limitations must remain explicit"
        )

    if warning_id != _expected_warning_id(supplied):
        raise ConcentrationWarningIntelligenceContractError(
            "warning_id does not match canonical warning content"
        )

    return supplied


def build_concentration_warning_intelligence_response(
    warning: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and expose one protected persistent warning as a pull-only service."""

    try:
        safe = validate_concentration_warning(warning)
    except ConcentrationWarningIntelligenceContractError as exc:
        chain = (
            str(warning.get("chain") or "x1").strip().lower()
            if isinstance(warning, Mapping)
            else "x1"
        )
        response = build_service_envelope(
            SERVICE,
            chain or "x1",
            ERROR,
            data={
                "contract_version": CONTRACT_VERSION,
                "delivery_mode": DELIVERY_MODE,
                "push_delivery_authorized": False,
                "public_service_promoted": True,
                "scout_reliance_promoted": True,
                "execution_authorized": False,
            },
            errors=[{
                "code": "concentration_warning_intelligence_contract_violation",
                "message": str(exc),
            }],
        )
        response["execution_authorized"] = False
        return response

    observations = safe["observations"]
    latest_observed_at = observations[-1]["after_observed_at"]
    sources = []
    seen = set()
    for observation in observations:
        key = (observation.get("source"), observation.get("after_observed_at"))
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "source": observation.get("source"),
            "observed_at": observation.get("after_observed_at"),
            "scope": observation.get("scope"),
        })

    response = build_service_envelope(
        SERVICE,
        SUPPORTED_CHAIN,
        OK,
        asset={"canonical_id": safe["asset_id"]},
        data={
            "contract_version": CONTRACT_VERSION,
            "delivery_mode": DELIVERY_MODE,
            "push_delivery_authorized": False,
            "public_service_promoted": True,
            "scout_reliance_promoted": True,
            "warning_id": safe["warning_id"],
            "warning_level": safe["warning_level"],
            "warning_active": safe["warning_active"],
            "warning_level_is_risk_severity": False,
            "policy": deepcopy(safe["policy"]),
            "freshness_policy": deepcopy(safe["freshness_policy"]),
            "persistence": deepcopy(safe["persistence"]),
            "observations": deepcopy(safe["observations"]),
            "evidence": deepcopy(safe["evidence"]),
            "limitations": deepcopy(safe["limitations"]),
            "canonical_warning": deepcopy(safe),
            "risk_interpretation": None,
            "risk_interpretation_verified": False,
            "behavioral_interpretation_verified": False,
            "ownership_interpretation_verified": False,
            "proof_strength_separate_from_risk": True,
            "execution_authorized": False,
        },
        risk=None,
        confidence={
            "canonical_warning_validated": True,
            "receipt_lineage_preserved": True,
            "proof_lineage_preserved": True,
            "freshness_verified": True,
        },
        sources=sources,
        observed_at=latest_observed_at,
        warnings=[{
            "code": "pull_only_warning_service",
            "message": (
                "This service is pull-only. It does not authorize push delivery, "
                "risk interpretation, prediction, or execution."
            ),
        }],
        errors=[],
    )
    response["execution_authorized"] = False
    return response


__all__ = [
    "CONTRACT_VERSION",
    "ConcentrationWarningIntelligenceContractError",
    "DELIVERY_MODE",
    "SERVICE",
    "SUPPORTED_CHAIN",
    "build_concentration_warning_intelligence_response",
    "validate_concentration_warning",
]
