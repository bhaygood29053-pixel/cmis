"""Safe HAR ingestion for Warp Issue #407 network evidence.

This module converts a browser-exported HAR observation into a narrow,
read-only candidate for warp_machine_contract_capture/v1. It does not
perform network requests, infer endpoint paths, accept semantics, or retain
request headers/cookies.
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
from liquidity_scout.providers.x1.warp_contract_capture import (
    capture_warp_machine_contract,
)

HAR_OBSERVATION_CONTRACT = "warp_har_network_observation/v1"
HAR_METADATA_OBSERVATION_CONTRACT = "warp_har_network_metadata_observation/v1"
OFFICIAL_BRIDGE_APP_HOST = "app.bridge.x1.xyz"
_ALLOWED_JSON_CONTENT_TYPES = frozenset(
    {
        "application/json",
        "application/problem+json",
    }
)


def _header_value(headers: Any, name: str) -> str | None:
    if not isinstance(headers, list):
        return None
    target = name.casefold()
    for item in headers:
        if not isinstance(item, Mapping):
            continue
        header_name = str(item.get("name") or "").strip().casefold()
        if header_name != target:
            continue
        value = str(item.get("value") or "").strip()
        return value or None
    return None


def _is_official_bridge_app_url(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    parsed = urlsplit(text)
    return (
        parsed.scheme.casefold() == "https"
        and (parsed.hostname or "").casefold() == OFFICIAL_BRIDGE_APP_HOST
        and not parsed.username
        and not parsed.password
    )


def _official_app_referrer(request: Mapping[str, Any]) -> str | None:
    headers = request.get("headers")
    referer = _header_value(headers, "referer")
    if _is_official_bridge_app_url(referer):
        return referer

    origin = _header_value(headers, "origin")
    if _is_official_bridge_app_url(origin):
        return origin
    return None


def _content_type(response: Mapping[str, Any]) -> str:
    content = response.get("content")
    if isinstance(content, Mapping):
        mime_type = str(content.get("mimeType") or "").strip()
        if mime_type:
            return mime_type.split(";", 1)[0].strip().casefold()

    header = _header_value(response.get("headers"), "content-type")
    if header:
        return header.split(";", 1)[0].strip().casefold()
    return ""


def _entries(har_document: Any) -> list[Any]:
    if not isinstance(har_document, Mapping):
        raise ValueError("HAR document must be a mapping")
    log = har_document.get("log")
    if not isinstance(log, Mapping):
        raise ValueError("HAR document must contain log")
    entries = log.get("entries")
    if not isinstance(entries, list):
        raise ValueError("HAR document must contain log.entries")
    return entries


def _entry_payload(entry: Any, entry_index: int) -> dict[str, Any] | None:
    if not isinstance(entry, Mapping):
        return None

    request = entry.get("request")
    response = entry.get("response")
    if not isinstance(request, Mapping) or not isinstance(response, Mapping):
        return None

    method = str(request.get("method") or "").strip().upper()
    if method != "GET":
        return None

    source_url = str(request.get("url") or "").strip()
    parsed = urlsplit(source_url)
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        return None

    referrer = _official_app_referrer(request)
    if referrer is None:
        return None

    try:
        status_code = int(response.get("status"))
    except (TypeError, ValueError):
        return None
    if status_code != 200:
        return None

    content_type = _content_type(response)
    if content_type not in _ALLOWED_JSON_CONTENT_TYPES:
        return None

    content = response.get("content")
    if not isinstance(content, Mapping):
        return None

    encoding = str(content.get("encoding") or "").strip().casefold()
    if encoding == "base64":
        return None

    response_text = content.get("text")
    if not isinstance(response_text, str) or not response_text.strip():
        return None
    if len(response_text.encode("utf-8")) > 1_000_000:
        return None

    try:
        parsed_json = json.loads(response_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed_json, (Mapping, list)):
        return None

    proof = BridgeSourceProof(
        proof_type="official_app_network_observation",
        reference=f"HAR entry {entry_index}; referrer={referrer}",
        exact_url=source_url,
    )
    try:
        provenance = evaluate_bridge_source_provenance(
            url=source_url,
            proofs=[proof],
        )
    except (TypeError, ValueError):
        return None
    if not (
        provenance.source_provenance_verified
        and provenance.read_probe_eligible
    ):
        return None

    return {
        "entry_index": entry_index,
        "source_url": source_url,
        "method": method,
        "status_code": status_code,
        "content_type": content_type,
        "response_text": response_text,
        "app_referrer": referrer,
        "proof": proof,
    }


def list_warp_har_observations(har_document: Any) -> list[dict[str, Any]]:
    """Return sanitized official-app GET+200+JSON network observations.

    This preserves exact endpoint provenance when a Chrome HAR contains
    response metadata but omits response.content.text. Metadata-only
    observations are never semantic capture candidates.
    """

    observations: list[dict[str, Any]] = []
    for index, entry in enumerate(_entries(har_document)):
        if not isinstance(entry, Mapping):
            continue

        request = entry.get("request")
        response = entry.get("response")
        if not isinstance(request, Mapping) or not isinstance(response, Mapping):
            continue

        method = str(request.get("method") or "").strip().upper()
        if method != "GET":
            continue

        source_url = str(request.get("url") or "").strip()
        parsed = urlsplit(source_url)
        if (
            parsed.scheme.casefold() != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            continue

        referrer = _official_app_referrer(request)
        if referrer is None:
            continue

        try:
            status_code = int(response.get("status"))
        except (TypeError, ValueError):
            continue
        if status_code != 200:
            continue

        content_type = _content_type(response)
        if content_type not in _ALLOWED_JSON_CONTENT_TYPES:
            continue

        content = response.get("content")
        if not isinstance(content, Mapping):
            continue
        encoding = str(content.get("encoding") or "").strip().casefold()
        if encoding == "base64":
            continue

        proof = BridgeSourceProof(
            proof_type="official_app_network_observation",
            reference=f"HAR entry {index}; referrer={referrer}",
            exact_url=source_url,
        )
        try:
            provenance = evaluate_bridge_source_provenance(
                url=source_url,
                proofs=[proof],
            )
        except (TypeError, ValueError):
            continue
        if not (
            provenance.source_provenance_verified
            and provenance.read_probe_eligible
        ):
            continue

        response_text = content.get("text")
        response_body_present = (
            isinstance(response_text, str) and bool(response_text.strip())
        )
        json_parse_verified = False
        response_sha256 = None
        response_size = content.get("size")
        if not isinstance(response_size, (int, float)) or response_size < 0:
            response_size = None
        else:
            response_size = int(response_size)

        if response_body_present:
            encoded = response_text.encode("utf-8")
            if len(encoded) <= 1_000_000:
                try:
                    parsed_json = json.loads(response_text)
                except json.JSONDecodeError:
                    parsed_json = None
                if isinstance(parsed_json, (Mapping, list)):
                    json_parse_verified = True
                    response_sha256 = hashlib.sha256(encoded).hexdigest()
                    response_size = len(encoded)

        observations.append(
            {
                "contract": HAR_METADATA_OBSERVATION_CONTRACT,
                "entry_index": index,
                "source_url": source_url,
                "app_referrer": referrer,
                "method": "GET",
                "status_code": status_code,
                "content_type": content_type,
                "response_size_bytes": response_size,
                "response_body_present": response_body_present,
                "response_sha256": response_sha256,
                "json_parse_verified": json_parse_verified,
                "semantic_capture_eligible": json_parse_verified,
                "official_app_network_observation": True,
                "request_headers_retained": False,
                "response_headers_retained": False,
                "response_body_retained": False,
                "read_only": True,
                "execution_authorized": False,
            }
        )
    return observations

def list_warp_har_candidates(har_document: Any) -> list[dict[str, Any]]:
    """Return sanitized metadata for exact GET+JSON observations.

    Response bodies, request headers, cookies, and authorization material are
    deliberately omitted from the returned candidate list.
    """

    candidates: list[dict[str, Any]] = []
    for index, entry in enumerate(_entries(har_document)):
        payload = _entry_payload(entry, index)
        if payload is None:
            continue
        response_text = payload["response_text"]
        candidates.append(
            {
                "contract": HAR_OBSERVATION_CONTRACT,
                "entry_index": index,
                "source_url": payload["source_url"],
                "app_referrer": payload["app_referrer"],
                "method": "GET",
                "status_code": payload["status_code"],
                "content_type": payload["content_type"],
                "response_sha256": hashlib.sha256(
                    response_text.encode("utf-8")
                ).hexdigest(),
                "response_bytes": len(response_text.encode("utf-8")),
                "json_parse_verified": True,
                "official_app_network_observation": True,
                "request_headers_retained": False,
                "response_body_retained": False,
                "read_only": True,
                "execution_authorized": False,
            }
        )
    return candidates


def capture_warp_machine_contract_from_har(
    *,
    har_document: Any,
    entry_index: Any,
    field_map: Any,
    timestamp_unit: Any,
    collected_at: Any,
) -> dict[str, Any]:
    """Submit one explicitly selected HAR entry to the existing capture gate."""

    try:
        index = int(entry_index)
    except (TypeError, ValueError) as exc:
        raise ValueError("entry_index must be an integer") from exc

    entries = _entries(har_document)
    if index < 0 or index >= len(entries):
        raise ValueError("entry_index is outside HAR log.entries")

    payload = _entry_payload(entries[index], index)
    if payload is None:
        raise ValueError(
            "selected HAR entry is not an official-app GET+200+JSON observation"
        )

    result = capture_warp_machine_contract(
        source_url=payload["source_url"],
        method=payload["method"],
        status_code=payload["status_code"],
        content_type=payload["content_type"],
        response_text=payload["response_text"],
        proofs=[payload["proof"]],
        field_map=field_map,
        timestamp_unit=timestamp_unit,
        collected_at=collected_at,
    )
    return {
        **result,
        "network_observation_contract": HAR_OBSERVATION_CONTRACT,
        "har_entry_index": index,
        "official_app_referrer": payload["app_referrer"],
        "official_app_network_observation": True,
    }


__all__ = [
    "HAR_OBSERVATION_CONTRACT",
    "HAR_METADATA_OBSERVATION_CONTRACT",
    "OFFICIAL_BRIDGE_APP_HOST",
    "capture_warp_machine_contract_from_har",
    "list_warp_har_candidates",
    "list_warp_har_observations",
]
