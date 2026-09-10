"""Public request contract for future X1 Intelligence Brief runtime promotion.

This module validates caller-supplied selectors only. It does not execute CMIS
component services, accept component evidence, advertise a capability, authorize
X1 Scout reliance, or change execution authority.

Runtime promotion remains tracked by CMIS #637 and blocked on protected Actions
recovery #52.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from liquidity_scout.services.cmis_x1_asset_identity import is_exact_x1_public_key
from liquidity_scout.services.cmis_x1_intelligence_brief_inputs import (
    MAX_WINDOW_SECONDS,
    SUPPORTED_COMPONENT_CONTRACTS,
)


REQUEST_CONTRACT_VERSION = "x1_intelligence_brief_request/v1"
SUPPORTED_CHAIN = "x1"

_ALLOWED_KEYS = frozenset(
    {
        "contract_version",
        "chain",
        "subjects",
        "window_start",
        "window_end",
        "requested_services",
    }
)
_FORBIDDEN_CALLER_KEYS = frozenset(
    {
        "component_responses",
        "component_evaluations",
        "items",
        "evidence",
        "evidence_receipt",
        "evidence_receipts",
        "proof_score",
        "proof_scores",
        "priority",
        "priorities",
        "fact_time",
        "fact_times",
        "risk",
        "provider",
        "provider_facts",
        "source",
        "sources",
        "freshness",
        "confidence",
        "coverage",
        "public_service_promoted",
        "scout_reliance_promoted",
        "execution_authorized",
    }
)


class X1IntelligenceBriefRequestError(ValueError):
    """Raised when a caller attempts an invalid or authority-expanding request."""


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise X1IntelligenceBriefRequestError("request must be a mapping")
    return value


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise X1IntelligenceBriefRequestError(
            f"{name} must be normalized non-empty text"
        )
    return value


def _sequence(name: str, value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray, Mapping)
    ):
        raise X1IntelligenceBriefRequestError(f"{name} must be a list")
    return list(value)


def _canonical_utc(name: str, value: Any) -> datetime:
    text = _text(name, value)
    if not text.endswith("Z"):
        raise X1IntelligenceBriefRequestError(
            f"{name} must be canonical UTC ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise X1IntelligenceBriefRequestError(
            f"{name} must be canonical UTC ending in Z"
        ) from exc
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != text:
        raise X1IntelligenceBriefRequestError(
            f"{name} must be canonical UTC ending in Z"
        )
    return parsed


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_x1_intelligence_brief_request(value: Any) -> dict[str, Any]:
    """Validate only caller-selectable scope for the future runtime service."""

    request = deepcopy(dict(_mapping(value)))

    forbidden_present = sorted(_FORBIDDEN_CALLER_KEYS.intersection(request))
    if forbidden_present:
        raise X1IntelligenceBriefRequestError(
            "caller may not supply CMIS-owned brief facts/authority fields: "
            + ", ".join(forbidden_present)
        )

    unknown = sorted(set(request) - _ALLOWED_KEYS)
    if unknown:
        raise X1IntelligenceBriefRequestError(
            "unsupported X1 Intelligence Brief request fields: "
            + ", ".join(unknown)
        )

    if request.get("contract_version") != REQUEST_CONTRACT_VERSION:
        raise X1IntelligenceBriefRequestError(
            f"request contract must be {REQUEST_CONTRACT_VERSION}"
        )
    if request.get("chain") != SUPPORTED_CHAIN:
        raise X1IntelligenceBriefRequestError(
            "X1 Intelligence Brief request must use chain=x1"
        )

    subjects_raw = _sequence("subjects", request.get("subjects"))
    if not subjects_raw:
        raise X1IntelligenceBriefRequestError("subjects must not be empty")
    subjects: list[str] = []
    for index, value in enumerate(subjects_raw):
        subject = _text(f"subjects[{index}]", value)
        if not is_exact_x1_public_key(subject):
            raise X1IntelligenceBriefRequestError(
                "every brief subject must be an exact X1 mint identity"
            )
        subjects.append(subject)
    if len(set(subjects)) != len(subjects):
        raise X1IntelligenceBriefRequestError("subjects must be unique")

    services_raw = _sequence(
        "requested_services", request.get("requested_services")
    )
    if not services_raw:
        raise X1IntelligenceBriefRequestError(
            "requested_services must not be empty"
        )
    services = [
        _text(f"requested_services[{index}]", value)
        for index, value in enumerate(services_raw)
    ]
    if len(set(services)) != len(services):
        raise X1IntelligenceBriefRequestError(
            "requested_services must be unique"
        )
    unsupported = sorted(set(services) - set(SUPPORTED_COMPONENT_CONTRACTS))
    if unsupported:
        raise X1IntelligenceBriefRequestError(
            "unsupported brief component services: " + ", ".join(unsupported)
        )

    start = _canonical_utc("window_start", request.get("window_start"))
    end = _canonical_utc("window_end", request.get("window_end"))
    duration = (end - start).total_seconds()
    if (
        duration <= 0
        or duration > MAX_WINDOW_SECONDS
        or not float(duration).is_integer()
    ):
        raise X1IntelligenceBriefRequestError(
            f"brief window must be whole seconds, >0 and <= {MAX_WINDOW_SECONDS} seconds"
        )

    return {
        "contract_version": REQUEST_CONTRACT_VERSION,
        "chain": SUPPORTED_CHAIN,
        "subjects": sorted(subjects),
        "window_start": _utc_text(start),
        "window_end": _utc_text(end),
        "requested_services": sorted(services),
        "runtime_component_responses_caller_supplied": False,
        "runtime_evidence_caller_supplied": False,
        "runtime_priority_caller_supplied": False,
        "runtime_fact_time_caller_supplied": False,
        "runtime_risk_caller_supplied": False,
        "runtime_provider_facts_caller_supplied": False,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "REQUEST_CONTRACT_VERSION",
    "SUPPORTED_CHAIN",
    "X1IntelligenceBriefRequestError",
    "validate_x1_intelligence_brief_request",
]
