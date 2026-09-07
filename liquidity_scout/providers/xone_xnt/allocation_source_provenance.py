"""XONE -> XNT allocation-source provenance discovery.

This contract searches for the *source of an allocation* rather than individual
holder rows.  It is deliberately narrower than generic XONE/XNT web discovery.

Concrete provenance classes:
- registry/export or structured holder/allocation files;
- API/data endpoints;
- Merkle root/tree/proof sources;
- IPFS/Arweave/content-addressed artifacts;
- exact X1 program IDs plus typed IDL/account/PDA schema context;
- release assets/manifests naming one of those sources.

A source candidate is not snapshot eligibility, an allocation formula, issuance,
vesting, or cross-chain correlation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

from .x1_xnt_distribution_mechanism import (
    X1XntMechanismDiscoveryError,
    normalize_x1_pubkey,
)


CONTRACT_VERSION = "xone_xnt_allocation_source_provenance/v1"
DISCOVERED = "DISCOVERED"

XONE_CONTRACT = "0x4DCDa2274899d9BbA3Bb6f5A852C107Dd6E4fE1c"
XONE_CONTRACT_NORMALIZED = XONE_CONTRACT.casefold()

SOURCE_CLASS_REGISTRY_EXPORT = "registry_export_artifact"
SOURCE_CLASS_STRUCTURED_FILE = "structured_allocation_file"
SOURCE_CLASS_API = "api_endpoint"
SOURCE_CLASS_MERKLE = "merkle_artifact"
SOURCE_CLASS_CONTENT_ADDRESSED = "content_addressed_artifact"
SOURCE_CLASS_X1_PROGRAM_SCHEMA = "x1_program_schema"
SOURCE_CLASS_RELEASE_ASSET = "release_asset"

SOURCE_CLASSES = (
    SOURCE_CLASS_REGISTRY_EXPORT,
    SOURCE_CLASS_STRUCTURED_FILE,
    SOURCE_CLASS_API,
    SOURCE_CLASS_MERKLE,
    SOURCE_CLASS_CONTENT_ADDRESSED,
    SOURCE_CLASS_X1_PROGRAM_SCHEMA,
    SOURCE_CLASS_RELEASE_ASSET,
)

STRUCTURED_EXTENSIONS = (
    ".csv",
    ".tsv",
    ".json",
    ".jsonl",
    ".ndjson",
    ".parquet",
)

XONE_TERMS = ("xone",)
XNT_TERMS = ("xnt", "xnt credit", "xnt credits")
ALLOCATION_TERMS = (
    "allocation",
    "allocations",
    "allocated",
    "airdrop",
    "claim",
    "claimable",
    "eligibility",
    "eligible",
    "holder",
    "holders",
    "snapshot",
    "distribution",
    "vesting",
    "unlock",
)
SOURCE_TERMS = (
    "registry",
    "export",
    "download",
    "dataset",
    "data file",
    "manifest",
    "api",
    "endpoint",
    "merkle",
    "root",
    "tree",
    "proof",
    "ipfs",
    "arweave",
    "program id",
    "program_id",
    "programid",
    "idl",
    "account schema",
    "pda",
    "release asset",
)
API_CONTEXT_TERMS = (
    "api",
    "endpoint",
    "graphql",
    "rest",
    "registry",
    "allocations",
    "allocation",
    "claims",
    "claim",
    "holders",
    "snapshot",
)
PROGRAM_CONTEXT_TERMS = (
    "program id",
    "program_id",
    "programid",
    "anchor.toml",
    "idl",
    "account",
    "account schema",
    "pda",
    "program",
)
MERKLE_CONTEXT_TERMS = (
    "merkle",
    "merkle root",
    "root",
    "claim root",
    "proof",
    "tree",
)

_HTTP_URL_RE = re.compile(r"https://[^\s<>\"'\)\]}]+", re.IGNORECASE)
_IPFS_URI_RE = re.compile(
    r"(?:(?:ipfs://)|(?:https://[^\s<>\"']+/ipfs/))"
    r"(?P<cid>(?:Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{20,}))",
    re.IGNORECASE,
)
_IPFS_CID_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<cid>Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{20,})"
    r"(?![A-Za-z0-9])"
)
_AR_URI_RE = re.compile(
    r"(?:(?:ar://)|(?:https://arweave\.net/))"
    r"(?P<tx>[A-Za-z0-9_-]{43})(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)
_BYTES32_RE = re.compile(r"(?<![0-9A-Fa-f])0x[0-9A-Fa-f]{64}(?![0-9A-Fa-f])")
_BASE58_RE = re.compile(
    r"(?<![A-Za-z0-9])[1-9A-HJ-NP-Za-km-z]{32,44}(?![A-Za-z0-9])"
)
_FILE_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"(?P<name>[A-Za-z0-9_.-]{2,120}\.(?:csv|tsv|json|jsonl|ndjson|parquet))"
    r"(?![A-Za-z0-9_.-])",
    re.IGNORECASE,
)

_CONTAINER_REGISTRY_TERMS = (
    "container registry",
    "docker registry",
    "ghcr.io",
    "npm registry",
    "package registry",
)


class XoneXntAllocationSourceProvenanceError(RuntimeError):
    """Raised when provenance evidence cannot be processed safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any, *, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def normalize_source_url(value: Any) -> str:
    parsed = urlparse(_text(value))
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise XoneXntAllocationSourceProvenanceError(
            "source URL must be absolute HTTPS"
        )
    if parsed.username is not None or parsed.password is not None:
        raise XoneXntAllocationSourceProvenanceError(
            "source URL must not embed credentials"
        )
    host = parsed.hostname.casefold().rstrip(".")
    netloc = host if parsed.port is None else f"{host}:{parsed.port}"
    return urlunparse(
        ("https", netloc, parsed.path or "/", "", parsed.query, "")
    )


def _normalized_path(path: Optional[str]) -> str:
    return _text(path).replace("\\", "/").casefold()


def _is_ordinary_abi_path(path: Optional[str]) -> bool:
    normalized = _normalized_path(path)
    return bool(
        normalized
        and (
            normalized.startswith("abi/")
            or "/abi/" in f"/{normalized}"
            or normalized.endswith(".abi.json")
        )
    )


def _semantic_flags(
    text: str,
    *,
    path: Optional[str],
    source_id: str,
    release_name: Optional[str],
) -> dict[str, bool]:
    # source_id is provenance metadata, not evidence text.  Including a
    # source id such as "xenblocks_airdrop_file" would incorrectly make every
    # unrelated file look like it contains allocation language.
    lowered = " ".join(
        item.casefold()
        for item in (
            _text(text),
            _text(path),
            _text(release_name),
        )
        if item
    )
    return {
        "xone_named": any(term in lowered for term in XONE_TERMS),
        "exact_xone_contract_mentioned":
            XONE_CONTRACT_NORMALIZED in lowered,
        "xnt_named": any(term in lowered for term in XNT_TERMS),
        "allocation_language_present":
            any(term in lowered for term in ALLOCATION_TERMS),
        "source_language_present":
            any(term in lowered for term in SOURCE_TERMS),
        "api_language_present":
            any(term in lowered for term in API_CONTEXT_TERMS),
        "program_schema_language_present":
            any(term in lowered for term in PROGRAM_CONTEXT_TERMS),
        "merkle_language_present":
            any(term in lowered for term in MERKLE_CONTEXT_TERMS),
        "container_registry_language_present":
            any(term in lowered for term in _CONTAINER_REGISTRY_TERMS),
    }


def _url_candidates(text: str) -> list[str]:
    rows: list[str] = []
    for match in _HTTP_URL_RE.finditer(_text(text)):
        value = match.group(0).rstrip(".,;:")
        try:
            value = normalize_source_url(value)
        except XoneXntAllocationSourceProvenanceError:
            continue
        if value not in rows:
            rows.append(value)
    return rows


def _structured_filenames(text: str, path: Optional[str]) -> list[str]:
    rows: list[str] = []
    for match in _FILE_TOKEN_RE.finditer(_text(text)):
        name = match.group("name")
        if name not in rows:
            rows.append(name)
    path_value = _text(path)
    if path_value.casefold().endswith(STRUCTURED_EXTENSIONS):
        name = path_value.rsplit("/", 1)[-1]
        if name and name not in rows:
            rows.append(name)
    return rows


def _ipfs_cids(text: str) -> list[str]:
    rows: list[str] = []
    for regex in (_IPFS_URI_RE, _IPFS_CID_RE):
        for match in regex.finditer(_text(text)):
            cid = match.group("cid")
            if cid not in rows:
                rows.append(cid)
    return rows


def _arweave_ids(text: str) -> list[str]:
    rows: list[str] = []
    for match in _AR_URI_RE.finditer(_text(text)):
        tx = match.group("tx")
        if tx not in rows:
            rows.append(tx)
    return rows


def _merkle_roots(text: str) -> list[str]:
    normalized = _text(text)
    rows: list[str] = []
    lowered = normalized.casefold()
    for match in _BYTES32_RE.finditer(normalized):
        start = max(0, match.start() - 160)
        end = min(len(normalized), match.end() + 160)
        window = lowered[start:end]
        if not any(term in window for term in MERKLE_CONTEXT_TERMS):
            continue
        value = match.group(0).casefold()
        if value not in rows:
            rows.append(value)
    return rows


def _x1_program_ids(text: str) -> list[str]:
    normalized = _text(text)
    rows: list[str] = []
    for match in _BASE58_RE.finditer(normalized):
        value = match.group(0)
        start = max(0, match.start() - 180)
        end = min(len(normalized), match.end() + 180)
        window = normalized[start:end].casefold()
        if not any(term in window for term in PROGRAM_CONTEXT_TERMS):
            continue
        try:
            pubkey = normalize_x1_pubkey(value)
        except X1XntMechanismDiscoveryError:
            continue
        if pubkey not in rows:
            rows.append(pubkey)
    return rows


def _api_urls(
    text: str,
    *,
    semantic: Mapping[str, bool],
) -> list[str]:
    if not semantic.get("api_language_present"):
        return []
    rows: list[str] = []
    provenance_url_terms = (
        "xone",
        "xnt",
        "allocation",
        "allocations",
        "claim",
        "claims",
        "holder",
        "holders",
        "snapshot",
        "registry",
        "eligibility",
        "airdrop",
    )
    for url in _url_candidates(text):
        parsed = urlparse(url)
        marker = " ".join(
            [
                (parsed.hostname or "").casefold(),
                parsed.path.casefold(),
                parsed.query.casefold(),
            ]
        )
        # Generic RPC/package/analytics endpoints are not allocation-source
        # provenance merely because the surrounding file discusses an airdrop.
        if not any(term in marker for term in provenance_url_terms):
            continue
        if url not in rows:
            rows.append(url)
    return rows


def _path_source_classes(
    path: Optional[str],
    *,
    semantic: Mapping[str, bool],
) -> list[str]:
    normalized = _normalized_path(path)
    if not normalized or _is_ordinary_abi_path(path):
        return []

    classes: list[str] = []
    basename = normalized.rsplit("/", 1)[-1]

    if basename.endswith(STRUCTURED_EXTENSIONS) and any(
        term in normalized
        for term in (
            "allocation",
            "holder",
            "snapshot",
            "claim",
            "registry",
            "airdrop",
            "distribution",
            "eligibility",
        )
    ):
        classes.append(SOURCE_CLASS_STRUCTURED_FILE)

    if any(term in normalized for term in ("registry", "export", "snapshot")):
        if semantic.get("allocation_language_present") or semantic.get("xone_named"):
            classes.append(SOURCE_CLASS_REGISTRY_EXPORT)

    pda_path = bool(
        re.search(r"(^|[/_.-])pda(?:s)?([/_.-]|$)", normalized)
    )
    if (
        "/idl/" in f"/{normalized}"
        or normalized.endswith("anchor.toml")
        or pda_path
        or any(
            term in normalized
            for term in (
                "account_schema",
                "account-schema",
                "onchain/types",
                "programs/",
            )
        )
    ):
        classes.append(SOURCE_CLASS_X1_PROGRAM_SCHEMA)

    return list(dict.fromkeys(classes))


def _candidate_source_classes(
    text: str,
    *,
    path: Optional[str],
    semantic: Mapping[str, bool],
    release_asset: bool,
) -> tuple[list[str], dict[str, list[str]]]:
    structured_files = _structured_filenames(text, path)
    api_urls = _api_urls(text, semantic=semantic)
    merkle_roots = _merkle_roots(text)
    ipfs_cids = _ipfs_cids(text)
    arweave_ids = _arweave_ids(text)
    program_ids = _x1_program_ids(text)

    classes = _path_source_classes(path, semantic=semantic)

    allocation_file_terms = (
        "xone",
        "xnt",
        "allocation",
        "allocations",
        "holder",
        "holders",
        "snapshot",
        "claim",
        "claims",
        "registry",
        "airdrop",
        "distribution",
        "eligibility",
    )
    relevant_structured_files = [
        name
        for name in structured_files
        if any(term in name.casefold() for term in allocation_file_terms)
    ]
    if (
        relevant_structured_files
        and semantic.get("allocation_language_present")
        and SOURCE_CLASS_X1_PROGRAM_SCHEMA not in classes
    ):
        classes.append(SOURCE_CLASS_STRUCTURED_FILE)

    lowered_text = _text(text).casefold()
    explicit_registry_export = (
        "allocation registry" in lowered_text
        or "holder registry" in lowered_text
        or "snapshot registry" in lowered_text
        or "claim registry" in lowered_text
        or "allocation export" in lowered_text
        or "holder export" in lowered_text
        or "snapshot export" in lowered_text
        or "export file" in lowered_text
        or "export artifact" in lowered_text
        or (
            "download" in lowered_text
            and semantic.get("allocation_language_present")
        )
    )
    if explicit_registry_export:
        classes.append(SOURCE_CLASS_REGISTRY_EXPORT)
    if api_urls:
        classes.append(SOURCE_CLASS_API)
    if merkle_roots and semantic.get("merkle_language_present"):
        classes.append(SOURCE_CLASS_MERKLE)
    if ipfs_cids or arweave_ids:
        classes.append(SOURCE_CLASS_CONTENT_ADDRESSED)
    if program_ids and semantic.get("program_schema_language_present"):
        classes.append(SOURCE_CLASS_X1_PROGRAM_SCHEMA)
    if release_asset and classes:
        classes.append(SOURCE_CLASS_RELEASE_ASSET)

    return (
        list(dict.fromkeys(classes)),
        {
            "structured_filenames": structured_files,
            "api_urls": api_urls,
            "merkle_roots": merkle_roots,
            "ipfs_cids": ipfs_cids,
            "arweave_ids": arweave_ids,
            "x1_program_ids": program_ids,
        },
    )


def _candidate_id(
    *,
    source_id: str,
    source_url: str,
    path: Optional[str],
    revision: Optional[str],
    release_name: Optional[str],
    source_classes: Sequence[str],
    pointers: Mapping[str, Sequence[str]],
    body_sha256: str,
) -> str:
    material = "|".join(
        [
            CONTRACT_VERSION,
            source_id,
            source_url,
            _text(path),
            _text(revision),
            _text(release_name),
            ",".join(sorted(source_classes)),
            ",".join(
                sorted(
                    f"{key}:{item}"
                    for key, values in pointers.items()
                    for item in values
                )
            ),
            body_sha256,
        ]
    )
    return sha256(material.encode("utf-8")).hexdigest()


def extract_allocation_source_provenance(
    text: str,
    *,
    source_id: str,
    source_role: str,
    url: str,
    observed_at: float,
    path: Optional[str] = None,
    revision: Optional[str] = None,
    release_name: Optional[str] = None,
    content_type: Optional[str] = None,
    body_sha256: Optional[str] = None,
    release_asset: bool = False,
    architecture_analogue: bool = False,
    max_candidates: int = 50,
) -> list[dict[str, Any]]:
    """Extract concrete allocation-source provenance from one bounded artifact."""

    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if not _text(source_id):
        raise ValueError("source_id is required")
    if not _text(source_role):
        raise ValueError("source_role is required")
    max_candidates = _positive_int(
        max_candidates,
        name="max_candidates",
        maximum=250,
    )
    normalized_url = normalize_source_url(url)

    # Ordinary EVM ABI JSON was a proven live false-positive class in the
    # preceding allocation-record gate. An ABI by itself is not a holder
    # allocation source.
    if _is_ordinary_abi_path(path):
        return []

    computed_sha = sha256(text.encode("utf-8")).hexdigest()
    if body_sha256 is not None:
        supplied = _text(body_sha256).casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", supplied):
            raise XoneXntAllocationSourceProvenanceError(
                "body_sha256 must be 64 lowercase/uppercase hex characters"
            )
        if supplied != computed_sha:
            raise XoneXntAllocationSourceProvenanceError(
                "body_sha256 does not match artifact content"
            )
    body_hash = computed_sha

    semantic = _semantic_flags(
        text,
        path=path,
        source_id=source_id,
        release_name=release_name,
    )
    source_classes, pointers = _candidate_source_classes(
        text,
        path=path,
        semantic=semantic,
        release_asset=release_asset,
    )

    # A container/package registry is not an allocation registry.
    if (
        semantic["container_registry_language_present"]
        and not semantic["allocation_language_present"]
        and not any(
            pointers[key]
            for key in (
                "merkle_roots",
                "ipfs_cids",
                "arweave_ids",
                "x1_program_ids",
            )
        )
    ):
        return []

    if not source_classes:
        return []

    exact_xone = bool(semantic["exact_xone_contract_mentioned"])
    xone_named = bool(semantic["xone_named"])
    allocation_language = bool(semantic["allocation_language_present"])
    xnt_named = bool(semantic["xnt_named"])

    # XONE allocation provenance requires semantic XONE context. Architecture
    # analogue sources are preserved separately even when XONE is absent.
    xone_semantic_binding = bool(
        xone_named and allocation_language
    )
    if not xone_semantic_binding and not architecture_analogue:
        return []

    if architecture_analogue and xone_semantic_binding:
        # Once a source actually names XONE in allocation context, it is no
        # longer merely an architecture analogue.
        architecture_analogue = False

    xone_source_binding_verified = exact_xone
    qualifying_xone_source_candidate = bool(
        xone_semantic_binding and source_classes
    )

    source_provenance_fields_verified = bool(
        normalized_url
        and body_hash
        and (
            (_text(path) and _text(revision))
            or _text(release_name)
            or source_role.startswith("official_")
        )
    )

    excerpt = re.sub(r"\s+", " ", text).strip()[:2200]
    candidate_id = _candidate_id(
        source_id=source_id,
        source_url=normalized_url,
        path=path,
        revision=revision,
        release_name=release_name,
        source_classes=source_classes,
        pointers=pointers,
        body_sha256=body_hash,
    )

    return [
        {
            "candidate_id": candidate_id,
            "contract_version": CONTRACT_VERSION,
            "discovery_state": DISCOVERED,
            "source_id": _text(source_id),
            "source_role": _text(source_role),
            "url": normalized_url,
            "path": _text(path) or None,
            "revision": _text(revision) or None,
            "release_name": _text(release_name) or None,
            "content_type": _text(content_type) or None,
            "body_sha256": body_hash,
            "observed_at": observed_at,
            "source_classes": source_classes,
            **pointers,
            "context_excerpt": excerpt,
            "xone_named": xone_named,
            "exact_xone_contract_mentioned": exact_xone,
            "xnt_named": xnt_named,
            "allocation_language_present": allocation_language,
            "source_language_present":
                semantic["source_language_present"],
            "xone_semantic_binding_discovered": xone_semantic_binding,
            "xone_source_binding_verified": xone_source_binding_verified,
            "source_provenance_fields_verified":
                source_provenance_fields_verified,
            "architecture_analogue": architecture_analogue,
            "qualifying_xone_allocation_source_candidate":
                qualifying_xone_source_candidate,
            "allocation_source_candidate_discovered": True,
            # Candidate discovery/provenance fields are not authoritative
            # allocation semantics or snapshot->XNT binding.
            "allocation_source_provenance_verified": False,
            "authoritative_allocation_source_verified": False,
            "official_registry_artifact_verified": False,
            "snapshot_eligibility_verified": False,
            "snapshot_xnt_allocation_binding_verified": False,
            "allocation_semantics_verified": False,
            "claim_state_verified": False,
            "vesting_or_unlock_state_verified": False,
            "xnt_issuance_verified": False,
            "xnt_vesting_or_unlock_verified": False,
            "xone_xnt_conversion_verified": False,
            "cross_chain_correlation_verified": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        }
    ][:max_candidates]


def provenance_path_score(path: str) -> int:
    """Rank source-shaped repository paths without treating rank as evidence."""

    normalized = _normalized_path(path)
    if not normalized or _is_ordinary_abi_path(path):
        return -1

    score = 0
    weighted = (
        ("xone", 16),
        ("allocation", 14),
        ("allocations", 14),
        ("holder", 10),
        ("snapshot", 10),
        ("registry", 10),
        ("export", 9),
        ("claim", 8),
        ("merkle", 12),
        ("airdrop", 5),
        ("distribution", 6),
        ("eligibility", 8),
        ("idl", 5),
        ("program", 4),
        ("account", 4),
        ("manifest", 5),
        ("config", 2),
    )
    for term, weight in weighted:
        if term in normalized:
            score += weight

    if re.search(r"(^|[/_.-])pda(?:s)?([/_.-]|$)", normalized):
        score += 5

    if normalized.endswith(STRUCTURED_EXTENSIONS):
        score += 8
    if normalized.endswith("anchor.toml"):
        score += 8
    if "/idl/" in f"/{normalized}":
        score += 7
    if normalized.startswith(".env") or normalized.endswith(".env.example"):
        score += 3
    return score


def summarize_allocation_source_provenance(
    candidates: Sequence[Mapping[str, Any]],
    *,
    max_candidates: int = 100,
) -> dict[str, Any]:
    if not isinstance(candidates, Sequence) or isinstance(
        candidates,
        (str, bytes, bytearray),
    ):
        raise ValueError("candidates must be a sequence")
    max_candidates = _positive_int(
        max_candidates,
        name="max_candidates",
        maximum=500,
    )

    deduped: dict[str, dict[str, Any]] = {}
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        candidate_id = _text(raw.get("candidate_id"))
        if not candidate_id:
            continue
        if candidate_id not in deduped:
            deduped[candidate_id] = dict(raw)

    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            -int(row.get("xone_source_binding_verified") is True),
            -int(
                row.get("qualifying_xone_allocation_source_candidate")
                is True
            ),
            -int(row.get("source_provenance_fields_verified") is True),
            -len(row.get("source_classes") or []),
            str(row.get("url") or ""),
            str(row.get("path") or ""),
        )
    )
    rows = rows[:max_candidates]

    class_counts = {
        source_class: sum(
            1
            for row in rows
            if source_class in (row.get("source_classes") or [])
        )
        for source_class in SOURCE_CLASSES
    }

    qualifying = [
        row
        for row in rows
        if row.get("qualifying_xone_allocation_source_candidate") is True
    ]
    exact_bound = [
        row
        for row in qualifying
        if row.get("xone_source_binding_verified") is True
    ]
    analogues = [
        row
        for row in rows
        if row.get("architecture_analogue") is True
    ]

    return {
        "contract_version": CONTRACT_VERSION,
        "candidate_count": len(rows),
        "qualifying_xone_candidate_count": len(qualifying),
        "exact_xone_source_bound_candidate_count": len(exact_bound),
        "architecture_analogue_candidate_count": len(analogues),
        "source_class_counts": class_counts,
        "candidates": rows,
        "allocation_source_provenance_discovery_verified": True,
        "allocation_source_provenance_verified": False,
        "authoritative_allocation_source_verified": False,
        "official_registry_artifact_verified": False,
        "zero_qualifying_candidates_are_scoped_public_source_evidence_only":
            len(qualifying) == 0,
        "private_or_unpublished_allocation_source_absence_proven": False,
        "snapshot_eligibility_verified": False,
        "snapshot_xnt_allocation_binding_verified": False,
        "allocation_semantics_verified": False,
        "claim_state_verified": False,
        "vesting_or_unlock_state_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }
