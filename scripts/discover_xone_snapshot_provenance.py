#!/usr/bin/env python3
"""Live bounded provenance expansion for the missing Ethereum XONE snapshot."""

from __future__ import annotations

import argparse
from functools import partial
import json
import time
from urllib.parse import quote, urlparse

import requests

from liquidity_scout.providers.ethereum import (
    DEFAULT_RPC_URLS,
    corroborate_xone_registry_proofs,
    ethereum_rpc_request,
    fetch_and_verify_xone_registry,
    promote_official_snapshot,
)
from liquidity_scout.providers.xone_xnt import (
    XONE_SNAPSHOT_PROVENANCE_CONTRACT_VERSION,
    XoneXntConversionScraper,
    XoneXntScraperError,
    discover_repository_path_candidates,
    extract_provenance_candidates,
    rank_provenance_candidates,
)


USER_AGENT = "CMIS-XONE-Snapshot-Provenance/1.0 (+read-only; bounded)"
MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_MAX_COMMITS = 100
DEFAULT_MAX_PATHS = 100
DEFAULT_MAX_FILES = 20

REPOSITORY_TARGETS = (
    ("FairCrypto", "XONE", "faircrypto_xone_primary"),
    ("FairCrypto", "x1-app", "faircrypto_x1_app_primary"),
    ("x1-labs", "xenblocks-airdrop", "x1_labs_source"),
)

OFFICIAL_X1_TARGETS = (
    ("x1_official_home", "x1_official", "https://x1.xyz/"),
    ("x1_docs_home", "x1_docs", "https://docs.x1.xyz/"),
    (
        "x1_docs_rewards",
        "x1_docs",
        "https://docs.x1.xyz/validating/validator-rewards/incentivized-testnet-rewards",
    ),
    ("x1_docs_next", "x1_docs", "https://next.x1.xyz/"),
)

INDEXED_HISTORY_TARGETS = (
    (
        "xspacegpt_jack_index",
        "https://www.twitterspacegpt.com/hosts/mrJackLevin",
    ),
    (
        "twstalker_jack_index",
        "https://mobile.twstalker.com/mrJackLevin",
    ),
)

ALLOWED_RAW_HOSTS = {"raw.githubusercontent.com"}
ALLOWED_INDEX_HOSTS = {
    "www.twitterspacegpt.com",
    "twitterspacegpt.com",
    "mobile.twstalker.com",
}


def _get(url: str, *, allowed_hosts: set[str], accept: str = "*/*") -> requests.Response:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or host not in allowed_hosts:
        raise RuntimeError(f"URL escaped provenance allowlist: {url}")
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
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


def _extract_document(
    *,
    text: str,
    source_id: str,
    source_role: str,
    url: str,
    observed_at: float,
    path: str | None = None,
    revision: str | None = None,
):
    return extract_provenance_candidates(
        text,
        source_id=source_id,
        source_role=source_role,
        url=url,
        observed_at=observed_at,
        path=path,
        revision=revision,
        max_candidates=100,
    )


def _scan_repository(
    owner: str,
    name: str,
    source_role: str,
    *,
    observed_at: float,
    max_commits: int,
    max_paths: int,
    max_files: int,
):
    repository_url = f"https://github.com/{owner}/{name}"
    source_prefix = f"{owner.casefold()}_{name.casefold().replace('-', '_')}"
    result = {
        "repository": f"{owner}/{name}",
        "repository_url": repository_url,
        "status": "AVAILABLE",
        "default_branch": None,
        "revision": None,
        "commit_rows": 0,
        "tag_rows": 0,
        "release_rows": 0,
        "tree_entries": 0,
        "path_candidate_count": 0,
        "content_files_attempted": 0,
        "content_files_available": 0,
        "candidate_count": 0,
        "errors": [],
    }
    candidates = []

    try:
        metadata, _ = _github_json(f"/repos/{owner}/{name}")
        default_branch = str(metadata.get("default_branch") or "main")
        result["default_branch"] = default_branch
        branch_data, _ = _github_json(
            f"/repos/{owner}/{name}/branches/{quote(default_branch, safe='')}"
        )
        revision = str(((branch_data.get("commit") or {}).get("sha")) or "")
        if not revision:
            raise RuntimeError("repository branch did not expose a revision SHA")
        result["revision"] = revision
    except Exception as exc:
        result["status"] = "UNAVAILABLE"
        result["errors"].append({
            "stage": "metadata",
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        return result, candidates

    # Commit-message history is provenance metadata, not file-content proof.
    try:
        commits, commits_url = _github_json(
            f"/repos/{owner}/{name}/commits?sha={quote(default_branch, safe='')}"
            f"&per_page={max_commits}"
        )
        if not isinstance(commits, list):
            raise RuntimeError("commit history is not a list")
        result["commit_rows"] = len(commits)
        history_lines = []
        for item in commits:
            commit = item.get("commit") or {}
            message = str(commit.get("message") or "")
            date = (
                ((commit.get("committer") or {}).get("date"))
                or ((commit.get("author") or {}).get("date"))
                or ""
            )
            history_lines.append(
                f"{item.get('sha') or ''} {date} {message}"
            )
        candidates.extend(
            _extract_document(
                text="\n".join(history_lines),
                source_id=f"{source_prefix}_commit_history",
                source_role=source_role,
                url=commits_url,
                observed_at=observed_at,
                revision=revision,
            )
        )
    except Exception as exc:
        result["errors"].append({
            "stage": "commits",
            "error_type": type(exc).__name__,
            "error": str(exc),
        })

    # Tags and releases can expose old exports or snapshot references.
    for stage, endpoint in (
        ("tags", f"/repos/{owner}/{name}/tags?per_page=100"),
        ("releases", f"/repos/{owner}/{name}/releases?per_page=100"),
    ):
        try:
            rows, source_url = _github_json(endpoint)
            if not isinstance(rows, list):
                raise RuntimeError(f"{stage} response is not a list")
            result[f"{stage[:-1] if stage.endswith('s') else stage}_rows"] = len(rows)
            texts = []
            for row in rows:
                if stage == "tags":
                    texts.append(
                        f"tag {row.get('name') or ''} "
                        f"{((row.get('commit') or {}).get('sha')) or ''}"
                    )
                else:
                    texts.append(
                        " ".join(
                            [
                                f"release {row.get('name') or ''}",
                                f"tag {row.get('tag_name') or ''}",
                                str(row.get("published_at") or ""),
                                str(row.get("body") or ""),
                            ]
                        )
                    )
            candidates.extend(
                _extract_document(
                    text="\n".join(texts),
                    source_id=f"{source_prefix}_{stage}",
                    source_role=source_role,
                    url=source_url,
                    observed_at=observed_at,
                    revision=revision,
                )
            )
        except Exception as exc:
            result["errors"].append({
                "stage": stage,
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

    # Recursive tree discovers filenames that may identify registry exports.
    path_candidates = []
    try:
        tree, tree_url = _github_json(
            f"/repos/{owner}/{name}/git/trees/{revision}?recursive=1"
        )
        entries = tree.get("tree")
        if not isinstance(entries, list):
            raise RuntimeError("recursive tree did not return entries")
        result["tree_entries"] = len(entries)
        path_candidates = discover_repository_path_candidates(
            entries,
            source_id=f"{source_prefix}_tree",
            source_role=source_role,
            repository_url=repository_url,
            revision=revision,
            observed_at=observed_at,
            max_candidates=max_paths,
        )
        result["path_candidate_count"] = len(path_candidates)
        candidates.extend(path_candidates)
    except Exception as exc:
        result["errors"].append({
            "stage": "tree",
            "error_type": type(exc).__name__,
            "error": str(exc),
        })

    # Fetch only top bounded path leads. Path-only evidence is never promoted.
    file_paths = []
    for candidate in path_candidates:
        path = str(candidate.get("path") or "")
        if path and path not in file_paths:
            file_paths.append(path)
        if len(file_paths) >= max_files:
            break

    for path in file_paths:
        result["content_files_attempted"] += 1
        raw_url = (
            f"https://raw.githubusercontent.com/{owner}/{name}/"
            f"{revision}/{path}"
        )
        try:
            response = _get(raw_url, allowed_hosts=ALLOWED_RAW_HOSTS)
        except Exception as exc:
            result["errors"].append({
                "stage": "content",
                "path": path,
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            continue
        result["content_files_available"] += 1
        text_value = response.content.decode("utf-8", errors="replace")
        candidates.extend(
            _extract_document(
                text=text_value,
                source_id=f"{source_prefix}_file",
                source_role=source_role,
                url=raw_url,
                path=path,
                revision=revision,
                observed_at=observed_at,
            )
        )

    result["candidate_count"] = len(candidates)
    return result, candidates


def _scan_official_x1(observed_at: float):
    scraper = XoneXntConversionScraper(
        observed_at_fn=lambda: observed_at,
        max_bytes=1_000_000,
    )
    results = []
    candidates = []
    for source_id, scraper_source_id, url in OFFICIAL_X1_TARGETS:
        try:
            scraped = scraper.scrape_url(
                scraper_source_id,
                url,
                max_claims=100,
            )
        except XoneXntScraperError as exc:
            results.append({
                "source_id": source_id,
                "url": url,
                "status": "UNAVAILABLE",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "candidate_count": 0,
            })
            continue
        text_rows = [
            str(claim.get("excerpt") or "")
            for claim in scraped["claims"]
            if claim.get("excerpt")
        ]
        extracted = _extract_document(
            text="\n".join(text_rows),
            source_id=source_id,
            source_role="x1_official",
            url=scraped["retrieval"]["final_url"],
            observed_at=observed_at,
        )
        candidates.extend(extracted)
        results.append({
            "source_id": source_id,
            "url": scraped["retrieval"]["final_url"],
            "status": "AVAILABLE",
            "generic_xone_xnt_claim_count": scraped["candidate_claim_count"],
            "candidate_count": len(extracted),
        })
    return results, candidates


def _scan_x1report(observed_at: float, max_urls: int):
    scraper = XoneXntConversionScraper(
        observed_at_fn=lambda: observed_at,
        max_bytes=1_000_000,
    )
    try:
        scraped = scraper.scrape_sitemap_candidates(
            "x1report",
            max_urls=max_urls,
            max_claims_per_url=75,
        )
    except XoneXntScraperError as exc:
        return {
            "status": "UNAVAILABLE",
            "pages_attempted": 0,
            "pages_available": 0,
            "generic_claim_count": 0,
            "candidate_count": 0,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }, []

    candidates = []
    for row in scraped["results"]:
        if row.get("status") != "AVAILABLE":
            continue
        text_value = "\n".join(
            str(claim.get("excerpt") or "")
            for claim in row.get("claims", [])
            if claim.get("excerpt")
        )
        candidates.extend(
            _extract_document(
                text=text_value,
                source_id="x1report_bounded_history",
                source_role="x1_report",
                url=str(row.get("url") or ""),
                observed_at=observed_at,
            )
        )

    return {
        "status": "AVAILABLE",
        "pages_attempted": scraped["pages_attempted"],
        "pages_available": sum(
            1 for row in scraped["results"]
            if row.get("status") == "AVAILABLE"
        ),
        "generic_claim_count": scraped["candidate_claim_count"],
        "candidate_count": len(candidates),
        "error": None,
    }, candidates


def _scan_indexed_history(observed_at: float):
    results = []
    candidates = []
    for source_id, url in INDEXED_HISTORY_TARGETS:
        try:
            response = _get(
                url,
                allowed_hosts=ALLOWED_INDEX_HOSTS,
                accept="text/html,*/*;q=0.1",
            )
        except Exception as exc:
            results.append({
                "source_id": source_id,
                "url": url,
                "status": "UNAVAILABLE",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "candidate_count": 0,
            })
            continue
        text_value = response.text
        extracted = _extract_document(
            text=text_value,
            source_id=source_id,
            source_role="indexed_mirror",
            url=url,
            observed_at=observed_at,
        )
        candidates.extend(extracted)
        results.append({
            "source_id": source_id,
            "url": url,
            "status": "AVAILABLE",
            "bytes": len(response.content),
            "candidate_count": len(extracted),
            "contains_xone": "xone" in text_value.casefold(),
            "contains_snapshot": "snapshot" in text_value.casefold(),
        })
    return results, candidates


def _maybe_reconstruct(provenance, *, rpc_urls, chunk_blocks, sample_size):
    blocks = provenance["authoritative_exact_snapshot_block_candidates"]
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
        and row.get("snapshot_block_candidates") == [block]
    ]
    if not eligible:
        return {
            "attempted": False,
            "reason": "no_authoritative_candidate_for_exact_block",
            "snapshot_block": block,
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
                log_chunk_blocks=chunk_blocks,
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
        source = eligible[0]
        snapshot_source = {
            "claim_id": source["candidate_id"],
            "source_id": source["source_id"],
            "source_role": source["source_role"],
            "url": source["url"],
            "authoritative_source": True,
            "exact_xone_contract_mentioned":
                source["exact_xone_contract_mentioned"],
            "snapshot_block_candidates": [block],
        }
        # Exact FairCrypto/XONE lineage is an accepted identity binding.
        if source["source_role"] == "faircrypto_xone_primary":
            snapshot_source["source_id"] = "faircrypto_xone_provenance"
        official = promote_official_snapshot(
            source_candidate=snapshot_source,
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
            "Expand public provenance around the missing Ethereum XONE holder "
            "snapshot and conditionally hand an authoritative exact block to "
            "the accepted direct registry reconstruction gate."
        )
    )
    parser.add_argument("--max-commits", type=int, default=DEFAULT_MAX_COMMITS)
    parser.add_argument("--max-paths", type=int, default=DEFAULT_MAX_PATHS)
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--x1report-max-urls", type=int, default=50)
    parser.add_argument("--rpc", action="append", dest="rpc_urls")
    parser.add_argument("--log-chunk-blocks", type=int, default=50_000)
    parser.add_argument("--balance-sample-size", type=int, default=25)
    args = parser.parse_args()

    observed_at = time.time()
    all_candidates = []
    repository_results = []

    for owner, name, role in REPOSITORY_TARGETS:
        result, candidates = _scan_repository(
            owner,
            name,
            role,
            observed_at=observed_at,
            max_commits=args.max_commits,
            max_paths=args.max_paths,
            max_files=args.max_files,
        )
        repository_results.append(result)
        all_candidates.extend(candidates)

    official_results, official_candidates = _scan_official_x1(observed_at)
    all_candidates.extend(official_candidates)

    x1report_result, x1report_candidates = _scan_x1report(
        observed_at,
        args.x1report_max_urls,
    )
    all_candidates.extend(x1report_candidates)

    indexed_results, indexed_candidates = _scan_indexed_history(observed_at)
    all_candidates.extend(indexed_candidates)

    provenance = rank_provenance_candidates(
        all_candidates,
        max_candidates=200,
    )
    reconstruction = _maybe_reconstruct(
        provenance,
        rpc_urls=args.rpc_urls or list(DEFAULT_RPC_URLS),
        chunk_blocks=args.log_chunk_blocks,
        sample_size=args.balance_sample_size,
    )

    faircrypto_available = sum(
        1 for row in repository_results
        if row["repository"].startswith("FairCrypto/")
        and row["status"] == "AVAILABLE"
    )
    x1_labs_available = any(
        row["repository"].startswith("x1-labs/")
        and row["status"] == "AVAILABLE"
        for row in repository_results
    )
    official_available = sum(
        1 for row in official_results if row["status"] == "AVAILABLE"
    )
    indexed_available = sum(
        1 for row in indexed_results if row["status"] == "AVAILABLE"
    )

    source_gate = (
        faircrypto_available == 2
        and x1_labs_available
        and official_available >= 2
        and x1report_result["status"] == "AVAILABLE"
        and x1report_result["pages_available"] > 0
        and indexed_available >= 1
    )

    blocks = provenance["authoritative_exact_snapshot_block_candidates"]
    reconstruction_required = bool(blocks)
    reconstruction_gate = (
        not reconstruction_required
        or (
            len(blocks) == 1
            and not provenance["authoritative_snapshot_block_conflict"]
            and reconstruction["attempted"] is True
            and reconstruction["official_snapshot"] is not None
        )
    )
    status = "PASS" if source_gate and reconstruction_gate else "FAIL"

    official_snapshot = reconstruction["official_snapshot"]
    output = {
        "status": status,
        "contract_version": XONE_SNAPSHOT_PROVENANCE_CONTRACT_VERSION,
        "observed_at": observed_at,
        "source_gate_passed": source_gate,
        "repository_results": repository_results,
        "faircrypto_repository_available_count": faircrypto_available,
        "x1_labs_repository_available": x1_labs_available,
        "official_x1_results": official_results,
        "official_x1_available_count": official_available,
        "x1report": x1report_result,
        "indexed_history_results": indexed_results,
        "indexed_history_available_count": indexed_available,
        "provenance": provenance,
        "reconstruction_required_by_authoritative_exact_block":
            reconstruction_required,
        "reconstruction_gate_passed": reconstruction_gate,
        "reconstruction": reconstruction,
        "official_xone_snapshot_verified": (
            official_snapshot is not None
            and official_snapshot.get("official_xone_snapshot_verified") is True
        ),
        "official_registry_artifact_verified": False,
        "xone_snapshot_eligibility_verified": False,
        "xone_snapshot_xnt_allocation_binding_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "october_6_unlock_applies_to_xone_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "zero_authoritative_blocks_are_scoped_public_provenance_only":
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
