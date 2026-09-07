"""Sanitized FortiBlox App browser/network observations.

This module ingests browser-exported HAR-like data and retains only bounded
metadata about public FortiBlox discovery traffic, already-qualified FortiSwap
read-only observation routes, and previously unknown same-host GET JSON/text
routes as unqualified discovery candidates.

It never replays requests, retains cookies/authorization/payment headers,
promotes provider claims into CMIS truth, or authorizes transaction execution.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from liquidity_scout.providers.x1.fortiswap import classify_route

from .base import DISCOVERED


NETWORK_OBSERVATION_CONTRACT = "fortiblox_network_observation/v1"
FORTIBLOX_APP_HOST = "app.fortiblox.com"
ALLOWED_TARGET_HOSTS = frozenset({FORTIBLOX_APP_HOST})

PUBLIC_DISCOVERY_ROUTES = frozenset(
    {
        ("GET", "/api/x402/discovery"),
        ("GET", "/llms.txt"),
    }
)

MAX_REQUEST_BODY_BYTES = 256_000
MAX_RESPONSE_BODY_BYTES = 1_000_000

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
        "payment_signature",
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
        "payment_signature",
        "private_key",
        "secret",
        "seed",
        "session",
    }
)

_ACCEPTED_RESPONSE_TYPES = frozenset(
    {
        "application/json",
        "application/problem+json",
        "text/json",
        "text/plain",
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


def _fortiblox_referrer(request: Mapping[str, Any]) -> str | None:
    for header_name in ("referer", "origin"):
        value = _header_value(request.get("headers"), header_name)
        if value is None:
            continue
        parsed = urlsplit(value)
        if (
            parsed.scheme.casefold() == "https"
            and (parsed.hostname or "").casefold() == FORTIBLOX_APP_HOST
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

    if parsed.hostname.casefold() not in ALLOWED_TARGET_HOSTS:
        return None

    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if key.casefold() in _SENSITIVE_QUERY_KEYS:
            return None

    return text


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


def _request_post_json(request: Mapping[str, Any]) -> tuple[Any, bytes] | None:
    post_data = request.get("postData")
    if not isinstance(post_data, Mapping):
        return None

    mime = str(post_data.get("mimeType") or "").split(";", 1)[0].strip().casefold()
    if mime not in {"application/json", ""}:
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
    return payload, encoded


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


def _response_metadata(response: Mapping[str, Any]) -> dict[str, Any] | None:
    try:
        status_code = int(response.get("status"))
    except (TypeError, ValueError):
        return None
    if status_code != 402 and not 200 <= status_code < 300:
        return None

    content = response.get("content")
    if not isinstance(content, Mapping):
        return None

    encoding = str(content.get("encoding") or "").strip().casefold()
    if encoding == "base64":
        return None

    content_type = _response_content_type(response)
    if content_type not in _ACCEPTED_RESPONSE_TYPES:
        return None

    response_text = content.get("text")
    body_present = isinstance(response_text, str) and bool(response_text.strip())

    response_size = content.get("size")
    if isinstance(response_size, bool) or not isinstance(response_size, (int, float)):
        response_size = None
    elif response_size < 0:
        response_size = None
    else:
        response_size = int(response_size)

    response_sha256 = None
    response_json_parse_verified = False
    body_within_bound = True

    if body_present:
        encoded = response_text.encode("utf-8")
        response_size = len(encoded)
        if len(encoded) > MAX_RESPONSE_BODY_BYTES:
            body_within_bound = False
        else:
            response_sha256 = hashlib.sha256(encoded).hexdigest()
            if content_type in {
                "application/json",
                "application/problem+json",
                "text/json",
            }:
                try:
                    parsed = json.loads(response_text)
                except json.JSONDecodeError:
                    parsed = None
                response_json_parse_verified = isinstance(parsed, (Mapping, list))

    return {
        "status_code": status_code,
        "payment_required_observed": status_code == 402,
        "content_type": content_type,
        "response_size_bytes": response_size,
        "response_body_present": body_present,
        "response_body_within_bound": body_within_bound,
        "response_sha256": response_sha256,
        "response_json_parse_verified": response_json_parse_verified,
        "response_body_retained": False,
        "response_headers_retained": False,
        "payment_headers_retained": False,
    }


def classify_fortiblox_network_route(method: Any, url: Any) -> dict[str, Any]:
    normalized_method = str(method or "").strip().upper()
    safe_url = _safe_target_url(url)
    if safe_url is None:
        return {
            "observable": False,
            "qualification": "outside_boundary",
            "method": normalized_method or None,
            "path": None,
            "execution_authorized": False,
        }

    path = urlsplit(safe_url).path or "/"
    if (normalized_method, path) in PUBLIC_DISCOVERY_ROUTES:
        return {
            "observable": True,
            "qualification": "public_discovery",
            "method": normalized_method,
            "path": path,
            "execution_authorized": False,
        }

    route = classify_route(normalized_method, safe_url)
    if route["status"] == "allowed_read_only":
        return {
            "observable": True,
            "qualification": "allowed_read_only",
            "method": normalized_method,
            "path": path,
            "route_template": route["route_template"],
            "execution_authorized": False,
        }

    if route["status"] == "blocked_execution":
        return {
            "observable": False,
            "qualification": "blocked_execution",
            "method": normalized_method,
            "path": path,
            "route_template": route["route_template"],
            "execution_authorized": False,
        }

    if normalized_method == "GET":
        return {
            "observable": True,
            "qualification": "unqualified_get_candidate",
            "method": normalized_method,
            "path": path,
            "route_template": route["route_template"],
            "execution_authorized": False,
        }

    return {
        "observable": False,
        "qualification": "unqualified_non_get",
        "method": normalized_method or None,
        "path": path,
        "route_template": route["route_template"],
        "execution_authorized": False,
    }


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


def _observation(entry: Any, entry_index: int) -> dict[str, Any] | None:
    if not isinstance(entry, Mapping):
        return None

    request = entry.get("request")
    response = entry.get("response")
    if not isinstance(request, Mapping) or not isinstance(response, Mapping):
        return None

    referrer = _fortiblox_referrer(request)
    if referrer is None:
        return None

    source_url = _safe_target_url(request.get("url"))
    if source_url is None:
        return None

    method = str(request.get("method") or "").strip().upper()
    classification = classify_fortiblox_network_route(method, source_url)
    if not classification["observable"]:
        return None

    response_meta = _response_metadata(response)
    if response_meta is None:
        return None

    request_body_sha256 = None
    request_body_bytes = None
    if method == "POST":
        parsed = _request_post_json(request)
        if parsed is None:
            return None
        _, raw_bytes = parsed
        request_body_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        request_body_bytes = len(raw_bytes)

    return {
        "contract": NETWORK_OBSERVATION_CONTRACT,
        "entry_index": entry_index,
        "source_url": source_url,
        "fortiblox_referrer": referrer,
        "transport_method": method,
        "route": classification,
        "request_body_sha256": request_body_sha256,
        "request_body_bytes": request_body_bytes,
        "request_body_retained": False,
        "request_headers_retained": False,
        "request_cookies_retained": False,
        "payment_signature_retained": False,
        **response_meta,
        "fortiblox_network_observation": True,
        "truth_state": {
            "discovery_state": DISCOVERED,
            "route_semantics_verified": (
                classification["qualification"] in {
                    "public_discovery",
                    "allowed_read_only",
                }
            ),
            "web_claim_verified": False,
            "cmis_verified": False,
            "source_independence_verified": False,
        },
        "read_only": True,
        "request_replay_authorized": False,
        "payment_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def list_fortiblox_network_observations(har_document: Any) -> list[dict[str, Any]]:
    """Return sanitized passive FortiBlox App network observations."""

    observations: list[dict[str, Any]] = []
    for index, entry in enumerate(_entries(har_document)):
        candidate = _observation(entry, index)
        if candidate is not None:
            observations.append(candidate)
    return observations


__all__ = [
    "ALLOWED_TARGET_HOSTS",
    "FORTIBLOX_APP_HOST",
    "MAX_REQUEST_BODY_BYTES",
    "MAX_RESPONSE_BODY_BYTES",
    "NETWORK_OBSERVATION_CONTRACT",
    "PUBLIC_DISCOVERY_ROUTES",
    "classify_fortiblox_network_route",
    "list_fortiblox_network_observations",
]
