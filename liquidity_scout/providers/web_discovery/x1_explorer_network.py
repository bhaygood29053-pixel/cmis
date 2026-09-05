"""Sanitized X1 Explorer browser/network observations.

This module ingests browser-exported HAR data. It does not launch a browser,
replay captured requests, retain cookies/authorization headers, or treat an
observed response as verified chain truth.

JSON-RPC uses HTTP POST even for read-only methods. This contract distinguishes
transport method from execution authority and accepts only an explicit bounded
read-only RPC method allowlist.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from .base import DISCOVERED
from .x1_explorer_structured import parse_x1_explorer_url


NETWORK_OBSERVATION_CONTRACT = "x1_explorer_network_observation/v1"
OFFICIAL_EXPLORER_HOST = "explorer.mainnet.x1.xyz"
ALLOWED_TARGET_HOSTS = frozenset(
    {
        "explorer.mainnet.x1.xyz",
        "rpc.mainnet.x1.xyz",
    }
)

READ_ONLY_RPC_METHODS = frozenset(
    {
        "getSignatureStatuses",
        "getBlockTime",
        "getTransaction",
        "getSignaturesForAddress",
        "getMultipleAccounts",
        "getBlock",
        "getBlocks",
        "getSlotLeaders",
        "getFirstAvailableBlock",
        "getEpochSchedule",
        "getEpochInfo",
    }
)

MAX_REQUEST_BODY_BYTES = 256_000
MAX_RESPONSE_BODY_BYTES = 1_000_000
MAX_RPC_BATCH = 50
MAX_SAFE_IDENTIFIERS = 50

_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "auth_token",
        "authorization",
        "bearer",
        "client_secret",
        "credential",
        "jwt",
        "password",
        "secret",
        "session",
        "token",
    }
)

_SENSITIVE_BODY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "auth_token",
        "authorization",
        "bearer",
        "client_secret",
        "credential",
        "jwt",
        "password",
        "secret",
        "session",
        "token",
    }
)


def _header_value(headers: Any, name: str) -> str | None:
    if not isinstance(headers, list):
        return None
    wanted = name.casefold()
    for item in headers:
        if not isinstance(item, Mapping):
            continue
        key = str(item.get("name") or "").strip().casefold()
        if key != wanted:
            continue
        value = str(item.get("value") or "").strip()
        return value or None
    return None


def _official_explorer_referrer(request: Mapping[str, Any]) -> str | None:
    for header_name in ("referer", "origin"):
        value = _header_value(request.get("headers"), header_name)
        if value is None:
            continue
        parsed = urlsplit(value)
        if (
            parsed.scheme.casefold() == "https"
            and (parsed.hostname or "").casefold() == OFFICIAL_EXPLORER_HOST
            and parsed.username is None
            and parsed.password is None
        ):
            return value
    return None


def _safe_target_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None

    parsed = urlsplit(text)
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        return None

    host = parsed.hostname.casefold()
    if host not in ALLOWED_TARGET_HOSTS:
        return None

    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if key.casefold() in _SENSITIVE_QUERY_KEYS:
            return None

    return text


def _response_content_type(response: Mapping[str, Any]) -> str:
    content = response.get("content")
    if isinstance(content, Mapping):
        mime = str(content.get("mimeType") or "").strip()
        if mime:
            return mime.split(";", 1)[0].strip().casefold()

    header = _header_value(response.get("headers"), "content-type")
    if header:
        return header.split(";", 1)[0].strip().casefold()
    return ""


def _entries(document: Any) -> list[Any]:
    if not isinstance(document, Mapping):
        raise ValueError("HAR document must be a mapping")
    log = document.get("log")
    if not isinstance(log, Mapping):
        raise ValueError("HAR document must contain log")
    entries = log.get("entries")
    if not isinstance(entries, list):
        raise ValueError("HAR document must contain log.entries")
    return entries


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in _SENSITIVE_BODY_KEYS:
                return True
            if _contains_sensitive_key(item):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _request_post_json(request: Mapping[str, Any]) -> Any | None:
    post_data = request.get("postData")
    if not isinstance(post_data, Mapping):
        return None

    mime = str(post_data.get("mimeType") or "").split(";", 1)[0].strip().casefold()
    if mime not in {"application/json", "application/json-rpc", ""}:
        return None

    text = post_data.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_REQUEST_BODY_BYTES:
        return None

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    if _contains_sensitive_key(payload):
        return None
    return payload


def _rpc_calls(payload: Any) -> list[Mapping[str, Any]] | None:
    if isinstance(payload, Mapping):
        calls = [payload]
    elif isinstance(payload, list):
        if not payload or len(payload) > MAX_RPC_BATCH:
            return None
        if not all(isinstance(item, Mapping) for item in payload):
            return None
        calls = list(payload)
    else:
        return None

    for call in calls:
        if str(call.get("jsonrpc") or "") != "2.0":
            return None
        method = str(call.get("method") or "").strip()
        if method not in READ_ONLY_RPC_METHODS:
            return None
        params = call.get("params", [])
        if not isinstance(params, list):
            return None
    return calls


def _candidate_from_explorer_route(path: str) -> dict[str, Any] | None:
    try:
        result = parse_x1_explorer_url(
            f"https://{OFFICIAL_EXPLORER_HOST}{path}"
        )
    except Exception:
        return None
    return result if result.get("supported") else None


def _safe_identifier_records(method: str, params: list[Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def add_route(path: str, role: str) -> None:
        if len(records) >= MAX_SAFE_IDENTIFIERS:
            return
        route = _candidate_from_explorer_route(path)
        if route is None:
            return
        records.append(
            {
                "role": role,
                "entity_type": route["entity_type"],
                "identifier": route["identifier"],
                "explorer_route": route["path"],
                "entity_identity_verified": False,
            }
        )

    if method == "getTransaction" and params and isinstance(params[0], str):
        add_route(f"/tx/{params[0]}", "transaction_signature")

    elif method == "getSignaturesForAddress" and params and isinstance(params[0], str):
        add_route(f"/address/{params[0]}", "address")

    elif method == "getMultipleAccounts" and params and isinstance(params[0], list):
        for value in params[0][:MAX_SAFE_IDENTIFIERS]:
            if isinstance(value, str):
                add_route(f"/address/{value}", "address")

    elif method == "getSignatureStatuses" and params and isinstance(params[0], list):
        for value in params[0][:MAX_SAFE_IDENTIFIERS]:
            if isinstance(value, str):
                add_route(f"/tx/{value}", "transaction_signature")

    elif method in {"getBlock", "getBlockTime"} and params:
        value = params[0]
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            add_route(f"/block/{value}", "slot")

    elif method == "getBlocks" and params:
        for value in params[:2]:
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                add_route(f"/block/{value}", "slot_bound")

    elif method == "getSlotLeaders" and params:
        value = params[0]
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            add_route(f"/block/{value}", "first_slot")

    return records


def _rpc_summary(calls: list[Mapping[str, Any]]) -> dict[str, Any]:
    methods: list[str] = []
    identifiers: list[dict[str, Any]] = []
    seen_identifiers: set[tuple[str, str, str]] = set()

    for call in calls:
        method = str(call["method"])
        methods.append(method)
        params = call.get("params", [])
        for record in _safe_identifier_records(method, params):
            key = (
                str(record["role"]),
                str(record["entity_type"]),
                str(record["identifier"]),
            )
            if key in seen_identifiers:
                continue
            seen_identifiers.add(key)
            identifiers.append(record)
            if len(identifiers) >= MAX_SAFE_IDENTIFIERS:
                break

    return {
        "rpc_call_count": len(calls),
        "rpc_methods": methods,
        "rpc_methods_unique": list(dict.fromkeys(methods)),
        "safe_identifiers": identifiers,
    }


def _response_metadata(response: Mapping[str, Any]) -> dict[str, Any] | None:
    try:
        status_code = int(response.get("status"))
    except (TypeError, ValueError):
        return None
    if status_code < 200 or status_code >= 300:
        return None

    content = response.get("content")
    if not isinstance(content, Mapping):
        return None

    encoding = str(content.get("encoding") or "").strip().casefold()
    if encoding == "base64":
        return None

    content_type = _response_content_type(response)
    response_text = content.get("text")
    body_present = isinstance(response_text, str) and bool(response_text.strip())

    response_size = content.get("size")
    if isinstance(response_size, bool) or not isinstance(response_size, (int, float)):
        response_size = None
    elif response_size < 0:
        response_size = None
    else:
        response_size = int(response_size)

    sha256 = None
    json_parse_verified = False
    body_within_bound = True

    if body_present:
        encoded = response_text.encode("utf-8")
        response_size = len(encoded)
        if len(encoded) > MAX_RESPONSE_BODY_BYTES:
            body_within_bound = False
        else:
            try:
                parsed = json.loads(response_text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, (Mapping, list)):
                json_parse_verified = True
                sha256 = hashlib.sha256(encoded).hexdigest()

    return {
        "status_code": status_code,
        "content_type": content_type or None,
        "response_size_bytes": response_size,
        "response_body_present": body_present,
        "response_body_within_bound": body_within_bound,
        "response_sha256": sha256,
        "response_json_parse_verified": json_parse_verified,
        "response_body_retained": False,
        "response_headers_retained": False,
    }


def _observation(entry: Any, entry_index: int) -> dict[str, Any] | None:
    if not isinstance(entry, Mapping):
        return None

    request = entry.get("request")
    response = entry.get("response")
    if not isinstance(request, Mapping) or not isinstance(response, Mapping):
        return None

    referrer = _official_explorer_referrer(request)
    if referrer is None:
        return None

    source_url = _safe_target_url(request.get("url"))
    if source_url is None:
        return None

    method = str(request.get("method") or "").strip().upper()
    if method not in {"GET", "POST"}:
        return None

    response_meta = _response_metadata(response)
    if response_meta is None:
        return None

    rpc_summary = None
    request_body_sha256 = None
    request_body_bytes = None

    if method == "POST":
        payload = _request_post_json(request)
        if payload is None:
            return None
        calls = _rpc_calls(payload)
        if calls is None:
            return None

        post_data = request.get("postData")
        assert isinstance(post_data, Mapping)
        raw_text = str(post_data.get("text") or "")
        raw_bytes = raw_text.encode("utf-8")
        request_body_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        request_body_bytes = len(raw_bytes)
        rpc_summary = _rpc_summary(calls)

    elif method == "GET":
        content_type = response_meta["content_type"]
        if content_type not in {
            "application/json",
            "application/problem+json",
            "text/json",
        }:
            return None

    return {
        "contract": NETWORK_OBSERVATION_CONTRACT,
        "entry_index": entry_index,
        "source_url": source_url,
        "explorer_referrer": referrer,
        "transport_method": method,
        "request_body_sha256": request_body_sha256,
        "request_body_bytes": request_body_bytes,
        "request_body_retained": False,
        "request_headers_retained": False,
        "request_cookies_retained": False,
        "rpc_read_method_recognized": rpc_summary is not None,
        "rpc": rpc_summary,
        **response_meta,
        "official_explorer_network_observation": True,
        "truth_state": {
            "discovery_state": DISCOVERED,
            "entity_identity_verified": False,
            "web_claim_verified": False,
            "cmis_verified": False,
            "source_independence_verified": False,
        },
        "read_only": True,
        "request_replay_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def list_x1_explorer_network_observations(har_document: Any) -> list[dict[str, Any]]:
    """Return sanitized official-X1-Explorer network observations."""

    observations: list[dict[str, Any]] = []
    for index, entry in enumerate(_entries(har_document)):
        candidate = _observation(entry, index)
        if candidate is not None:
            observations.append(candidate)
    return observations


__all__ = [
    "ALLOWED_TARGET_HOSTS",
    "MAX_REQUEST_BODY_BYTES",
    "MAX_RESPONSE_BODY_BYTES",
    "NETWORK_OBSERVATION_CONTRACT",
    "OFFICIAL_EXPLORER_HOST",
    "READ_ONLY_RPC_METHODS",
    "list_x1_explorer_network_observations",
]
