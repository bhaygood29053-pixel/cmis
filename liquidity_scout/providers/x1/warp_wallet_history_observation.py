"""Sanitized official Warp wallet-history network observation gate.

This module records the exact read-only History-page endpoint pattern discovered
from official app network traffic while deliberately redacting the wallet
identifier. It does not infer transaction field semantics or promote history
responses into CMIS flow facts.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from liquidity_scout.providers.x1.bridge_source_provenance import (
    BridgeSourceProof,
    evaluate_bridge_source_provenance,
)

CONTRACT = "warp_wallet_history_observation/v1"
OFFICIAL_APP_HOST = "app.bridge.x1.xyz"
OFFICIAL_HISTORY_URL = "https://app.bridge.x1.xyz/history"
SOURCE_URL_TEMPLATE = (
    "https://app.bridge.x1.xyz/api/bridge/transactions/wallet/{wallet}?limit=100"
)
_HISTORY_PATH_RE = re.compile(
    r"^/api/bridge/transactions/wallet/([1-9A-HJ-NP-Za-km-z]{32,64})$"
)
_ALLOWED_JSON_CONTENT_TYPES = {
    "application/json",
    "application/problem+json",
}


def _header_value(headers: Any, name: str) -> str | None:
    if not isinstance(headers, list):
        return None
    target = name.casefold()
    for item in headers:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("name") or "").strip().casefold() != target:
            continue
        value = str(item.get("value") or "").strip()
        return value or None
    return None


def _content_type(response: Mapping[str, Any]) -> str:
    content = response.get("content")
    if isinstance(content, Mapping):
        mime_type = str(content.get("mimeType") or "").strip()
        if mime_type:
            return mime_type.split(";", 1)[0].strip().casefold()
    header = _header_value(response.get("headers"), "content-type")
    return (
        header.split(";", 1)[0].strip().casefold()
        if header
        else ""
    )


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


def _is_exact_history_referrer(request: Mapping[str, Any]) -> bool:
    value = _header_value(request.get("headers"), "referer")
    if not value:
        return False
    parsed = urlsplit(value)
    return (
        parsed.scheme.casefold() == "https"
        and (parsed.hostname or "").casefold() == OFFICIAL_APP_HOST
        and parsed.path == "/history"
        and not parsed.query
        and not parsed.fragment
        and not parsed.username
        and not parsed.password
    )


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def list_warp_wallet_history_observations(
    har_document: Any,
) -> list[dict[str, Any]]:
    """Return sanitized exact History-page wallet-transaction observations.

    The wallet identifier and exact wallet-bearing source URL are never returned.
    """

    observations: list[dict[str, Any]] = []
    for index, entry in enumerate(_entries(har_document)):
        if not isinstance(entry, Mapping):
            continue
        request = entry.get("request")
        response = entry.get("response")
        if not isinstance(request, Mapping) or not isinstance(response, Mapping):
            continue

        if str(request.get("method") or "").strip().upper() != "GET":
            continue
        if not _is_exact_history_referrer(request):
            continue

        source_url = str(request.get("url") or "").strip()
        parsed = urlsplit(source_url)
        if (
            parsed.scheme.casefold() != "https"
            or (parsed.hostname or "").casefold() != OFFICIAL_APP_HOST
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            continue

        match = _HISTORY_PATH_RE.fullmatch(parsed.path)
        if match is None:
            continue

        query = parse_qsl(parsed.query, keep_blank_values=True)
        if query != [("limit", "100")]:
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
        if str(content.get("encoding") or "").strip().casefold() == "base64":
            continue

        proof = BridgeSourceProof(
            proof_type="official_app_network_observation",
            reference=(
                f"HAR entry {index}; referrer={OFFICIAL_HISTORY_URL}; "
                "wallet_identifier_redacted=true"
            ),
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
        if isinstance(response_size, bool) or not isinstance(
            response_size, (int, float)
        ) or response_size < 0:
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

        sanitized_core = {
            "contract": CONTRACT,
            "entry_index": index,
            "source_url_template": SOURCE_URL_TEMPLATE,
            "method": "GET",
            "query_limit": 100,
            "status_code": status_code,
            "content_type": content_type,
            "response_size_bytes": response_size,
            "response_body_present": response_body_present,
            "response_sha256": response_sha256,
            "json_parse_verified": json_parse_verified,
        }

        observations.append(
            {
                **sanitized_core,
                "observation_sha256": _canonical_sha256(sanitized_core),
                "official_history_network_observation": True,
                "source_provenance_verified": True,
                "wallet_identifier_retained": False,
                "exact_wallet_url_retained": False,
                "semantic_capture_eligible": json_parse_verified,
                "transaction_semantics_accepted": False,
                "coverage_semantics_accepted": False,
                "request_headers_retained": False,
                "response_headers_retained": False,
                "response_body_retained": False,
                "read_only": True,
                "execution_authorized": False,
            }
        )

    return observations


__all__ = [
    "CONTRACT",
    "OFFICIAL_HISTORY_URL",
    "SOURCE_URL_TEMPLATE",
    "list_warp_wallet_history_observations",
]
