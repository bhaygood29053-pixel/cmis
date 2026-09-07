#!/usr/bin/env python3
"""Live bounded XONE/XNT -> X1 exact binding discovery."""

from __future__ import annotations

import argparse
import json
import time

from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, rpc_request
from liquidity_scout.providers.xone_xnt import (
    OFFICIAL_REWARDS_URL,
    XoneXntConversionScraper,
    XoneXntScraperError,
    discover_x1_binding_candidates,
    qualify_x1_binding_candidate,
)


OFFICIAL_TARGETS = (
    ("x1_official", "https://x1.xyz/"),
    ("x1_docs", "https://docs.x1.xyz/"),
    ("x1_docs", OFFICIAL_REWARDS_URL),
    ("x1_docs", "https://next.x1.xyz/"),
)


def _dedupe_claims(claims):
    result = []
    seen = set()
    for claim in claims:
        claim_id = str(claim.get("claim_id") or "")
        if not claim_id or claim_id in seen:
            continue
        seen.add(claim_id)
        result.append(claim)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Discover exact X1 account/program candidates explicitly named in "
            "bounded XONE/XNT source claims, then qualify bounded X1 history."
        )
    )
    parser.add_argument("--rpc", default=DEFAULT_X1_RPC_URL)
    parser.add_argument("--x1report-max-urls", type=int, default=20)
    parser.add_argument("--max-candidates", type=int, default=25)
    parser.add_argument("--history-limit", type=int, default=25)
    parser.add_argument("--transaction-limit", type=int, default=10)
    args = parser.parse_args()

    scraper = XoneXntConversionScraper(\n        observed_at_fn=time.time,\n        max_bytes=1_000_000,\n    )
    source_results = []
    claims = []

    for source_id, url in OFFICIAL_TARGETS:
        try:
            result = scraper.scrape_url(source_id, url, max_claims=100)
        except XoneXntScraperError as exc:
            source_results.append(
                {
                    "source_id": source_id,
                    "url": url,
                    "source_role": (
                        "official_x1_documentation"
                        if source_id == "x1_docs"
                        else "official_x1_web"
                    ),
                    "status": "UNAVAILABLE",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "candidate_claim_count": 0,
                }
            )
            continue

        source_results.append(
            {
                "source_id": source_id,
                "url": result["retrieval"]["final_url"],
                "source_role": result["source"]["role"],
                "status": "AVAILABLE",
                "body_sha256": result["retrieval"]["body_sha256"],
                "body_bytes": result["retrieval"]["body_bytes"],
                "candidate_claim_count": result["candidate_claim_count"],
            }
        )
        claims.extend(result["claims"])

    x1report_result = None
    x1report_error = None
    try:
        x1report_result = scraper.scrape_sitemap_candidates(
            "x1report",
            max_urls=args.x1report_max_urls,
            max_claims_per_url=50,
        )
        claims.extend(x1report_result["claims"])
    except XoneXntScraperError as exc:
        x1report_error = {
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    claims = _dedupe_claims(claims)
    discovery = discover_x1_binding_candidates(
        claims,
        max_candidates=args.max_candidates,
    )

    qualifications = []
    qualification_errors = []
    for candidate in discovery["candidates"]:
        if not candidate.get("eligible_for_history_qualification"):
            qualifications.append(
                qualify_x1_binding_candidate(
                    candidate,
                    rpc_call=lambda method, params: rpc_request(
                        method,
                        params,
                        rpc_url=args.rpc,
                    ),
                    source_url=args.rpc,
                    history_limit=args.history_limit,
                    transaction_limit=args.transaction_limit,
                )
            )
            continue
        try:
            proof = qualify_x1_binding_candidate(
                candidate,
                rpc_call=lambda method, params: rpc_request(
                    method,
                    params,
                    rpc_url=args.rpc,
                ),
                source_url=args.rpc,
                history_limit=args.history_limit,
                transaction_limit=args.transaction_limit,
            )
        except Exception as exc:
            qualification_errors.append(
                {
                    "candidate_pubkey": candidate["candidate_pubkey"],
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue
        qualifications.append(proof)

    official_available = [
        row
        for row in source_results
        if row["status"] == "AVAILABLE"
        and row["source_role"].startswith("official_x1")
    ]
    rewards_available = any(
        row["status"] == "AVAILABLE"
        and row["url"].rstrip("/") == OFFICIAL_REWARDS_URL.rstrip("/")
        for row in source_results
    )
    x1report_pages_attempted = (
        int(x1report_result["pages_attempted"])
        if x1report_result is not None
        else 0
    )
    x1report_pages_available = (
        sum(
            1
            for row in x1report_result["results"]
            if row.get("status") == "AVAILABLE"
        )
        if x1report_result is not None
        else 0
    )

    source_gate = (
        len(official_available) >= 2
        and rewards_available
        and x1report_result is not None
        and x1report_pages_attempted > 0
        and x1report_pages_available > 0
    )
    candidate_gate = (
        not qualification_errors
        and (
            discovery["history_qualifiable_candidate_count"] == 0
            or sum(
                1
                for row in qualifications
                if row.get("bounded_history_verified") is True
            )
            == discovery["history_qualifiable_candidate_count"]
        )
    )
    status = "PASS" if source_gate and candidate_gate else "FAIL"

    output = {
        "status": status,
        "contract_version": "xone_xnt_x1_binding_discovery/v1",
        "sources": {
            "official_targets": source_results,
            "official_available_count": len(official_available),
            "rewards_page_available": rewards_available,
            "x1report": {
                "available": x1report_result is not None,
                "error": x1report_error,
                "pages_attempted": x1report_pages_attempted,
                "pages_available": x1report_pages_available,
                "candidate_claim_count": (
                    x1report_result["candidate_claim_count"]
                    if x1report_result is not None
                    else 0
                ),
            },
        },
        "bounded_claim_count": len(claims),
        "candidate_discovery": discovery,
        "candidate_qualifications": qualifications,
        "qualification_errors": qualification_errors,
        "source_gate_passed": source_gate,
        "candidate_qualification_gate_passed": candidate_gate,
        "zero_candidates_are_scoped_corpus_evidence_only": (
            discovery["candidate_count"] == 0
        ),
        "x1_binding_identified": False,
        "xnt_distribution_mechanism_identified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
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
