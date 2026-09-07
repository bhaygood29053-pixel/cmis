#!/usr/bin/env python3
"""Bounded live discovery for the Ethereum XONE holder snapshot / registry."""

from __future__ import annotations

import argparse
from functools import partial
import json
import time
from urllib.parse import urlparse

import requests

from liquidity_scout.providers.ethereum import (
    DEFAULT_RPC_URLS,
    XONE_CONTRACT,
    corroborate_xone_registry_proofs,
    discover_official_snapshot_candidates,
    ethereum_rpc_request,
    extract_xone_snapshot_claims,
    fetch_and_verify_xone_registry,
    promote_official_snapshot,
)
from liquidity_scout.providers.xone_xnt import (
    OFFICIAL_REWARDS_URL,
    XoneXntConversionScraper,
    XoneXntScraperError,
)


CONTRACT_VERSION = "ethereum_xone_snapshot_registry/v1"
USER_AGENT = "CMIS-XONE-Snapshot-Registry/1.0 (+read-only; bounded-source-discovery)"
MAX_BYTES = 1_500_000

FAIRCRYPTO_XONE_COMMIT = "267bfeaabd69bf81f272cfd52aa5082333cd317a"
FAIRCRYPTO_X1_APP_COMMIT = "abf168fad119e91a8da0773625fd6115e8756cb4"
X1_LABS_AIRDROP_COMMIT = "fc20337c2e048d7a6ba0fc76d430c791f8072836"

RAW_TARGETS = (
    (
        "faircrypto_xone_readme",
        "faircrypto_source",
        f"https://raw.githubusercontent.com/FairCrypto/XONE/{FAIRCRYPTO_XONE_COMMIT}/README.md",
    ),
    (
        "faircrypto_xone_source",
        "faircrypto_source",
        f"https://raw.githubusercontent.com/FairCrypto/XONE/{FAIRCRYPTO_XONE_COMMIT}/contracts/XONE.sol",
    ),
    (
        "faircrypto_x1_app_env",
        "faircrypto_source",
        f"https://raw.githubusercontent.com/FairCrypto/x1-app/{FAIRCRYPTO_X1_APP_COMMIT}/.env.local.example",
    ),
    (
        "faircrypto_x1_app_runtime",
        "faircrypto_source",
        f"https://raw.githubusercontent.com/FairCrypto/x1-app/{FAIRCRYPTO_X1_APP_COMMIT}/app/libs/runtimeConfig.ts",
    ),
    (
        "faircrypto_x1_app_networks",
        "faircrypto_source",
        f"https://raw.githubusercontent.com/FairCrypto/x1-app/{FAIRCRYPTO_X1_APP_COMMIT}/config/networks.ts",
    ),
    (
        "faircrypto_x1_app_projects",
        "faircrypto_source",
        f"https://raw.githubusercontent.com/FairCrypto/x1-app/{FAIRCRYPTO_X1_APP_COMMIT}/config/projects.ts",
    ),
)

GITHUB_HISTORY_TARGETS = (
    (
        "faircrypto_xone_commit_history",
        "faircrypto_source",
        "FairCrypto",
        "XONE",
        FAIRCRYPTO_XONE_COMMIT,
    ),
    (
        "faircrypto_x1_app_commit_history",
        "faircrypto_source",
        "FairCrypto",
        "x1-app",
        FAIRCRYPTO_X1_APP_COMMIT,
    ),
)

OFFICIAL_TARGETS = (
    ("x1_official_home", "x1_official", "x1_official", "https://x1.xyz/"),
    ("x1_docs_home", "x1_docs", "x1_official", "https://docs.x1.xyz/"),
    (
        "x1_docs_rewards",
        "x1_docs",
        "x1_official",
        OFFICIAL_REWARDS_URL,
    ),
    ("x1_docs_next", "x1_docs", "x1_official", "https://next.x1.xyz/"),
)

ANALOGUE_TARGETS = (
    (
        "x1_labs_airdrop_readme",
        f"https://raw.githubusercontent.com/x1-labs/xenblocks-airdrop/{X1_LABS_AIRDROP_COMMIT}/README.md",
    ),
    (
        "x1_labs_airdrop_types",
        f"https://raw.githubusercontent.com/x1-labs/xenblocks-airdrop/{X1_LABS_AIRDROP_COMMIT}/src/airdrop/types.ts",
    ),
    (
        "x1_labs_airdrop_onchain_client",
        f"https://raw.githubusercontent.com/x1-labs/xenblocks-airdrop/{X1_LABS_AIRDROP_COMMIT}/src/onchain/client.ts",
    ),
)


def _fetch_text(url: str, allowed_hosts: set[str]) -> dict:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or host not in allowed_hosts:
        raise RuntimeError(f"URL escaped source allowlist: {url}")

    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/plain,application/json,text/html,*/*;q=0.1",
        },
        timeout=20,
        allow_redirects=False,
    )
    response.raise_for_status()
    if len(response.content) > MAX_BYTES:
        raise RuntimeError(f"response exceeds {MAX_BYTES} bytes: {url}")
    return {
        "url": url,
        "status_code": response.status_code,
        "content_type": response.headers.get("Content-Type"),
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "bytes": len(response.content),
        "text": response.content.decode("utf-8", errors="replace"),
    }


def _fetch_commit_history(
    *,
    owner: str,
    repository: str,
    until_sha: str,
    max_commits: int = 100,
) -> dict:
    url = (
        f"https://api.github.com/repos/{owner}/{repository}/commits"
        f"?sha={until_sha}&per_page={max_commits}"
    )
    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
        timeout=20,
        allow_redirects=False,
    )
    response.raise_for_status()
    if len(response.content) > MAX_BYTES:
        raise RuntimeError(f"commit-history response exceeds {MAX_BYTES} bytes")
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("GitHub commit-history response is not a list")

    rows = []
    text_rows = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        sha = str(item.get("sha") or "")
        commit = item.get("commit") or {}
        message = str(commit.get("message") or "")
        date = (
            ((commit.get("committer") or {}).get("date"))
            or ((commit.get("author") or {}).get("date"))
        )
        rows.append({"sha": sha, "date": date, "message": message})
        text_rows.append(f"{sha} {date or ''} {message}")
    return {
        "url": url,
        "count": len(rows),
        "rows": rows,
        "text": "\n".join(text_rows),
    }


def _snapshot_claims_from_generic_claims(
    generic_claims,
    *,
    source_id: str,
    source_role: str,
    observed_at: float,
):
    result = []
    seen = set()
    for generic in generic_claims:
        excerpt = str(generic.get("excerpt") or "").strip()
        url = str(generic.get("url") or "").strip()
        if not excerpt or not url:
            continue
        for claim in extract_xone_snapshot_claims(
            excerpt,
            source_id=source_id,
            source_role=source_role,
            url=url,
            observed_at=observed_at,
            max_claims=25,
        ):
            claim_id = claim["claim_id"]
            if claim_id in seen:
                continue
            seen.add(claim_id)
            result.append(claim)
    return result


def _collect_sources(*, x1report_max_urls: int):
    observed_at = time.time()
    claims = []
    source_results = []

    # Exact FairCrypto repository artifacts.
    for source_id, source_role, url in RAW_TARGETS:
        try:
            row = _fetch_text(url, {"raw.githubusercontent.com"})
        except Exception as exc:
            source_results.append({
                "source_id": source_id,
                "source_role": source_role,
                "url": url,
                "status": "UNAVAILABLE",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "snapshot_claim_count": 0,
            })
            continue
        extracted = extract_xone_snapshot_claims(
            row["text"],
            source_id=source_id,
            source_role=source_role,
            url=url,
            observed_at=observed_at,
        )
        claims.extend(extracted)
        source_results.append({
            "source_id": source_id,
            "source_role": source_role,
            "url": url,
            "status": "AVAILABLE",
            "bytes": row["bytes"],
            "snapshot_claim_count": len(extracted),
        })

    # Bounded commit-message history for the two FairCrypto repos.
    for source_id, source_role, owner, name, sha in GITHUB_HISTORY_TARGETS:
        history_url = f"https://github.com/{owner}/{name}/commits/{sha}"
        try:
            history = _fetch_commit_history(
                owner=owner,
                repository=name,
                until_sha=sha,
            )
        except Exception as exc:
            source_results.append({
                "source_id": source_id,
                "source_role": source_role,
                "url": history_url,
                "status": "UNAVAILABLE",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "snapshot_claim_count": 0,
            })
            continue
        extracted = extract_xone_snapshot_claims(
            history["text"],
            source_id=source_id,
            source_role=source_role,
            url=history_url,
            observed_at=observed_at,
        )
        claims.extend(extracted)
        source_results.append({
            "source_id": source_id,
            "source_role": source_role,
            "url": history_url,
            "status": "AVAILABLE",
            "commit_count": history["count"],
            "snapshot_claim_count": len(extracted),
        })

    # Official X1 public corpus, reusing the accepted bounded scraper.
    scraper = XoneXntConversionScraper(
        observed_at_fn=lambda: observed_at,
        max_bytes=1_000_000,
    )
    for source_id, scraper_source_id, source_role, url in OFFICIAL_TARGETS:
        try:
            result = scraper.scrape_url(
                scraper_source_id,
                url,
                max_claims=100,
            )
        except XoneXntScraperError as exc:
            source_results.append({
                "source_id": source_id,
                "source_role": source_role,
                "url": url,
                "status": "UNAVAILABLE",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "snapshot_claim_count": 0,
            })
            continue
        extracted = _snapshot_claims_from_generic_claims(
            result["claims"],
            source_id=source_id,
            source_role=source_role,
            observed_at=observed_at,
        )
        claims.extend(extracted)
        source_results.append({
            "source_id": source_id,
            "source_role": source_role,
            "url": result["retrieval"]["final_url"],
            "status": "AVAILABLE",
            "body_sha256": result["retrieval"]["body_sha256"],
            "bytes": result["retrieval"]["body_bytes"],
            "generic_xone_xnt_claim_count": result["candidate_claim_count"],
            "snapshot_claim_count": len(extracted),
        })

    # X1 Report is explicitly secondary evidence.
    x1report = {
        "available": False,
        "pages_attempted": 0,
        "pages_available": 0,
        "snapshot_claim_count": 0,
        "error": None,
    }
    try:
        result = scraper.scrape_sitemap_candidates(
            "x1report",
            max_urls=x1report_max_urls,
            max_claims_per_url=50,
        )
        extracted = _snapshot_claims_from_generic_claims(
            result["claims"],
            source_id="x1report_bounded_sitemap",
            source_role="x1_report",
            observed_at=observed_at,
        )
        claims.extend(extracted)
        x1report.update({
            "available": True,
            "pages_attempted": result["pages_attempted"],
            "pages_available": sum(
                1 for row in result["results"]
                if row.get("status") == "AVAILABLE"
            ),
            "snapshot_claim_count": len(extracted),
        })
    except XoneXntScraperError as exc:
        x1report["error"] = {
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    # Deduplicate exact snapshot claims.
    deduped = []
    seen = set()
    for claim in claims:
        claim_id = str(claim.get("claim_id") or "")
        if not claim_id or claim_id in seen:
            continue
        seen.add(claim_id)
        deduped.append(claim)

    return {
        "observed_at": observed_at,
        "claims": deduped,
        "source_results": source_results,
        "x1report": x1report,
    }


def _collect_architecture_analogue():
    retrieval = []
    combined = []
    for source_id, url in ANALOGUE_TARGETS:
        try:
            row = _fetch_text(url, {"raw.githubusercontent.com"})
        except Exception as exc:
            retrieval.append({
                "source_id": source_id,
                "url": url,
                "status": "UNAVAILABLE",
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            continue
        retrieval.append({
            "source_id": source_id,
            "url": url,
            "status": "AVAILABLE",
            "bytes": row["bytes"],
        })
        combined.append(row["text"])

    text = "\n".join(combined)
    lowered = text.casefold()
    return {
        "repository": "x1-labs/xenblocks-airdrop",
        "commit": X1_LABS_AIRDROP_COMMIT,
        "retrieval": retrieval,
        "available_count": sum(
            1 for row in retrieval if row["status"] == "AVAILABLE"
        ),
        "xone_reference_present": "xone" in lowered,
        "ethereum_address_keying_present": (
            "ethaddress" in lowered or "eth_address" in lowered
        ),
        "native_xnt_airdrop_present": (
            "xnt" in lowered and "native" in lowered and "airdrop" in lowered
        ),
        "architectural_analogue_only": True,
        "xone_snapshot_or_registry_binding_verified": False,
    }


def _maybe_reconstruct(discovery, *, rpc_urls, log_chunk_blocks, sample_size):
    blocks = discovery["authoritative_exact_block_candidates"]
    if discovery["authoritative_block_conflict"] or len(blocks) != 1:
        return {
            "attempted": False,
            "reason": (
                "authoritative_block_conflict"
                if discovery["authoritative_block_conflict"]
                else "no_single_authoritative_exact_block"
            ),
            "registry_proofs": [],
            "registry_failures": [],
            "corroboration": None,
            "official_snapshot": None,
        }

    block = blocks[0]
    eligible = [
        row for row in discovery["candidates"]
        if row["authoritative_source"]
        and row["snapshot_block_candidates"] == [block]
        and (
            row["exact_xone_contract_mentioned"]
            or str(row.get("source_id") or "").casefold().startswith(
                "faircrypto_xone"
            )
        )
    ]
    if not eligible:
        return {
            "attempted": False,
            "reason": "authoritative_block_has_no_exact_xone_identity_binding",
            "registry_proofs": [],
            "registry_failures": [],
            "corroboration": None,
            "official_snapshot": None,
        }

    proofs = []
    failures = []
    for url in rpc_urls:
        rpc = partial(ethereum_rpc_request, rpc_url=url)
        try:
            proof = fetch_and_verify_xone_registry(
                rpc_call=rpc,
                snapshot_block=block,
                source_url=url,
                log_chunk_blocks=log_chunk_blocks,
                balance_sample_size=sample_size,
            )
        except Exception as exc:
            failures.append({
                "rpc_url": url,
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
        official = promote_official_snapshot(
            source_candidate=eligible[0],
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
            "Discover authoritative Ethereum XONE snapshot/registry evidence and "
            "conditionally reconstruct the holder ledger when an exact block is found."
        )
    )
    parser.add_argument("--x1report-max-urls", type=int, default=30)
    parser.add_argument("--rpc", action="append", dest="rpc_urls")
    parser.add_argument("--log-chunk-blocks", type=int, default=50_000)
    parser.add_argument("--balance-sample-size", type=int, default=25)
    args = parser.parse_args()

    corpus = _collect_sources(x1report_max_urls=args.x1report_max_urls)
    analogue = _collect_architecture_analogue()
    discovery = discover_official_snapshot_candidates(corpus["claims"])
    reconstruction = _maybe_reconstruct(
        discovery,
        rpc_urls=args.rpc_urls or list(DEFAULT_RPC_URLS),
        log_chunk_blocks=args.log_chunk_blocks,
        sample_size=args.balance_sample_size,
    )

    faircrypto_available = sum(
        1
        for row in corpus["source_results"]
        if row["source_role"] == "faircrypto_source"
        and row["status"] == "AVAILABLE"
    )
    official_x1_available = sum(
        1
        for row in corpus["source_results"]
        if row["source_role"] == "x1_official"
        and row["status"] == "AVAILABLE"
    )
    source_gate = (
        faircrypto_available >= 4
        and official_x1_available >= 2
        and corpus["x1report"]["available"]
        and corpus["x1report"]["pages_available"] > 0
        and analogue["available_count"] >= 2
    )

    reconstruction_gate = True
    if reconstruction["attempted"]:
        reconstruction_gate = reconstruction["official_snapshot"] is not None

    status = "PASS" if source_gate and reconstruction_gate else "FAIL"
    official = reconstruction["official_snapshot"]
    output = {
        "status": status,
        "contract_version": CONTRACT_VERSION,
        "source_gate_passed": source_gate,
        "source_corpus": {
            "observed_at": corpus["observed_at"],
            "results": corpus["source_results"],
            "faircrypto_available_count": faircrypto_available,
            "official_x1_available_count": official_x1_available,
            "x1report": corpus["x1report"],
        },
        "snapshot_claim_count": len(corpus["claims"]),
        "snapshot_claims": corpus["claims"],
        "snapshot_discovery": discovery,
        "architecture_analogue": analogue,
        "reconstruction": reconstruction,
        "official_xone_snapshot_verified": (
            official is not None
            and official["official_xone_snapshot_verified"] is True
        ),
        "official_registry_artifact_verified": False,
        "xone_snapshot_eligibility_verified": False,
        "xone_snapshot_xnt_allocation_binding_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "october_6_unlock_applies_to_xone_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "zero_official_candidates_are_scoped_corpus_evidence_only": (
            discovery["official_snapshot_candidate_count"] == 0
        ),
        "private_or_unpublished_snapshot_absence_proven": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
