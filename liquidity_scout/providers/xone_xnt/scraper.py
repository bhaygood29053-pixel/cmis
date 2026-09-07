"""Dedicated XONE/XNT conversion web scraper beneath CMIS.

This module is intentionally separate from the generic CMIS Web Discovery
provider registry. It collects bounded candidate evidence about the Ethereum
XONE -> X1 XNT migration/conversion only. Web statements are not promoted to
chain truth by being scraped.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
import time
from typing import Any, Optional
from urllib.parse import urljoin, urlparse, urlunparse
from xml.etree import ElementTree

import requests


SCRAPER_CONTRACT = "xone_xnt_conversion_scraper/v1"
DISCOVERED = "DISCOVERED"
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_BYTES = 512_000
DEFAULT_MAX_CLAIMS = 100
DEFAULT_MAX_SITEMAP_URLS = 250
MAX_REDIRECTS = 5
MAX_EXCERPT_CHARS = 1_500
USER_AGENT = "CMIS-XONE-XNT-Conversion/1.0 (+read-only; candidate-evidence)"


class XoneXntScraperError(RuntimeError):
    """Base error for the dedicated XONE/XNT scraper."""


class XoneXntSourceBoundaryError(XoneXntScraperError):
    """Raised when a URL escapes the dedicated source registry."""


class XoneXntHTTPError(XoneXntScraperError):
    """Raised when a bounded HTTP request fails."""


class XoneXntContentError(XoneXntScraperError):
    """Raised when fetched content cannot be safely normalized."""


def _normalize_https_url(value: str) -> str:
    text_value = str(value or "").strip()
    if not text_value:
        raise ValueError("url must not be empty")
    parsed = urlparse(text_value)
    if parsed.scheme.casefold() != "https":
        raise XoneXntSourceBoundaryError("XONE/XNT scraper permits HTTPS only")
    if not parsed.hostname:
        raise XoneXntSourceBoundaryError("URL must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise XoneXntSourceBoundaryError("URL must not embed credentials")
    host = parsed.hostname.casefold().rstrip(".")
    netloc = host if parsed.port is None else f"{host}:{parsed.port}"
    return urlunparse(("https", netloc, parsed.path or "/", "", parsed.query, ""))


@dataclass(frozen=True)
class XoneXntSource:
    source_id: str
    source_name: str
    source_role: str
    base_urls: tuple[str, ...]
    allowed_hosts: tuple[str, ...]
    sitemap_urls: tuple[str, ...] = ()

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
        for url in (*self.base_urls, *self.sitemap_urls):
            self.validate_url(url)

    def validate_url(self, value: str) -> str:
        normalized = _normalize_https_url(value)
        host = (urlparse(normalized).hostname or "").casefold()
        if host not in {item.casefold() for item in self.allowed_hosts}:
            raise XoneXntSourceBoundaryError(
                f"{self.source_id} URL host {host!r} is outside the source allowlist"
            )
        return normalized


XONE_XNT_SOURCE_REGISTRY: tuple[XoneXntSource, ...] = (
    XoneXntSource(
        source_id="x1_official",
        source_name="X1",
        source_role="official_x1_web",
        base_urls=("https://x1.xyz/",),
        allowed_hosts=("x1.xyz", "www.x1.xyz"),
    ),
    XoneXntSource(
        source_id="x1_docs",
        source_name="X1 Docs",
        source_role="official_x1_documentation",
        base_urls=("https://docs.x1.xyz/", "https://next.x1.xyz/"),
        allowed_hosts=("docs.x1.xyz", "next.x1.xyz"),
    ),
    XoneXntSource(
        source_id="x1report",
        source_name="X1 Report",
        source_role="third_party_x1_reporting",
        base_urls=("https://x1report.com/",),
        allowed_hosts=("x1report.com", "www.x1report.com"),
        sitemap_urls=("https://x1report.com/sitemap.xml",),
    ),
)
_SOURCE_BY_ID = {source.source_id: source for source in XONE_XNT_SOURCE_REGISTRY}

TOPIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("conversion", ("convert", "conversion", "migrate", "migration", "redeem", "ratio", "1:1")),
    ("burn", ("burn", "burned", "burnt", "destroy", "dead address")),
    ("eligibility", ("eligible", "eligibility", "qualify", "qualified", "snapshot")),
    ("claim", ("claim", "claimable", "redeem")),
    ("lockup", ("lockup", "lock-up", "locked", "lock period")),
    ("vesting", ("vest", "vesting", "cliff")),
    ("unlock", ("unlock", "unlocked")),
    ("transferability", ("transferable", "transferability", "freely transferable")),
    ("distribution", ("distribution", "distributed", "allocation", "airdrop")),
    ("contract", ("contract", "program address", "contract address")),
    ("cross_chain", ("ethereum", "erc-20", "erc20", "x1 mainnet", "cross-chain", "cross chain")),
)
RELEVANCE_TERMS = (
    "xone", "xnt", "convert", "conversion", "migration", "vesting", "unlock",
    "lockup", "investor", "snapshot", "claim", "burn", "jack levin", "october 6",
)
MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
DATE_RE = re.compile(
    rf"\b(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b",
    re.IGNORECASE,
)
RATIO_RE = re.compile(r"\b\d+(?:\.\d+)?\s*:\s*\d+(?:\.\d+)?\b")
PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%")
ETH_ADDRESS_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
TOKEN_AMOUNT_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?\s+(?:XONE|XNT)\b", re.IGNORECASE)


def source_ids() -> tuple[str, ...]:
    return tuple(source.source_id for source in XONE_XNT_SOURCE_REGISTRY)


def source_catalog() -> list[dict[str, Any]]:
    return [
        {
            "source_id": source.source_id,
            "source_name": source.source_name,
            "source_role": source.source_role,
            "base_urls": list(source.base_urls),
            "sitemap_urls": list(source.sitemap_urls),
            "allowed_hosts": list(source.allowed_hosts),
            "read_only": True,
            "xone_xnt_only": True,
            "web_claim_verified": False,
            "cmis_verified": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        }
        for source in XONE_XNT_SOURCE_REGISTRY
    ]


def get_source(source_id: str) -> XoneXntSource:
    key = str(source_id or "").strip()
    if not key:
        raise ValueError("source_id must not be empty")
    source = _SOURCE_BY_ID.get(key)
    if source is None:
        raise ValueError(f"unsupported XONE/XNT source_id {key!r}; supported={list(source_ids())}")
    return source


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._anchor_href: Optional[str] = None
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        name = tag.casefold()
        if name in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if name == "a":
            href = next((value for key, value in attrs if key.casefold() == "href"), None)
            self._anchor_href = str(href) if href else None
            self._anchor_text = []

    def handle_endtag(self, tag: str) -> None:
        name = tag.casefold()
        if name in {"script", "style", "noscript", "svg"}:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if name == "a" and self._anchor_href:
            self.links.append((self._anchor_href, " ".join(self._anchor_text).strip()))
            self._anchor_href = None
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text_value = re.sub(r"\s+", " ", str(data or "")).strip()
        if not text_value:
            return
        self.text_parts.append(text_value)
        if self._anchor_href is not None:
            self._anchor_text.append(text_value)


def _normalize_html(text_value: str) -> tuple[str, list[tuple[str, str]]]:
    parser = _TextParser()
    try:
        parser.feed(text_value)
        parser.close()
    except Exception as exc:
        raise XoneXntContentError(f"HTML parsing failed: {exc}") from exc
    return "\n".join(parser.text_parts), parser.links


def _normalize_body(body: bytes, content_type: str) -> tuple[str, list[tuple[str, str]]]:
    text_value = body.decode("utf-8", errors="replace")
    lowered = content_type.casefold()
    stripped = text_value.lstrip()
    if "json" in lowered:
        try:
            value = json.loads(text_value)
        except json.JSONDecodeError as exc:
            raise XoneXntContentError(f"JSON parsing failed: {exc}") from exc
        return json.dumps(value, sort_keys=True, ensure_ascii=False), []
    if "html" in lowered or stripped.lower().startswith(("<!doctype", "<html")):
        return _normalize_html(text_value)
    if "xml" in lowered or stripped.startswith("<?xml") or stripped.startswith("<urlset"):
        return text_value, []
    if lowered.startswith("text/") or not lowered:
        return text_value, []
    raise XoneXntContentError(f"unsupported content type: {content_type or 'unknown'}")


def _response_header(response: Any, name: str) -> Optional[str]:
    headers = getattr(response, "headers", None)
    if not isinstance(headers, Mapping):
        return None
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            text_value = str(value or "").strip()
            return text_value or None
    return None


def _response_bytes(response: Any) -> bytes:
    content_value = getattr(response, "content", None)
    if isinstance(content_value, bytes):
        return content_value
    if isinstance(content_value, bytearray):
        return bytes(content_value)
    text_value = getattr(response, "text", None)
    if text_value is None:
        raise XoneXntContentError("response exposes neither bytes nor text")
    return str(text_value).encode("utf-8", errors="replace")


def _truth_state() -> dict[str, Any]:
    return {
        "discovery_state": DISCOVERED,
        "source_boundary_verified": True,
        "web_claim_verified": False,
        "ethereum_event_verified": False,
        "x1_event_verified": False,
        "cross_chain_correlation_verified": False,
        "freshness_verified": False,
        "source_independence_verified": False,
        "cmis_verified": False,
    }


def _split_segments(text_value: str) -> list[str]:
    normalized = re.sub(r"[\t\r ]+", " ", str(text_value or ""))
    normalized = re.sub(r"\n{2,}", "\n", normalized)
    raw = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    return [segment.strip() for segment in raw if segment.strip()]


def _topics(segment: str) -> list[str]:
    lowered = segment.casefold()
    return [
        topic
        for topic, needles in TOPIC_PATTERNS
        if any(needle in lowered for needle in needles)
    ]


def _normalized_values(segment: str) -> dict[str, list[str]]:
    def unique(values: Iterable[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            clean = re.sub(r"\s+", " ", value).strip()
            if clean and clean not in result:
                result.append(clean)
        return result

    return {
        "ratios": unique(match.group(0) for match in RATIO_RE.finditer(segment)),
        "percentages": unique(match.group(0) for match in PERCENT_RE.finditer(segment)),
        "dates": unique(match.group(0) for match in DATE_RE.finditer(segment)),
        "ethereum_addresses": unique(match.group(0) for match in ETH_ADDRESS_RE.finditer(segment)),
        "token_amounts": unique(match.group(0) for match in TOKEN_AMOUNT_RE.finditer(segment)),
    }


def _handoffs(topics: Sequence[str], segment: str) -> list[dict[str, str]]:
    lowered = segment.casefold()
    result: list[dict[str, str]] = []

    def add(target: str, reason: str) -> None:
        row = {"target": target, "reason": reason}
        if row not in result:
            result.append(row)

    if "burn" in topics or "ethereum" in lowered or "erc-20" in lowered or "erc20" in lowered:
        add(
            "Ethereum RPC / verified XONE contract",
            "Verify exact XONE token identity and any claimed burn/lock/migration event on Ethereum.",
        )
    if any(topic in topics for topic in ("conversion", "distribution", "claim", "unlock", "vesting", "lockup", "contract")):
        add(
            "X1 RPC / verified XNT distribution or vesting account",
            "Verify any claimed XNT issuance, allocation, vesting, claim or unlock on X1.",
        )
    if "conversion" in topics or "cross_chain" in topics:
        add(
            "CMIS cross-chain correlator",
            "Correlate Ethereum-side XONE evidence and X1-side XNT evidence; neither side alone proves conversion.",
        )
    if not result:
        add(
            "CMIS primary-source review",
            "Seek an authoritative X1/XONE primary source before promoting the web statement.",
        )
    return result


def extract_xone_xnt_claims(
    text_value: str,
    *,
    source_id: str,
    url: str,
    observed_at: float,
    max_claims: int = DEFAULT_MAX_CLAIMS,
) -> list[dict[str, Any]]:
    """Extract bounded XONE/XNT conversion-related candidate claims."""

    source = get_source(source_id)
    normalized_url = source.validate_url(url)
    if isinstance(max_claims, bool) or not isinstance(max_claims, int) or max_claims < 1:
        raise ValueError("max_claims must be a positive integer")

    segments = _split_segments(text_value)
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, segment in enumerate(segments):
        lowered = segment.casefold()
        if "xone" not in lowered:
            continue
        topics = _topics(segment)
        if "xnt" not in lowered and not topics:
            continue

        window = segment
        if index + 1 < len(segments) and len(window) < 900:
            nxt = segments[index + 1]
            if "xnt" in nxt.casefold() or _topics(nxt):
                window = f"{window} {nxt}"

        excerpt = re.sub(r"\s+", " ", window).strip()[:MAX_EXCERPT_CHARS]
        topics = _topics(excerpt)
        values = _normalized_values(excerpt)
        digest = sha256(f"{source_id}\n{normalized_url}\n{excerpt}".encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)

        token_mentions = []
        excerpt_lower = excerpt.casefold()
        if "xone" in excerpt_lower:
            token_mentions.append("XONE")
        if "xnt" in excerpt_lower:
            token_mentions.append("XNT")

        claims.append(
            {
                "claim_id": digest,
                "source_id": source.source_id,
                "source_name": source.source_name,
                "source_role": source.source_role,
                "url": normalized_url,
                "observed_at": observed_at,
                "excerpt": excerpt,
                "topics": topics,
                "token_mentions": token_mentions,
                "normalized_values": values,
                "truth_state": _truth_state(),
                "corroboration_handoff": _handoffs(topics, excerpt),
                "read_only": True,
                "public_service_promoted": False,
                "scout_reliance_promoted": False,
                "cmis_promotable": False,
                "execution_authorized": False,
            }
        )
        if len(claims) >= max_claims:
            break
    return claims


def group_claims_for_review(claims: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Group claims by topic and flag differing extracted values for review."""

    topic_claims: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for claim in claims:
        topics = claim.get("topics")
        if not isinstance(topics, Sequence) or isinstance(topics, (str, bytes)):
            continue
        for topic in topics:
            topic_claims[str(topic)].append(claim)

    groups: list[dict[str, Any]] = []
    for topic in sorted(topic_claims):
        rows = topic_claims[topic]
        distinct_values: dict[str, list[str]] = {
            "ratios": [],
            "percentages": [],
            "dates": [],
            "ethereum_addresses": [],
            "token_amounts": [],
        }
        for row in rows:
            values = row.get("normalized_values")
            if not isinstance(values, Mapping):
                continue
            for key in distinct_values:
                raw = values.get(key)
                if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
                    continue
                for value in raw:
                    text_value = str(value)
                    if text_value not in distinct_values[key]:
                        distinct_values[key].append(text_value)

        conflict_dimensions = [
            key for key, values in distinct_values.items() if len(values) > 1
        ]
        groups.append(
            {
                "topic": topic,
                "claim_ids": [str(row.get("claim_id")) for row in rows],
                "source_ids": sorted({str(row.get("source_id")) for row in rows}),
                "distinct_values": distinct_values,
                "potential_conflict": bool(conflict_dimensions),
                "conflict_dimensions": conflict_dimensions,
                "conflict_verified": False,
                "cmis_verified": False,
            }
        )
    return groups


def rank_sitemap_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    max_urls: int = DEFAULT_MAX_SITEMAP_URLS,
) -> list[dict[str, Any]]:
    if isinstance(max_urls, bool) or not isinstance(max_urls, int) or max_urls < 1:
        raise ValueError("max_urls must be a positive integer")

    ranked: list[dict[str, Any]] = []
    for position, entry in enumerate(entries):
        url = str(entry.get("url") or "").strip()
        title = str(entry.get("title") or "").strip()
        lastmod = str(entry.get("lastmod") or "").strip() or None
        haystack = f"{url} {title}".casefold()
        matched = [term for term in RELEVANCE_TERMS if term in haystack]
        weights = {"xone": 10, "xnt": 2}
        score = sum(weights.get(term, 1) for term in matched)
        if score == 0:
            continue
        ranked.append(
            {
                "url": url,
                "title": title or None,
                "lastmod": lastmod,
                "matched_terms": matched,
                "relevance_score": score,
                "sitemap_position": position,
            }
        )
    ranked.sort(key=lambda row: (-row["relevance_score"], row["sitemap_position"]))
    return ranked[:max_urls]


def parse_sitemap(
    xml_text: str,
    *,
    source_id: str,
    max_urls: int = DEFAULT_MAX_SITEMAP_URLS,
) -> list[dict[str, Any]]:
    source = get_source(source_id)
    try:
        root = ElementTree.fromstring(str(xml_text or ""))
    except ElementTree.ParseError as exc:
        raise XoneXntContentError(f"sitemap XML parsing failed: {exc}") from exc

    entries: list[dict[str, Any]] = []
    for url_node in root.findall("{*}url"):
        loc = url_node.findtext("{*}loc")
        if not loc:
            continue
        try:
            normalized = source.validate_url(loc)
        except XoneXntSourceBoundaryError:
            continue
        lastmod = url_node.findtext("{*}lastmod")
        title = None
        for child in url_node.iter():
            if child.tag.endswith("title") and child.text:
                title = child.text.strip()
                break
        entries.append({"url": normalized, "title": title, "lastmod": lastmod})
    return rank_sitemap_entries(entries, max_urls=max_urls)


class XoneXntConversionScraper:
    """Bounded dedicated scraper for XONE/XNT conversion candidate evidence."""

    contract = SCRAPER_CONTRACT

    def __init__(
        self,
        *,
        session=requests,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        observed_at_fn=time.time,
    ) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
            raise ValueError("timeout must be a positive integer")
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        self.session = session
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.observed_at_fn = observed_at_fn

    def _fetch(self, source: XoneXntSource, url: str) -> dict[str, Any]:
        requested_url = source.validate_url(url)
        current_url = requested_url
        redirects: list[dict[str, Any]] = []
        response = None

        for redirect_index in range(MAX_REDIRECTS + 1):
            try:
                response = self.session.get(
                    current_url,
                    timeout=self.timeout,
                    allow_redirects=False,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "text/html,application/json,application/xml,text/xml,text/plain;q=0.9,*/*;q=0.1",
                    },
                )
            except Exception as exc:
                raise XoneXntHTTPError(f"{source.source_id} request failed: {exc}") from exc

            status = getattr(response, "status_code", None)
            if isinstance(status, bool) or not isinstance(status, int):
                raise XoneXntHTTPError("response status code is missing or invalid")

            if status in {301, 302, 303, 307, 308}:
                if redirect_index >= MAX_REDIRECTS:
                    raise XoneXntHTTPError(f"redirect count exceeds {MAX_REDIRECTS}")
                location = _response_header(response, "Location")
                if not location:
                    raise XoneXntHTTPError(f"HTTP {status} redirect missing Location")
                next_url = source.validate_url(urljoin(current_url, location))
                redirects.append(
                    {"status_code": status, "from_url": current_url, "to_url": next_url}
                )
                current_url = next_url
                continue

            if status < 200 or status >= 300:
                raise XoneXntHTTPError(f"{source.source_id} request returned HTTP {status}")
            break

        if response is None:
            raise XoneXntHTTPError("request produced no response")

        final_url = source.validate_url(str(getattr(response, "url", "") or current_url))
        body = _response_bytes(response)
        if len(body) > self.max_bytes:
            raise XoneXntContentError(f"response exceeds max_bytes={self.max_bytes}")
        content_type = _response_header(response, "Content-Type") or ""
        normalized_text, links = _normalize_body(body, content_type)
        return {
            "requested_url": requested_url,
            "final_url": final_url,
            "status_code": status,
            "content_type": content_type or None,
            "body_bytes": len(body),
            "body_sha256": sha256(body).hexdigest(),
            "redirects": redirects,
            "text": normalized_text,
            "links": links,
        }

    def scrape_url(
        self,
        source_id: str,
        url: str,
        *,
        max_claims: int = DEFAULT_MAX_CLAIMS,
    ) -> dict[str, Any]:
        source = get_source(source_id)
        observed_at = float(self.observed_at_fn())
        fetched = self._fetch(source, url)
        claims = extract_xone_xnt_claims(
            fetched["text"],
            source_id=source_id,
            url=fetched["final_url"],
            observed_at=observed_at,
            max_claims=max_claims,
        )
        return {
            "contract": SCRAPER_CONTRACT,
            "source": {"id": source.source_id, "name": source.source_name, "role": source.source_role},
            "retrieval": {
                key: value for key, value in fetched.items() if key not in {"text", "links"}
            } | {"observed_at": observed_at},
            "candidate_claim_count": len(claims),
            "claims": claims,
            "claim_groups": group_claims_for_review(claims),
            "truth_state": _truth_state(),
            "read_only": True,
            "xone_xnt_only": True,
            "background_monitoring_authorized": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }

    def discover_sitemap_candidates(
        self,
        source_id: str,
        *,
        sitemap_url: Optional[str] = None,
        max_urls: int = DEFAULT_MAX_SITEMAP_URLS,
    ) -> dict[str, Any]:
        source = get_source(source_id)
        target = sitemap_url
        if target is None:
            if not source.sitemap_urls:
                raise ValueError(f"source {source_id!r} has no registered sitemap")
            target = source.sitemap_urls[0]
        fetched = self._fetch(source, target)
        candidates = parse_sitemap(fetched["text"], source_id=source_id, max_urls=max_urls)
        return {
            "contract": SCRAPER_CONTRACT,
            "source_id": source.source_id,
            "sitemap_url": fetched["final_url"],
            "candidate_url_count": len(candidates),
            "candidate_urls": candidates,
            "truth_state": _truth_state(),
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }

    def scrape_sitemap_candidates(
        self,
        source_id: str,
        *,
        sitemap_url: Optional[str] = None,
        max_urls: int = 20,
        max_claims_per_url: int = 25,
    ) -> dict[str, Any]:
        discovery = self.discover_sitemap_candidates(
            source_id,
            sitemap_url=sitemap_url,
            max_urls=max_urls,
        )
        results: list[dict[str, Any]] = []
        all_claims: list[dict[str, Any]] = []
        for candidate in discovery["candidate_urls"]:
            url = candidate["url"]
            try:
                result = self.scrape_url(source_id, url, max_claims=max_claims_per_url)
            except XoneXntScraperError as exc:
                results.append(
                    {
                        "url": url,
                        "status": "UNAVAILABLE",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "claims": [],
                    }
                )
                continue
            results.append(
                {
                    "url": url,
                    "status": "AVAILABLE",
                    "error_type": None,
                    "error": None,
                    "claims": result["claims"],
                }
            )
            all_claims.extend(result["claims"])

        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for claim in all_claims:
            claim_id = str(claim["claim_id"])
            if claim_id in seen:
                continue
            seen.add(claim_id)
            deduped.append(claim)

        return {
            "contract": SCRAPER_CONTRACT,
            "source_id": source_id,
            "candidate_url_count": len(discovery["candidate_urls"]),
            "pages_attempted": len(results),
            "candidate_claim_count": len(deduped),
            "claims": deduped,
            "claim_groups": group_claims_for_review(deduped),
            "results": results,
            "truth_state": _truth_state(),
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }


__all__ = [
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_CLAIMS",
    "DEFAULT_MAX_SITEMAP_URLS",
    "DISCOVERED",
    "SCRAPER_CONTRACT",
    "XONE_XNT_SOURCE_REGISTRY",
    "XoneXntContentError",
    "XoneXntConversionScraper",
    "XoneXntHTTPError",
    "XoneXntScraperError",
    "XoneXntSource",
    "XoneXntSourceBoundaryError",
    "extract_xone_xnt_claims",
    "get_source",
    "group_claims_for_review",
    "parse_sitemap",
    "rank_sitemap_entries",
    "source_catalog",
    "source_ids",
]
