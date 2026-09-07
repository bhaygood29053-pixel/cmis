"""Archived asset-graph resolution for the Ethereum XONE snapshot trail.

This layer traverses application assets preserved behind archived XEN/X1 pages:
scripts, manifests, JSON/static data, source maps, data files, stable X URLs and
content-addressed pointers.  Archive transport never adds publisher authority.

The contract is intentionally discovery-first.  A retrieved authoritative-host
asset may preserve primary-source content, but snapshot truth still requires the
accepted ethereum_xone_snapshot_registry/v1 direct-chain gate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from .snapshot_archival_recovery import (
    extract_archival_provenance_candidates,
    original_host_is_authoritative,
    recover_stable_x_urls,
    source_role_for_original_url,
)
from .snapshot_provenance import rank_provenance_candidates


CONTRACT_VERSION = "xone_snapshot_archived_asset_graph_resolution/v1"
MAX_GRAPH_DEPTH = 2

TRAVERSABLE_ASSET_KINDS = frozenset({
    "javascript",
    "manifest",
    "json",
    "source_map",
    "data",
})

_CONTENT_ADDRESSED_RE = re.compile(
    r"(?P<url>(?:ipfs://[A-Za-z0-9/_\-.]+|ar://[A-Za-z0-9_-]+))",
    re.IGNORECASE,
)
_ABSOLUTE_URL_RE = re.compile(
    r"https?://[^\s\"'<>\\)\]]+",
    re.IGNORECASE,
)
_QUOTED_ASSET_RE = re.compile(
    r"""(?P<quote>["'])(?P<value>
        (?:/|\./|\.\./)?
        [^"'\s<>]{1,600}?
        (?:
            \.m?js(?:\?[^"'\s<>]*)?
            |\.json(?:\?[^"'\s<>]*)?
            |\.map(?:\?[^"'\s<>]*)?
            |\.csv(?:\?[^"'\s<>]*)?
            |\.tsv(?:\?[^"'\s<>]*)?
            |\.jsonl(?:\?[^"'\s<>]*)?
            |\.ndjson(?:\?[^"'\s<>]*)?
            |manifest[^"'\s<>]*
            |_next/static/[^"'\s<>]+
            |_next/data/[^"'\s<>]+
        )
    )(?P=quote)""",
    re.IGNORECASE | re.VERBOSE,
)

_DISALLOWED_SCHEMES = {"data", "javascript", "mailto", "tel", "blob"}
_RELEVANCE_TERMS = (
    "xone",
    "snapshot",
    "holder",
    "registry",
    "allocation",
    "claim",
    "airdrop",
    "merkle",
    "vesting",
    "unlock",
    "xnt",
    "balance",
    "export",
)


class XoneSnapshotArchivedAssetGraphError(RuntimeError):
    """Raised when archived asset graph evidence cannot be interpreted safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normal_original_http_url(value: Any) -> str:
    text = _text(value)
    parsed = urlparse(text)
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise XoneSnapshotArchivedAssetGraphError(
            "asset original URL must be HTTP or HTTPS"
        )
    if not parsed.hostname:
        raise XoneSnapshotArchivedAssetGraphError(
            "asset original URL is missing a host"
        )
    if parsed.username is not None or parsed.password is not None:
        raise XoneSnapshotArchivedAssetGraphError(
            "asset original URL must not embed credentials"
        )
    return text


def _same_origin(left: str, right: str) -> bool:
    a = urlparse(_normal_original_http_url(left))
    b = urlparse(_normal_original_http_url(right))
    def port(parsed):
        if parsed.port is not None:
            return parsed.port
        return 443 if parsed.scheme.casefold() == "https" else 80
    return (
        a.scheme.casefold() == b.scheme.casefold()
        and (a.hostname or "").casefold().rstrip(".")
            == (b.hostname or "").casefold().rstrip(".")
        and port(a) == port(b)
    )


def classify_archived_asset_kind(url: str) -> str:
    """Classify an original asset URL without treating its label as evidence."""

    text = _text(url)
    lowered = text.casefold()
    if lowered.startswith("ipfs://"):
        return "ipfs"
    if lowered.startswith("ar://"):
        return "arweave"

    parsed = urlparse(_normal_original_http_url(text))
    host = (parsed.hostname or "").casefold()
    path = (parsed.path or "").casefold()
    query = (parsed.query or "").casefold()

    if host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
        if "/status/" in path:
            return "x_status"
        if "/i/spaces/" in path:
            return "x_space"
        return "external_link"

    if path.endswith(".map"):
        return "source_map"
    if "manifest" in path or "manifest" in query:
        return "manifest"
    if path.endswith((".js", ".mjs")) or "/_next/static/" in path:
        return "javascript"
    if path.endswith(".json") or "/_next/data/" in path:
        return "json"
    if path.endswith((".csv", ".tsv", ".jsonl", ".ndjson", ".txt")):
        return "data"
    if path.endswith((".html", ".htm", "/")) or not path.rsplit("/", 1)[-1].count("."):
        return "html"
    return "other"


def asset_reference_relevance_score(reference: Mapping[str, Any]) -> int:
    """Rank asset graph edges for bounded live traversal."""

    url = _text(reference.get("url"))
    kind = _text(reference.get("asset_kind"))
    lowered = url.casefold()
    score = {
        "manifest": 30,
        "json": 25,
        "data": 25,
        "javascript": 20,
        "source_map": 18,
        "x_status": 15,
        "x_space": 15,
        "ipfs": 15,
        "arweave": 15,
        "html": 5,
        "other": 0,
        "external_link": 0,
    }.get(kind, 0)
    for term in _RELEVANCE_TERMS:
        if term in lowered:
            score += 10
    if "xone" in lowered:
        score += 25
    if "snapshot" in lowered or "registry" in lowered:
        score += 35
    if reference.get("same_origin") is True:
        score += 10
    return score


class _AssetHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs):
        values = {str(k).casefold(): v for k, v in attrs if k}
        tag = tag.casefold()
        if tag == "script" and values.get("src"):
            self.refs.append((str(values["src"]), "html_script_src"))
        elif tag == "link" and values.get("href"):
            self.refs.append((str(values["href"]), "html_link_href"))
        elif tag == "a" and values.get("href"):
            self.refs.append((str(values["href"]), "html_anchor_href"))
        elif tag in {"source", "img"} and values.get("src"):
            self.refs.append((str(values["src"]), f"html_{tag}_src"))


def _normalize_reference(
    raw: str,
    *,
    parent_original_url: str,
    discovery_basis: str,
) -> dict[str, Any] | None:
    raw = _text(raw).rstrip(".,;:")
    if not raw or raw.startswith("#"):
        return None
    lowered = raw.casefold()
    scheme = urlparse(raw).scheme.casefold()
    if scheme in _DISALLOWED_SCHEMES:
        return None

    if lowered.startswith("ipfs://") or lowered.startswith("ar://"):
        kind = classify_archived_asset_kind(raw)
        return {
            "url": raw,
            "asset_kind": kind,
            "discovery_basis": discovery_basis,
            "same_origin": False,
            "traversable_via_wayback": False,
            "stable_primary_social_url": False,
            "content_addressed_pointer": True,
            "execution_authorized": False,
        }

    if raw.startswith("//"):
        parent_scheme = urlparse(parent_original_url).scheme or "https"
        raw = f"{parent_scheme}:{raw}"

    try:
        absolute = urljoin(parent_original_url, raw)
        absolute = _normal_original_http_url(absolute)
    except (ValueError, XoneSnapshotArchivedAssetGraphError):
        return None

    kind = classify_archived_asset_kind(absolute)
    same_origin = _same_origin(parent_original_url, absolute)
    stable_social = kind in {"x_status", "x_space"}
    return {
        "url": absolute,
        "asset_kind": kind,
        "discovery_basis": discovery_basis,
        "same_origin": same_origin,
        "traversable_via_wayback":
            same_origin and kind in TRAVERSABLE_ASSET_KINDS,
        "stable_primary_social_url": stable_social,
        "content_addressed_pointer": False,
        "execution_authorized": False,
    }


def extract_archived_asset_references(
    text: str,
    *,
    parent_original_url: str,
    content_type: str = "",
    max_references: int = 100,
) -> list[dict[str, Any]]:
    """Extract bounded asset/social/content-addressed references from a node."""

    if isinstance(max_references, bool) or not isinstance(max_references, int) or max_references < 1:
        raise ValueError("max_references must be a positive integer")
    parent_original_url = _normal_original_http_url(parent_original_url)
    value = _text(text)
    candidates: list[tuple[str, str]] = []

    if "html" in _text(content_type).casefold() or "<" in value[:500]:
        parser = _AssetHTMLParser()
        try:
            parser.feed(value)
        except Exception:
            pass
        candidates.extend(parser.refs)

    for match in _QUOTED_ASSET_RE.finditer(value):
        candidates.append((match.group("value"), "embedded_asset_string"))

    for match in _CONTENT_ADDRESSED_RE.finditer(value):
        candidates.append((match.group("url"), "content_addressed_pointer"))

    for stable in recover_stable_x_urls(value):
        candidates.append((str(stable["url"]), "stable_x_primary_url"))

    # Full absolute URLs can expose API/static asset paths that are not quoted.
    for match in _ABSOLUTE_URL_RE.finditer(value):
        raw = match.group(0).rstrip(".,;:")
        kind = None
        try:
            kind = classify_archived_asset_kind(raw)
        except XoneSnapshotArchivedAssetGraphError:
            pass
        if kind in TRAVERSABLE_ASSET_KINDS | {
            "x_status", "x_space", "ipfs", "arweave"
        }:
            candidates.append((raw, "absolute_asset_url"))

    unique: dict[str, dict[str, Any]] = {}
    for raw, basis in candidates:
        row = _normalize_reference(
            raw,
            parent_original_url=parent_original_url,
            discovery_basis=basis,
        )
        if row is None:
            continue
        key = row["url"].casefold()
        previous = unique.get(key)
        if previous is None:
            row["relevance_score"] = asset_reference_relevance_score(row)
            unique[key] = row
        elif basis not in str(previous.get("discovery_basis") or ""):
            previous["discovery_basis"] = (
                f"{previous['discovery_basis']}+{basis}"
            )

    rows = sorted(
        unique.values(),
        key=lambda row: (
            -int(row.get("relevance_score", 0)),
            str(row.get("url") or ""),
        ),
    )
    return rows[:max_references]


def build_asset_graph_edges(
    parent: Mapping[str, Any],
    references: Sequence[Mapping[str, Any]],
    *,
    depth: int,
) -> list[dict[str, Any]]:
    """Bind discovered references to exact archive parent provenance."""

    if isinstance(depth, bool) or not isinstance(depth, int) or depth < 1 or depth > MAX_GRAPH_DEPTH:
        raise ValueError(f"depth must be between 1 and {MAX_GRAPH_DEPTH}")
    if parent.get("archival_capture_retrieved") is not True:
        raise XoneSnapshotArchivedAssetGraphError(
            "asset parent must be a retrieved archival capture"
        )
    root_capture_id = _text(
        parent.get("root_capture_id") or parent.get("capture_id")
    )
    parent_capture_id = _text(parent.get("capture_id"))
    parent_original = _normal_original_http_url(parent.get("original"))
    timestamp = _text(parent.get("timestamp"))
    digest = _text(parent.get("digest"))
    if not root_capture_id or not parent_capture_id or not timestamp or not digest:
        raise XoneSnapshotArchivedAssetGraphError(
            "asset parent is missing archive provenance"
        )

    edges: list[dict[str, Any]] = []
    for reference in references:
        if not isinstance(reference, Mapping):
            continue
        url = _text(reference.get("url"))
        if not url:
            continue
        edge_id = sha256(
            (
                f"{CONTRACT_VERSION}|{root_capture_id}|{parent_capture_id}|"
                f"{depth}|{url}|{reference.get('discovery_basis')}"
            ).encode("utf-8")
        ).hexdigest()
        edges.append({
            "edge_id": edge_id,
            "root_capture_id": root_capture_id,
            "parent_capture_id": parent_capture_id,
            "parent_original": parent_original,
            "parent_archive_timestamp": timestamp,
            "parent_archive_digest": digest,
            "depth": depth,
            "asset_original": url,
            "asset_kind": reference.get("asset_kind"),
            "discovery_basis": reference.get("discovery_basis"),
            "same_origin": reference.get("same_origin") is True,
            "traversable_via_wayback":
                reference.get("traversable_via_wayback") is True,
            "stable_primary_social_url":
                reference.get("stable_primary_social_url") is True,
            "content_addressed_pointer":
                reference.get("content_addressed_pointer") is True,
            "relevance_score": int(reference.get("relevance_score", 0)),
            "asset_capture_discovered": False,
            "asset_capture_retrieved": False,
            "semantic_candidate_discovered": False,
            "execution_authorized": False,
        })
    return edges


def annotate_retrieved_asset_capture(
    capture: Mapping[str, Any],
    *,
    root_capture_id: str,
    parent_capture_id: str,
    depth: int,
    retrieved_bytes: int,
    retrieved_content_type: str,
    content_sha256: str,
) -> dict[str, Any]:
    """Add graph provenance to one exact retrieved asset capture."""

    if capture.get("archival_capture_discovered") is not True:
        raise XoneSnapshotArchivedAssetGraphError(
            "asset capture must originate from validated CDX metadata"
        )
    if isinstance(retrieved_bytes, bool) or not isinstance(retrieved_bytes, int) or retrieved_bytes < 0:
        raise ValueError("retrieved_bytes must be non-negative")
    content_sha256 = _text(content_sha256).casefold()
    if len(content_sha256) != 64:
        raise ValueError("content_sha256 must be a 64-character digest")

    row = dict(capture)
    row.update({
        "root_capture_id": _text(root_capture_id),
        "parent_capture_id": _text(parent_capture_id),
        "depth": depth,
        "archival_capture_retrieved": True,
        "asset_capture_retrieved": True,
        "retrieved_bytes": retrieved_bytes,
        "retrieved_content_type": _text(retrieved_content_type),
        "retrieved_content_sha256": content_sha256,
        "original_source_role":
            source_role_for_original_url(str(capture.get("original") or "")),
        "original_host_authoritative":
            original_host_is_authoritative(str(capture.get("original") or "")),
        "execution_authorized": False,
    })
    return row


def extract_asset_provenance_candidates(
    text: str,
    *,
    asset_capture: Mapping[str, Any],
    observed_at: float,
    max_candidates: int = 50,
) -> list[dict[str, Any]]:
    """Extract snapshot semantics from a retrieved archived application asset."""

    candidates = extract_archival_provenance_candidates(
        text,
        capture=asset_capture,
        observed_at=observed_at,
        max_candidates=max_candidates,
    )
    for row in candidates:
        row["asset_graph_contract"] = CONTRACT_VERSION
        row["asset_root_capture_id"] = asset_capture.get("root_capture_id")
        row["asset_parent_capture_id"] = asset_capture.get("parent_capture_id")
        row["asset_capture_id"] = asset_capture.get("capture_id")
        row["asset_original"] = asset_capture.get("original")
        row["asset_depth"] = asset_capture.get("depth")
        row["asset_content_sha256"] = asset_capture.get(
            "retrieved_content_sha256"
        )
        row["asset_semantic_candidate_discovered"] = True
        row["official_xone_snapshot_verified"] = False
        row["official_registry_artifact_verified"] = False
        row["xone_snapshot_eligibility_verified"] = False
        row["xone_snapshot_xnt_allocation_binding_verified"] = False
        row["execution_authorized"] = False
    return candidates


def summarize_archived_asset_graph(
    root_captures: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    asset_captures: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    *,
    max_candidates: int = 100,
) -> dict[str, Any]:
    """Summarize graph coverage while keeping snapshot authority fail closed."""

    ranked = rank_provenance_candidates(
        candidates,
        max_candidates=max_candidates,
    )
    stable_social = sorted({
        str(edge.get("asset_original"))
        for edge in edges
        if edge.get("stable_primary_social_url") is True
        and edge.get("asset_original")
    })
    content_addressed = sorted({
        str(edge.get("asset_original"))
        for edge in edges
        if edge.get("content_addressed_pointer") is True
        and edge.get("asset_original")
    })
    same_origin_traversable = sum(
        1 for edge in edges
        if edge.get("traversable_via_wayback") is True
    )
    retrieved_assets = sum(
        1 for row in asset_captures
        if row.get("asset_capture_retrieved") is True
    )
    authoritative_asset_candidates = sum(
        1
        for row in ranked["candidates"]
        if row.get("direct_primary_archival_source_recovered") is True
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "root_capture_count": len(root_captures),
        "root_capture_retrieved_count": sum(
            1 for row in root_captures
            if row.get("archival_capture_retrieved") is True
        ),
        "asset_edge_count": len(edges),
        "same_origin_traversable_edge_count": same_origin_traversable,
        "asset_capture_count": len(asset_captures),
        "asset_capture_retrieved_count": retrieved_assets,
        "stable_primary_social_url_count": len(stable_social),
        "stable_primary_social_urls": stable_social,
        "content_addressed_pointer_count": len(content_addressed),
        "content_addressed_pointers": content_addressed,
        "asset_semantic_candidate_count": ranked["candidate_count"],
        "direct_primary_archival_asset_candidate_count":
            authoritative_asset_candidates,
        "provenance": ranked,
        "authoritative_exact_snapshot_block_candidates":
            ranked["authoritative_exact_snapshot_block_candidates"],
        "authoritative_exact_snapshot_block_discovered":
            ranked["authoritative_exact_snapshot_block_discovered"],
        "asset_graph_traversal_verified":
            len(root_captures) > 0
            and len(edges) > 0,
        "official_xone_snapshot_verified": False,
        "official_registry_artifact_verified": False,
        "xone_snapshot_eligibility_verified": False,
        "xone_snapshot_xnt_allocation_binding_verified": False,
        "zero_semantic_candidates_are_scoped_asset_graph_evidence_only":
            ranked["candidate_count"] == 0,
        "private_or_unpublished_snapshot_absence_proven": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT_VERSION",
    "MAX_GRAPH_DEPTH",
    "TRAVERSABLE_ASSET_KINDS",
    "XoneSnapshotArchivedAssetGraphError",
    "annotate_retrieved_asset_capture",
    "asset_reference_relevance_score",
    "build_asset_graph_edges",
    "classify_archived_asset_kind",
    "extract_archived_asset_references",
    "extract_asset_provenance_candidates",
    "summarize_archived_asset_graph",
]
