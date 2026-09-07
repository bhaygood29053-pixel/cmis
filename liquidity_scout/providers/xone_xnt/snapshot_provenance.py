"""Bounded provenance expansion for the Ethereum XONE holder snapshot.

This contract searches historical source material for provenance leads without
promoting mirrors, filenames, repository history, or secondary reporting into
official snapshot truth.  It is deliberately separate from the direct Ethereum
registry reconstruction contract.

A provenance lead may tell CMIS where to look next.  Only a primary/direct
source with explicit XONE snapshot semantics can supply an authoritative exact
snapshot block to ethereum_xone_snapshot_registry/v1.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Any
from urllib.parse import urlparse

from liquidity_scout.providers.ethereum.xone_identity import XONE_CONTRACT


CONTRACT_VERSION = "xone_snapshot_provenance_expansion/v1"

SOURCE_STRENGTH = {
    "faircrypto_xone_primary": 100,
    "x1_official": 95,
    "jack_levin_direct": 92,
    "faircrypto_x1_app_primary": 85,
    "x1_labs_source": 75,
    "x1_report": 55,
    "indexed_mirror": 30,
    "secondary_report": 25,
}

PRIMARY_ROLES = {
    "faircrypto_xone_primary",
    "x1_official",
    "jack_levin_direct",
    "faircrypto_x1_app_primary",
}

AUTHORITATIVE_SNAPSHOT_ROLES = {
    "faircrypto_xone_primary",
    "x1_official",
    "jack_levin_direct",
}

SNAPSHOT_TERMS = (
    "snapshot",
    "snapshotted",
    "holder snapshot",
    "snapshot block",
    "holder registry",
    "holder list",
    "eligibility list",
    "snapshot registry",
)
ARTIFACT_TERMS = (
    "merkle",
    "root",
    "proof",
    "registry",
    "holders",
    "holder",
    "balances",
    "balance",
    "eligibility",
    "allocation",
    "claim",
    "airdrop",
    "vesting",
    "unlock",
    "distribution",
    "export",
    "snapshot",
)
XNT_TERMS = (
    "xnt",
    "allocation",
    "airdrop",
    "claim",
    "vesting",
    "unlock",
    "distribution",
)
HISTORICAL_CONTEXT_TERMS = (
    "xone mint",
    "xone launch",
    "xone is live",
    "xone mint is live",
    "xone roadmap",
    "xone x1",
)

ARTIFACT_SUFFIXES = (
    ".csv",
    ".json",
    ".jsonl",
    ".ndjson",
    ".txt",
    ".tsv",
    ".merkle",
)

BLOCK_RE = re.compile(
    r"(?i)\b(?:ethereum\s+)?block(?:\s+(?:number|height))?\s*"
    r"(?:#|:|=|is|was|at)?\s*(0x[0-9a-f]+|\d{7,9})\b"
)
HASH_RE = re.compile(r"0x[a-fA-F0-9]{64}")
ETH_ADDRESS_RE = re.compile(r"0x[a-fA-F0-9]{40}")
URL_RE = re.compile(
    r"(?:https://[^\s\]\[<>()\"']+|ipfs://[A-Za-z0-9/_\-.]+|"
    r"ar://[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b",
    re.IGNORECASE,
)
ISO_DATE_RE = re.compile(
    r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}"
    r"(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?\b"
)


class XoneSnapshotProvenanceError(RuntimeError):
    """Raised when provenance input cannot be classified safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe(values: Sequence[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _extract_block_candidates(text: str) -> list[int]:
    values: list[int] = []
    for match in BLOCK_RE.finditer(text):
        raw = match.group(1)
        try:
            block = int(raw, 16 if raw.casefold().startswith("0x") else 10)
        except ValueError:
            continue
        if block not in values:
            values.append(block)
    return values


def _extract_hash_candidates(text: str) -> list[str]:
    result: list[str] = []
    lowered = text.casefold()
    for match in HASH_RE.finditer(text):
        prefix = lowered[max(0, match.start() - 100):match.start()]
        if any(
            term in prefix
            for term in (
                "merkle",
                "root",
                "snapshot",
                "registry",
                "block hash",
                "digest",
            )
        ):
            value = match.group(0).casefold()
            if value not in result:
                result.append(value)
    return result


def _extract_dates(text: str) -> list[str]:
    result: list[str] = []
    for regex in (DATE_RE, ISO_DATE_RE):
        for match in regex.finditer(text):
            value = match.group(0)
            if value not in result:
                result.append(value)
    return result


def _extract_urls(text: str) -> list[str]:
    return _dedupe(
        [match.group(0).rstrip(".,;:") for match in URL_RE.finditer(text)]
    )


def _artifact_indicators(text: str, *, path: str | None = None) -> list[str]:
    lowered = text.casefold()
    path_lower = _text(path).casefold()
    result: list[str] = []
    for term in ARTIFACT_TERMS:
        if term in lowered or term in path_lower:
            result.append(term)
    for suffix in ARTIFACT_SUFFIXES:
        if path_lower.endswith(suffix):
            result.append(suffix.lstrip("."))
    if "ipfs://" in lowered:
        result.append("ipfs")
    if "ar://" in lowered or "arweave" in lowered:
        result.append("arweave")
    if "merkle" in lowered:
        result.append("merkle")
    return _dedupe(result)


def _candidate_kind(
    text: str,
    *,
    path: str | None,
) -> str | None:
    lowered = text.casefold()
    path_lower = _text(path).casefold()

    # A path may bind otherwise ambiguous file contents to XONE, but an ordinary
    # XONE ABI/config filename must not turn every JSON line into a snapshot
    # artifact. Snapshot/artifact semantics must appear in the bounded text
    # itself. Repository path discovery passes the path as text explicitly, so
    # meaningful names such as xone-holder-snapshot.json still become leads.
    has_xone = "xone" in lowered or "xone" in path_lower
    has_snapshot = any(term in lowered for term in SNAPSHOT_TERMS)
    indicators = _artifact_indicators(text, path=None)
    strong_artifact_indicators = {
        "snapshot",
        "registry",
        "merkle",
        "proof",
        "eligibility",
        "allocation",
        "claim",
        "airdrop",
        "vesting",
        "unlock",
        "distribution",
        "export",
        "ipfs",
        "arweave",
    }
    has_artifact = any(
        indicator in strong_artifact_indicators for indicator in indicators
    )
    has_history = any(term in lowered for term in HISTORICAL_CONTEXT_TERMS)

    if has_xone and has_snapshot:
        return "snapshot_statement"
    if has_xone and has_artifact:
        return "artifact_reference"
    if has_xone and has_history:
        return "historical_context"
    return None


def _score_candidate(
    *,
    source_role: str,
    candidate_kind: str,
    exact_contract: bool,
    exact_blocks: Sequence[int],
    artifact_indicators: Sequence[str],
    xnt_binding_language: bool,
    direct_source_url_present: bool,
) -> int:
    score = SOURCE_STRENGTH[source_role]
    score += {
        "snapshot_statement": 45,
        "artifact_reference": 20,
        "historical_context": 5,
    }[candidate_kind]
    if exact_contract:
        score += 25
    if exact_blocks:
        score += 35
    if "merkle" in artifact_indicators:
        score += 15
    if any(kind in artifact_indicators for kind in ("csv", "json", "jsonl", "ipfs", "arweave")):
        score += 10
    if xnt_binding_language:
        score += 10
    if direct_source_url_present:
        score += 5
    return score


def extract_provenance_candidates(
    text: str,
    *,
    source_id: str,
    source_role: str,
    url: str,
    observed_at: float,
    path: str | None = None,
    revision: str | None = None,
    max_candidates: int = 50,
) -> list[dict[str, Any]]:
    """Extract bounded provenance leads from one document/history row.

    Mirrors can produce discovery leads, but only PRIMARY_ROLES can set
    direct_primary_source_recovered.  Only AUTHORITATIVE_SNAPSHOT_ROLES with
    explicit snapshot semantics and an exact block can set
    authoritative_exact_snapshot_block_discovered.
    """

    if source_role not in SOURCE_STRENGTH:
        raise ValueError(f"unsupported source_role {source_role!r}")
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer")

    normalized = re.sub(r"[\t\r ]+", " ", _text(text))
    if not normalized:
        return []

    segments = [
        segment.strip()
        for segment in re.split(r"(?<=[.!?])\s+|\n+", normalized)
        if segment.strip()
    ]
    if not segments:
        segments = [normalized]

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, segment in enumerate(segments):
        parts = [segment]
        if index > 0 and len(segments[index - 1]) <= 800:
            parts.insert(0, segments[index - 1])
        if index + 1 < len(segments) and len(segments[index + 1]) <= 800:
            parts.append(segments[index + 1])
        excerpt = re.sub(r"\s+", " ", " ".join(parts)).strip()[:2500]

        kind = _candidate_kind(excerpt, path=path)
        if kind is None:
            continue

        lowered = excerpt.casefold()
        blocks = _extract_block_candidates(excerpt)
        hashes = _extract_hash_candidates(excerpt)
        dates = _extract_dates(excerpt)
        addresses = _dedupe(
            [value.casefold() for value in ETH_ADDRESS_RE.findall(excerpt)]
        )
        urls = _extract_urls(excerpt)
        indicators = _artifact_indicators(excerpt, path=path)
        exact_contract = XONE_CONTRACT in lowered
        xnt_binding_language = (
            "xnt" in lowered
            and any(term in lowered for term in XNT_TERMS)
        )
        direct_primary = source_role in PRIMARY_ROLES
        authoritative_block = (
            source_role in AUTHORITATIVE_SNAPSHOT_ROLES
            and kind == "snapshot_statement"
            and len(blocks) == 1
            and (exact_contract or source_role == "faircrypto_xone_primary")
        )
        artifact_candidate = (
            kind == "artifact_reference"
            or bool(hashes)
            or any(
                indicator in indicators
                for indicator in (
                    "csv",
                    "json",
                    "jsonl",
                    "ipfs",
                    "arweave",
                    "merkle",
                    "registry",
                    "holders",
                    "balances",
                )
            )
        )

        candidate_id = sha256(
            (
                f"{CONTRACT_VERSION}|{source_id}|{source_role}|{url}|"
                f"{_text(path)}|{_text(revision)}|{excerpt}"
            ).encode("utf-8")
        ).hexdigest()
        if candidate_id in seen:
            continue
        seen.add(candidate_id)

        score = _score_candidate(
            source_role=source_role,
            candidate_kind=kind,
            exact_contract=exact_contract,
            exact_blocks=blocks,
            artifact_indicators=indicators,
            xnt_binding_language=xnt_binding_language,
            direct_source_url_present=bool(_text(url)),
        )

        candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_kind": kind,
                "score": score,
                "source_id": _text(source_id),
                "source_role": source_role,
                "url": _text(url),
                "path": _text(path) or None,
                "revision": _text(revision) or None,
                "observed_at": observed_at,
                "excerpt": excerpt,
                "snapshot_block_candidates": blocks,
                "hash_candidates": hashes,
                "date_candidates": dates,
                "ethereum_address_candidates": addresses,
                "artifact_url_candidates": urls,
                "artifact_indicators": indicators,
                "exact_xone_contract_mentioned": exact_contract,
                "xnt_allocation_binding_language_present": xnt_binding_language,
                "provenance_candidate_discovered": True,
                "direct_primary_source_recovered": direct_primary,
                "snapshot_artifact_candidate_discovered": artifact_candidate,
                "authoritative_exact_snapshot_block_discovered": authoritative_block,
                "official_xone_snapshot_verified": False,
                "official_registry_artifact_verified": False,
                "xone_snapshot_eligibility_verified": False,
                "xone_snapshot_xnt_allocation_binding_verified": False,
                "xnt_issuance_verified": False,
                "xnt_vesting_or_unlock_verified": False,
                "october_6_unlock_applies_to_xone_verified": False,
                "xone_xnt_conversion_verified": False,
                "cross_chain_correlation_verified": False,
                "public_service_promoted": False,
                "scout_reliance_promoted": False,
                "execution_authorized": False,
            }
        )
        if len(candidates) >= max_candidates:
            break

    return candidates


def discover_repository_path_candidates(
    entries: Sequence[Mapping[str, Any]],
    *,
    source_id: str,
    source_role: str,
    repository_url: str,
    revision: str,
    observed_at: float,
    max_candidates: int = 100,
) -> list[dict[str, Any]]:
    """Turn bounded repository tree rows into path-level provenance leads."""

    if source_role not in SOURCE_STRENGTH:
        raise ValueError(f"unsupported source_role {source_role!r}")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes, bytearray)):
        raise ValueError("entries must be a sequence")

    candidates: list[dict[str, Any]] = []
    for row in entries:
        if not isinstance(row, Mapping):
            continue
        path = _text(row.get("path"))
        entry_type = _text(row.get("type"))
        if not path or entry_type not in {"blob", "file"}:
            continue
        kind = _candidate_kind(path, path=path)
        if kind is None:
            continue
        # Path-only rows are leads, never proof of file contents.
        path_text = f"Repository path candidate: {path}"
        rows = extract_provenance_candidates(
            path_text,
            source_id=source_id,
            source_role=source_role,
            url=repository_url,
            path=path,
            revision=revision,
            observed_at=observed_at,
            max_candidates=1,
        )
        for candidate in rows:
            candidate["direct_primary_source_recovered"] = False
            candidate["authoritative_exact_snapshot_block_discovered"] = False
            candidate["path_only_candidate"] = True
            candidate["score"] = max(0, int(candidate["score"]) - 20)
            candidates.append(candidate)
        if len(candidates) >= max_candidates:
            break

    candidates.sort(
        key=lambda row: (-int(row["score"]), str(row.get("path") or ""))
    )
    return candidates[:max_candidates]


def rank_provenance_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    max_candidates: int = 100,
) -> dict[str, Any]:
    """Deduplicate and rank provenance leads without promoting snapshot truth."""

    if not isinstance(candidates, Sequence) or isinstance(
        candidates, (str, bytes, bytearray)
    ):
        raise ValueError("candidates must be a sequence")
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer")

    unique: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        candidate_id = _text(candidate.get("candidate_id"))
        if not candidate_id:
            continue
        row = dict(candidate)
        previous = unique.get(candidate_id)
        if previous is None or int(row.get("score", 0)) > int(previous.get("score", 0)):
            unique[candidate_id] = row

    ranked = sorted(
        unique.values(),
        key=lambda row: (
            -int(row.get("score", 0)),
            str(row.get("source_role") or ""),
            str(row.get("source_id") or ""),
            str(row.get("candidate_id") or ""),
        ),
    )[:max_candidates]

    authoritative_blocks = sorted(
        {
            int(block)
            for row in ranked
            if row.get("authoritative_exact_snapshot_block_discovered") is True
            for block in row.get("snapshot_block_candidates", [])
        }
    )
    direct_primary_count = sum(
        1 for row in ranked if row.get("direct_primary_source_recovered") is True
    )
    artifact_count = sum(
        1
        for row in ranked
        if row.get("snapshot_artifact_candidate_discovered") is True
    )
    mirror_count = sum(
        1 for row in ranked if row.get("source_role") == "indexed_mirror"
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "candidate_count": len(ranked),
        "candidates": ranked,
        "direct_primary_source_candidate_count": direct_primary_count,
        "snapshot_artifact_candidate_count": artifact_count,
        "indexed_mirror_candidate_count": mirror_count,
        "authoritative_exact_snapshot_block_candidates": authoritative_blocks,
        "authoritative_exact_snapshot_block_discovered":
            len(authoritative_blocks) == 1,
        "authoritative_snapshot_block_conflict": len(authoritative_blocks) > 1,
        "official_xone_snapshot_verified": False,
        "official_registry_artifact_verified": False,
        "xone_snapshot_eligibility_verified": False,
        "xone_snapshot_xnt_allocation_binding_verified": False,
        "zero_authoritative_blocks_are_scoped_provenance_evidence_only":
            len(authoritative_blocks) == 0,
        "private_or_unpublished_snapshot_absence_proven": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


def validate_provenance_url(
    url: str,
    *,
    allowed_hosts: Sequence[str],
) -> str:
    """Validate an HTTPS provenance target against an explicit host allowlist."""

    parsed = urlparse(_text(url))
    host = (parsed.hostname or "").casefold().rstrip(".")
    allowed = {str(value).casefold().rstrip(".") for value in allowed_hosts}
    if parsed.scheme.casefold() != "https":
        raise XoneSnapshotProvenanceError("provenance URL must use HTTPS")
    if not host or host not in allowed:
        raise XoneSnapshotProvenanceError(
            f"provenance URL host {host!r} is outside the allowlist"
        )
    if parsed.username is not None or parsed.password is not None:
        raise XoneSnapshotProvenanceError(
            "provenance URL must not embed credentials"
        )
    return url


__all__ = [
    "ARTIFACT_SUFFIXES",
    "ARTIFACT_TERMS",
    "AUTHORITATIVE_SNAPSHOT_ROLES",
    "CONTRACT_VERSION",
    "HISTORICAL_CONTEXT_TERMS",
    "PRIMARY_ROLES",
    "SNAPSHOT_TERMS",
    "SOURCE_STRENGTH",
    "XoneSnapshotProvenanceError",
    "discover_repository_path_candidates",
    "extract_provenance_candidates",
    "rank_provenance_candidates",
    "validate_provenance_url",
]
