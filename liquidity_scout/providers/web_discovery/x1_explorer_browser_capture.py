"""Operator-controlled passive X1 Explorer browser capture.

Playwright is an optional operator dependency and is imported lazily. The
capture opens exactly one explicitly supplied, structured X1 Explorer mainnet
route in a fresh ephemeral browser context, observes bounded network responses,
immediately sanitizes each eligible event through
x1_explorer_network_observation/v1, and returns only sanitized records.

No clicks, form submission, wallet interaction, request replay, persistent
browser profile, raw HAR retention, or execution authority is provided.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

from .x1_explorer_network import (
    ALLOWED_TARGET_HOSTS,
    MAX_RESPONSE_BODY_BYTES,
    list_x1_explorer_network_observations,
)
from .x1_explorer_structured import parse_x1_explorer_url


BROWSER_CAPTURE_CONTRACT = "x1_explorer_browser_capture/v1"

DEFAULT_NAVIGATION_TIMEOUT_MS = 20_000
MAX_NAVIGATION_TIMEOUT_MS = 30_000
DEFAULT_DWELL_SECONDS = 3.0
MAX_DWELL_SECONDS = 10.0
DEFAULT_MAX_NETWORK_EVENTS = 100
MAX_NETWORK_EVENTS = 250


def _bounded_int(name: str, value: Any, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _bounded_float(
    name: str,
    value: Any,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _load_sync_playwright() -> Callable[[], Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "X1 Explorer browser capture requires the optional Playwright "
            "operator dependency. Install Playwright and its Chromium browser "
            "explicitly before using this capture utility."
        ) from exc
    return sync_playwright


def _headers_list(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, Mapping):
        return []
    result: list[dict[str, str]] = []
    for key, item in value.items():
        result.append({"name": str(key), "value": str(item)})
    return result


def _content_type(headers: Any) -> str:
    if not isinstance(headers, Mapping):
        return ""
    for key, value in headers.items():
        if str(key).casefold() == "content-type":
            return str(value or "").split(";", 1)[0].strip().casefold()
    return ""


def _allowed_target(url: str) -> bool:
    parsed = urlsplit(str(url or ""))
    return (
        parsed.scheme.casefold() == "https"
        and (parsed.hostname or "").casefold() in ALLOWED_TARGET_HOSTS
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )


def _transient_har_entry(response: Any) -> dict[str, Any] | None:
    """Build one in-memory HAR-like entry solely for immediate sanitization."""

    request = getattr(response, "request", None)
    if request is None:
        return None

    request_url = str(getattr(request, "url", "") or "")
    method = str(getattr(request, "method", "") or "").strip().upper()
    if not _allowed_target(request_url) or method not in {"GET", "POST"}:
        return None

    response_headers = getattr(response, "headers", {})
    mime_type = _content_type(response_headers)

    if method == "GET" and mime_type not in {
        "application/json",
        "application/problem+json",
        "text/json",
    }:
        return None

    request_headers = getattr(request, "headers", {})
    request_record: dict[str, Any] = {
        "method": method,
        "url": request_url,
        "headers": _headers_list(request_headers),
        "cookies": [],
    }

    if method == "POST":
        post_data = getattr(request, "post_data", None)
        if not isinstance(post_data, str) or not post_data.strip():
            return None
        request_record["postData"] = {
            "mimeType": _content_type(request_headers) or "application/json",
            "text": post_data,
        }

    status = getattr(response, "status", None)
    if isinstance(status, bool) or not isinstance(status, int):
        return None

    body_bytes: bytes | None = None
    size = None

    if isinstance(response_headers, Mapping):
        for key, value in response_headers.items():
            if str(key).casefold() != "content-length":
                continue
            try:
                parsed_size = int(str(value))
            except (TypeError, ValueError):
                parsed_size = None
            if parsed_size is not None and parsed_size >= 0:
                size = parsed_size
            break

    if size is None or size <= MAX_RESPONSE_BODY_BYTES:
        try:
            candidate = response.body()
        except Exception:
            candidate = None
        if isinstance(candidate, bytes):
            body_bytes = candidate
            size = len(candidate)

    content: dict[str, Any] = {
        "mimeType": mime_type,
        "size": size,
    }

    if body_bytes is not None and len(body_bytes) <= MAX_RESPONSE_BODY_BYTES:
        try:
            content["text"] = body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            pass

    return {
        "request": request_record,
        "response": {
            "status": status,
            "headers": _headers_list(response_headers),
            "content": content,
        },
    }


def _single_entry_har(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "log": {
            "version": "1.2",
            "entries": [dict(entry)],
        }
    }


def capture_x1_explorer_page_network(
    page_url: str,
    *,
    navigation_timeout_ms: int = DEFAULT_NAVIGATION_TIMEOUT_MS,
    dwell_seconds: float = DEFAULT_DWELL_SECONDS,
    max_network_events: int = DEFAULT_MAX_NETWORK_EVENTS,
    headless: bool = True,
    playwright_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Passively capture one explicit X1 Explorer page.

    The playwright_factory argument exists for deterministic tests; production
    callers normally omit it, which triggers the lazy optional Playwright
    import.
    """

    if not isinstance(headless, bool):
        raise ValueError("headless must be a boolean")

    timeout_ms = _bounded_int(
        "navigation_timeout_ms",
        navigation_timeout_ms,
        minimum=1_000,
        maximum=MAX_NAVIGATION_TIMEOUT_MS,
    )
    dwell = _bounded_float(
        "dwell_seconds",
        dwell_seconds,
        minimum=0.0,
        maximum=MAX_DWELL_SECONDS,
    )
    event_limit = _bounded_int(
        "max_network_events",
        max_network_events,
        minimum=1,
        maximum=MAX_NETWORK_EVENTS,
    )

    structured_route = parse_x1_explorer_url(page_url)
    if not structured_route["supported"]:
        raise ValueError(
            "page_url must be a supported structured X1 Explorer mainnet route"
        )

    factory = playwright_factory or _load_sync_playwright()
    observations: list[dict[str, Any]] = []
    network_events_seen = 0

    with factory() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = None
        try:
            context = browser.new_context(
                accept_downloads=False,
                service_workers="block",
            )
            page = context.new_page()

            def on_response(response: Any) -> None:
                nonlocal network_events_seen
                if network_events_seen >= event_limit:
                    return
                network_events_seen += 1

                transient = _transient_har_entry(response)
                if transient is None:
                    return

                sanitized = list_x1_explorer_network_observations(
                    _single_entry_har(transient)
                )
                if sanitized:
                    item = dict(sanitized[0])
                    item["capture_event_index"] = network_events_seen - 1
                    observations.append(item)

            page.on("response", on_response)
            page.goto(
                structured_route["url"],
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            if dwell > 0:
                page.wait_for_timeout(int(dwell * 1000))
        finally:
            if context is not None:
                context.close()
            browser.close()

    return {
        "contract": BROWSER_CAPTURE_CONTRACT,
        "requested_page_url": structured_route["url"],
        "structured_route": structured_route,
        "capture_bounds": {
            "one_page": True,
            "navigation_timeout_ms": timeout_ms,
            "dwell_seconds": dwell,
            "max_network_events": event_limit,
        },
        "network_events_seen": network_events_seen,
        "observation_count": len(observations),
        "observations": observations,
        "browser_context_ephemeral": True,
        "browser_storage_state_supplied": False,
        "downloads_allowed": False,
        "clicks_performed": 0,
        "forms_submitted": 0,
        "wallet_interaction_performed": False,
        "raw_har_retained": False,
        "raw_network_records_retained": False,
        "raw_request_bodies_retained": False,
        "raw_response_bodies_retained": False,
        "request_replay_authorized": False,
        "background_monitoring_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "BROWSER_CAPTURE_CONTRACT",
    "DEFAULT_DWELL_SECONDS",
    "DEFAULT_MAX_NETWORK_EVENTS",
    "DEFAULT_NAVIGATION_TIMEOUT_MS",
    "MAX_DWELL_SECONDS",
    "MAX_NETWORK_EVENTS",
    "MAX_NAVIGATION_TIMEOUT_MS",
    "capture_x1_explorer_page_network",
]
