"""Deterministic X1 Agents Radio structured discovery beneath CMIS Web Discovery.

This module interprets only the accepted public X1 Agents Radio discovery
surfaces and provider-reported JSON candidates. It does not authenticate,
subscribe, register webhooks, infer program semantics, or promote Radio data
into verified CMIS truth.

The normalizer is deliberately tolerant of provider envelope changes: it looks
for bounded program/deployment candidate records by field shape rather than
assuming one exact top-level JSON schema. Unknown provider fields remain visible
as unmapped field names and never gain inferred semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

from .base import DISCOVERED
from .x1_agents_radio import (
    PUBLIC_DISCOVERY_PATHS,
    validate_x1_agents_radio_public_url,
)


STRUCTURED_CONTRACT = "x1_agents_radio_structured_discovery/v1"

MAX_RECORDS = 100
MAX_WALK_DEPTH = 4
MAX_INSTRUCTIONS = 50
MAX_UNMAPPED_FIELDS = 50
MAX_TEXT_CHARS = 500

_ENDPOINT_TYPES = {
    "/api/bootstrap": "bootstrap",
    "/api/catalog": "catalog",
    "/api/deployments": "deployments",
    "/api/health": "health",
}

_PROGRAM_ID_FIELDS = (
    "program_id",
    "programId",
    "program_address",
    "programAddress",
    "address",
    "pubkey",
    "__container_key_program_id",
)
_NAME_FIELDS = ("name", "program_name", "programName", "label")
_CATEGORY_FIELDS = ("category", "program_category", "programCategory", "program_type", "programType")
_INSTRUCTION_FIELDS = (
    "instructions",
    "instruction_names",
    "instructionNames",
    "methods",
    "operations",
)
_ACTIVITY_ALIASES = {
    "transaction_count": ("transaction_count", "transactionCount", "tx_count", "txCount"),
    "activity_count": ("activity_count", "activityCount"),
    "last_active_slot": ("last_active_slot", "lastActiveSlot"),
    "last_seen_slot": ("last_seen_slot", "lastSeenSlot"),
    "last_active_at": ("last_active_at", "lastActiveAt"),
    "last_seen_at": ("last_seen_at", "lastSeenAt"),
}
_DEPLOYMENT_ALIASES = {
    "deployment_slot": ("deployment_slot", "deploymentSlot", "deployed_slot", "deployedSlot"),
    "upgrade_slot": ("upgrade_slot", "upgradeSlot", "upgraded_slot", "upgradedSlot"),
    "deployed_at": ("deployed_at", "deployedAt"),
    "upgraded_at": ("upgraded_at", "upgradedAt"),
    "event_type": (
        "event_type",
        "eventType",
        "change_type",
        "changeType",
        "deployment_type",
        "deploymentType",
        "type",
    ),
    "status": ("status", "deployment_status", "deploymentStatus"),
    "transaction_signature": (
        "transaction_signature",
        "transactionSignature",
        "tx_signature",
        "txSignature",
        "signature",
    ),
}
_HEALTH_ALIASES = {
    "status": ("status", "watcher_status", "watcherStatus"),
    "healthy": ("healthy", "ok"),
    "latest_slot": ("latest_slot", "latestSlot", "last_slot", "lastSlot", "slot"),
    "indexed_program_count": (
        "indexed_program_count",
        "indexedProgramCount",
        "program_count",
        "programCount",
        "indexed_programs",
        "indexedPrograms",
    ),
    "last_updated_at": ("last_updated_at", "lastUpdatedAt", "updated_at", "updatedAt"),
    "uptime": ("uptime", "uptime_seconds", "uptimeSeconds"),
    "version": ("version",),
}

_RECOGNIZED_PROGRAM_FIELDS = frozenset(
    _PROGRAM_ID_FIELDS
    + _NAME_FIELDS
    + _CATEGORY_FIELDS
    + _INSTRUCTION_FIELDS
    + tuple(field for values in _ACTIVITY_ALIASES.values() for field in values)
    + tuple(field for values in _DEPLOYMENT_ALIASES.values() for field in values)
    + ("program",)
)


class X1AgentsRadioStructuredDiscoveryError(ValueError):
    """Raised when structured Radio discovery input is malformed."""


def _truth_state(*, route_verified: bool) -> dict[str, Any]:
    return {
        "discovery_state": DISCOVERED,
        "x1_agents_radio_route_verified": route_verified,
        "program_identity_verified": False,
        "program_semantics_verified": False,
        "instruction_semantics_verified": False,
        "deployment_verified": False,
        "upgrade_verified": False,
        "activity_verified": False,
        "freshness_verified": False,
        "web_claim_verified": False,
        "cmis_verified": False,
        "source_independence_verified": False,
    }


def _bounded_text(value: Any) -> str | None:
    if value is None or isinstance(value, (Mapping, list, tuple, set)):
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:MAX_TEXT_CHARS]


def _scalar_candidate(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:MAX_TEXT_CHARS]
    return None


def _first_value(record: Mapping[str, Any], fields: Sequence[str]) -> tuple[str | None, Any]:
    for field in fields:
        if field in record:
            value = record.get(field)
            if value is not None:
                return field, value
    return None, None


def _base58_decoded_length(value: str) -> int | None:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    index = {char: position for position, char in enumerate(alphabet)}
    text = str(value or "").strip()
    if not text:
        return None

    number = 0
    leading_zeros = 0
    for position, char in enumerate(text):
        digit = index.get(char)
        if digit is None:
            return None
        if position == leading_zeros and char == "1":
            leading_zeros += 1
        number = number * 58 + digit

    payload_length = (number.bit_length() + 7) // 8 if number else 0
    return leading_zeros + payload_length


def _program_id_candidate(record: Mapping[str, Any]) -> tuple[str | None, str | None]:
    field, value = _first_value(record, _PROGRAM_ID_FIELDS)
    if field is not None:
        text = _bounded_text(value)
        if text is not None:
            return field, text

    nested = record.get("program")
    if isinstance(nested, Mapping):
        field, value = _first_value(nested, _PROGRAM_ID_FIELDS)
        text = _bounded_text(value)
        if text is not None:
            return f"program.{field}", text
        fallback = _bounded_text(nested.get("id"))
        if fallback is not None and _base58_decoded_length(fallback) == 32:
            return "program.id", fallback
    elif isinstance(nested, str):
        text = _bounded_text(nested)
        if text is not None:
            return "program", text

    fallback = _bounded_text(record.get("id"))
    if fallback is not None and _base58_decoded_length(fallback) == 32:
        return "id", fallback

    return None, None


def _looks_like_program_record(record: Mapping[str, Any]) -> bool:
    field, candidate = _program_id_candidate(record)
    return field is not None and candidate is not None


def _bounded_instructions(value: Any) -> list[str]:
    result: list[str] = []

    def add(item: Any) -> None:
        text = _bounded_text(item)
        if text is not None and text not in result and len(result) < MAX_INSTRUCTIONS:
            result.append(text)

    if isinstance(value, Mapping):
        for key in value:
            add(key)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            if isinstance(item, Mapping):
                _, name = _first_value(item, ("name", "instruction", "method", "operation"))
                if name is not None:
                    add(name)
            else:
                add(item)
    else:
        add(value)

    return result


def _normalize_alias_fields(
    record: Mapping[str, Any],
    aliases: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for normalized_name, source_fields in aliases.items():
        _, value = _first_value(record, source_fields)
        scalar = _scalar_candidate(value)
        if scalar is not None:
            result[normalized_name] = scalar
    return result


def _unmapped_fields(record: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for key in record:
        name = str(key)
        if name in _RECOGNIZED_PROGRAM_FIELDS:
            continue
        if name.startswith("__"):
            continue
        result.append(name)
        if len(result) >= MAX_UNMAPPED_FIELDS:
            break
    return result


def _record_handoff(
    *,
    program_id: str | None,
    program_id_syntax_valid: bool,
    endpoint_type: str,
    transaction_signature: str | None,
) -> list[dict[str, Any]]:
    handoff: list[dict[str, Any]] = []

    if program_id is not None and program_id_syntax_valid:
        handoff.extend(
            [
                {
                    "target": "X1 RPC getAccountInfo",
                    "purpose": "verify exact account identity, executable state, owner, and account data candidate",
                    "required": True,
                    "program_id": program_id,
                },
                {
                    "target": "X1 RPC getSignaturesForAddress",
                    "purpose": "bounded activity/deployment history discovery for the exact program id",
                    "required": False,
                    "program_id": program_id,
                },
                {
                    "target": "CMIS source/IDL verification",
                    "purpose": "verify provider-reported program name, category, and instruction semantics against accepted implementation or IDL evidence",
                    "required": False,
                    "program_id": program_id,
                },
            ]
        )

    if endpoint_type == "deployments" and transaction_signature:
        handoff.append(
            {
                "target": "X1 RPC getTransaction",
                "purpose": "verify provider-reported deployment/upgrade transaction candidate",
                "required": False,
                "signature": transaction_signature,
            }
        )

    return handoff


def _normalize_program_record(
    record: Mapping[str, Any],
    *,
    endpoint_type: str,
    source_path: str,
) -> dict[str, Any]:
    program_id_field, program_id = _program_id_candidate(record)
    decoded_length = _base58_decoded_length(program_id) if program_id is not None else None
    program_id_syntax_valid = decoded_length == 32

    nested_program = record.get("program")
    nested = nested_program if isinstance(nested_program, Mapping) else {}

    _, name_value = _first_value(record, _NAME_FIELDS)
    if name_value is None and nested:
        _, name_value = _first_value(nested, _NAME_FIELDS)

    _, category_value = _first_value(record, _CATEGORY_FIELDS)
    if category_value is None and nested:
        _, category_value = _first_value(nested, _CATEGORY_FIELDS)

    _, instruction_value = _first_value(record, _INSTRUCTION_FIELDS)
    if instruction_value is None and nested:
        _, instruction_value = _first_value(nested, _INSTRUCTION_FIELDS)

    activity = _normalize_alias_fields(nested, _ACTIVITY_ALIASES)
    activity.update(_normalize_alias_fields(record, _ACTIVITY_ALIASES))

    deployment = _normalize_alias_fields(nested, _DEPLOYMENT_ALIASES)
    deployment.update(_normalize_alias_fields(record, _DEPLOYMENT_ALIASES))
    transaction_signature = _bounded_text(deployment.get("transaction_signature"))

    return {
        "record_type": (
            "deployment_candidate" if endpoint_type == "deployments" else "program_candidate"
        ),
        "source_path": source_path,
        "program_id": program_id,
        "program_id_source_field": program_id_field,
        "program_id_decoded_bytes": decoded_length,
        "program_id_syntax_valid": program_id_syntax_valid,
        "provider_name": _bounded_text(name_value),
        "provider_category": _bounded_text(category_value),
        "provider_instructions": _bounded_instructions(instruction_value),
        "provider_activity": activity,
        "provider_deployment": deployment,
        "unmapped_provider_fields": _unmapped_fields(record),
        "unmapped_nested_program_fields": (
            _unmapped_fields(nested) if nested else []
        ),
        "verification_handoff": _record_handoff(
            program_id=program_id,
            program_id_syntax_valid=program_id_syntax_valid,
            endpoint_type=endpoint_type,
            transaction_signature=transaction_signature,
        ),
        "truth_state": _truth_state(route_verified=True),
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def _walk_program_records(
    value: Any,
    *,
    max_records: int,
    depth: int = 0,
    path: str = "$",
) -> list[tuple[str, Mapping[str, Any]]]:
    if depth > MAX_WALK_DEPTH:
        return []

    result: list[tuple[str, Mapping[str, Any]]] = []

    if isinstance(value, Mapping):
        if _looks_like_program_record(value):
            result.append((path, value))
            return result

        for key, child in value.items():
            if len(result) >= max_records:
                break
            child_path = f"{path}.{key}"
            if isinstance(child, Mapping):
                candidate_child: Mapping[str, Any] = child
                if (
                    _base58_decoded_length(str(key)) == 32
                    and not _looks_like_program_record(child)
                ):
                    enriched = dict(child)
                    enriched["__container_key_program_id"] = str(key)
                    candidate_child = enriched
                result.extend(
                    _walk_program_records(
                        candidate_child,
                        max_records=max_records - len(result),
                        depth=depth + 1,
                        path=child_path,
                    )
                )
            elif isinstance(child, Sequence) and not isinstance(
                child, (str, bytes, bytearray)
            ):
                result.extend(
                    _walk_program_records(
                        child,
                        max_records=max_records - len(result),
                        depth=depth + 1,
                        path=child_path,
                    )
                )

    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            if len(result) >= max_records:
                break
            result.extend(
                _walk_program_records(
                    child,
                    max_records=max_records - len(result),
                    depth=depth + 1,
                    path=f"{path}[{index}]",
                )
            )

    return result[:max_records]


def _health_candidate(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _normalize_alias_fields(payload, _HEALTH_ALIASES)
    recognized = {
        field
        for aliases in _HEALTH_ALIASES.values()
        for field in aliases
    }
    unmapped: list[str] = []
    for key in payload:
        name = str(key)
        if name in recognized:
            continue
        unmapped.append(name)
        if len(unmapped) >= MAX_UNMAPPED_FIELDS:
            break

    return {
        "record_type": "health_candidate",
        "provider_health": normalized,
        "unmapped_provider_fields": unmapped,
        "verification_handoff": [
            {
                "target": "CMIS Web Discovery transport observation",
                "purpose": "retain Radio service-health response as source availability evidence only",
                "required": False,
            }
        ],
        "truth_state": _truth_state(route_verified=True),
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def _positive_max_records(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise X1AgentsRadioStructuredDiscoveryError("max_records must be an integer")
    if value < 1 or value > MAX_RECORDS:
        raise X1AgentsRadioStructuredDiscoveryError(
            f"max_records must be between 1 and {MAX_RECORDS}"
        )
    return value


def parse_x1_agents_radio_url(url: str) -> dict[str, Any]:
    """Classify one accepted public X1 Agents Radio endpoint."""

    normalized = validate_x1_agents_radio_public_url(url)
    path = urlparse(normalized).path.rstrip("/") or "/"
    endpoint_type = _ENDPOINT_TYPES.get(path)
    if endpoint_type is None:
        raise X1AgentsRadioStructuredDiscoveryError(
            f"unsupported X1 Agents Radio public path {path!r}"
        )

    return {
        "contract": STRUCTURED_CONTRACT,
        "supported": True,
        "url": normalized,
        "path": path,
        "endpoint_type": endpoint_type,
        "transport_method": "GET",
        "payload_normalized": False,
        "verification_handoff": [
            {
                "target": "X1 Agents Radio Web Discovery source",
                "purpose": "collect bounded public provider candidate evidence",
                "required": False,
            }
        ],
        "truth_state": _truth_state(route_verified=True),
        "read_only": True,
        "authentication_authorized": False,
        "subscription_authorized": False,
        "webhook_registration_authorized": False,
        "request_signing_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def normalize_x1_agents_radio_payload(
    url: str,
    payload: Any,
    *,
    max_records: int = MAX_RECORDS,
) -> dict[str, Any]:
    """Normalize one already-observed Radio JSON payload into bounded candidates."""

    endpoint = parse_x1_agents_radio_url(url)
    record_limit = _positive_max_records(max_records)
    endpoint_type = endpoint["endpoint_type"]

    if not isinstance(payload, (Mapping, list, tuple)):
        raise X1AgentsRadioStructuredDiscoveryError(
            "Radio structured payload must be a JSON object or array"
        )

    if endpoint_type == "health":
        if not isinstance(payload, Mapping):
            raise X1AgentsRadioStructuredDiscoveryError(
                "Radio health payload must be a JSON object"
            )
        health = _health_candidate(payload)
        return {
            **endpoint,
            "payload_normalized": True,
            "record_limit": record_limit,
            "candidate_record_count": 1,
            "records_truncated": False,
            "records": [health],
            "top_level_type": "object",
        }

    walked = _walk_program_records(payload, max_records=record_limit)
    records = [
        _normalize_program_record(
            record,
            endpoint_type=endpoint_type,
            source_path=source_path,
        )
        for source_path, record in walked
    ]

    total_hint = len(records)
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        total_hint = len(payload)
    elif isinstance(payload, Mapping):
        for key in ("programs", "catalog", "deployments", "items", "data"):
            candidate = payload.get(key)
            if isinstance(candidate, Sequence) and not isinstance(
                candidate, (str, bytes, bytearray)
            ):
                total_hint = max(total_hint, len(candidate))
                break
            if isinstance(candidate, Mapping):
                total_hint = max(total_hint, len(candidate))
                break

    top_level_fields = (
        [str(key) for key in list(payload)[:MAX_UNMAPPED_FIELDS]]
        if isinstance(payload, Mapping)
        else []
    )

    return {
        **endpoint,
        "payload_normalized": True,
        "record_limit": record_limit,
        "candidate_record_count": len(records),
        "records_truncated": total_hint > len(records) and len(records) >= record_limit,
        "top_level_type": "object" if isinstance(payload, Mapping) else "array",
        "top_level_fields": top_level_fields,
        "records": records,
    }


__all__ = [
    "MAX_INSTRUCTIONS",
    "MAX_RECORDS",
    "MAX_WALK_DEPTH",
    "STRUCTURED_CONTRACT",
    "X1AgentsRadioStructuredDiscoveryError",
    "normalize_x1_agents_radio_payload",
    "parse_x1_agents_radio_url",
]
