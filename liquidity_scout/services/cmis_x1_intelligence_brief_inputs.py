"""Deterministic bounded X1 Intelligence Brief input composition.

Issue #635 defines a foundation-only contract for ROBERTA's future X1 Daily
Intelligence Brief.  This module composes already accepted CMIS service
responses; it does not fetch providers, summarize with an LLM, infer missing
events, claim whole-X1 coverage, promote a runtime service, or authorize
execution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from liquidity_scout.services.cmis_contract import SERVICE_STATUSES
from liquidity_scout.services.cmis_x1_asset_identity import is_exact_x1_public_key


CONTRACT_VERSION = "x1_intelligence_brief_inputs/v1"
SUPPORTED_CHAIN = "x1"
MAX_WINDOW_SECONDS = 86_400
SUPPORTED_COMPONENT_CONTRACTS = {
    "concentration_warning_intelligence": "concentration_warning_intelligence/v1",
    "large_trade_discovery": "large_trade_discovery/v1",
    "discovery_intelligence": "discovery_intelligence/v1",
}
PRIORITY_ORDER = {
    "persistent_warning": 20,
    "large_verified_activity": 30,
    "new_verified_observation": 40,
    "informational": 60,
}


class X1IntelligenceBriefInputsError(ValueError):
    """Raised when bounded brief inputs cannot be composed safely."""


def _sequence(name: str, value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise X1IntelligenceBriefInputsError(f"{name} must be a sequence")
    return list(value)


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise X1IntelligenceBriefInputsError(
            f"{name} must be normalized non-empty text"
        )
    return value


def _mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise X1IntelligenceBriefInputsError(f"{name} must be a mapping")
    return value


def _canonical_utc(name: str, value: Any) -> datetime:
    text = _text(name, value)
    if not text.endswith("Z"):
        raise X1IntelligenceBriefInputsError(
            f"{name} must be canonical UTC ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise X1IntelligenceBriefInputsError(
            f"{name} must be canonical UTC ending in Z"
        ) from exc
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != text:
        raise X1IntelligenceBriefInputsError(
            f"{name} must be canonical UTC ending in Z"
        )
    return parsed


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch_seconds(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise X1IntelligenceBriefInputsError(f"{name} must be integer Unix seconds")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise X1IntelligenceBriefInputsError(
            f"{name} must be integer Unix seconds"
        ) from exc
    if not parsed.is_finite() or parsed < 0 or parsed != parsed.to_integral_value():
        raise X1IntelligenceBriefInputsError(
            f"{name} must be integer Unix seconds"
        )
    return int(parsed)


def _epoch_datetime(name: str, value: Any) -> datetime:
    seconds = _epoch_seconds(name, value)
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise X1IntelligenceBriefInputsError(
            f"{name} is outside supported Unix time range"
        ) from exc


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
        raise X1IntelligenceBriefInputsError(
            "brief input material must be canonical JSON-compatible data"
        ) from exc


def _content_id(prefix: str, material: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


def _subjects(value: Any) -> list[str]:
    raw = _sequence("subjects", value)
    if not raw:
        raise X1IntelligenceBriefInputsError("subjects must not be empty")
    result = [_text(f"subjects[{index}]", item) for index, item in enumerate(raw)]
    if len(set(result)) != len(result):
        raise X1IntelligenceBriefInputsError("subjects must be unique")
    for subject in result:
        if not is_exact_x1_public_key(subject):
            raise X1IntelligenceBriefInputsError(
                "every brief subject must be an exact X1 mint identity"
            )
    return sorted(result)


def _services(value: Any) -> list[str]:
    raw = _sequence("requested_services", value)
    if not raw:
        raise X1IntelligenceBriefInputsError("requested_services must not be empty")
    result = [
        _text(f"requested_services[{index}]", item)
        for index, item in enumerate(raw)
    ]
    if len(set(result)) != len(result):
        raise X1IntelligenceBriefInputsError("requested_services must be unique")
    unsupported = sorted(set(result) - set(SUPPORTED_COMPONENT_CONTRACTS))
    if unsupported:
        raise X1IntelligenceBriefInputsError(
            "unsupported brief component services: " + ", ".join(unsupported)
        )
    return sorted(result)


def _response_subject(response: Mapping[str, Any]) -> str:
    asset = _mapping("component.asset", response.get("asset"))
    mint = asset.get("mint")
    canonical_id = asset.get("canonical_id")
    if mint is not None and canonical_id is not None and mint != canonical_id:
        raise X1IntelligenceBriefInputsError(
            "component asset mint and canonical_id disagree"
        )
    subject = mint or canonical_id
    subject = _text("component asset mint", subject)
    if not is_exact_x1_public_key(subject):
        raise X1IntelligenceBriefInputsError(
            "component response must bind an exact X1 mint identity"
        )
    return subject


def _validate_component_surface(
    response: Mapping[str, Any],
    *,
    requested_subjects: set[str],
    requested_services: set[str],
) -> tuple[str, str]:
    service = _text("component.service", response.get("service"))
    if service not in requested_services:
        raise X1IntelligenceBriefInputsError(
            "component service is outside the requested brief service set"
        )
    if response.get("chain") != SUPPORTED_CHAIN:
        raise X1IntelligenceBriefInputsError("brief components must be X1 only")
    status = response.get("status")
    if status not in SERVICE_STATUSES:
        raise X1IntelligenceBriefInputsError("component status is invalid")
    if response.get("execution_authorized") is not False:
        raise X1IntelligenceBriefInputsError(
            "component execution_authorized must remain false"
        )

    subject = _response_subject(response)
    if subject not in requested_subjects:
        raise X1IntelligenceBriefInputsError(
            "component subject is outside the requested brief subject set"
        )

    data = _mapping("component.data", response.get("data"))
    expected_contract = SUPPORTED_COMPONENT_CONTRACTS[service]
    if data.get("contract_version") != expected_contract:
        raise X1IntelligenceBriefInputsError(
            f"{service} component contract mismatch"
        )
    if data.get("execution_authorized") not in {None, False}:
        raise X1IntelligenceBriefInputsError(
            "component data execution_authorized must remain false"
        )
    return subject, service


def _component_matrix(
    responses: Any,
    *,
    subjects: list[str],
    services: list[str],
) -> tuple[dict[tuple[str, str], dict[str, Any]], int]:
    grouped: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
    duplicate_count = 0
    for index, raw in enumerate(_sequence("component_responses", responses)):
        response = deepcopy(dict(_mapping(f"component_responses[{index}]", raw)))
        subject, service = _validate_component_surface(
            response,
            requested_subjects=set(subjects),
            requested_services=set(services),
        )
        key = (subject, service)
        fingerprint = hashlib.sha256(
            _canonical_json(response).encode("utf-8")
        ).hexdigest()
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = (fingerprint, response)
        elif existing[0] == fingerprint:
            duplicate_count += 1
        else:
            raise X1IntelligenceBriefInputsError(
                "conflicting component responses exist for one subject/service pair"
            )

    expected = {(subject, service) for subject in subjects for service in services}
    missing = sorted(expected - set(grouped))
    if missing:
        labels = [f"{subject}:{service}" for subject, service in missing]
        raise X1IntelligenceBriefInputsError(
            "component response matrix is incomplete: " + ", ".join(labels)
        )
    return {key: value[1] for key, value in grouped.items()}, duplicate_count


def _base_item(
    *,
    subject: str,
    service: str,
    priority: str,
    fact_time: datetime,
    event_key: str,
    facts: Mapping[str, Any],
    response: Mapping[str, Any],
) -> dict[str, Any]:
    if priority not in PRIORITY_ORDER:
        raise X1IntelligenceBriefInputsError("unsupported brief priority")
    data = _mapping("component.data", response.get("data"))
    material = {
        "subject_mint": subject,
        "source_service": service,
        "source_contract_version": data["contract_version"],
        "priority": priority,
        "priority_rank": PRIORITY_ORDER[priority],
        "fact_time": _utc_text(fact_time),
        "event_key": _text("event_key", event_key),
        "facts": deepcopy(dict(facts)),
        "source_status": response.get("status"),
        "source_observed_at": response.get("observed_at"),
        "source_freshness": deepcopy(response.get("freshness")),
        "source_confidence": deepcopy(response.get("confidence") or {}),
        "source_sources": deepcopy(response.get("sources") or []),
        "source_warnings": deepcopy(response.get("warnings") or []),
        "source_errors": deepcopy(response.get("errors") or []),
        "risk": deepcopy(response.get("risk")),
        "proof_strength_separate_from_risk": True,
        "priority_is_risk_severity": False,
        "complete_x1_ecosystem_coverage_verified": False,
        "execution_authorized": False,
    }
    return {"brief_item_id": _content_id("xbi", material), **material}


def _discovery_items(
    response: Mapping[str, Any],
    *,
    subject: str,
) -> list[dict[str, Any]]:
    if response.get("status") in {"error", "ambiguous"}:
        return []
    if response.get("status") not in {"partial", "unavailable"}:
        raise X1IntelligenceBriefInputsError(
            "discovery_intelligence brief input expects partial or unavailable status"
        )
    data = _mapping("discovery.data", response.get("data"))
    if data.get("token_launch_time_verified") is not False:
        raise X1IntelligenceBriefInputsError(
            "Discovery brief input must not promote first observation as launch time"
        )
    coverage = _mapping("discovery.data.coverage", data.get("coverage"))
    if coverage.get("continuous_coverage_verified") is not False:
        raise X1IntelligenceBriefInputsError(
            "Discovery brief input must not claim continuous coverage"
        )
    if coverage.get("archive_completeness_verified") is not False:
        raise X1IntelligenceBriefInputsError(
            "Discovery brief input must not claim archive completeness"
        )
    count = data.get("verified_observation_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise X1IntelligenceBriefInputsError(
            "Discovery verified_observation_count is invalid"
        )
    if count == 0:
        if response.get("status") != "unavailable":
            raise X1IntelligenceBriefInputsError(
                "empty Discovery input must remain unavailable"
            )
        return []

    recent = _mapping(
        "discovery.data.most_recent_verified_observation",
        data.get("most_recent_verified_observation"),
    )
    if recent.get("mint") != subject:
        raise X1IntelligenceBriefInputsError(
            "Discovery most-recent observation subject mismatch"
        )
    if recent.get("fact_time_verified") is not True:
        raise X1IntelligenceBriefInputsError(
            "Discovery most-recent fact time must be verified"
        )
    if recent.get("execution_authorized") is not False:
        raise X1IntelligenceBriefInputsError(
            "Discovery observation execution_authorized must remain false"
        )
    fact_time = _epoch_datetime(
        "discovery most recent fact_time_unix", recent.get("fact_time_unix")
    )
    return [
        _base_item(
            subject=subject,
            service="discovery_intelligence",
            priority="new_verified_observation",
            fact_time=fact_time,
            event_key=_text("discovery content_id", recent.get("content_id")),
            facts={
                "observation_kind": recent.get("observation_kind"),
                "verification_state": recent.get("verification_state"),
                "source_id": recent.get("source_id"),
                "first_verified_observation": deepcopy(
                    data.get("first_verified_observation")
                ),
                "most_recent_verified_observation": deepcopy(recent),
                "verified_observation_count": count,
                "coverage": deepcopy(dict(coverage)),
                "token_launch_time": None,
                "token_launch_time_verified": False,
            },
            response=response,
        )
    ]


def _warning_items(
    response: Mapping[str, Any],
    *,
    subject: str,
) -> list[dict[str, Any]]:
    if response.get("status") != "ok":
        return []
    data = _mapping("concentration warning data", response.get("data"))
    if data.get("warning_level_is_risk_severity") is not False:
        raise X1IntelligenceBriefInputsError(
            "warning level must remain separate from risk severity"
        )
    if data.get("risk_interpretation") is not None:
        raise X1IntelligenceBriefInputsError(
            "concentration warning must not add risk interpretation"
        )
    if data.get("execution_authorized") is not False:
        raise X1IntelligenceBriefInputsError(
            "concentration warning execution_authorized must remain false"
        )
    observations = _sequence(
        "concentration warning observations", data.get("observations")
    )
    if not observations:
        raise X1IntelligenceBriefInputsError(
            "concentration warning must preserve observations"
        )
    latest = _mapping("latest concentration observation", observations[-1])
    fact_time = _canonical_utc(
        "latest concentration observation time", latest.get("after_observed_at")
    )
    level = data.get("warning_level")
    active = data.get("warning_active")
    if level not in {"WATCH", "CLEAR"} or not isinstance(active, bool):
        raise X1IntelligenceBriefInputsError(
            "concentration warning state is invalid"
        )
    if active is not (level == "WATCH"):
        raise X1IntelligenceBriefInputsError(
            "concentration warning active state does not match level"
        )
    return [
        _base_item(
            subject=subject,
            service="concentration_warning_intelligence",
            priority="persistent_warning" if active else "informational",
            fact_time=fact_time,
            event_key=_text("warning_id", data.get("warning_id")),
            facts={
                "warning_id": data.get("warning_id"),
                "warning_level": level,
                "warning_active": active,
                "warning_level_is_risk_severity": False,
                "policy": deepcopy(data.get("policy")),
                "persistence": deepcopy(data.get("persistence")),
                "evidence": deepcopy(data.get("evidence")),
                "limitations": deepcopy(data.get("limitations") or []),
                "risk_interpretation": None,
            },
            response=response,
        )
    ]


def _large_trade_items(
    response: Mapping[str, Any],
    *,
    subject: str,
) -> list[dict[str, Any]]:
    if response.get("status") != "ok":
        return []
    data = _mapping("large trade data", response.get("data"))
    if data.get("execution_authorized") is not False:
        raise X1IntelligenceBriefInputsError(
            "large trade execution_authorized must remain false"
        )
    boundaries = _mapping(
        "large trade evidence boundaries", data.get("evidence_boundaries")
    )
    for field in (
        "global_x1_dex_trade_ranking_authorized",
        "wallet_owner_identity_inference_authorized",
        "whale_insider_manipulator_label_authorized",
        "intent_inference_authorized",
        "coordinated_wallet_inference_authorized",
        "whole_market_price_impact_claim_authorized",
        "volume_causality_claim_authorized",
        "automatic_risk_conclusion_authorized",
        "trade_recommendation_authorized",
    ):
        if boundaries.get(field) is not False:
            raise X1IntelligenceBriefInputsError(
                f"large trade boundary {field} must remain false"
            )
    rows = _sequence("large trade results", data.get("results"))
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        row = _mapping(f"large trade results[{index}]", raw)
        signature = _text(
            f"large trade results[{index}].transaction_signature",
            row.get("transaction_signature"),
        )
        if signature in seen:
            raise X1IntelligenceBriefInputsError(
                "large trade brief input contains duplicate transaction signatures"
            )
        seen.add(signature)
        if row.get("asset_mint") != subject:
            raise X1IntelligenceBriefInputsError(
                "large trade result subject mismatch"
            )
        if row.get("usd_notional_verified") is not True:
            raise X1IntelligenceBriefInputsError(
                "large trade USD notional must be verified"
            )
        if row.get("real_world_wallet_owner_verified") is not False:
            raise X1IntelligenceBriefInputsError(
                "large trade result must not claim real-world wallet ownership"
            )
        fact_time = _epoch_datetime(
            f"large trade results[{index}].block_time", row.get("block_time")
        )
        result.append(
            _base_item(
                subject=subject,
                service="large_trade_discovery",
                priority="large_verified_activity",
                fact_time=fact_time,
                event_key=signature,
                facts={
                    "transaction_signature": signature,
                    "slot": row.get("slot"),
                    "pool_address": row.get("pool_address"),
                    "direction": row.get("direction"),
                    "asset_amount": row.get("asset_amount"),
                    "quote_mint": row.get("quote_mint"),
                    "quote_amount": row.get("quote_amount"),
                    "verified_usd_notional": row.get("verified_usd_notional"),
                    "usd_notional_verified": True,
                    "wallet_address": row.get("wallet_address"),
                    "wallet_attribution_verified": row.get(
                        "wallet_attribution_verified"
                    ),
                    "real_world_wallet_owner_verified": False,
                    "trade_price_impact_evidence_id": row.get(
                        "trade_price_impact_evidence_id"
                    ),
                    "ranking_scope": data.get("ranking_scope"),
                    "requested_window": deepcopy(data.get("requested_window")),
                    "evidence_boundaries": deepcopy(dict(boundaries)),
                },
                response=response,
            )
        )
    return result


def _items_for_response(
    response: Mapping[str, Any],
    *,
    subject: str,
    service: str,
) -> list[dict[str, Any]]:
    if service == "discovery_intelligence":
        return _discovery_items(response, subject=subject)
    if service == "concentration_warning_intelligence":
        return _warning_items(response, subject=subject)
    if service == "large_trade_discovery":
        return _large_trade_items(response, subject=subject)
    raise X1IntelligenceBriefInputsError("unsupported brief component service")


def build_x1_intelligence_brief_inputs(
    *,
    subjects: Any,
    window_start: Any,
    window_end: Any,
    requested_services: Any,
    component_responses: Any,
) -> dict[str, Any]:
    """Compose deterministic bounded brief inputs from trusted CMIS responses."""

    subject_list = _subjects(subjects)
    service_list = _services(requested_services)
    start = _canonical_utc("window_start", window_start)
    end = _canonical_utc("window_end", window_end)
    duration = (end - start).total_seconds()
    if (
        duration <= 0
        or duration > MAX_WINDOW_SECONDS
        or not float(duration).is_integer()
    ):
        raise X1IntelligenceBriefInputsError(
            f"brief window must be whole seconds, >0 and <= {MAX_WINDOW_SECONDS} seconds"
        )

    matrix, duplicate_components = _component_matrix(
        component_responses,
        subjects=subject_list,
        services=service_list,
    )

    included: dict[str, dict[str, Any]] = {}
    outside_window_count = 0
    evaluations: list[dict[str, Any]] = []
    for subject in subject_list:
        for service in service_list:
            response = matrix[(subject, service)]
            produced = _items_for_response(
                response,
                subject=subject,
                service=service,
            )
            in_window_count = 0
            for item in produced:
                fact_time = _canonical_utc("brief item fact_time", item["fact_time"])
                if start <= fact_time < end:
                    item_id = item["brief_item_id"]
                    existing = included.get(item_id)
                    if existing is not None and existing != item:
                        raise X1IntelligenceBriefInputsError(
                            "brief item content id collision"
                        )
                    included[item_id] = item
                    in_window_count += 1
                else:
                    outside_window_count += 1
            evaluations.append(
                {
                    "subject_mint": subject,
                    "service": service,
                    "contract_version": SUPPORTED_COMPONENT_CONTRACTS[service],
                    "source_status": response.get("status"),
                    "produced_item_count": len(produced),
                    "included_item_count": in_window_count,
                    "execution_authorized": False,
                }
            )

    items = list(included.values())
    items.sort(
        key=lambda item: (
            item["priority_rank"],
            -int(
                _canonical_utc("item.fact_time", item["fact_time"]).timestamp()
            ),
            item["brief_item_id"],
        )
    )
    fact_times = [
        _canonical_utc("item.fact_time", item["fact_time"]) for item in items
    ]

    service_statuses: dict[str, set[str]] = {service: set() for service in service_list}
    for evaluation in evaluations:
        service_statuses[evaluation["service"]].add(evaluation["source_status"])

    coverage = {
        "requested_subject_count": len(subject_list),
        "resolved_subject_count": len(subject_list),
        "requested_service_count": len(service_list),
        "input_service_classes_requested": list(service_list),
        "input_service_classes_evaluated": list(service_list),
        "partial_service_classes": sorted(
            service for service, statuses in service_statuses.items()
            if "partial" in statuses
        ),
        "unavailable_service_classes": sorted(
            service for service, statuses in service_statuses.items()
            if "unavailable" in statuses
        ),
        "error_or_ambiguous_service_classes": sorted(
            service for service, statuses in service_statuses.items()
            if statuses.intersection({"error", "ambiguous"})
        ),
        "component_response_matrix_complete": True,
        "duplicate_exact_component_responses_collapsed": duplicate_components,
        "included_item_count": len(items),
        "outside_window_item_count": outside_window_count,
        "window_start": _utc_text(start),
        "window_end": _utc_text(end),
        "window_end_exclusive": True,
        "earliest_included_fact_time": (
            _utc_text(min(fact_times)) if fact_times else None
        ),
        "latest_included_fact_time": (
            _utc_text(max(fact_times)) if fact_times else None
        ),
        "complete_x1_ecosystem_coverage_verified": False,
    }

    base = {
        "contract_version": CONTRACT_VERSION,
        "chain": SUPPORTED_CHAIN,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "subjects": subject_list,
        "requested_services": service_list,
        "window": {
            "start": _utc_text(start),
            "end": _utc_text(end),
            "end_exclusive": True,
            "duration_seconds": int(duration),
        },
        "items": items,
        "component_evaluations": evaluations,
        "coverage": coverage,
        "priority_is_risk_severity": False,
        "proof_score_separate_from_risk": True,
        "missing_evidence_zero_filled": False,
        "complete_x1_ecosystem_coverage_verified": False,
        "execution_authorized": False,
    }
    return {"brief_inputs_id": _content_id("xib", base), **base}


__all__ = [
    "CONTRACT_VERSION",
    "MAX_WINDOW_SECONDS",
    "PRIORITY_ORDER",
    "SUPPORTED_CHAIN",
    "SUPPORTED_COMPONENT_CONTRACTS",
    "X1IntelligenceBriefInputsError",
    "build_x1_intelligence_brief_inputs",
]
