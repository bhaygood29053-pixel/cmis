#!/usr/bin/env python3
"""Live multi-RPC proof for XONE burn-redeemer / migration-sink semantics."""

from __future__ import annotations

import argparse
from functools import partial
import json

from liquidity_scout.providers.ethereum.xone_identity import (
    DEFAULT_RPC_URLS,
    ethereum_rpc_request,
    verify_xone_identity,
)
from liquidity_scout.providers.ethereum.xone_migration_sink_semantics import (
    corroborate_xone_burn_surface,
    verify_burn_redeemer_candidate,
    verify_xone_burn_surface,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the exact XONE burn-accounting surface and optional redeemer candidate."
    )
    parser.add_argument("--rpc", action="append", dest="rpc_urls")
    parser.add_argument("--candidate", help="Optional exact Ethereum contract candidate.")
    parser.add_argument("--minimum-proofs", type=int, default=2)
    args = parser.parse_args()

    if args.minimum_proofs < 2:
        parser.error("--minimum-proofs must be at least 2")

    urls = args.rpc_urls or list(DEFAULT_RPC_URLS)
    surface_proofs = []
    identity_proofs = []
    candidate_proofs = []
    failures = []

    for url in urls:
        rpc = partial(ethereum_rpc_request, rpc_url=url)
        try:
            identity = verify_xone_identity(rpc_call=rpc, source_url=url)
            surface = verify_xone_burn_surface(rpc_call=rpc, source_url=url)
            candidate = None
            if args.candidate:
                candidate = verify_burn_redeemer_candidate(
                    args.candidate,
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
        identity_proofs.append(identity)
        surface_proofs.append(surface)
        if candidate is not None:
            candidate_proofs.append(candidate)

    if len(surface_proofs) < args.minimum_proofs:
        print(json.dumps({
            "status": "FAIL",
            "reason": "insufficient_direct_rpc_proofs",
            "minimum_proofs": args.minimum_proofs,
            "successful_proof_count": len(surface_proofs),
            "failures": failures,
            "execution_authorized": False,
        }, indent=2, sort_keys=True))
        return 2

    corroboration = corroborate_xone_burn_surface(
        surface_proofs[: args.minimum_proofs]
    )

    print(json.dumps({
        "status": "PASS",
        "burn_surface": corroboration,
        "surface_proofs": surface_proofs,
        "candidate_proofs": candidate_proofs,
        "failures": failures,
        "migration_sink_identified": False,
        "xone_xnt_conversion_verified": False,
        "xnt_issuance_verified": False,
        "cross_chain_correlation_verified": False,
        "execution_authorized": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
