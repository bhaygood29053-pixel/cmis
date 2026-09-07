#!/usr/bin/env python3
"""Live bounded XONE/XNT conversion-candidate discovery and qualification."""

from __future__ import annotations

import argparse
from functools import partial
import json

from liquidity_scout.providers.ethereum.xone_identity import (
    DEFAULT_RPC_URLS,
    ethereum_rpc_request,
)
from liquidity_scout.providers.xone_xnt import (
    CANDIDATE_DISCOVERY_CONTRACT_VERSION,
    XoneXntConversionScraper,
    discover_conversion_candidates,
    qualify_conversion_candidate,
)


def canonical_qualification_view(proof):
    return (
        proof.get("candidate_address"),
        proof.get("qualification_state"),
        proof.get("runtime_code_present"),
        proof.get("burn_redeemer_interface_verified"),
        proof.get("migration_sink_identified"),
        proof.get("xone_xnt_conversion_verified"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape bounded XONE/XNT claims, discover exact Ethereum address "
            "candidates, and qualify them without promoting conversion truth."
        )
    )
    parser.add_argument("--source-id", default="x1report", choices=["x1report"])
    parser.add_argument("--max-urls", type=int, default=30)
    parser.add_argument("--max-claims-per-url", type=int, default=25)
    parser.add_argument("--max-candidates", type=int, default=10)
    parser.add_argument("--rpc", action="append", dest="rpc_urls")
    args = parser.parse_args()

    if args.max_urls < 1 or args.max_candidates < 1:
        parser.error("max bounds must be positive")

    scraper = XoneXntConversionScraper()
    scrape = scraper.scrape_sitemap_candidates(
        args.source_id,
        max_urls=args.max_urls,
        max_claims_per_url=args.max_claims_per_url,
    )
    discovery = discover_conversion_candidates(
        scrape["claims"],
        max_candidates=args.max_candidates,
    )

    rpc_urls = args.rpc_urls or list(DEFAULT_RPC_URLS)
    candidate_qualifications = []
    technical_disagreements = []

    for candidate in discovery["candidates"]:
        if not candidate["eligible_for_ethereum_qualification"]:
            candidate_qualifications.append(
                {
                    "candidate_address": candidate["candidate_address"],
                    "candidate_role": candidate["candidate_role"],
                    "qualification_state": "excluded_known_identity",
                    "proofs": [],
                    "failures": [],
                    "multi_rpc_technical_agreement": False,
                    "technical_qualification_complete": True,
                    "migration_sink_identified": False,
                    "xone_xnt_conversion_verified": False,
                    "execution_authorized": False,
                }
            )
            continue

        proofs = []
        failures = []
        for url in rpc_urls:
            rpc = partial(ethereum_rpc_request, rpc_url=url)
            try:
                proof = qualify_conversion_candidate(
                    candidate,
                    rpc_call=rpc,
                    source_url=url,
                )
            except Exception as exc:
                failures.append(
                    {
                        "rpc_url": url,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                continue
            proofs.append(proof)

        agreement = False
        disagreement = False
        if len(proofs) >= 2:
            views = {canonical_qualification_view(proof) for proof in proofs}
            agreement = len(views) == 1
            disagreement = not agreement

        if disagreement:
            technical_disagreements.append(candidate["candidate_address"])

        candidate_qualifications.append(
            {
                "candidate_address": candidate["candidate_address"],
                "candidate_role": candidate["candidate_role"],
                "proofs": proofs,
                "failures": failures,
                "successful_rpc_proof_count": len(proofs),
                "multi_rpc_technical_agreement": agreement,
                "technical_disagreement": disagreement,
                "technical_qualification_complete": len(proofs) >= 2 and agreement,
                "migration_sink_identified": False,
                "xone_xnt_conversion_verified": False,
                "xnt_issuance_verified": False,
                "cross_chain_correlation_verified": False,
                "execution_authorized": False,
            }
        )

    status = "PASS" if not technical_disagreements else "FAIL"
    result = {
        "status": status,
        "contract_version": CANDIDATE_DISCOVERY_CONTRACT_VERSION,
        "source_id": args.source_id,
        "pages_attempted": scrape["pages_attempted"],
        "candidate_claim_count": scrape["candidate_claim_count"],
        "page_results": [
            {
                "url": row["url"],
                "status": row["status"],
                "error_type": row["error_type"],
                "error": row["error"],
                "claim_count": len(row["claims"]),
            }
            for row in scrape["results"]
        ],
        "candidate_discovery": discovery,
        "candidate_qualifications": candidate_qualifications,
        "technical_disagreements": technical_disagreements,
        "zero_candidates_mean_only_no_exact_address_candidates_in_bounded_live_corpus":
            discovery["candidate_count"] == 0,
        "migration_sink_identified": False,
        "xone_xnt_conversion_verified": False,
        "xnt_issuance_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
