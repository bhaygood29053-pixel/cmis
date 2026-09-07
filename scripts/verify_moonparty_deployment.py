#!/usr/bin/env python3
"""Bounded live discovery and direct-RPC proof for FairCrypto MoonParty."""

from __future__ import annotations

from collections import defaultdict
from functools import partial
from html.parser import HTMLParser
import argparse
import json
from pathlib import PurePosixPath
import sys
from urllib.parse import urljoin, urlparse

import requests

from liquidity_scout.providers.ethereum.xone_identity import (
    DEFAULT_RPC_URLS,
    ethereum_rpc_request,
)
from liquidity_scout.providers.xone_xnt import (
    FAIRCRYPTO_X1_APP_COMMIT,
    FAIRCRYPTO_X1_APP_REPO,
    MOONPARTY_ABI_PATH,
    corroborate_moonparty_deployment,
    discover_moonparty_deployment_candidates,
    verify_moonparty_deployment_candidate,
)


CONTRACT_VERSION = "moonparty_deployment_verification/v1"
USER_AGENT = "CMIS-MoonParty-Deployment-Verification/1.0 (+read-only)"
MAX_DOCUMENT_BYTES = 1_500_000
MAX_CHUNKS_PER_HOST = 40
MAX_TOTAL_CHUNK_BYTES_PER_HOST = 12_000_000

PINNED_SOURCE_URLS = {
    "pinned_moonparty_artifact": (
        f"https://raw.githubusercontent.com/{FAIRCRYPTO_X1_APP_REPO}/"
        f"{FAIRCRYPTO_X1_APP_COMMIT}/{MOONPARTY_ABI_PATH}"
    ),
    "pinned_env_example": (
        f"https://raw.githubusercontent.com/{FAIRCRYPTO_X1_APP_REPO}/"
        f"{FAIRCRYPTO_X1_APP_COMMIT}/.env.local.example"
    ),
    "pinned_runtime_config": (
        f"https://raw.githubusercontent.com/{FAIRCRYPTO_X1_APP_REPO}/"
        f"{FAIRCRYPTO_X1_APP_COMMIT}/app/libs/runtimeConfig.ts"
    ),
    "pinned_network_config": (
        f"https://raw.githubusercontent.com/{FAIRCRYPTO_X1_APP_REPO}/"
        f"{FAIRCRYPTO_X1_APP_COMMIT}/config/networks.ts"
    ),
}

LIVE_FRONTEND_URLS = (
    "https://xen.network/x1/moon-party",
    "https://xen.network/x1/portfolio",
    "https://xen.network/",
    "https://preview.xen.network/x1/moon-party",
    "https://preview.xen.network/x1/portfolio",
    "https://preview.xen.network/",
)

ALLOWED_FRONTEND_HOSTS = {
    "xen.network",
    "www.xen.network",
    "preview.xen.network",
}


class ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.srcs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() != "script":
            return
        values = dict(attrs)
        src = values.get("src")
        if src:
            self.srcs.append(src)


def _fetch(
    url: str,
    *,
    allowed_hosts: set[str] | None = None,
    max_bytes: int = MAX_DOCUMENT_BYTES,
    timeout: int = 20,
) -> dict:
    current = url
    redirects = []
    for _ in range(4):
        parsed = urlparse(current)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or not host:
            raise RuntimeError(f"non-HTTPS or invalid URL: {current}")
        if allowed_hosts is not None and host not in allowed_hosts:
            raise RuntimeError(f"source host escaped allowlist: {host}")

        response = requests.get(
            current,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/javascript,text/plain,application/json,*/*;q=0.1",
            },
            timeout=timeout,
            allow_redirects=False,
            stream=True,
        )
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            if not location:
                raise RuntimeError(f"redirect missing Location: {current}")
            target = urljoin(current, location)
            target_host = (urlparse(target).hostname or "").casefold()
            if allowed_hosts is not None and target_host not in allowed_hosts:
                raise RuntimeError(
                    f"redirect escaped allowlist: {host} -> {target_host}"
                )
            redirects.append({"from": current, "to": target})
            current = target
            continue

        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            content.extend(chunk)
            if len(content) > max_bytes:
                raise RuntimeError(
                    f"source exceeds bounded maximum {max_bytes} bytes: {current}"
                )
        text = bytes(content).decode("utf-8", errors="replace")
        return {
            "requested_url": url,
            "final_url": current,
            "status_code": response.status_code,
            "content_type": response.headers.get("Content-Type"),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "bytes": len(content),
            "redirects": redirects,
            "text": text,
        }
    raise RuntimeError(f"too many redirects: {url}")


def _frontend_documents() -> tuple[list[dict], dict]:
    documents: list[dict] = []
    targets = []
    chunk_seen: dict[str, set[str]] = defaultdict(set)
    chunk_bytes: dict[str, int] = defaultdict(int)
    chunks = []

    for index, url in enumerate(LIVE_FRONTEND_URLS):
        try:
            row = _fetch(url, allowed_hosts=ALLOWED_FRONTEND_HOSTS)
        except Exception as exc:
            targets.append(
                {
                    "url": url,
                    "available": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue

        target = {
            "url": url,
            "available": True,
            "final_url": row["final_url"],
            "status_code": row["status_code"],
            "bytes": row["bytes"],
            "content_type": row["content_type"],
        }
        targets.append(target)
        documents.append(
            {
                "source_id": f"live_frontend_{index}",
                "url": row["final_url"],
                "text": row["text"],
            }
        )

        parser = ScriptParser()
        try:
            parser.feed(row["text"])
        except Exception:
            pass

        base_host = (urlparse(row["final_url"]).hostname or "").casefold()
        for src in parser.srcs:
            if len(chunk_seen[base_host]) >= MAX_CHUNKS_PER_HOST:
                break
            chunk_url = urljoin(row["final_url"], src)
            chunk_host = (urlparse(chunk_url).hostname or "").casefold()
            if chunk_host != base_host or chunk_host not in ALLOWED_FRONTEND_HOSTS:
                continue
            if chunk_url in chunk_seen[base_host]:
                continue
            chunk_seen[base_host].add(chunk_url)
            remaining = MAX_TOTAL_CHUNK_BYTES_PER_HOST - chunk_bytes[base_host]
            if remaining <= 0:
                break
            try:
                chunk = _fetch(
                    chunk_url,
                    allowed_hosts=ALLOWED_FRONTEND_HOSTS,
                    max_bytes=min(MAX_DOCUMENT_BYTES, remaining),
                )
            except Exception as exc:
                chunks.append(
                    {
                        "url": chunk_url,
                        "host": base_host,
                        "available": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                continue
            chunk_bytes[base_host] += chunk["bytes"]
            chunks.append(
                {
                    "url": chunk_url,
                    "final_url": chunk["final_url"],
                    "host": base_host,
                    "available": True,
                    "bytes": chunk["bytes"],
                    "content_type": chunk["content_type"],
                }
            )
            documents.append(
                {
                    "source_id": f"live_chunk_{base_host}_{len(chunks)}",
                    "url": chunk["final_url"],
                    "text": chunk["text"],
                }
            )

    summary = {
        "targets": targets,
        "target_attempted_count": len(targets),
        "target_available_count": sum(1 for row in targets if row["available"]),
        "chunks": chunks,
        "chunk_attempted_count": len(chunks),
        "chunk_available_count": sum(1 for row in chunks if row["available"]),
        "chunk_bytes_by_host": dict(chunk_bytes),
    }
    return documents, summary


def _pinned_documents() -> tuple[dict, list[dict], dict]:
    artifact = None
    documents = []
    retrieval = []
    for source_id, url in PINNED_SOURCE_URLS.items():
        try:
            row = _fetch(url, allowed_hosts={"raw.githubusercontent.com"})
        except Exception as exc:
            retrieval.append(
                {
                    "source_id": source_id,
                    "url": url,
                    "available": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue

        retrieval.append(
            {
                "source_id": source_id,
                "url": url,
                "available": True,
                "status_code": row["status_code"],
                "bytes": row["bytes"],
                "etag": row["etag"],
                "last_modified": row["last_modified"],
            }
        )
        if source_id == "pinned_moonparty_artifact":
            artifact = json.loads(row["text"])
        else:
            documents.append(
                {
                    "source_id": source_id,
                    "url": url,
                    "text": row["text"],
                }
            )

    return artifact, documents, {
        "retrieval": retrieval,
        "available_count": sum(1 for row in retrieval if row["available"]),
        "required_count": len(PINNED_SOURCE_URLS),
        "artifact_available": artifact is not None,
    }


def _qualify_candidates(artifact: dict, candidates: list[dict], rpc_urls: list[str]):
    qualifications = []
    corroborations = []
    for candidate in candidates:
        address = candidate["candidate_address"]
        proofs = []
        failures = []
        for rpc_url in rpc_urls:
            rpc = partial(ethereum_rpc_request, rpc_url=rpc_url)
            try:
                proof = verify_moonparty_deployment_candidate(
                    address,
                    artifact=artifact,
                    rpc_call=rpc,
                    source_url=rpc_url,
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

        corroboration = None
        if len(proofs) >= 2:
            try:
                corroboration = corroborate_moonparty_deployment(proofs)
            except Exception as exc:
                failures.append(
                    {
                        "rpc_url": "multi_rpc_corroboration",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )

        qualifications.append(
            {
                "candidate_address": address,
                "source_bindings": candidate.get("source_bindings", []),
                "successful_rpc_proof_count": len(proofs),
                "proofs": proofs,
                "failures": failures,
                "moonparty_deployment_verified": bool(
                    corroboration
                    and corroboration.get("moonparty_deployment_verified") is True
                ),
            }
        )
        if corroboration:
            corroborations.append(corroboration)
    return qualifications, corroborations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover and verify exact FairCrypto MoonParty deployment."
    )
    parser.add_argument(
        "--rpc",
        action="append",
        dest="rpc_urls",
        help="Ethereum mainnet HTTPS JSON-RPC URL; repeat to add providers.",
    )
    args = parser.parse_args()

    artifact, pinned_documents, pinned = _pinned_documents()
    frontend_documents, frontend = _frontend_documents()

    source_gate_passed = (
        pinned["available_count"] == pinned["required_count"]
        and pinned["artifact_available"]
        and frontend["target_available_count"] >= 1
    )
    if not source_gate_passed:
        output = {
            "status": "FAIL",
            "contract_version": CONTRACT_VERSION,
            "reason": "bounded_source_gate_unavailable",
            "pinned_sources": pinned,
            "frontend_sources": frontend,
            "moonparty_deployment_verified": False,
            "xnt_credit_to_native_xnt_equivalence_verified": False,
            "xnt_issuance_verified": False,
            "xone_xnt_conversion_verified": False,
            "cross_chain_correlation_verified": False,
            "execution_authorized": False,
        }
        print(json.dumps(output, indent=2, sort_keys=True))
        return 2

    documents = pinned_documents + frontend_documents
    discovery = discover_moonparty_deployment_candidates(documents)
    qualifications, corroborations = _qualify_candidates(
        artifact,
        discovery["candidates"],
        args.rpc_urls or list(DEFAULT_RPC_URLS),
    )

    verified = [
        row
        for row in corroborations
        if row.get("moonparty_deployment_verified") is True
    ]
    conflicting_verified = {
        row["moonparty_address"]
        for row in verified
    }
    if len(conflicting_verified) > 1:
        status = "FAIL"
        reason = "multiple_distinct_verified_moonparty_deployments_in_same_gate"
    else:
        status = "PASS"
        reason = (
            "deployment_verified"
            if verified
            else (
                "no_exact_candidate_in_bounded_corpus"
                if discovery["deployment_candidate_count"] == 0
                else "candidates_not_multi_rpc_qualified"
            )
        )

    deployment = verified[0] if len(verified) == 1 else None
    output = {
        "status": status,
        "reason": reason,
        "contract_version": CONTRACT_VERSION,
        "source_gate_passed": True,
        "pinned_sources": pinned,
        "frontend_sources": frontend,
        "candidate_discovery": discovery,
        "candidate_qualifications": qualifications,
        "verified_deployment": deployment,
        "moonparty_deployment_verified": deployment is not None,
        "moonparty_deployment_chain_verified": deployment is not None,
        "moonparty_runtime_compatible": (
            deployment is not None
            and deployment["moonparty_runtime_compatible"] is True
        ),
        "moonparty_xone_binding_verified": (
            deployment is not None
            and deployment["moonparty_xone_binding_verified"] is True
        ),
        "zero_candidates_are_scoped_corpus_evidence_only": (
            discovery["deployment_candidate_count"] == 0
        ),
        "xnt_credit_to_native_xnt_equivalence_verified": False,
        "xnt_credit_transferability_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "october_6_unlock_applies_to_xone_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
