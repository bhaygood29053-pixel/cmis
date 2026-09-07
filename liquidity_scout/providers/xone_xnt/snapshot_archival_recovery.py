"""Archival recovery for the missing Ethereum XONE holder snapshot.

Internet Archive / Wayback is treated as a preservation transport, never as the
original publisher.  Original URL/host, capture timestamp and archive digest are
kept separate.  A mirror may reveal a stable original X/X Spaces URL, but mirror
text itself never becomes direct Jack Levin authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import quote, urlparse

from .snapshot_provenance import (
    extract_provenance_candidates,
    rank_provenance_candidates,
)

CONTRACT_VERSION = "xone_snapshot_archival_source_recovery/v1"
WAYBACK_HOST = "web.archive.org"
CDX_FIELDS = (
    "timestamp",
    "original",
    "mimetype",
    "statuscode",
    "digest",
    "length",
)

ORIGINAL_HOST_ROLES = {
    "x1.xyz": "x1_official",
    "www.x1.xyz": "x1_official",
    "docs.x1.xyz": "x1_official",
    "next.x1.xyz": "x1_official",
    "xen.network": "faircrypto_xone_primary",
    "www.xen.network": "faircrypto_xone_primary",
    "preview.xen.network": "faircrypto_xone_primary",
}

AUTHORITATIVE_ORIGINAL_HOSTS = frozenset(ORIGINAL_HOST_ROLES)
SOCIAL_MIRROR_ROLES = {"indexed_mirror", "secondary_report"}

_ARCHIVE_TIMESTAMP_RE = re.compile(r"^20\d{12}$")
_STABLE_X_STATUS_RE = re.compile(
    r"https?://(?:www\.)?(?:x|twitter)\.com/"
    r"(?P<user>[A-Za-z0-9_]{1,15})/status/(?P<id>\d{5,30})",
    re.IGNORECASE,
)
_STABLE_X_SPACE_RE = re.compile(
    r"https?://(?:www\.)?(?:x|twitter)\.com/i/spaces/"
    r"(?P<id>[A-Za-z0-9_-]{5,80})",
    re.IGNORECASE,
)
_ARCHIVE_PATH_TERMS = (
    "xone",
    "snapshot",
    "holder",
    "registry",
    "allocation",
    "airdrop",
    "claim",
    "merkle",
    "export",
    "vesting",
    "unlock",
    "xnt",
)


class XoneSnapshotArchivalRecoveryError(RuntimeError):
    """Raised when archive/capture evidence cannot be interpreted safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_original_url(value: Any) -> str:
    text = _text(value)
    parsed = urlparse(text)
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise XoneSnapshotArchivalRecoveryError(
            "archived original URL must be HTTP or HTTPS"
        )
    if not parsed.hostname:
        raise XoneSnapshotArchivalRecoveryError(
            "archived original URL is missing a host"
        )
    if parsed.username is not None or parsed.password is not None:
        raise XoneSnapshotArchivalRecoveryError(
            "archived original URL must not contain credentials"
        )
    return text


def source_role_for_original_url(url: str) -> str:
    parsed = urlparse(_normalize_original_url(url))
    host = (parsed.hostname or "").casefold().rstrip(".")
    return ORIGINAL_HOST_ROLES.get(host, "secondary_report")


def original_host_is_authoritative(url: str) -> bool:
    parsed = urlparse(_normalize_original_url(url))
    host = (parsed.hostname or "").casefold().rstrip(".")
    return host in AUTHORITATIVE_ORIGINAL_HOSTS


def build_wayback_replay_url(
    *,
    timestamp: str,
    original_url: str,
) -> str:
    """Build an identity/raw replay URL from validated capture metadata."""

    timestamp = _text(timestamp)
    if not _ARCHIVE_TIMESTAMP_RE.fullmatch(timestamp):
        raise XoneSnapshotArchivalRecoveryError(
            "Wayback timestamp must be 14 decimal digits"
        )
    original = _normalize_original_url(original_url)
    # id_ avoids injecting rewritten archive-navigation markup into evidence.
    return (
        "https://web.archive.org/web/"
        f"{timestamp}id_/{quote(original, safe=':/?&=%#,+;@~!$()*[]')}"
    )


def parse_cdx_json(payload: Any, *, max_captures: int = 250) -> list[dict[str, Any]]:
    """Parse one bounded Wayback CDX JSON response.

    CDX returns a header row followed by value rows. Only successful HTTP 200
    captures with a valid timestamp and original URL are retained.
    """

    if isinstance(max_captures, bool) or not isinstance(max_captures, int) or max_captures < 1:
        raise ValueError("max_captures must be a positive integer")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise XoneSnapshotArchivalRecoveryError("CDX JSON is malformed") from exc
    if not isinstance(payload, Sequence) or isinstance(
        payload, (str, bytes, bytearray)
    ):
        raise XoneSnapshotArchivalRecoveryError("CDX payload must be a JSON array")
    if not payload:
        return []
    header = payload[0]
    if not isinstance(header, Sequence) or isinstance(header, (str, bytes, bytearray)):
        raise XoneSnapshotArchivalRecoveryError("CDX header is invalid")
    columns = [str(value) for value in header]
    required = set(CDX_FIELDS)
    if not required.issubset(set(columns)):
        raise XoneSnapshotArchivalRecoveryError(
            "CDX response is missing required provenance fields"
        )

    captures: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in payload[1:]:
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
            continue
        if len(raw) != len(columns):
            continue
        row = {columns[i]: raw[i] for i in range(len(columns))}
        timestamp = _text(row.get("timestamp"))
        original = _text(row.get("original"))
        statuscode = _text(row.get("statuscode"))
        digest = _text(row.get("digest"))
        mimetype = _text(row.get("mimetype")).casefold()
        length_text = _text(row.get("length"))

        if not _ARCHIVE_TIMESTAMP_RE.fullmatch(timestamp):
            continue
        if statuscode != "200":
            continue
        if not digest:
            continue
        try:
            original = _normalize_original_url(original)
        except XoneSnapshotArchivalRecoveryError:
            continue
        try:
            length = int(length_text) if length_text else None
        except ValueError:
            length = None
        capture_id = sha256(
            f"{timestamp}|{original}|{digest}".encode("utf-8")
        ).hexdigest()
        if capture_id in seen:
            continue
        seen.add(capture_id)
        captures.append(
            {
                "capture_id": capture_id,
                "timestamp": timestamp,
                "original": original,
                "mimetype": mimetype,
                "statuscode": 200,
                "digest": digest,
                "length": length,
                "original_host_authoritative":
                    original_host_is_authoritative(original),
                "original_source_role": source_role_for_original_url(original),
                "replay_url": build_wayback_replay_url(
                    timestamp=timestamp,
                    original_url=original,
                ),
                "archival_capture_discovered": True,
                "archival_capture_retrieved": False,
                "execution_authorized": False,
            }
        )
        if len(captures) >= max_captures:
            break
    return captures


def archival_url_relevance_score(url: str) -> int:
    parsed = urlparse(_normalize_original_url(url))
    lowered = (
        (parsed.path or "") + "?" + (parsed.query or "")
    ).casefold()
    score = 0
    for term in _ARCHIVE_PATH_TERMS:
        if term in lowered:
            score += 10
    if "xone" in lowered:
        score += 30
    if "snapshot" in lowered or "registry" in lowered:
        score += 40
    if original_host_is_authoritative(url):
        score += 20
    return score


def rank_archival_captures(
    captures: Sequence[Mapping[str, Any]],
    *,
    max_captures: int = 50,
) -> list[dict[str, Any]]:
    if isinstance(max_captures, bool) or not isinstance(max_captures, int) or max_captures < 1:
        raise ValueError("max_captures must be a positive integer")
    if not isinstance(captures, Sequence) or isinstance(
        captures, (str, bytes, bytearray)
    ):
        raise ValueError("captures must be a sequence")

    unique: dict[str, dict[str, Any]] = {}
    for capture in captures:
        if not isinstance(capture, Mapping):
            continue
        capture_id = _text(capture.get("capture_id"))
        original = _text(capture.get("original"))
        if not capture_id or not original:
            continue
        row = dict(capture)
        row["relevance_score"] = archival_url_relevance_score(original)
        previous = unique.get(capture_id)
        if previous is None or row["relevance_score"] > previous["relevance_score"]:
            unique[capture_id] = row

    rows = sorted(
        unique.values(),
        key=lambda row: (
            -int(row["relevance_score"]),
            str(row.get("original") or ""),
            str(row.get("timestamp") or ""),
        ),
    )
    return rows[:max_captures]


def recover_stable_x_urls(text: str) -> list[dict[str, Any]]:
    """Recover stable original X/X Spaces URLs from mirror/index text."""

    text = _text(text)
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    for match in _STABLE_X_STATUS_RE.finditer(text):
        user = match.group("user")
        status_id = match.group("id")
        url = f"https://x.com/{user}/status/{status_id}"
        key = url.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "url": url,
                "kind": "x_status",
                "account": user,
                "status_id": status_id,
                "jack_levin_account_match": user.casefold() == "mrjacklevin",
                "stable_primary_url_recovered": True,
                "direct_primary_source_recovered": False,
                "execution_authorized": False,
            }
        )

    for match in _STABLE_X_SPACE_RE.finditer(text):
        space_id = match.group("id")
        url = f"https://x.com/i/spaces/{space_id}"
        key = url.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "url": url,
                "kind": "x_space",
                "space_id": space_id,
                "jack_levin_account_match": False,
                "stable_primary_url_recovered": True,
                "direct_primary_source_recovered": False,
                "execution_authorized": False,
            }
        )
    return results


def extract_archival_provenance_candidates(
    text: str,
    *,
    capture: Mapping[str, Any],
    observed_at: float,
    max_candidates: int = 50,
) -> list[dict[str, Any]]:
    """Extract XONE snapshot leads from one retrieved archival capture."""

    if capture.get("archival_capture_discovered") is not True:
        raise XoneSnapshotArchivalRecoveryError(
            "capture must originate from validated CDX metadata"
        )
    original = _normalize_original_url(capture.get("original"))
    timestamp = _text(capture.get("timestamp"))
    digest = _text(capture.get("digest"))
    if not _ARCHIVE_TIMESTAMP_RE.fullmatch(timestamp) or not digest:
        raise XoneSnapshotArchivalRecoveryError(
            "capture provenance is incomplete"
        )

    source_role = source_role_for_original_url(original)
    candidates = extract_provenance_candidates(
        text,
        source_id=f"wayback_{urlparse(original).hostname or 'unknown'}",
        source_role=source_role,
        url=original,
        observed_at=observed_at,
        revision=f"wayback:{timestamp}:{digest}",
        max_candidates=max_candidates,
    )

    authoritative_original = original_host_is_authoritative(original)
    stable_urls = recover_stable_x_urls(text)
    for row in candidates:
        row["archive_transport"] = "internet_archive_wayback"
        row["archive_capture_id"] = capture.get("capture_id")
        row["archive_timestamp"] = timestamp
        row["archive_digest"] = digest
        row["archive_replay_url"] = capture.get("replay_url")
        row["archival_capture_discovered"] = True
        row["archival_capture_retrieved"] = True
        row["original_host_authoritative"] = authoritative_original
        row["stable_primary_url_candidates"] = stable_urls
        row["stable_primary_url_recovered"] = bool(stable_urls)
        row["direct_primary_archival_source_recovered"] = (
            authoritative_original
            and row.get("direct_primary_source_recovered") is True
        )
        # Wayback transport does not add authority. The underlying original
        # source role controls exact-block eligibility.
        row["official_xone_snapshot_verified"] = False
        row["official_registry_artifact_verified"] = False
        row["xone_snapshot_eligibility_verified"] = False
        row["xone_snapshot_xnt_allocation_binding_verified"] = False
        row["execution_authorized"] = False
    return candidates


def summarize_archival_recovery(
    captures: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    *,
    stable_primary_urls: Sequence[Mapping[str, Any]] = (),
    max_candidates: int = 100,
) -> dict[str, Any]:
    """Summarize archival recovery without promoting official snapshot truth."""

    ranked = rank_provenance_candidates(
        candidates,
        max_candidates=max_candidates,
    )
    retrieved_capture_count = sum(
        1 for row in captures if row.get("archival_capture_retrieved") is True
    )
    direct_archival_count = sum(
        1
        for row in ranked["candidates"]
        if row.get("direct_primary_archival_source_recovered") is True
    )
    stable_urls = []
    seen_urls: set[str] = set()
    for row in stable_primary_urls:
        if not isinstance(row, Mapping):
            continue
        url = _text(row.get("url"))
        if not url or url.casefold() in seen_urls:
            continue
        seen_urls.add(url.casefold())
        stable_urls.append(dict(row))
    for row in ranked["candidates"]:
        for stable in row.get("stable_primary_url_candidates", []) or []:
            if not isinstance(stable, Mapping):
                continue
            url = _text(stable.get("url"))
            if not url or url.casefold() in seen_urls:
                continue
            seen_urls.add(url.casefold())
            stable_urls.append(dict(stable))

    return {
        "contract_version": CONTRACT_VERSION,
        "archival_capture_count": len(captures),
        "archival_capture_retrieved_count": retrieved_capture_count,
        "stable_primary_url_count": len(stable_urls),
        "stable_primary_urls": stable_urls,
        "direct_primary_archival_source_candidate_count": direct_archival_count,
        "provenance": ranked,
        "authoritative_exact_snapshot_block_candidates":
            ranked["authoritative_exact_snapshot_block_candidates"],
        "authoritative_exact_snapshot_block_discovered":
            ranked["authoritative_exact_snapshot_block_discovered"],
        "official_xone_snapshot_verified": False,
        "official_registry_artifact_verified": False,
        "xone_snapshot_eligibility_verified": False,
        "xone_snapshot_xnt_allocation_binding_verified": False,
        "zero_authoritative_blocks_are_scoped_archival_evidence_only":
            len(ranked["authoritative_exact_snapshot_block_candidates"]) == 0,
        "private_or_unpublished_snapshot_absence_proven": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "AUTHORITATIVE_ORIGINAL_HOSTS",
    "CDX_FIELDS",
    "CONTRACT_VERSION",
    "ORIGINAL_HOST_ROLES",
    "WAYBACK_HOST",
    "XoneSnapshotArchivalRecoveryError",
    "archival_url_relevance_score",
    "build_wayback_replay_url",
    "extract_archival_provenance_candidates",
    "original_host_is_authoritative",
    "parse_cdx_json",
    "rank_archival_captures",
    "recover_stable_x_urls",
    "source_role_for_original_url",
    "summarize_archival_recovery",
]
