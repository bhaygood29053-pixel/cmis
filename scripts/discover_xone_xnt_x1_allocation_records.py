#!/usr/bin/env python3
"""Live bounded X1-side XONE->XNT allocation-record discovery."""

from __future__ import annotations

import argparse
import json
import os
import time
from urllib.parse import quote, urlparse

import requests

from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, rpc_request
from liquidity_scout.providers.xone_xnt import (
    XoneXntConversionScraper,
    XoneXntScraperError,
    extract_x1_allocation_records,
    qualify_x1_allocation_candidate,
    summarize_x1_allocation_records,
)


USER_AGENT = "CMIS-XONE-XNT-X1-Allocation-Record/1.0 (+read-only; bounded)"
MAX_RESPONSE_BYTES = 2_000_000

REPOSITORY_TARGETS = (
    ("FairCrypto", "x1-app", "faircrypto_x1_app_primary"),
    ("FairCrypto", "XONE", "faircrypto_xone_primary"),
    ("x1-labs", "xenblocks-airdrop", "x1_labs_source"),
)

OFFICIAL_TARGETS = (
    ("x1_official", "official_x1_web", "https://x1.xyz/"),
    ("x1_docs", "official_x1_documentation", "https://docs.x1.xyz/"),
    ("x1_docs", "official_x1_documentation", "https://next.x1.xyz/"),
)

_TEXT_EXTENSIONS = (
    ".json",
    ".jsonl",
    ".ndjson",
    ".csv",
    ".tsv",
    ".txt",
    ".md",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".py",
    ".rs",
    ".yml",
    ".yaml",
)

_PATH_TERMS = {
    "xone": 12,
    "xnt": 10,
    "allocation": 12,
    "airdrop": 10,
    "claim": 8,
    "registry": 8,
    "holder": 7,
    "snapshot": 7,
    "vest": 6,
    "unlock": 6,
    "credit": 5,
    "reward": 4,
    "wallet": 4,
    "address": 3,
    "distribution": 6,
}


def _headers(accept: str = "*/*") -> dict[str, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    return headers


def _get(
    url: str,
    *,
    allowed_hosts: set[str],
    accept: str = "*/*",
) -> requests.Response:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or host not in allowed_hosts:
        raise RuntimeError(f"URL escaped allocation-record allowlist: {url}")
    response = requests.get(
        url,
        headers=_headers(accept),
        timeout=25,
        allow_redirects=False,
    )
    response.raise_for_status()
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise RuntimeError(
            f"response exceeds {MAX_RESPONSE_BYTES} bytes: {url}"
        )
    return response


def _github_json(path: str):
    url = f"https://api.github.com{path}"
    response = _get(
        url,
        allowed_hosts={"api.github.com"},
        accept="application/vnd.github+json",
    )
    return response.json(), url


def _path_score(path: str) -> int:
    lowered = path.casefold()
    if not lowered.endswith(_TEXT_EXTENSIONS):
        return -1
    score = 0
    for term, weight in _PATH_TERMS.items():
        if term in lowered:
            score += weight
    if "/data/" in lowered or lowered.startswith("data/"):
        score += 3
    if "/public/" in lowered or lowered.startswith("public/"):
        score += 2
    if lowered.endswith((".json", ".jsonl", ".ndjson", ".csv", ".tsv")):
        score += 3
    return score


def _scan_repository(
    owner: str,
    name: str,
    source_role: str,
    *,
    observed_at: float,
    max_files: int,
    max_records_per_file: int,
):
    repository = f"{owner}/{name}"
    result = {
        "repository": repository,
        "repository_url": f"https://github.com/{repository}",
        "status": "AVAILABLE",
        "revision": None,
        "tree_entries": 0,
        "ranked_path_count": 0,
        "files_attempted": 0,
        "files_available": 0,
        "allocation_record_count": 0,
        "errors": [],
    }
    records = []

    try:
        metadata, _ = _github_json(f"/repos/{owner}/{name}")
        branch = str(metadata.get("default_branch") or "main")
        branch_data, _ = _github_json(
            f"/repos/{owner}/{name}/branches/{quote(branch, safe='')}"
        )
        revision = str(((branch_data.get("commit") or {}).get("sha")) or "")
        if not revision:
            raise RuntimeError("repository branch did not expose revision")
        result["revision"] = revision
        tree, _ = _github_json(
            f"/repos/{owner}/{name}/git/trees/{revision}?recursive=1"
        )
        entries = tree.get("tree")
        if not isinstance(entries, list):
            raise RuntimeError("recursive tree response did not contain a list")
        result["tree_entries"] = len(entries)
    except Exception as exc:
        result["status"] = "UNAVAILABLE"
        result["errors"].append(
            {
                "stage": "metadata_or_tree",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        return result, records

    ranked = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") != "blob":
            continue
        path = str(entry.get("path") or "")
        score = _path_score(path)
        if score < 8:
            continue
        ranked.append((score, path))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    result["ranked_path_count"] = len(ranked)

    for _score, path in ranked[:max_files]:
        result["files_attempted"] += 1
        raw_url = (
            f"https://raw.githubusercontent.com/{owner}/{name}/"
            f"{revision}/{path}"
        )
        try:
            response = _get(
                raw_url,
                allowed_hosts={"raw.githubusercontent.com"},
            )
        except Exception as exc:
            result["errors"].append(
                {
                    "stage": "file",
                    "path": path,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue

        result["files_available"] += 1
        text_value = response.content.decode("utf-8", errors="replace")
        file_records = extract_x1_allocation_records(
            text_value,
            source_id=f"{owner.casefold()}_{name.casefold().replace('-', '_')}_file",
            source_role=source_role,
            url=raw_url,
            observed_at=observed_at,
            path=path,
            revision=revision,
            max_records=max_records_per_file,
        )
        records.extend(file_records)

    result["allocation_record_count"] = len(records)
    return result, records


def _scan_official(
    *,
    observed_at: float,
    max_records_per_document: int,
):
    scraper = XoneXntConversionScraper(
        observed_at_fn=lambda: observed_at,
        max_bytes=1_000_000,
    )
    results = []
    records = []
    for source_id, source_role, url in OFFICIAL_TARGETS:
        try:
            scraped = scraper.scrape_url(
                source_id,
                url,
                max_claims=100,
            )
        except XoneXntScraperError as exc:
            results.append(
                {
                    "source_id": source_id,
                    "source_role": source_role,
                    "url": url,
                    "status": "UNAVAILABLE",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "candidate_claim_count": 0,
                    "allocation_record_count": 0,
                }
            )
            continue

        text_value = "\n".join(
            str(claim.get("excerpt") or "")
            for claim in scraped.get("claims", [])
            if claim.get("excerpt")
        )
        extracted = extract_x1_allocation_records(
            text_value,
            source_id=source_id,
            source_role=source_role,
            url=scraped["retrieval"]["final_url"],
            observed_at=observed_at,
            max_records=max_records_per_document,
        )
        records.extend(extracted)
        results.append(
            {
                "source_id": source_id,
                "source_role": source_role,
                "url": scraped["retrieval"]["final_url"],
                "status": "AVAILABLE",
                "body_sha256": scraped["retrieval"]["body_sha256"],
                "body_bytes": scraped["retrieval"]["body_bytes"],
                "candidate_claim_count": scraped["candidate_claim_count"],
                "allocation_record_count": len(extracted),
            }
        )
    return results, records


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Discover bounded public X1-side records that bind Ethereum "
            "addresses to X1 pubkeys in XONE/XNT allocation context."
        )
    )
    parser.add_argument("--rpc", default=DEFAULT_X1_RPC_URL)
    parser.add_argument("--max-files-per-repo", type=int, default=30)
    parser.add_argument("--max-records-per-file", type=int, default=50)
    parser.add_argument("--max-candidates", type=int, default=50)
    parser.add_argument("--max-qualifications", type=int, default=10)
    args = parser.parse_args()

    observed_at = time.time()
    repository_results = []
    records = []

    for owner, name, source_role in REPOSITORY_TARGETS:
        result, found = _scan_repository(
            owner,
            name,
            source_role,
            observed_at=observed_at,
            max_files=args.max_files_per_repo,
            max_records_per_file=args.max_records_per_file,
        )
        repository_results.append(result)
        records.extend(found)

    official_results, official_records = _scan_official(
        observed_at=observed_at,
        max_records_per_document=args.max_records_per_file,
    )
    records.extend(official_records)

    discovery = summarize_x1_allocation_records(
        records,
        max_candidates=args.max_candidates,
    )

    qualifications = []
    qualification_errors = []
    for candidate in discovery["candidates"][: args.max_qualifications]:
        try:
            proof = qualify_x1_allocation_candidate(
                candidate,
                rpc_call=lambda method, params: rpc_request(
                    method,
                    params,
                    rpc_url=args.rpc,
                ),
                source_url=args.rpc,
            )
        except Exception as exc:
            qualification_errors.append(
                {
                    "ethereum_address": candidate["ethereum_address"],
                    "x1_pubkey": candidate["x1_pubkey"],
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue
        qualifications.append(proof)

    repo_available = [
        row for row in repository_results if row["status"] == "AVAILABLE"
    ]
    repo_files_available = sum(
        int(row["files_available"]) for row in repository_results
    )
    official_available = [
        row for row in official_results if row["status"] == "AVAILABLE"
    ]

    source_gate = (
        len(repo_available) >= 2
        and repo_files_available >= 1
        and len(official_available) >= 1
    )
    qualification_gate = (
        not qualification_errors
        and len(qualifications)
        == min(
            discovery["candidate_count"],
            args.max_qualifications,
        )
    )
    status = "PASS" if source_gate and qualification_gate else "FAIL"

    output = {
        "status": status,
        "contract_version": "xone_xnt_x1_allocation_record_discovery/v1",
        "observed_at": observed_at,
        "sources": {
            "repositories": repository_results,
            "repository_available_count": len(repo_available),
            "repository_files_available_count": repo_files_available,
            "official_targets": official_results,
            "official_available_count": len(official_available),
        },
        "record_count": len(records),
        "allocation_record_discovery": discovery,
        "candidate_qualifications": qualifications,
        "qualification_errors": qualification_errors,
        "source_gate_passed": source_gate,
        "candidate_qualification_gate_passed": qualification_gate,
        "private_or_unpublished_allocation_registry_absence_proven": False,
        "official_xone_snapshot_verified": False,
        "official_registry_artifact_verified": False,
        "xone_snapshot_eligibility_verified": False,
        "xone_snapshot_xnt_allocation_binding_verified": False,
        "allocation_semantics_verified": False,
        "claim_state_verified": False,
        "vesting_or_unlock_state_verified": False,
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
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
