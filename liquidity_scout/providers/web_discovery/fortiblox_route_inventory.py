"""Bounded multi-page FortiBlox App browser/network inventory.

The inventory discovers same-host navigation destinations from one explicit
FortiBlox App page without clicking them, then passively opens a bounded subset
one at a time through the accepted fortiblox_browser_capture/v1 sanitizer.

Only sanitized network observations survive. No wallet interaction, forms,
authentication, payments, request replay, transaction construction, raw HAR,
or execution authority are provided.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from .fortiblox import FORTIBLOX_APP_SOURCE
from .fortiblox_browser_capture import capture_fortiblox_page_network


ROUTE_INVENTORY_CONTRACT = "fortiblox_route_inventory/v1"

DEFAULT_NAVIGATION_TIMEOUT_MS = 20_000
MAX_NAVIGATION_TIMEOUT_MS = 30_000
DEFAULT_ROUTE_DISCOVERY_DWELL_SECONDS = 3.0
MAX_ROUTE_DISCOVERY_DWELL_SECONDS = 10.0
DEFAULT_MAX_DISCOVERED_ROUTES = 20
MAX_DISCOVERED_ROUTES = 20
DEFAULT_MAX_CAPTURE_PAGES = 10
MAX_CAPTURE_PAGES = 10
DEFAULT_CAPTURE_DWELL_SECONDS = 5.0
MAX_CAPTURE_DWELL_SECONDS = 10.0
DEFAULT_MAX_NETWORK_EVENTS_PER_PAGE = 150
MAX_NETWORK_EVENTS_PER_PAGE = 150
MAX_RAW_ANCHORS = 200


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
            "FortiBlox multi-page route inventory requires the optional "
            "Playwright operator dependency."
        ) from exc
    return sync_playwright


def _navigation_page_url(value: Any, *, base_url: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None

    absolute = urljoin(base_url, text)
    parsed = urlsplit(absolute)
    if (
        parsed.scheme.casefold() != "https"
        or (parsed.hostname or "").casefold() != "app.fortiblox.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return None

    path = parsed.path or "/"
    if path.startswith("/api/") or path == "/llms.txt":
        return None

    normalized = urlunsplit(("https", "app.fortiblox.com", path, "", ""))
    try:
        return FORTIBLOX_APP_SOURCE.validate_url(normalized)
    except Exception:
        return None


def normalize_fortiblox_navigation_urls(
    page_url: str,
    hrefs: Iterable[Any],
    *,
    max_routes: int = DEFAULT_MAX_DISCOVERED_ROUTES,
) -> list[str]:
    """Return a bounded, deduplicated same-host navigation catalog."""

    limit = _bounded_int(
        "max_routes",
        max_routes,
        minimum=1,
        maximum=MAX_DISCOVERED_ROUTES,
    )
    root = FORTIBLOX_APP_SOURCE.validate_url(page_url)
    root_page = _navigation_page_url(root, base_url=root)
    if root_page is None:
        raise ValueError("page_url must be a FortiBlox navigation page")

    routes: list[str] = [root_page]
    seen = {root_page}

    for href in hrefs:
        candidate = _navigation_page_url(href, base_url=root_page)
        if candidate is None or candidate in seen:
            continue
        seen.add(candidate)
        routes.append(candidate)
        if len(routes) >= limit:
            break

    return routes


def discover_fortiblox_navigation_routes(
    page_url: str = "https://app.fortiblox.com/",
    *,
    navigation_timeout_ms: int = DEFAULT_NAVIGATION_TIMEOUT_MS,
    dwell_seconds: float = DEFAULT_ROUTE_DISCOVERY_DWELL_SECONDS,
    max_routes: int = DEFAULT_MAX_DISCOVERED_ROUTES,
    headless: bool = True,
    playwright_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Read same-host anchor destinations from one FortiBlox page, no clicks."""

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
        maximum=MAX_ROUTE_DISCOVERY_DWELL_SECONDS,
    )
    route_limit = _bounded_int(
        "max_routes",
        max_routes,
        minimum=1,
        maximum=MAX_DISCOVERED_ROUTES,
    )

    normalized_page_url = FORTIBLOX_APP_SOURCE.validate_url(page_url)
    factory = playwright_factory or _load_sync_playwright()
    raw_hrefs: list[Any] = []

    with factory() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = None
        try:
            context = browser.new_context(
                accept_downloads=False,
                service_workers="block",
            )
            page = context.new_page()
            page.goto(
                normalized_page_url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            if dwell > 0:
                page.wait_for_timeout(int(dwell * 1000))
            discovered = page.eval_on_selector_all(
                "a[href]",
                f"els => els.slice(0, {MAX_RAW_ANCHORS}).map(el => el.href)",
            )
            if isinstance(discovered, list):
                raw_hrefs = discovered[:MAX_RAW_ANCHORS]
        finally:
            if context is not None:
                context.close()
            browser.close()

    routes = normalize_fortiblox_navigation_urls(
        normalized_page_url,
        raw_hrefs,
        max_routes=route_limit,
    )
    return {
        "contract": "fortiblox_navigation_route_discovery/v1",
        "requested_page_url": normalized_page_url,
        "raw_anchor_count_bounded": len(raw_hrefs),
        "navigation_route_count": len(routes),
        "navigation_routes": routes,
        "browser_context_ephemeral": True,
        "browser_storage_state_supplied": False,
        "downloads_allowed": False,
        "clicks_performed": 0,
        "forms_submitted": 0,
        "wallet_interaction_performed": False,
        "authentication_performed": False,
        "payment_performed": False,
        "execution_authorized": False,
    }


def capture_fortiblox_route_inventory(
    page_url: str = "https://app.fortiblox.com/",
    *,
    max_routes: int = DEFAULT_MAX_DISCOVERED_ROUTES,
    max_pages: int = DEFAULT_MAX_CAPTURE_PAGES,
    route_discovery_dwell_seconds: float = DEFAULT_ROUTE_DISCOVERY_DWELL_SECONDS,
    capture_dwell_seconds: float = DEFAULT_CAPTURE_DWELL_SECONDS,
    max_network_events_per_page: int = DEFAULT_MAX_NETWORK_EVENTS_PER_PAGE,
    headless: bool = True,
    route_discovery_fn: Callable[..., dict[str, Any]] = discover_fortiblox_navigation_routes,
    capture_fn: Callable[..., dict[str, Any]] = capture_fortiblox_page_network,
) -> dict[str, Any]:
    """Discover navigation routes and passively capture a bounded subset."""

    route_limit = _bounded_int(
        "max_routes",
        max_routes,
        minimum=1,
        maximum=MAX_DISCOVERED_ROUTES,
    )
    page_limit = _bounded_int(
        "max_pages",
        max_pages,
        minimum=1,
        maximum=MAX_CAPTURE_PAGES,
    )
    route_dwell = _bounded_float(
        "route_discovery_dwell_seconds",
        route_discovery_dwell_seconds,
        minimum=0.0,
        maximum=MAX_ROUTE_DISCOVERY_DWELL_SECONDS,
    )
    capture_dwell = _bounded_float(
        "capture_dwell_seconds",
        capture_dwell_seconds,
        minimum=0.0,
        maximum=MAX_CAPTURE_DWELL_SECONDS,
    )
    event_limit = _bounded_int(
        "max_network_events_per_page",
        max_network_events_per_page,
        minimum=1,
        maximum=MAX_NETWORK_EVENTS_PER_PAGE,
    )

    route_discovery = route_discovery_fn(
        page_url,
        dwell_seconds=route_dwell,
        max_routes=route_limit,
        headless=headless,
    )
    routes = list(route_discovery.get("navigation_routes") or [])
    selected_routes = routes[:page_limit]

    page_results: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    candidate_urls: list[str] = []
    seen_candidates: set[str] = set()

    for route in selected_routes:
        try:
            capture = capture_fn(
                route,
                dwell_seconds=capture_dwell,
                max_network_events=event_limit,
                headless=headless,
            )
        except Exception as exc:
            page_results.append(
                {
                    "page_url": route,
                    "status": "UNAVAILABLE",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue

        page_results.append(
            {
                "page_url": route,
                "status": "AVAILABLE",
                "network_events_seen": capture.get("network_events_seen", 0),
                "observation_count": capture.get("observation_count", 0),
            }
        )
        for item in capture.get("observations", []):
            if not isinstance(item, dict):
                continue
            record = dict(item)
            record["page_url"] = route
            observations.append(record)
            qualification = str(
                record.get("route", {}).get("qualification") or "unknown"
            )
            counts[qualification] += 1
            if qualification == "unqualified_get_candidate":
                source_url = str(record.get("source_url") or "")
                if source_url and source_url not in seen_candidates:
                    seen_candidates.add(source_url)
                    candidate_urls.append(source_url)

    return {
        "contract": ROUTE_INVENTORY_CONTRACT,
        "source_id": "fortiblox_app",
        "route_discovery": route_discovery,
        "selected_navigation_routes": selected_routes,
        "pages_attempted": len(selected_routes),
        "page_results": page_results,
        "sanitized_observation_count": len(observations),
        "qualification_counts": dict(sorted(counts.items())),
        "unqualified_get_candidates": candidate_urls,
        "observations": observations,
        "raw_har_retained": False,
        "raw_network_records_retained": False,
        "raw_request_bodies_retained": False,
        "raw_response_bodies_retained": False,
        "request_replay_authorized": False,
        "background_monitoring_authorized": False,
        "payment_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "DEFAULT_CAPTURE_DWELL_SECONDS",
    "DEFAULT_MAX_CAPTURE_PAGES",
    "DEFAULT_MAX_DISCOVERED_ROUTES",
    "DEFAULT_MAX_NETWORK_EVENTS_PER_PAGE",
    "DEFAULT_ROUTE_DISCOVERY_DWELL_SECONDS",
    "MAX_CAPTURE_PAGES",
    "MAX_DISCOVERED_ROUTES",
    "MAX_NETWORK_EVENTS_PER_PAGE",
    "ROUTE_INVENTORY_CONTRACT",
    "capture_fortiblox_route_inventory",
    "discover_fortiblox_navigation_routes",
    "normalize_fortiblox_navigation_urls",
]
