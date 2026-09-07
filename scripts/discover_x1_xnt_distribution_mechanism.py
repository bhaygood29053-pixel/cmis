#!/usr/bin/env python3
"""Live bounded X1-side XNT distribution / vesting mechanism discovery."""

from __future__ import annotations

import argparse
import json
import time
from urllib.parse import urlparse

import requests

from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, rpc_request
from liquidity_scout.providers.xone_xnt import (
    OFFICIAL_REWARDS_URL,
    discover_xnt_distribution_candidates,
    extract_xnt_mechanism_claims,
    qualify_xnt_distribution_candidate,
)


USER_AGENT = "CMIS-X1-XNT-Mechanism/1.0 (+read-only; evidence-discovery)"
MAX_BYTES = 512_000


def fetch_official(url: str) -> dict:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/markdown,text/plain,text/html,*/*;q=0.2"},
        timeout=20,
        allow_redirects=True,
    )
    response.raise_for_status()
    final_url = str(response.url)
    host = (urlparse(final_url).hostname or "").casefold()
    if host not in {"docs.x1.xyz", "next.x1.xyz"}:
        raise RuntimeError(f"official X1 docs redirect escaped allowlist: {host!r}")
    body = response.content
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"official X1 docs response exceeds {MAX_BYTES} bytes")
    return {
        "requested_url": url,
        "final_url": final_url,
        "content_type": response.headers.get("Content-Type"),
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "bytes": len(body),
        "text": body.decode("utf-8", errors="replace"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover X1-side XNT distribution/vesting mechanism candidates."
    )
    parser.add_argument("--url", default=OFFICIAL_REWARDS_URL)
    parser.add_argument("--rpc", default=DEFAULT_X1_RPC_URL)
    parser.add_argument("--max-candidates", type=int, default=25)
    args = parser.parse_args()

    observed_at = time.time()
    document = fetch_official(args.url)
    claims = extract_xnt_mechanism_claims(
        document["text"],
        source_id="x1_docs",
        url=document["final_url"],
        observed_at=observed_at,
        max_claims=100,
    )
    discovery = discover_xnt_distribution_candidates(
        claims,
        max_candidates=args.max_candidates,
    )

    qualifications = []
    for candidate in discovery["candidates"]:
        proof = qualify_xnt_distribution_candidate(
            candidate,
            rpc_call=lambda method, params: rpc_request(
                method,
                params,
                rpc_url=args.rpc,
            ),
            source_url=args.rpc,
        )
        qualifications.append(proof)

    topics = sorted({topic for claim in claims for topic in claim["topics"]})
    percentages = sorted({
        value
        for claim in claims
        for value in claim["normalized_values"]["percentages"]
    })
    day_periods = sorted({
        value
        for claim in claims
        for value in claim["normalized_values"]["day_periods"]
    })
    credit_xnt_rates = sorted({
        value
        for claim in claims
        for value in claim["normalized_values"]["credit_xnt_rates"]
    })

    source_expectations = {
        "validator_reward_topic_present": "validator_rewards" in topics,
        "lock_or_vesting_or_unlock_topic_present": bool(
            {"lockup", "vesting", "unlock"} & set(topics)
        ),
        "credit_xnt_rate_50000_to_1_present": any(
            "50,000" in value and "1 XNT" in value
            for value in credit_xnt_rates
        ),
        "ten_percent_present": any(value.replace(" ", "") == "10%" for value in percentages),
        "ninety_percent_present": any(value.replace(" ", "") == "90%" for value in percentages),
        "365_days_present": any(value.replace(",", "").casefold().startswith("365 day") for value in day_periods),
    }

    source_gate_passed = all(source_expectations.values()) and bool(claims)
    status = "PASS" if source_gate_passed else "FAIL"

    print(json.dumps({
        "status": status,
        "contract_version": "x1_xnt_distribution_mechanism_discovery/v1",
        "source": {
            key: value
            for key, value in document.items()
            if key != "text"
        },
        "observed_at": observed_at,
        "claim_count": len(claims),
        "topics": topics,
        "percentages": percentages,
        "day_periods": day_periods,
        "credit_xnt_rates": credit_xnt_rates,
        "source_expectations": source_expectations,
        "claims": claims,
        "candidate_discovery": discovery,
        "candidate_qualifications": qualifications,
        "native_xnt_not_wxnt": True,
        "xnt_rule_claim_verified": False,
        "xnt_distribution_mechanism_identified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
