#!/usr/bin/env python3
"""Live direct-RPC proof for the exact Ethereum XONE identity."""

from __future__ import annotations

import argparse
from functools import partial
import json
import sys

from liquidity_scout.providers.ethereum.xone_identity import (
    DEFAULT_RPC_URLS,
    EthereumXoneIdentityError,
    corroborate_xone_identity_proofs,
    ethereum_rpc_request,
    verify_xone_identity,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the exact Ethereum XONE contract identity from direct JSON-RPC."
    )
    parser.add_argument(
        "--rpc",
        action="append",
        dest="rpc_urls",
        help="Ethereum mainnet HTTPS JSON-RPC URL; repeat to add providers.",
    )
    parser.add_argument(
        "--minimum-proofs",
        type=int,
        default=2,
        help="Minimum matching distinct RPC proofs required (default: 2).",
    )
    args = parser.parse_args()

    urls = args.rpc_urls or list(DEFAULT_RPC_URLS)
    if args.minimum_proofs < 2:
        parser.error("--minimum-proofs must be at least 2")

    proofs = []
    failures = []
    for url in urls:
        rpc = partial(ethereum_rpc_request, rpc_url=url)
        try:
            proof = verify_xone_identity(rpc_call=rpc, source_url=url)
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

    if len(proofs) < args.minimum_proofs:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": "insufficient_direct_rpc_proofs",
                    "minimum_proofs": args.minimum_proofs,
                    "successful_proof_count": len(proofs),
                    "failures": failures,
                    "execution_authorized": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    try:
        corroboration = corroborate_xone_identity_proofs(
            proofs[: args.minimum_proofs]
        )
    except EthereumXoneIdentityError as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": "rpc_proof_disagreement",
                    "error": str(exc),
                    "proofs": proofs,
                    "failures": failures,
                    "execution_authorized": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 3

    print(
        json.dumps(
            {
                "status": "PASS",
                "corroboration": corroboration,
                "proofs": proofs,
                "failures": failures,
                "execution_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
