#!/usr/bin/env python3
"""Bounded archived asset-graph traversal for XONE snapshot provenance."""

from __future__ import annotations

import argparse
from functools import partial
from hashlib import sha256
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
    XONE_SNAPSHOT_ARCHIVED_ASSET_GRAPH_CONTRACT_VERSION,
    annotate_retrieved_asset_capture,
    build_asset_graph_edges,
    extract_archived_asset_references,
    extract_asset_provenance_candidates,
    parse_cdx_json,
    select_diverse_archival_captures,
    summarize_archived_asset_graph,
)


USER_AGENT = "CMIS-XONE-Archived-Asset-Graph/1.0 (+read-only; bounded)"
WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"
MAX_BYTES = 2_500_000
MAX_REDIRECTS = 3

ROOT_QUERIES = (
    ("xen_root", "https://xen.network/"),
    ("x1_root", "https://x1.xyz/"),
    ("next_x1_root", "https://next.x1.xyz/"),
    ("docs_x1_root", "https://docs.x1.xyz/"),
)


def _safe_get(url: str, *, allowed_hosts: set[str], params=None, timeout=12):
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


def _fetch_cdx_exact(url: str, *, limit: int = 50):
    params = {
        "url": url,
        "matchType": "exact",
        "output": "json",
        "fl": "timestamp,original,mimetype,statuscode,digest,length",
        "filter": ["statuscode:200"],
        "collapse": "digest",
        "from": "2023",
        "to": "2026",
        "limit": str(limit),
    }
    last_error = None
    for attempt in range(1):
        try:
            response = _safe_get(
                WAYBACK_CDX,
                allowed_hosts={"web.archive.org"},
                params=params,
                timeout=12,
            )
            return parse_cdx_json(
                response.json(),
                max_captures=limit,
            ), None
        except Exception as exc:
            last_error = exc
    return [], {
        "error_type": type(last_error).__name__,
        "error": str(last_error),
    }


def _nearest_capture(captures, timestamp: str):
    if not captures:
        return None
    try:
        target = int(timestamp)
    except (TypeError, ValueError):
        target = 0
    return min(
        captures,
        key=lambda row: (
            abs(int(str(row.get("timestamp") or "0")) - target),
            str(row.get("timestamp") or ""),
            str(row.get("capture_id") or ""),
        ),
    )


def _decode_text(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def _root_captures(*, per_root_limit: int):
    query_results = []
    captures = []
    for query_id, url in ROOT_QUERIES:
        rows, error = _fetch_cdx_exact(url, limit=per_root_limit)
        if error:
            query_results.append({
                "query_id": query_id,
                "url": url,
                "status": "UNAVAILABLE",
                "capture_count": 0,
                **error,
            })
            continue
        query_results.append({
            "query_id": query_id,
            "url": url,
            "status": "AVAILABLE",
            "capture_count": len(rows),
        })
        captures.extend(rows)
    deduped = {
        row["capture_id"]: row
        for row in captures
    }
    return query_results, list(deduped.values())


def _replay_roots(captures, *, max_replays: int, max_refs_per_node: int):
    selected = select_diverse_archival_captures(
        captures,
        max_captures=max_replays,
    )
    root_results = []
    retrieved_roots = []
    edges = []

    for capture in selected:
        try:
            response = _safe_get(
                capture["replay_url"],
                allowed_hosts={"web.archive.org"},
                timeout=12,
            )
        except Exception as exc:
            root_results.append({
                "capture_id": capture["capture_id"],
                "original": capture["original"],
                "timestamp": capture["timestamp"],
                "status": "UNAVAILABLE",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "reference_count": 0,
            })
            continue

        row = dict(capture)
        row["archival_capture_retrieved"] = True
        row["root_capture_id"] = capture["capture_id"]
        row["retrieved_bytes"] = len(response.content)
        row["retrieved_content_type"] = (
            response.headers.get("Content-Type")
            or capture.get("mimetype")
            or "text/html"
        )
        row["retrieved_content_sha256"] = sha256(response.content).hexdigest()
        retrieved_roots.append(row)

        text_value = _decode_text(response.content)
        refs = extract_archived_asset_references(
            text_value,
            parent_original_url=row["original"],
            content_type=row["retrieved_content_type"],
            max_references=max_refs_per_node,
        )
        node_edges = build_asset_graph_edges(
            row,
            refs,
            depth=1,
        )
        edges.extend(node_edges)
        root_results.append({
            "capture_id": row["capture_id"],
            "original": row["original"],
            "timestamp": row["timestamp"],
            "status": "AVAILABLE",
            "bytes": len(response.content),
            "reference_count": len(refs),
            "traversable_reference_count": sum(
                1 for ref in refs
                if ref.get("traversable_via_wayback") is True
            ),
        })
    return root_results, retrieved_roots, edges


def _select_edges_for_lookup(edges, *, max_lookups: int):
    rows = [
        edge for edge in edges
        if edge.get("traversable_via_wayback") is True
    ]
    rows.sort(
        key=lambda edge: (
            -int(edge.get("relevance_score", 0)),
            int(edge.get("depth", 0)),
            str(edge.get("asset_original") or ""),
            str(edge.get("parent_archive_timestamp") or ""),
        )
    )
    selected = []
    seen = set()
    for edge in rows:
        key = (
            str(edge.get("asset_original") or "").casefold(),
            str(edge.get("parent_archive_timestamp") or "")[:8],
        )
        if key in seen:
            continue
        seen.add(key)
        selected.append(edge)
        if len(selected) >= max_lookups:
            break
    return selected


def _traverse_assets(
    initial_edges,
    *,
    max_asset_lookups: int,
    max_asset_replays: int,
    max_refs_per_node: int,
):
    all_edges = list(initial_edges)
    asset_captures = []
    candidates = []
    lookup_results = []
    replay_results = []
    replay_count = 0
    lookup_count = 0
    visited_capture_ids = set()

    queue = _select_edges_for_lookup(
        all_edges,
        max_lookups=max_asset_lookups,
    )
    queued_edge_ids = {str(row["edge_id"]) for row in queue}

    index = 0
    while index < len(queue) and lookup_count < max_asset_lookups:
        edge = queue[index]
        index += 1
        lookup_count += 1
        asset_url = str(edge["asset_original"])
        rows, error = _fetch_cdx_exact(asset_url, limit=30)
        if error:
            lookup_results.append({
                "edge_id": edge["edge_id"],
                "asset_original": asset_url,
                "depth": edge["depth"],
                "status": "UNAVAILABLE",
                "capture_count": 0,
                **error,
            })
            continue

        lookup_results.append({
            "edge_id": edge["edge_id"],
            "asset_original": asset_url,
            "depth": edge["depth"],
            "status": "AVAILABLE",
            "capture_count": len(rows),
        })
        capture = _nearest_capture(
            rows,
            str(edge.get("parent_archive_timestamp") or ""),
        )
        if capture is None:
            continue
        edge["asset_capture_discovered"] = True
        edge["asset_capture_id"] = capture["capture_id"]

        if replay_count >= max_asset_replays:
            continue
        if capture["capture_id"] in visited_capture_ids:
            continue
        replay_count += 1
        visited_capture_ids.add(capture["capture_id"])

        try:
            response = _safe_get(
                capture["replay_url"],
                allowed_hosts={"web.archive.org"},
                timeout=12,
            )
        except Exception as exc:
            replay_results.append({
                "edge_id": edge["edge_id"],
                "capture_id": capture["capture_id"],
                "asset_original": asset_url,
                "status": "UNAVAILABLE",
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            continue

        annotated = annotate_retrieved_asset_capture(
            capture,
            root_capture_id=str(edge["root_capture_id"]),
            parent_capture_id=str(edge["parent_capture_id"]),
            depth=int(edge["depth"]),
            retrieved_bytes=len(response.content),
            retrieved_content_type=(
                response.headers.get("Content-Type")
                or capture.get("mimetype")
                or ""
            ),
            content_sha256=sha256(response.content).hexdigest(),
        )
        asset_captures.append(annotated)
        edge["asset_capture_retrieved"] = True
        edge["retrieved_content_sha256"] = annotated[
            "retrieved_content_sha256"
        ]

        text_value = _decode_text(response.content)
        semantic = extract_asset_provenance_candidates(
            text_value,
            asset_capture=annotated,
            observed_at=time.time(),
            max_candidates=75,
        )
        candidates.extend(semantic)
        edge["semantic_candidate_discovered"] = bool(semantic)

        nested_count = 0
        if int(edge["depth"]) < 2:
            refs = extract_archived_asset_references(
                text_value,
                parent_original_url=asset_url,
                content_type=annotated["retrieved_content_type"],
                max_references=max_refs_per_node,
            )
            nested_edges = build_asset_graph_edges(
                annotated,
                refs,
                depth=int(edge["depth"]) + 1,
            )
            all_edges.extend(nested_edges)
            nested_count = len(nested_edges)

            # Add new high-value traversable nested edges while respecting the
            # global lookup budget.
            remaining = max_asset_lookups - len(queue)
            if remaining > 0:
                additions = _select_edges_for_lookup(
                    nested_edges,
                    max_lookups=remaining,
                )
                for candidate_edge in additions:
                    edge_id = str(candidate_edge["edge_id"])
                    if edge_id in queued_edge_ids:
                        continue
                    queued_edge_ids.add(edge_id)
                    queue.append(candidate_edge)

        replay_results.append({
            "edge_id": edge["edge_id"],
            "capture_id": annotated["capture_id"],
            "asset_original": asset_url,
            "depth": edge["depth"],
            "status": "AVAILABLE",
            "bytes": len(response.content),
            "content_type": annotated["retrieved_content_type"],
            "semantic_candidate_count": len(semantic),
            "nested_reference_count": nested_count,
        })

    return {
        "edges": all_edges,
        "asset_captures": asset_captures,
        "semantic_candidates": candidates,
        "lookup_results": lookup_results,
        "replay_results": replay_results,
        "asset_cdx_lookup_attempted_count": len(lookup_results),
        "asset_cdx_lookup_available_count": sum(
            1 for row in lookup_results if row["status"] == "AVAILABLE"
        ),
        "asset_capture_discovered_count": sum(
            1 for edge in all_edges
            if edge.get("asset_capture_discovered") is True
        ),
        "asset_replay_attempted_count": len(replay_results),
        "asset_replay_available_count": sum(
            1 for row in replay_results if row["status"] == "AVAILABLE"
        ),
    }


def _maybe_reconstruct(summary, *, rpc_urls, chunk_blocks, sample_size):
    blocks = summary["authoritative_exact_snapshot_block_candidates"]
    provenance = summary["provenance"]
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
            "reason": "authoritative_block_lacks_direct_primary_archival_asset",
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
            failures.append({
                "rpc_url": rpc_url,
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
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
                "faircrypto_xone_archived_asset"
                if source["source_role"] == "faircrypto_xone_primary"
                else str(source["source_id"])
            ),
            "source_role": source["source_role"],
            "url": source["url"],
            "authoritative_source": True,
            "exact_xone_contract_mentioned":
                source.get("exact_xone_contract_mentioned") is True,
            "snapshot_block_candidates": [block],
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
            "Traverse a bounded Wayback asset graph behind historical XEN/X1 "
            "pages to recover XONE snapshot provenance hidden in application assets."
        )
    )
    parser.add_argument("--root-cdx-limit", type=int, default=40)
    parser.add_argument("--max-root-replays", type=int, default=12)
    parser.add_argument("--max-refs-per-node", type=int, default=80)
    parser.add_argument("--max-asset-lookups", type=int, default=40)
    parser.add_argument("--max-asset-replays", type=int, default=20)
    parser.add_argument("--rpc", action="append", dest="rpc_urls")
    parser.add_argument("--log-chunk-blocks", type=int, default=50_000)
    parser.add_argument("--balance-sample-size", type=int, default=25)
    args = parser.parse_args()

    query_results, root_captures = _root_captures(
        per_root_limit=args.root_cdx_limit,
    )
    root_results, retrieved_roots, initial_edges = _replay_roots(
        root_captures,
        max_replays=args.max_root_replays,
        max_refs_per_node=args.max_refs_per_node,
    )
    traversal = _traverse_assets(
        initial_edges,
        max_asset_lookups=args.max_asset_lookups,
        max_asset_replays=args.max_asset_replays,
        max_refs_per_node=args.max_refs_per_node,
    )
    summary = summarize_archived_asset_graph(
        retrieved_roots,
        traversal["edges"],
        traversal["asset_captures"],
        traversal["semantic_candidates"],
        max_candidates=150,
    )
    reconstruction = _maybe_reconstruct(
        summary,
        rpc_urls=args.rpc_urls or list(DEFAULT_RPC_URLS),
        chunk_blocks=args.log_chunk_blocks,
        sample_size=args.balance_sample_size,
    )

    root_cdx_available = sum(
        1 for row in query_results if row["status"] == "AVAILABLE"
    )
    root_replay_available = sum(
        1 for row in root_results if row["status"] == "AVAILABLE"
    )
    traversable_edges = summary["same_origin_traversable_edge_count"]
    source_gate = (
        root_cdx_available >= 3
        and len(root_captures) > 0
        and root_replay_available >= 1
        and summary["asset_edge_count"] > 0
        and traversable_edges > 0
        and traversal["asset_cdx_lookup_attempted_count"] > 0
        and traversal["asset_cdx_lookup_available_count"] > 0
    )

    blocks = summary["authoritative_exact_snapshot_block_candidates"]
    reconstruction_required = bool(blocks)
    reconstruction_gate = (
        not reconstruction_required
        or (
            len(blocks) == 1
            and not summary["provenance"]["authoritative_snapshot_block_conflict"]
            and reconstruction["attempted"] is True
            and reconstruction["official_snapshot"] is not None
        )
    )
    status = "PASS" if source_gate and reconstruction_gate else "FAIL"
    official = reconstruction["official_snapshot"]

    output = {
        "status": status,
        "contract_version":
            XONE_SNAPSHOT_ARCHIVED_ASSET_GRAPH_CONTRACT_VERSION,
        "source_gate_passed": source_gate,
        "root_cdx_query_results": query_results,
        "root_cdx_query_available_count": root_cdx_available,
        "root_capture_discovered_count": len(root_captures),
        "root_replay_results": root_results,
        "root_replay_available_count": root_replay_available,
        "asset_cdx_lookup_results": traversal["lookup_results"],
        "asset_cdx_lookup_attempted_count":
            traversal["asset_cdx_lookup_attempted_count"],
        "asset_cdx_lookup_available_count":
            traversal["asset_cdx_lookup_available_count"],
        "asset_capture_discovered_count":
            traversal["asset_capture_discovered_count"],
        "asset_replay_results": traversal["replay_results"],
        "asset_replay_attempted_count":
            traversal["asset_replay_attempted_count"],
        "asset_replay_available_count":
            traversal["asset_replay_available_count"],
        "asset_graph": summary,
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
        "private_or_unpublished_snapshot_absence_proven": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
