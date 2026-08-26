"""Read-only X1 Agents Radio discovery provider for CMIS.

X1 Agents Radio is treated as a third-party discovery and observational source.

Its names, categories, verification flags, activity counts, and deployment
labels remain provider claims. This module does not promote those claims to
CMIS-verified identities and does not duplicate X1 RPC verification.

Independent on-chain verification remains the responsibility of existing X1
RPC and deterministic evidence modules.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import requests


CHAIN = "x1"
NETWORK = "x1-mainnet"

X1_AGENTS_RADIO_BASE_URL = "https://x1agentsradio.xyz"
X1_AGENTS_RADIO_SOURCE = "x1agentsradio.xyz"

X1_AGENTS_RADIO_HEALTH_PATH = "/api/health"
X1_AGENTS_RADIO_BOOTSTRAP_PATH = "/api/bootstrap"
X1_AGENTS_RADIO_CATALOG_PATH = "/api/catalog"
X1_AGENTS_RADIO_DEPLOYMENTS_PATH = "/api/deployments"

BOOTSTRAP_CURATED = "bootstrap_curated"
CATALOG_OBSERVED = "catalog_observed"
RADIO_REGISTERED = "radio_registered"
DEPLOYMENT_EVENT = "deployment_event"


class X1AgentsRadioAPIError(RuntimeError):
    """Raised when X1 Agents Radio data cannot be safely consumed."""


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nonnegative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None

    return parsed if parsed >= 0 else None


def _require_object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise X1AgentsRadioAPIError(
            f"{label} must be a JSON object."
        )
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise X1AgentsRadioAPIError(
            f"{label} must be a JSON list."
        )
    return value


def _optional_object(
    payload: Mapping[str, Any],
    key: str,
) -> dict[str, Any]:
    value = payload.get(key)

    if value is None:
        return {}

    if not isinstance(value, Mapping):
        raise X1AgentsRadioAPIError(
            f"X1 Agents Radio {key} must be a JSON object."
        )

    return dict(value)


def _optional_list(
    payload: Mapping[str, Any],
    key: str,
) -> list[Any]:
    value = payload.get(key)

    if value is None:
        return []

    if not isinstance(value, list):
        raise X1AgentsRadioAPIError(
            f"X1 Agents Radio {key} must be a JSON list."
        )

    return list(value)


def _normalize_program(
    record: Any,
    *,
    evidence_tier: str,
    section: str,
    observed_at: str | None,
) -> dict[str, Any]:
    record = _require_object(
        record,
        "X1 Agents Radio program record",
    )

    program_id = _text(record.get("program_id"))

    if not program_id:
        raise X1AgentsRadioAPIError(
            "X1 Agents Radio program record is missing program_id."
        )

    provider_verified_claim = record.get("verified")

    if not isinstance(provider_verified_claim, bool):
        provider_verified_claim = None

    return {
        "chain": CHAIN,
        "network": NETWORK,
        "program_id": program_id,
        "name": _text(record.get("name")),
        "name_source": _text(record.get("name_source")),
        "category": _text(record.get("category")),
        "priority": _text(record.get("priority")),
        "status": _text(record.get("status")),
        "framework": _text(record.get("framework")),
        "website": _text(record.get("website")),
        "description": _text(record.get("description")),
        "provider_verified_claim": provider_verified_claim,
        "cmis_identity_promoted": False,
        "onchain_account_verified": False,
        "onchain_executable_verified": False,
        "evidence_tier": evidence_tier,
        "section": section,
        "observed_at": observed_at,
        "source": X1_AGENTS_RADIO_SOURCE,
        "raw": dict(record),
    }


def parse_health(payload: Any) -> dict[str, Any]:
    payload = _require_object(
        payload,
        "X1 Agents Radio health response",
    )

    status = (_text(payload.get("status")) or "").lower()

    if not status:
        raise X1AgentsRadioAPIError(
            "X1 Agents Radio health response is missing status."
        )

    return {
        "chain": CHAIN,
        "network": NETWORK,
        "status": status,
        "operational": status == "ok",
        "registry_program_id": _text(payload.get("program")),
        "treasury": _text(payload.get("treasury")),
        "registered_programs": _nonnegative_int(
            payload.get("registered_programs")
        ),
        "active_subscribers": _nonnegative_int(
            payload.get("active_subscribers")
        ),
        "last_digest_at": _nonnegative_int(
            payload.get("last_digest_at")
        ),
        "source": X1_AGENTS_RADIO_SOURCE,
        "observed_at": None,
        "scope": "provider_discovery_registry",
    }


def parse_bootstrap(payload: Any) -> dict[str, Any]:
    payload = _require_object(
        payload,
        "X1 Agents Radio bootstrap response",
    )

    network = _text(payload.get("network"))

    if network != NETWORK:
        raise X1AgentsRadioAPIError(
            "X1 Agents Radio bootstrap network mismatch: "
            f"{network!r}."
        )

    generated_at = _text(payload.get("generated_at"))

    if not generated_at:
        raise X1AgentsRadioAPIError(
            "X1 Agents Radio bootstrap is missing generated_at."
        )

    programs: list[dict[str, Any]] = []

    for section, value in payload.items():
        if not isinstance(value, list):
            continue

        evidence_tier = (
            RADIO_REGISTERED
            if section == "registered_programs"
            else BOOTSTRAP_CURATED
        )

        for item in value:
            if not isinstance(item, Mapping):
                continue

            if not _text(item.get("program_id")):
                continue

            programs.append(
                _normalize_program(
                    item,
                    evidence_tier=evidence_tier,
                    section=section,
                    observed_at=generated_at,
                )
            )

    return {
        "chain": CHAIN,
        "network": network,
        "schema_version": _text(
            payload.get("schema_version")
        ),
        "generated_at": generated_at,
        "program_count": len(programs),
        "programs": programs,
        "skills": _optional_list(payload, "skills"),
        "metadata": _optional_object(payload, "metadata"),
        "registry": _optional_object(payload, "registry"),
        "api": _optional_object(payload, "api"),
        "source": X1_AGENTS_RADIO_SOURCE,
        "observed_at": generated_at,
        "scope": "program_discovery",
    }


def parse_catalog(payload: Any) -> dict[str, Any]:
    payload = _require_object(
        payload,
        "X1 Agents Radio catalog response",
    )

    generated_at = _text(payload.get("generated_at"))

    if not generated_at:
        raise X1AgentsRadioAPIError(
            "X1 Agents Radio catalog is missing generated_at."
        )

    records = _require_list(
        payload.get("programs"),
        "X1 Agents Radio catalog programs",
    )

    count = _nonnegative_int(payload.get("count"))

    if count is None:
        raise X1AgentsRadioAPIError(
            "X1 Agents Radio catalog is missing a valid count."
        )

    if count != len(records):
        raise X1AgentsRadioAPIError(
            "X1 Agents Radio catalog count mismatch: "
            f"count={count}, programs={len(records)}."
        )

    programs = [
        _normalize_program(
            record,
            evidence_tier=CATALOG_OBSERVED,
            section="programs",
            observed_at=generated_at,
        )
        for record in records
    ]

    return {
        "chain": CHAIN,
        "network": NETWORK,
        "generated_at": generated_at,
        "count": count,
        "total_note": _text(payload.get("total_note")),
        "programs": programs,
        "source": X1_AGENTS_RADIO_SOURCE,
        "observed_at": generated_at,
        "scope": "program_catalog_observation",
    }


def parse_deployments(payload: Any) -> dict[str, Any]:
    payload = _require_object(
        payload,
        "X1 Agents Radio deployments response",
    )

    records = _require_list(
        payload.get("events"),
        "X1 Agents Radio deployment events",
    )

    count = _nonnegative_int(payload.get("count"))

    if count is None:
        raise X1AgentsRadioAPIError(
            "X1 Agents Radio deployments are missing a valid count."
        )

    if count != len(records):
        raise X1AgentsRadioAPIError(
            "X1 Agents Radio deployment count mismatch: "
            f"count={count}, events={len(records)}."
        )

    events: list[dict[str, Any]] = []

    for record in records:
        record = _require_object(
            record,
            "X1 Agents Radio deployment event",
        )

        event_type = (
            _text(record.get("type")) or ""
        ).lower()

        slot = _nonnegative_int(record.get("slot"))
        detected_at = _text(record.get("detected_at"))

        if not event_type:
            raise X1AgentsRadioAPIError(
                "X1 Agents Radio deployment event is missing type."
            )

        if slot is None:
            raise X1AgentsRadioAPIError(
                "X1 Agents Radio deployment event "
                "is missing a valid slot."
            )

        if not detected_at:
            raise X1AgentsRadioAPIError(
                "X1 Agents Radio deployment event "
                "is missing detected_at."
            )

        event = _normalize_program(
            record,
            evidence_tier=DEPLOYMENT_EVENT,
            section="events",
            observed_at=detected_at,
        )

        event.update(
            {
                "event_type": event_type,
                "slot": slot,
                "prev_slot": _nonnegative_int(
                    record.get("prev_slot")
                ),
                "detected_at": detected_at,
                "tx_count_24h": _nonnegative_int(
                    record.get("tx_count_24h")
                ),
            }
        )

        events.append(event)

    observed_at = max(
        (
            event["detected_at"]
            for event in events
            if event.get("detected_at")
        ),
        default=None,
    )

    return {
        "chain": CHAIN,
        "network": NETWORK,
        "count": count,
        "events": events,
        "source": X1_AGENTS_RADIO_SOURCE,
        "observed_at": observed_at,
        "scope": "program_deployment_observation",
    }


def _fetch_json(
    path: str,
    *,
    base_url: str = X1_AGENTS_RADIO_BASE_URL,
    timeout: int = 15,
    get=requests.get,
) -> Any:
    base_url = (_text(base_url) or "").rstrip("/")
    path = "/" + (_text(path) or "").lstrip("/")

    if not base_url:
        raise ValueError(
            "X1 Agents Radio base URL is required."
        )

    try:
        response = get(
            f"{base_url}{path}",
            headers={"accept": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except X1AgentsRadioAPIError:
        raise
    except Exception as exc:
        raise X1AgentsRadioAPIError(
            "X1 Agents Radio request failed for "
            f"{path}: {exc}"
        ) from exc


def fetch_health(**kwargs) -> dict[str, Any]:
    return parse_health(
        _fetch_json(
            X1_AGENTS_RADIO_HEALTH_PATH,
            **kwargs,
        )
    )


def fetch_bootstrap(**kwargs) -> dict[str, Any]:
    return parse_bootstrap(
        _fetch_json(
            X1_AGENTS_RADIO_BOOTSTRAP_PATH,
            **kwargs,
        )
    )


def fetch_catalog(**kwargs) -> dict[str, Any]:
    return parse_catalog(
        _fetch_json(
            X1_AGENTS_RADIO_CATALOG_PATH,
            **kwargs,
        )
    )


def fetch_deployments(**kwargs) -> dict[str, Any]:
    return parse_deployments(
        _fetch_json(
            X1_AGENTS_RADIO_DEPLOYMENTS_PATH,
            **kwargs,
        )
    )


class X1AgentsRadioProvider:
    """Read-only X1 Agents Radio discovery facade."""

    chain = CHAIN
    source = X1_AGENTS_RADIO_SOURCE

    def __init__(
        self,
        *,
        base_url: str = X1_AGENTS_RADIO_BASE_URL,
        timeout: int = 15,
        get=requests.get,
    ):
        self.base_url = (
            _text(base_url) or ""
        ).rstrip("/")
        self.timeout = timeout
        self.get = get

        if not self.base_url:
            raise ValueError(
                "X1 Agents Radio base URL is required."
            )

    def get_health(self) -> dict[str, Any]:
        return fetch_health(
            base_url=self.base_url,
            timeout=self.timeout,
            get=self.get,
        )

    def get_bootstrap(self) -> dict[str, Any]:
        return fetch_bootstrap(
            base_url=self.base_url,
            timeout=self.timeout,
            get=self.get,
        )

    def get_catalog(self) -> dict[str, Any]:
        return fetch_catalog(
            base_url=self.base_url,
            timeout=self.timeout,
            get=self.get,
        )

    def get_deployments(self) -> dict[str, Any]:
        return fetch_deployments(
            base_url=self.base_url,
            timeout=self.timeout,
            get=self.get,
        )


__all__ = [
    "BOOTSTRAP_CURATED",
    "CATALOG_OBSERVED",
    "CHAIN",
    "DEPLOYMENT_EVENT",
    "NETWORK",
    "RADIO_REGISTERED",
    "X1_AGENTS_RADIO_BASE_URL",
    "X1_AGENTS_RADIO_BOOTSTRAP_PATH",
    "X1_AGENTS_RADIO_CATALOG_PATH",
    "X1_AGENTS_RADIO_DEPLOYMENTS_PATH",
    "X1_AGENTS_RADIO_HEALTH_PATH",
    "X1_AGENTS_RADIO_SOURCE",
    "X1AgentsRadioAPIError",
    "X1AgentsRadioProvider",
    "fetch_bootstrap",
    "fetch_catalog",
    "fetch_deployments",
    "fetch_health",
    "parse_bootstrap",
    "parse_catalog",
    "parse_deployments",
    "parse_health",
]
