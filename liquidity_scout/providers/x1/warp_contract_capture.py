"""Deterministic capture gate for candidate Warp machine-readable contracts.

This module does not discover URLs and does not accept endpoint semantics. It
validates a read-only captured response plus exact source provenance so the
capture can be submitted for a separate semantic-contract review.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from liquidity_scout.providers.x1.bridge_source_provenance import (
    BridgeSourceProof,
    evaluate_bridge_source_provenance,
)

CAPTURE_CONTRACT = "warp_machine_contract_capture/v1"
REQUIRED_SEMANTIC_FIELDS = (
    "route_id",
    "source_asset_id",
    "destination_asset_id",
    "route_status",
    "backing_model",
    "custody_dependency",
    "source_timestamp",
)
_ALLOWED_JSON_CONTENT_TYPES = frozenset(
    {
        "application/json",
        "application/problem+json",
    }
)
_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "apikey",
        "api_key",
        "api-key",
        "x-api-key",
        "access_token",
        "accesstoken",
        "refresh_token",
        "refreshtoken",
        "client_secret",
        "clientsecret",
        "password",
        "secret",
        "jwt",
        "cookie",
        "set-cookie",
        "session",
        "sessionid",
        "session_id",
    }
)


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _normalized_sensitive_key(value: Any) -> str:
    return str(value).strip().casefold().replace("-", "_")


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = _normalized_sensitive_key(key)
            if normalized in {_normalized_sensitive_key(k) for k in _SENSITIVE_KEYS}:
                return True
            if _contains_sensitive_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _content_type_base(value: Any) -> str:
    raw = _required_text(value, "content_type")
    return raw.split(";", 1)[0].strip().casefold()


def _resolve_path(document: Any, path: str) -> tuple[bool, Any]:
    current = document
    for part in path.split("."):
        if not part:
            return False, None
        if isinstance(current, Mapping):
            if part not in current:
                return False, None
            current = current[part]
            continue
        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                return False, None
            if index < 0 or index >= len(current):
                return False, None
            current = current[index]
            continue
        return False, None
    return True, current


def _response_hash(response_text: str) -> str:
    return hashlib.sha256(response_text.encode("utf-8")).hexdigest()


def _manifest_id(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "wmc_" + hashlib.sha256(canonical).hexdigest()[:32]


def capture_warp_machine_contract(
    *,
    source_url: Any,
    method: Any,
    status_code: Any,
    content_type: Any,
    response_text: Any,
    proofs: Any,
    field_map: Any,
    timestamp_unit: Any,
    collected_at: Any,
) -> dict[str, Any]:
    """Validate one candidate read-only machine-contract capture.

    A successful result can become *eligible for semantic review*. It never
    self-accepts endpoint semantics and never mutates the accepted registry.
    """

    url = _required_text(source_url, "source_url")
    parsed = urlsplit(url)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise ValueError("source_url must be an absolute https URL")

    normalized_method = _required_text(method, "method").upper()
    if normalized_method != "GET":
        raise ValueError("Warp machine-contract capture must use GET/read-only")

    try:
        code = int(status_code)
    except (TypeError, ValueError) as exc:
        raise ValueError("status_code must be an integer") from exc

    content_type_base = _content_type_base(content_type)
    text = _required_text(response_text, "response_text")
    if len(text.encode("utf-8")) > 1_000_000:
        raise ValueError("response_text exceeds 1 MB capture limit")

    if not isinstance(proofs, (list, tuple)):
        raise ValueError("proofs must be a list/tuple of BridgeSourceProof values")
    provenance = evaluate_bridge_source_provenance(
        url=url,
        proofs=proofs,
    )

    json_body: Any = None
    json_parse_verified = False
    if content_type_base in _ALLOWED_JSON_CONTENT_TYPES:
        try:
            json_body = json.loads(text)
        except json.JSONDecodeError:
            json_body = None
        else:
            json_parse_verified = isinstance(json_body, (Mapping, list))

    if json_parse_verified and _contains_sensitive_key(json_body):
        raise ValueError("captured response contains credential-like keys")

    if not isinstance(field_map, Mapping):
        raise ValueError("field_map must be a mapping")

    normalized_field_map: dict[str, str] = {}
    field_presence: dict[str, bool] = {}
    field_values: dict[str, Any] = {}
    for semantic_field in REQUIRED_SEMANTIC_FIELDS:
        path = _required_text(
            field_map.get(semantic_field),
            f"field_map.{semantic_field}",
        )
        normalized_field_map[semantic_field] = path
        present = False
        value = None
        if json_parse_verified:
            present, value = _resolve_path(json_body, path)
        field_presence[semantic_field] = present
        field_values[semantic_field] = value if present else None

    normalized_timestamp_unit = _required_text(
        timestamp_unit,
        "timestamp_unit",
    ).casefold()
    timestamp_unit_declared = normalized_timestamp_unit in {
        "seconds",
        "milliseconds",
        "microseconds",
        "nanoseconds",
        "iso8601",
    }

    try:
        collected = float(collected_at)
    except (TypeError, ValueError) as exc:
        raise ValueError("collected_at must be numeric epoch seconds") from exc
    if collected <= 0:
        raise ValueError("collected_at must be positive")

    source_provenance_verified = (
        provenance.source_provenance_verified
        and provenance.read_probe_eligible
    )
    http_read_verified = code == 200 and normalized_method == "GET"
    machine_json_verified = (
        http_read_verified
        and content_type_base in _ALLOWED_JSON_CONTENT_TYPES
        and json_parse_verified
    )
    required_fields_present = all(field_presence.values())

    semantic_review_ready = bool(
        source_provenance_verified
        and machine_json_verified
        and required_fields_present
        and timestamp_unit_declared
    )

    manifest_core = {
        "contract": CAPTURE_CONTRACT,
        "source_url": url,
        "host": parsed.hostname.casefold(),
        "method": normalized_method,
        "status_code": code,
        "content_type": content_type_base,
        "response_sha256": _response_hash(text),
        "response_bytes": len(text.encode("utf-8")),
        "proof_types": list(provenance.proof_types),
        "source_provenance_verified": source_provenance_verified,
        "json_parse_verified": json_parse_verified,
        "field_map": normalized_field_map,
        "field_presence": field_presence,
        "timestamp_unit": normalized_timestamp_unit,
        "timestamp_unit_declared": timestamp_unit_declared,
        "collected_at": collected,
        "semantic_review_ready": semantic_review_ready,
    }

    blockers: list[str] = []
    if not source_provenance_verified:
        blockers.append("exact_source_provenance_not_verified")
    if not http_read_verified:
        blockers.append("read_response_not_http_200")
    if content_type_base not in _ALLOWED_JSON_CONTENT_TYPES:
        blockers.append("machine_json_content_type_not_verified")
    elif not json_parse_verified:
        blockers.append("json_parse_not_verified")
    if not required_fields_present:
        blockers.append("required_semantic_fields_missing")
    if not timestamp_unit_declared:
        blockers.append("timestamp_unit_not_declared")

    return {
        **manifest_core,
        "capture_id": _manifest_id(manifest_core),
        "field_values_for_review": field_values,
        "blockers": blockers,
        "semantic_contract_accepted": False,
        "accepted_registry_mutation_authorized": False,
        "cmis_promotable": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CAPTURE_CONTRACT",
    "REQUIRED_SEMANTIC_FIELDS",
    "capture_warp_machine_contract",
]
