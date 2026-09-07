#!/usr/bin/env python3
"""Live bounded XONE -> XNT allocation-source provenance discovery."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
import time
from urllib.parse import quote, urlparse

import requests

from liquidity_scout.providers.xone_xnt import (
    extract_allocation_source_provenance,
    provenance_path_score,
    summarize_allocation_source_provenance,
)


USER_AGENT = "CMIS-XONE-XNT-Allocation-Source-Provenance/1.0 (+read-only; bounded)"
MAX_RESPONSE_BYTES = 2_000_000

REPOSITORY_TARGETS = (
    ("FairCrypto", "x1-app", "faircrypto_x1_app_primary", False),
    ("FairCrypto", "XONE", "faircrypto_xone_primary", False),
    (
        "x1-labs",
        "xenblocks-airdrop",
        "x1_labs_architecture_analogue",
        True,
    ),
)

OFFICIAL_TARGETS = (
    ("x1_official", "official_x1_web", "https://x1.xyz/"),
    ("x1_docs", "official_x1_documentation", "https://docs.x1.xyz/"),
    ("x1_next", "official_x1_documentation", "https://next.x1.xyz/"),
)

FORCED_ANALOGUE_PATHS = (
    "Anchor.toml",
    ".env.example",
    "target/idl/xenblocks_airdrop_tracker.json",
    "target/types/xenblocks_airdrop_tracker.ts",
    "programs/xenblocks-airdrop-tracker/src/lib.rs",
    "src/onchain/pda.ts",
    "src/onchain/types.ts",
    "docs/plans/2026-01-27-eth-only-pda-migration.md",
)


def _headers(accept: str = "*/*") -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": accept}
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
        raise RuntimeError(f"URL escaped allocation-source allowlist: {url}")
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


def _scan_releases(
    owner: str,
    name: str,
    source_role: str,
    *,
    observed_at: float,
    architecture_analogue: bool,
):
    result = {
        "repository": f"{owner}/{name}",
        "status": "AVAILABLE",
        "release_count": 0,
        "release_asset_count": 0,
        "candidate_count": 0,
        "errors": [],
    }
    candidates = []
    try:
        releases, source_url = _github_json(
            f"/repos/{owner}/{name}/releases?per_page=100"
        )
        if not isinstance(releases, list):
            raise RuntimeError("release response is not a list")
        result["release_count"] = len(releases)
    except Exception as exc:
        result["status"] = "UNAVAILABLE"
        result["errors"].append(
            {
                "stage": "releases",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        return result, candidates

    for release in releases:
        if not isinstance(release, dict):
            continue
        tag = str(release.get("tag_name") or release.get("name") or "")
        assets = release.get("assets")
        if not isinstance(assets, list):
            assets = []
        result["release_asset_count"] += len(assets)

        lines = [
            f"release {tag}",
            str(release.get("name") or ""),
            str(release.get("body") or ""),
        ]
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            lines.extend(
                [
                    f"release asset {asset.get('name') or ''}",
                    str(asset.get("browser_download_url") or ""),
                    str(asset.get("content_type") or ""),
                ]
            )

        text_value = "\n".join(lines)
        candidates.extend(
            extract_allocation_source_provenance(
                text_value,
                source_id=(
                    f"{owner.casefold()}_"
                    f"{name.casefold().replace('-', '_')}_release"
                ),
                source_role=source_role,
                url=str(release.get("html_url") or source_url),
                observed_at=observed_at,
                release_name=tag or None,
                content_type="application/vnd.github.release+json",
                release_asset=bool(assets),
                architecture_analogue=architecture_analogue,
                max_candidates=25,
            )
        )

    result["candidate_count"] = len(candidates)
    return result, candidates


def _scan_repository(
    owner: str,
    name: str,
    source_role: str,
    *,
    observed_at: float,
    architecture_analogue: bool,
    max_files: int,
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
        "candidate_count": 0,
        "errors": [],
    }
    candidates = []

    try:
        metadata, _ = _github_json(f"/repos/{owner}/{name}")
        default_branch = str(metadata.get("default_branch") or "main")
        branch_data, _ = _github_json(
            f"/repos/{owner}/{name}/branches/"
            f"{quote(default_branch, safe='')}"
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
            raise RuntimeError("recursive tree response is not a list")
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
        return result, candidates

    ranked = []
    available_paths = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") != "blob":
            continue
        path = str(entry.get("path") or "")
        available_paths.add(path)
        score = provenance_path_score(path)
        if score >= 5:
            ranked.append((score, path))

    if architecture_analogue:
        for path in FORCED_ANALOGUE_PATHS:
            if path in available_paths and path not in {p for _, p in ranked}:
                ranked.append((100, path))

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
        digest = sha256(text_value.encode("utf-8")).hexdigest()
        candidates.extend(
            extract_allocation_source_provenance(
                text_value,
                source_id=(
                    f"{owner.casefold()}_"
                    f"{name.casefold().replace('-', '_')}_file"
                ),
                source_role=source_role,
                url=raw_url,
                observed_at=observed_at,
                path=path,
                revision=revision,
                content_type=response.headers.get("Content-Type"),
                body_sha256=digest,
                architecture_analogue=architecture_analogue,
                max_candidates=25,
            )
        )

    result["candidate_count"] = len(candidates)
    return result, candidates


def _scan_official(observed_at: float):
    results = []
    candidates = []
    allowed_hosts = {
        "x1.xyz",
        "www.x1.xyz",
        "docs.x1.xyz",
        "next.x1.xyz",
    }
    for source_id, source_role, url in OFFICIAL_TARGETS:
        try:
            response = _get(url, allowed_hosts=allowed_hosts)
        except Exception as exc:
            results.append(
                {
                    "source_id": source_id,
                    "source_role": source_role,
                    "url": url,
                    "status": "UNAVAILABLE",
                    "candidate_count": 0,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue

        text_value = response.content.decode("utf-8", errors="replace")
        digest = sha256(text_value.encode("utf-8")).hexdigest()
        found = extract_allocation_source_provenance(
            text_value,
            source_id=source_id,
            source_role=source_role,
            url=url,
            observed_at=observed_at,
            content_type=response.headers.get("Content-Type"),
            body_sha256=digest,
            max_candidates=25,
        )
        candidates.extend(found)
        results.append(
            {
                "source_id": source_id,
                "source_role": source_role,
                "url": url,
                "status": "AVAILABLE",
                "body_bytes": len(response.content),
                "body_sha256": digest,
                "candidate_count": len(found),
            }
        )
    return results, candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Discover concrete public provenance for a possible XONE-derived "
            "XNT allocation source without repeating broad snapshot searches."
        )
    )
    parser.add_argument("--max-files-per-repo", type=int, default=30)
    parser.add_argument("--max-candidates", type=int, default=100)
    args = parser.parse_args()

    observed_at = time.time()
    repository_results = []
    release_results = []
    candidates = []

    for owner, name, source_role, architecture_analogue in REPOSITORY_TARGETS:
        repo_result, repo_candidates = _scan_repository(
            owner,
            name,
            source_role,
            observed_at=observed_at,
            architecture_analogue=architecture_analogue,
            max_files=args.max_files_per_repo,
        )
        repository_results.append(repo_result)
        candidates.extend(repo_candidates)

        release_result, release_candidates = _scan_releases(
            owner,
            name,
            source_role,
            observed_at=observed_at,
            architecture_analogue=architecture_analogue,
        )
        release_results.append(release_result)
        candidates.extend(release_candidates)

    official_results, official_candidates = _scan_official(observed_at)
    candidates.extend(official_candidates)

    summary = summarize_allocation_source_provenance(
        candidates,
        max_candidates=args.max_candidates,
    )

    repos_available = [
        row for row in repository_results if row["status"] == "AVAILABLE"
    ]
    files_available = sum(
        int(row["files_available"]) for row in repository_results
    )
    release_queries_available = [
        row for row in release_results if row["status"] == "AVAILABLE"
    ]
    official_available = [
        row for row in official_results if row["status"] == "AVAILABLE"
    ]

    source_gate = (
        len(repos_available) == len(REPOSITORY_TARGETS)
        and files_available >= 5
        and len(release_queries_available) == len(REPOSITORY_TARGETS)
        and len(official_available) >= 1
    )
    status = "PASS" if source_gate else "FAIL"

    output = {
        "status": status,
        "contract_version": "xone_xnt_allocation_source_provenance/v1",
        "observed_at": observed_at,
        "sources": {
            "repositories": repository_results,
            "repository_available_count": len(repos_available),
            "repository_files_available_count": files_available,
            "release_queries": release_results,
            "release_query_available_count": len(release_queries_available),
            "official_targets": official_results,
            "official_available_count": len(official_available),
        },
        "allocation_source_provenance": summary,
        "source_gate_passed": source_gate,
        "private_or_unpublished_allocation_source_absence_proven": False,
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
