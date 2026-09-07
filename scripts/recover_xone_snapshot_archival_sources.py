#!/usr/bin/env python3
"""Bounded archival recovery for the missing Ethereum XONE holder snapshot."""

from __future__ import annotations

import argparse
from functools import partial
from html.parser import HTMLParser
import json
import time
from urllib.parse import urlparse

import requests

from liquidity_scout.providers.ethereum import (
    DEFAULT_RPC_URLS,
    corroborate_xone_registry_proofs,
    ethereum_rpc_request,
    fetch_and_verify_xone_registry,
    promote_official_snapshot,
)
from liquidity_scout.providers.xone_xnt import (
    XONE_SNAPSHOT_ARCHIVAL_RECOVERY_CONTRACT_VERSION,
    extract_archival_provenance_candidates,
    parse_cdx_json,
    rank_archival_captures,
    recover_stable_x_urls,
    summarize_archival_recovery,
)

USER_AGENT = "CMIS-XONE-Archival-Recovery/1.0 (+read-only; bounded)"
MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3
WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"

CDX_QUERIES = (
    {
        "id": "xen_root_exact",
        "url": "https://xen.network/",
        "matchType": "exact",
    },
    {
        "id": "xen_xone_prefix",
        "url": "https://xen.network/xone",
        "matchType": "prefix",
    },
    {
        "id": "xen_xone_filtered_prefix",
        "url": "https://xen.network/",
        "matchType": "prefix",
        "filter": "original:.*[xX][oO][nN][eE].*",
    },
    {
        "id": "x1_root_exact",
        "url": "https://x1.xyz/",
        "matchType": "exact",
    },
    {
        "id": "x1_xone_prefix",
        "url": "https://x1.xyz/xone",
        "matchType": "prefix",
    },
    {
        "id": "x1_snapshot_prefix",
        "url": "https://x1.xyz/snapshot",
        "matchType": "prefix",
    },
    {
        "id": "next_x1_root_exact",
        "url": "https://next.x1.xyz/",
        "matchType": "exact",
    },
    {
        "id": "next_x1_xone_prefix",
        "url": "https://next.x1.xyz/xone",
        "matchType": "prefix",
    },
    {
        "id": "docs_x1_root_exact",
        "url": "https://docs.x1.xyz/",
        "matchType": "exact",
    },
)

INDEX_TARGETS = (
    (
        "xspacegpt_jack",
        "https://www.twitterspacegpt.com/hosts/mrJackLevin",
        {"www.twitterspacegpt.com", "twitterspacegpt.com"},
    ),
    (
        "twstalker_jack",
        "https://mobile.twstalker.com/mrJackLevin",
        {"mobile.twstalker.com"},
    ),
)


class _TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.casefold() in {"script", "style", "noscript", "svg"}:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag.casefold() in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            value = " ".join(data.split())
            if value:
                self.parts.append(value)


def _normalize_text(content: bytes, content_type: str) -> str:
    text = content.decode("utf-8", errors="replace")
    if "html" not in (content_type or "").casefold():
        return text
    parser = _TextHTMLParser()
    try:
        parser.feed(text)
    except Exception:
        return text
    return "\n".join(parser.parts)


def _safe_get(url: str, *, allowed_hosts: set[str], params=None, timeout=30):
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        parsed = urlparse(current)
        host = (parsed.hostname or "").casefold().rstrip(".")
        if parsed.scheme != "https" or host not in allowed_hosts:
            raise RuntimeError(f"URL escaped allowlist: {current}")
        response = requests.get(
            current,
            params=params if current == url else None,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            timeout=timeout,
            allow_redirects=False,
        )
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            if not location:
                raise RuntimeError("redirect missing Location")
            if location.startswith("/"):
                current = f"https://{host}{location}"
            else:
                current = location
            continue
        response.raise_for_status()
        if len(response.content) > MAX_BYTES:
            raise RuntimeError(f"response exceeds {MAX_BYTES} bytes")
        return response
    raise RuntimeError("too many redirects")


def _fetch_cdx(query, *, limit):
    params = {
        "url": query["url"],
        "matchType": query["matchType"],
        "output": "json",
        "fl": "timestamp,original,mimetype,statuscode,digest,length",
        "filter": ["statuscode:200"],
        "collapse": "digest",
        "from": "2023",
        "to": "2026",
        "limit": str(limit),
    }
    if query.get("filter"):
        params["filter"].append(query["filter"])

    last_error = None
    for attempt in range(3):
        try:
            response = _safe_get(
                WAYBACK_CDX,
                allowed_hosts={"web.archive.org"},
                params=params,
                timeout=35,
            )
            return parse_cdx_json(
                response.json(),
                max_captures=limit,
            ), None
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    return [], {
        "error_type": type(last_error).__name__,
        "error": str(last_error),
    }


def _scan_cdx(*, limit):
    captures = []
    results = []
    for query in CDX_QUERIES:
        rows, error = _fetch_cdx(query, limit=limit)
        if error:
            results.append(
                {
                    "query_id": query["id"],
                    "target_url": query["url"],
                    "match_type": query["matchType"],
                    "status": "UNAVAILABLE",
                    "capture_count": 0,
                    **error,
                }
            )
            continue
        captures.extend(rows)
        results.append(
            {
                "query_id": query["id"],
                "target_url": query["url"],
                "match_type": query["matchType"],
                "status": "AVAILABLE",
                "capture_count": len(rows),
            }
        )

    deduped = {}
    for capture in captures:
        deduped[capture["capture_id"]] = capture
    return results, list(deduped.values())


def _retrieve_archival_captures(captures, *, max_replays):
    selected = rank_archival_captures(captures, max_captures=max_replays)
    results = []
    recovered_candidates = []
    retrieved = []

    for capture in selected:
        replay_url = capture["replay_url"]
        try:
            response = _safe_get(
                replay_url,
                allowed_hosts={"web.archive.org"},
                timeout=35,
            )
        except Exception as exc:
            results.append(
                {
                    "capture_id": capture["capture_id"],
                    "original": capture["original"],
                    "timestamp": capture["timestamp"],
                    "status": "UNAVAILABLE",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue

        row = dict(capture)
        row["archival_capture_retrieved"] = True
        content_type = response.headers.get("Content-Type") or capture.get("mimetype") or ""
        text_value = _normalize_text(response.content, content_type)
        row["retrieved_bytes"] = len(response.content)
        row["retrieved_content_type"] = content_type
        retrieved.append(row)

        candidates = extract_archival_provenance_candidates(
            text_value,
            capture=row,
            observed_at=time.time(),
            max_candidates=75,
        )
        recovered_candidates.extend(candidates)
        results.append(
            {
                "capture_id": capture["capture_id"],
                "original": capture["original"],
                "timestamp": capture["timestamp"],
                "status": "AVAILABLE",
                "bytes": len(response.content),
                "candidate_count": len(candidates),
                "contains_xone": "xone" in text_value.casefold(),
                "contains_snapshot": "snapshot" in text_value.casefold(),
            }
        )

    return results, retrieved, recovered_candidates


def _scan_index_targets():
    results = []
    stable_urls = []
    for source_id, url, allowed_hosts in INDEX_TARGETS:
        try:
            response = _safe_get(url, allowed_hosts=set(allowed_hosts), timeout=25)
        except Exception as exc:
            results.append(
                {
                    "source_id": source_id,
                    "url": url,
                    "status": "UNAVAILABLE",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "stable_primary_url_count": 0,
                }
            )
            continue
        text_value = _normalize_text(
            response.content,
            response.headers.get("Content-Type") or "text/html",
        )
        recovered = recover_stable_x_urls(text_value)
        stable_urls.extend(recovered)
        results.append(
            {
                "source_id": source_id,
                "url": url,
                "status": "AVAILABLE",
                "bytes": len(response.content),
                "contains_xone": "xone" in text_value.casefold(),
                "contains_snapshot": "snapshot" in text_value.casefold(),
                "stable_primary_url_count": len(recovered),
            }
        )

    deduped = {}
    for row in stable_urls:
        deduped[str(row["url"]).casefold()] = row
    return results, list(deduped.values())


def _maybe_reconstruct(recovery, *, rpc_urls, chunk_blocks, sample_size):
    blocks = recovery["authoritative_exact_snapshot_block_candidates"]
    provenance = recovery["provenance"]
    if provenance["authoritative_snapshot_block_conflict"] or len(blocks) != 1:
        return {
            "attempted": False,
            "reason": (
                "authoritative_block_conflict"
                if provenance["authoritative_snapshot_block_conflict"]
                else "no_single_authoritative_exact_snapshot_block"
            ),
            "snapshot_block": None,
            "registry_proofs": [],
            "registry_failures": [],
            "corroboration": None,
            "official_snapshot": None,
        }

    block = blocks[0]
    eligible = [
        row
        for row in provenance["candidates"]
        if row.get("authoritative_exact_snapshot_block_discovered") is True
        and row.get("direct_primary_archival_source_recovered") is True
        and row.get("snapshot_block_candidates") == [block]
    ]
    if not eligible:
        return {
            "attempted": False,
            "reason": "authoritative_block_lacks_direct_primary_archival_source",
            "snapshot_block": block,
            "registry_proofs": [],
            "registry_failures": [],
            "corroboration": None,
            "official_snapshot": None,
        }

    proofs = []
    failures = []
    for rpc_url in rpc_urls:
        rpc = partial(ethereum_rpc_request, rpc_url=rpc_url)
        try:
            proof = fetch_and_verify_xone_registry(
                rpc_call=rpc,
                snapshot_block=block,
                source_url=rpc_url,
                log_chunk_blocks=chunk_blocks,
                balance_sample_size=sample_size,
            )
        except Exception as exc:
            failures.append(
                {
                    "rpc_url": rpc_url,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue
        proofs.append(proof)
        if len(proofs) >= 2:
            break

    corroboration = None
    official = None
    if len(proofs) >= 2:
        corroboration = corroborate_xone_registry_proofs(proofs)
        source = eligible[0]
        source_candidate = {
            "claim_id": source["candidate_id"],
            "source_id": (
                "faircrypto_xone_archival"
                if source["source_role"] == "faircrypto_xone_primary"
                else source["source_id"]
            ),
            "source_role": source["source_role"],
            "url": source["url"],
            "authoritative_source": True,
            "snapshot_block_candidates": [block],
            "exact_xone_contract_mentioned":
                source.get("exact_xone_contract_mentioned") is True,
        }
        official = promote_official_snapshot(
            source_candidate=source_candidate,
            registry_proof=corroboration,
        )

    return {
        "attempted": True,
        "reason": (
            "official_snapshot_reconstructed"
            if official is not None
            else "insufficient_matching_registry_proofs"
        ),
        "snapshot_block": block,
        "registry_proofs": proofs,
        "registry_failures": failures,
        "corroboration": corroboration,
        "official_snapshot": official,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Recover archived XONE snapshot provenance and conditionally hand "
            "an authoritative exact block to the accepted registry verifier."
        )
    )
    parser.add_argument("--cdx-limit", type=int, default=100)
    parser.add_argument("--max-replays", type=int, default=24)
    parser.add_argument("--rpc", action="append", dest="rpc_urls")
    parser.add_argument("--log-chunk-blocks", type=int, default=50_000)
    parser.add_argument("--balance-sample-size", type=int, default=25)
    args = parser.parse_args()

    cdx_results, captures = _scan_cdx(limit=args.cdx_limit)
    replay_results, retrieved_captures, candidates = _retrieve_archival_captures(
        captures,
        max_replays=args.max_replays,
    )
    index_results, stable_urls = _scan_index_targets()

    recovery = summarize_archival_recovery(
        retrieved_captures,
        candidates,
        stable_primary_urls=stable_urls,
        max_candidates=200,
    )
    reconstruction = _maybe_reconstruct(
        recovery,
        rpc_urls=args.rpc_urls or list(DEFAULT_RPC_URLS),
        chunk_blocks=args.log_chunk_blocks,
        sample_size=args.balance_sample_size,
    )

    cdx_available = [row for row in cdx_results if row["status"] == "AVAILABLE"]
    available_original_hosts = {
        (urlparse(row["target_url"]).hostname or "").casefold()
        for row in cdx_available
    }
    index_available = [row for row in index_results if row["status"] == "AVAILABLE"]

    source_gate = (
        len(cdx_available) >= 3
        and len(available_original_hosts) >= 2
        and len(index_available) >= 1
    )

    blocks = recovery["authoritative_exact_snapshot_block_candidates"]
    reconstruction_required = bool(blocks)
    reconstruction_gate = (
        not reconstruction_required
        or (
            len(blocks) == 1
            and not recovery["provenance"]["authoritative_snapshot_block_conflict"]
            and reconstruction["attempted"] is True
            and reconstruction["official_snapshot"] is not None
        )
    )
    status = "PASS" if source_gate and reconstruction_gate else "FAIL"

    official = reconstruction["official_snapshot"]
    output = {
        "status": status,
        "contract_version": XONE_SNAPSHOT_ARCHIVAL_RECOVERY_CONTRACT_VERSION,
        "source_gate_passed": source_gate,
        "cdx_query_results": cdx_results,
        "cdx_available_query_count": len(cdx_available),
        "cdx_available_original_hosts": sorted(available_original_hosts),
        "archival_capture_discovered_count": len(captures),
        "replay_results": replay_results,
        "archival_capture_retrieved_count": len(retrieved_captures),
        "index_results": index_results,
        "index_available_count": len(index_available),
        "stable_primary_url_count": len(stable_urls),
        "stable_primary_urls": stable_urls,
        "recovery": recovery,
        "reconstruction_required_by_authoritative_exact_block":
            reconstruction_required,
        "reconstruction_gate_passed": reconstruction_gate,
        "reconstruction": reconstruction,
        "official_xone_snapshot_verified": (
            official is not None
            and official.get("official_xone_snapshot_verified") is True
        ),
        "official_registry_artifact_verified": False,
        "xone_snapshot_eligibility_verified": False,
        "xone_snapshot_xnt_allocation_binding_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "october_6_unlock_applies_to_xone_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "zero_authoritative_blocks_are_scoped_archival_evidence_only":
            len(blocks) == 0,
        "private_or_unpublished_snapshot_absence_proven": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
