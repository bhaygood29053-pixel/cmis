"""Bounded read-only web discovery transport beneath CMIS.

This module collects candidate web evidence only. It does not promote a web
page, API response, documentation statement, explorer label, repository file,
or reporting claim into verified CMIS truth.

Every observation produced here starts at discovery_state=DISCOVERED and keeps
CMIS verification, source-independence, public-service promotion, Scout
reliance, and execution authority false.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
import time
from typing import Any, Optional
from urllib.parse import urljoin, urlparse, urlunparse

import requests


CONTRACT = "cmis_web_discovery/v1"
DISCOVERED = "DISCOVERED"

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_BYTES = 256_000
DEFAULT_MAX_LINKS = 100
DEFAULT_MAX_PAGES = 5
DEFAULT_MAX_DEPTH = 1
MAX_ALLOWED_DEPTH = 2
MAX_REDIRECTS = 5
MAX_QUERY_LENGTH = 500
MAX_EXCERPT_CHARS = 8_000

USER_AGENT = "CMIS-Web-Discovery/1.0 (+read-only; candidate-evidence)"


class WebDiscoveryError(RuntimeError):
    """Base error for bounded CMIS web discovery."""


class SourceBoundaryError(WebDiscoveryError):
    """Raised when a request or redirect escapes a source allowlist."""


class WebDiscoveryHTTPError(WebDiscoveryError):
    """Raised when a bounded HTTP request cannot be accepted."""


class WebDiscoveryContentError(WebDiscoveryError):
    """Raised when response content cannot be safely normalized."""


@dataclass(frozen=True)
class WebDiscoverySource:
    """Source-specific authority boundary for one discovery provider."""

    source_id: str
    source_name: str
    source_role: str
    base_urls: tuple[str, ...]
    allowed_hosts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id must not be empty")
        if not self.source_name.strip():
            raise ValueError("source_name must not be empty")
        if not self.source_role.strip():
            raise ValueError("source_role must not be empty")
        if not self.base_urls:
            raise ValueError("base_urls must not be empty")
        if not self.allowed_hosts:
            raise ValueError("allowed_hosts must not be empty")

        normalized_hosts = tuple(_normalize_host(host) for host in self.allowed_hosts)
        if len(set(normalized_hosts)) != len(normalized_hosts):
            raise ValueError("allowed_hosts must be unique")

        for url in self.base_urls:
            normalized = normalize_http_url(url)
            host = _normalize_host(urlparse(normalized).hostname or "")
            if host not in normalized_hosts:
                raise ValueError(
                    f"base URL host {host!r} is not present in allowed_hosts"
                )

    @property
    def default_url(self) -> str:
        return normalize_http_url(self.base_urls[0])

    def validate_url(self, url: str) -> str:
        normalized = normalize_http_url(url)
        host = _normalize_host(urlparse(normalized).hostname or "")
        allowed = {_normalize_host(item) for item in self.allowed_hosts}
        if host not in allowed:
            raise SourceBoundaryError(
                f"{self.source_id} discovery URL host {host!r} is outside "
                f"the source allowlist"
            )
        return normalized


def _normalize_host(value: str) -> str:
    text = str(value or "").strip().rstrip(".").casefold()
    if not text:
        raise ValueError("host must not be empty")
    return text


def normalize_http_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("url must not be empty")

    parsed = urlparse(text)
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise SourceBoundaryError("web discovery supports only http/https URLs")
    if not parsed.hostname:
        raise SourceBoundaryError("web discovery URL must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise SourceBoundaryError("web discovery URL must not embed credentials")

    scheme = parsed.scheme.casefold()
    host = _normalize_host(parsed.hostname)
    port = parsed.port
    netloc = host if port is None else f"{host}:{port}"
    path = parsed.path or "/"
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def _positive_int(name: str, value: Any, *, maximum: Optional[int] = None) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < 1:
        raise ValueError(f"{name} must be positive")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return parsed


def _nonnegative_int(name: str, value: Any, *, maximum: Optional[int] = None) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return parsed


def _header(response: Any, name: str) -> Optional[str]:
    headers = getattr(response, "headers", None)
    if not isinstance(headers, Mapping):
        return None
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            text = str(value or "").strip()
            return text or None
    return None


def _response_bytes(response: Any) -> bytes:
    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content
    if isinstance(content, bytearray):
        return bytes(content)

    text = getattr(response, "text", None)
    if text is None:
        raise WebDiscoveryContentError("response exposes neither bytes nor text")
    return str(text).encode("utf-8", errors="replace")


def _decode_body(response: Any, body: bytes) -> str:
    encoding = str(getattr(response, "encoding", "") or "").strip() or "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _normalized_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _query_terms(query: Optional[str]) -> tuple[str, ...]:
    if query is None:
        return ()
    text = str(query).strip()
    if not text:
        return ()
    if len(text) > MAX_QUERY_LENGTH:
        raise ValueError(f"query must be <= {MAX_QUERY_LENGTH} characters")

    terms: list[str] = []
    for token in re.findall(r"[A-Za-z0-9_.:/-]+", text.casefold()):
        if token and token not in terms:
            terms.append(token)
    return tuple(terms)


def _query_record(text: str, query: Optional[str]) -> dict[str, Any]:
    terms = _query_terms(query)
    haystack = text.casefold()
    counts = {term: haystack.count(term) for term in terms}
    matched = [term for term, count in counts.items() if count > 0]
    return {
        "query": None if query is None else str(query),
        "terms": list(terms),
        "matched": bool(matched) if terms else None,
        "matched_terms": matched,
        "term_counts": counts,
    }


class _HTMLDiscoveryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        name = tag.casefold()
        if name in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if name == "title":
            self._in_title = True
        if name == "a":
            for key, value in attrs:
                if key.casefold() == "href" and value:
                    self.hrefs.append(str(value))

    def handle_endtag(self, tag: str) -> None:
        name = tag.casefold()
        if name in {"script", "style", "noscript", "svg"}:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if name == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = _normalized_whitespace(data)
        if not text:
            return
        self.text_parts.append(text)
        if self._in_title:
            self.title_parts.append(text)


def _extract_html(
    text: str,
    *,
    final_url: str,
    source: WebDiscoverySource,
    max_links: int,
) -> dict[str, Any]:
    parser = _HTMLDiscoveryParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        raise WebDiscoveryContentError(f"HTML parsing failed: {exc}") from exc

    links: list[str] = []
    omitted_external = 0
    omitted_invalid = 0
    for raw_href in parser.hrefs:
        if len(links) >= max_links:
            break
        candidate = urljoin(final_url, raw_href)
        try:
            normalized = source.validate_url(candidate)
        except SourceBoundaryError:
            omitted_external += 1
            continue
        except Exception:
            omitted_invalid += 1
            continue
        if normalized not in links:
            links.append(normalized)

    body_text = _normalized_whitespace(" ".join(parser.text_parts))
    title = _normalized_whitespace(" ".join(parser.title_parts)) or None
    return {
        "kind": "html",
        "title": title,
        "text": body_text,
        "links": links,
        "external_links_omitted": omitted_external,
        "invalid_links_omitted": omitted_invalid,
    }


def _extract_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WebDiscoveryContentError(
            f"JSON response could not be parsed: {exc}"
        ) from exc

    normalized = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return {
        "kind": "json",
        "title": None,
        "text": normalized,
        "links": [],
        "external_links_omitted": 0,
        "invalid_links_omitted": 0,
    }


def _extract_text(text: str) -> dict[str, Any]:
    return {
        "kind": "text",
        "title": None,
        "text": _normalized_whitespace(text),
        "links": [],
        "external_links_omitted": 0,
        "invalid_links_omitted": 0,
    }


def _extract_content(
    *,
    text: str,
    content_type: str,
    final_url: str,
    source: WebDiscoverySource,
    max_links: int,
) -> dict[str, Any]:
    lowered = content_type.casefold()
    stripped = text.lstrip()

    if "json" in lowered:
        return _extract_json(text)
    if "html" in lowered or stripped.startswith("<!DOCTYPE") or stripped.startswith("<html"):
        return _extract_html(
            text,
            final_url=final_url,
            source=source,
            max_links=max_links,
        )
    if lowered.startswith("text/") or not lowered:
        return _extract_text(text)

    raise WebDiscoveryContentError(
        f"unsupported content type for discovery: {content_type or 'unknown'}"
    )


def _discovery_truth_state() -> dict[str, Any]:
    return {
        "discovery_state": DISCOVERED,
        "web_claim_verified": False,
        "cmis_verified": False,
        "source_independence_verified": False,
        "evidence_receipt_promoted": False,
        "proof_score_promoted": False,
        "risk_promoted": False,
    }


class CMISWebDiscoveryProvider:
    """Bounded HTTP discovery provider with a source-specific URL boundary."""

    source: WebDiscoverySource

    def __init__(
        self,
        *,
        session=requests,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_links: int = DEFAULT_MAX_LINKS,
        observed_at_fn=time.time,
    ) -> None:
        if not isinstance(getattr(self, "source", None), WebDiscoverySource):
            raise TypeError("provider source must be a WebDiscoverySource")
        self.session = session
        self.timeout = _positive_int("timeout", timeout)
        self.max_bytes = _positive_int("max_bytes", max_bytes)
        self.max_links = _positive_int("max_links", max_links)
        self.observed_at_fn = observed_at_fn

    def discover_url(
        self,
        url: Optional[str] = None,
        *,
        query: Optional[str] = None,
    ) -> dict[str, Any]:
        requested_url = self.source.validate_url(url or self.source.default_url)

        response = None
        current_url = requested_url
        redirect_chain: list[dict[str, Any]] = []

        for redirect_index in range(MAX_REDIRECTS + 1):
            try:
                response = self.session.get(
                    current_url,
                    timeout=self.timeout,
                    allow_redirects=False,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.1",
                    },
                )
            except Exception as exc:
                raise WebDiscoveryHTTPError(
                    f"{self.source.source_id} discovery request failed: {exc}"
                ) from exc

            status = getattr(response, "status_code", None)
            if isinstance(status, bool) or not isinstance(status, int):
                raise WebDiscoveryHTTPError(
                    "response status code is missing or invalid"
                )

            if status in {301, 302, 303, 307, 308}:
                if redirect_index >= MAX_REDIRECTS:
                    raise WebDiscoveryHTTPError(
                        f"redirect count exceeds MAX_REDIRECTS={MAX_REDIRECTS}"
                    )
                location = _header(response, "Location")
                if location is None:
                    raise WebDiscoveryHTTPError(
                        f"HTTP {status} redirect is missing Location"
                    )
                next_url = self.source.validate_url(urljoin(current_url, location))
                redirect_chain.append(
                    {
                        "status_code": status,
                        "from_url": current_url,
                        "to_url": next_url,
                    }
                )
                current_url = next_url
                continue

            if status < 200 or status >= 300:
                raise WebDiscoveryHTTPError(
                    f"{self.source.source_id} discovery request returned HTTP {status}"
                )
            break
        else:
            raise WebDiscoveryHTTPError("redirect handling exhausted unexpectedly")

        raw_final_url = str(getattr(response, "url", "") or current_url)
        final_url = self.source.validate_url(raw_final_url)

        body = _response_bytes(response)
        if len(body) > self.max_bytes:
            raise WebDiscoveryContentError(
                f"response exceeds max_bytes={self.max_bytes}"
            )

        content_type = _header(response, "Content-Type") or ""
        text = _decode_body(response, body)
        extracted = _extract_content(
            text=text,
            content_type=content_type,
            final_url=final_url,
            source=self.source,
            max_links=self.max_links,
        )

        normalized_text = str(extracted["text"])
        excerpt = normalized_text[:MAX_EXCERPT_CHARS]
        query_record = _query_record(normalized_text, query)

        return {
            "contract": CONTRACT,
            "source": {
                "id": self.source.source_id,
                "name": self.source.source_name,
                "role": self.source.source_role,
                "allowed_hosts": list(self.source.allowed_hosts),
            },
            "retrieval": {
                "method": "HTTP_GET",
                "requested_url": requested_url,
                "final_url": final_url,
                "observed_at": self.observed_at_fn(),
                "status_code": status,
                "content_type": content_type or None,
                "body_bytes": len(body),
                "body_sha256": sha256(body).hexdigest(),
                "redirects": redirect_chain,
            },
            "content": {
                "kind": extracted["kind"],
                "title": extracted["title"],
                "text_excerpt": excerpt,
                "text_truncated": len(normalized_text) > len(excerpt),
                "links": list(extracted["links"]),
                "external_links_omitted": extracted["external_links_omitted"],
                "invalid_links_omitted": extracted["invalid_links_omitted"],
            },
            "query": query_record,
            "truth_state": _discovery_truth_state(),
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }

    def crawl(
        self,
        url: Optional[str] = None,
        *,
        query: Optional[str] = None,
        max_pages: int = 1,
        max_depth: int = 0,
    ) -> dict[str, Any]:
        page_limit = _positive_int(
            "max_pages",
            max_pages,
            maximum=DEFAULT_MAX_PAGES,
        )
        depth_limit = _nonnegative_int(
            "max_depth",
            max_depth,
            maximum=MAX_ALLOWED_DEPTH,
        )

        start_url = self.source.validate_url(url or self.source.default_url)
        queue: list[tuple[str, int]] = [(start_url, 0)]
        queued = {start_url}
        visited: set[str] = set()
        pages: list[dict[str, Any]] = []

        while queue and len(pages) < page_limit:
            current_url, depth = queue.pop(0)
            if current_url in visited:
                continue
            visited.add(current_url)

            page = self.discover_url(current_url, query=query)
            page["crawl_depth"] = depth
            pages.append(page)

            if depth >= depth_limit:
                continue
            for link in page["content"]["links"]:
                if link in visited or link in queued:
                    continue
                queue.append((link, depth + 1))
                queued.add(link)
                if len(queue) + len(visited) >= page_limit * max(self.max_links, 1):
                    break

        matched_pages = [
            index
            for index, page in enumerate(pages)
            if page["query"]["matched"] is True
        ]
        return {
            "contract": CONTRACT,
            "source_id": self.source.source_id,
            "start_url": start_url,
            "page_limit": page_limit,
            "depth_limit": depth_limit,
            "pages_collected": len(pages),
            "matched_page_indexes": matched_pages,
            "pages": pages,
            "truth_state": _discovery_truth_state(),
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }


__all__ = [
    "CMISWebDiscoveryProvider",
    "CONTRACT",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_LINKS",
    "DEFAULT_MAX_PAGES",
    "DEFAULT_TIMEOUT_SECONDS",
    "DISCOVERED",
    "MAX_ALLOWED_DEPTH",
    "MAX_REDIRECTS",
    "MAX_QUERY_LENGTH",
    "SourceBoundaryError",
    "WebDiscoveryContentError",
    "WebDiscoveryError",
    "WebDiscoveryHTTPError",
    "WebDiscoverySource",
    "normalize_http_url",
]
