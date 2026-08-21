"""Deterministic internal concentration-threshold alert evidence.

This module wraps the accepted concentration-threshold evaluator. It adds
freshness, explicit comparator identity, single-observation persistence, and
content-addressed evidence/alert identities without promoting the result into
a public service, Scout-reliance contract, behavioral inference, risk score, or
execution authority.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any, Mapping

from liquidity_scout.cmis.concentration_threshold import evaluate_concentration_threshold


_ALERT_SCHEMA = "cmis_concentration_threshold_alert.v1"
_EVIDENCE_ID_PREFIX = "ce_"
_ALERT_ID_PREFIX = "ca_"
_SUPPORTED_COMPARATORS = frozenset({"GT", "GTE"})
_CHANGE_KEYS = frozenset(
    {
        "schema",
        "chain",
        "asset_id",
        "source",
        "scope",
        "requested_account_limit",
        "observed_account_count",
        "before_observed_at",
        "after_observed_at",
        "before_share_exact",
        "after_share_exact",
        "delta_share_exact",
        "before_share",
        "after_share",
        "delta_share",
        "delta_bps",
        "direction",
        "identity_verified",
        "scope_complete",
        "holder_semantics_verified",
        "beneficial_owner_identity_verified",
        "behavioral_interpretation_verified",
        "cmis_promotable",
        "limitations",
    }
)


def _normalized_text(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a normalized non-empty string.")
    text = value.strip()
    if not text or text != value:
        raise ValueError(f"{name} must be a normalized non-empty string.")
    return text


def _nonnegative_int(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative integer.")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isdigit() and str(int(value)) == value:
        result = int(value)
    else:
        raise ValueError(f"{name} must be a non-negative integer.")
    if result < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return result


def _canonical_utc_timestamp(name: str, value: Any) -> datetime:
    text = _normalized_text(name, value)
    if not text.endswith("Z"):
        raise ValueError(f"{name} must be canonical UTC ending in Z.")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{name} must be canonical UTC ending in Z.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != text:
        raise ValueError(f"{name} must be canonical UTC ending in Z.")
    return parsed


def _canonical_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


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
        raise ValueError("alert material must be canonical JSON-compatible data.") from exc


def _content_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}{digest}"


def _observation_age_seconds(after_observed_at: datetime, evaluated_at: datetime) -> Decimal:
    delta = evaluated_at - after_observed_at
    micros = (
        delta.days * 86_400 * 1_000_000
        + delta.seconds * 1_000_000
        + delta.microseconds
    )
    return Decimal(micros) / Decimal(1_000_000)


def build_concentration_threshold_alert(
    *,
    change: Mapping[str, Any],
    policy_id: str,
    policy_version: str,
    absolute_delta_threshold_bps: Any,
    comparator: str,
    evaluated_at: str,
    max_evidence_age_seconds: Any,
) -> dict[str, Any]:
    """Build one internal, read-only concentration-threshold alert evaluation.

    First-slice persistence is deliberately limited to one canonical
    observation. Multi-observation windows/repetition are not accepted by this
    contract and require a later separately reviewed slice.
    """
    if not isinstance(change, Mapping):
        raise ValueError("change must be a canonical CMIS concentration change object.")
    if set(change) != set(_CHANGE_KEYS):
        raise ValueError("change must contain exactly the canonical v1 concentration-change fields.")

    policy = _normalized_text("policy_id", policy_id)
    version = _normalized_text("policy_version", policy_version)
    comparison = _normalized_text("comparator", comparator)
    if comparison not in _SUPPORTED_COMPARATORS:
        raise ValueError("comparator must be one of GT or GTE.")

    evaluation_time = _canonical_utc_timestamp("evaluated_at", evaluated_at)
    observation_time = _canonical_utc_timestamp(
        "change.after_observed_at", change.get("after_observed_at")
    )
    if evaluation_time < observation_time:
        raise ValueError("evaluated_at cannot be earlier than change.after_observed_at.")

    max_age = _nonnegative_int("max_evidence_age_seconds", max_evidence_age_seconds)
    age = evaluation_time - observation_time
    if age > timedelta(seconds=max_age):
        raise ValueError("concentration evidence is stale for the accepted alert freshness policy.")

    threshold_evaluation = evaluate_concentration_threshold(
        change=change,
        policy_id=policy,
        policy_version=version,
        absolute_delta_threshold_bps=absolute_delta_threshold_bps,
    )

    if threshold_evaluation["status"] == "EXCEEDS_THRESHOLD":
        condition_state = "ABOVE_THRESHOLD"
    elif threshold_evaluation["status"] == "AT_THRESHOLD":
        condition_state = "AT_THRESHOLD"
    elif threshold_evaluation["status"] == "WITHIN_THRESHOLD":
        condition_state = "BELOW_THRESHOLD"
    else:
        raise ValueError("threshold evaluator returned an unsupported status.")

    if comparison == "GT":
        triggered = threshold_evaluation["threshold_exceeded"] is True
    else:  # GTE
        triggered = (
            threshold_evaluation["threshold_exceeded"] is True
            or threshold_evaluation["threshold_matched"] is True
        )

    evidence_id = _content_id(_EVIDENCE_ID_PREFIX, dict(change))
    triggering_ids = [evidence_id] if triggered else []
    satisfied_observations = 1 if triggered else 0
    age_seconds = _canonical_decimal(
        _observation_age_seconds(observation_time, evaluation_time)
    )

    material = {
        "schema": _ALERT_SCHEMA,
        "chain": threshold_evaluation["chain"],
        "asset_id": threshold_evaluation["asset_id"],
        "source": threshold_evaluation["source"],
        "scope": threshold_evaluation["scope"],
        "evaluated_at": evaluated_at,
        "evidence": {
            "kind": "canonical_cmis_concentration_change",
            "evidence_id": evidence_id,
            "after_observed_at": change["after_observed_at"],
            "age_seconds": age_seconds,
            "max_age_seconds": max_age,
            "fresh": True,
            "evidence_receipt_id": None,
            "proof_score_id": None,
        },
        "policy": {
            "policy_id": policy,
            "policy_version": version,
            "metric": "absolute_delta_bps",
            "unit": "basis_points",
            "absolute_delta_threshold_bps": threshold_evaluation["policy"][
                "absolute_delta_threshold_bps"
            ],
            "comparator": comparison,
            "comparison_symbol": ">" if comparison == "GT" else ">=",
            "hidden_default_threshold": False,
        },
        "observation": {
            "direction": threshold_evaluation["direction"],
            "delta_bps": threshold_evaluation["delta_bps"],
            "absolute_delta_bps": threshold_evaluation["absolute_delta_bps"],
            "condition_state": condition_state,
        },
        "alert_triggered": triggered,
        "persistence": {
            "mode": "single_observation",
            "required_observations": 1,
            "satisfied_observations": satisfied_observations,
            "evaluated_evidence_ids": [evidence_id],
            "triggering_evidence_ids": triggering_ids,
            "duplicate_evidence_can_inflate_count": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "behavioral_interpretation_verified": False,
        "risk_interpretation_verified": False,
        "execution_authorized": False,
        "limitations": [
            "alert_is_deterministic_policy_evaluation_not_a_market_fact",
            "single_observation_persistence_only",
            "evidence_receipt_and_proof_score_are_unavailable_in_this_first_slice",
            "alert_state_is_not_risk_or_severity",
            "alert_does_not_establish_whale_insider_bot_or_behavioral_identity",
            "alert_does_not_establish_ownership_beneficial_ownership_or_coordinated_control",
            "alert_does_not_establish_manipulation_fraud_scam_intent_causality_or_price_direction",
            "token_accounts_are_not_unique_holder_identities",
            "observed_top_account_scope_is_incomplete",
            "alert_is_not_a_public_service_or_scout_reliance_contract",
            "alert_does_not_authorize_execution_or_value_movement",
        ],
    }
    return {"alert_id": _content_id(_ALERT_ID_PREFIX, material), **material}


__all__ = ["build_concentration_threshold_alert"]
