#!/usr/bin/env python3
"""Live multi-RPC proof for bounded Ethereum XONE Transfer-event observation."""

from __future__ import annotations

import argparse
from functools import partial
import json

from liquidity_scout.providers.ethereum.xone_event_observer import (
    EthereumXoneEventError,
    corroborate_xone_event_observations,
    observe_xone_transfer_events,
)
from liquidity_scout.providers.ethereum.xone_identity import (
    DEFAULT_RPC_URLS,
    corroborate_xone_identity_proofs,
    ethereum_rpc_request,
    verify_xone_identity,
)


def parse_block(value: str) -> int:
    text = value.strip()
    return int(text, 16 if text.startswith("0x") else 10)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify bounded canonical XONE Transfer events from direct Ethereum RPC."
    )
    parser.add_argument(
        "--rpc",
        action="append",
        dest="rpc_urls",
        help="Ethereum mainnet HTTPS JSON-RPC URL; repeat for provider quorum.",
    )
    parser.add_argument("--from-block", help="Inclusive block number; decimal or 0x hex.")
    parser.add_argument("--to-block", help="Inclusive block number; decimal or 0x hex.")
    parser.add_argument(
        "--minimum-proofs",
        type=int,
        default=2,
        help="Minimum matching distinct RPC observations required (default: 2).",
    )
    parser.add_argument(
        "--enrich-recipient-code",
        action="store_true",
        help="Best-effort current code check for nonzero recipient addresses.",
    )
    args = parser.parse_args()

    if (args.from_block is None) != (args.to_block is None):
        parser.error("--from-block and --to-block must be supplied together")
    if args.minimum_proofs < 2:
        parser.error("--minimum-proofs must be at least 2")

    explicit_from = parse_block(args.from_block) if args.from_block else None
    explicit_to = parse_block(args.to_block) if args.to_block else None
    urls = args.rpc_urls or list(DEFAULT_RPC_URLS)

    identity_proofs = []
    observations = []
    failures = []

    for url in urls:
        rpc = partial(ethereum_rpc_request, rpc_url=url)
        try:
            identity = verify_xone_identity(rpc_call=rpc, source_url=url)
            if explicit_from is None:
                start = int(identity["creation_block"], 16)
                end = start
            else:
                start = explicit_from
                end = explicit_to
            observation = observe_xone_transfer_events(
                rpc_call=rpc,
                from_block=start,
                to_block=end,
                source_url=url,
                enrich_recipient_code=args.enrich_recipient_code,
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
        observations.append(observation)

    if len(observations) < args.minimum_proofs:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": "insufficient_direct_rpc_observations",
                    "minimum_proofs": args.minimum_proofs,
                    "successful_observation_count": len(observations),
                    "failures": failures,
                    "execution_authorized": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    try:
        identity = corroborate_xone_identity_proofs(
            identity_proofs[: args.minimum_proofs]
        )
        event_window = corroborate_xone_event_observations(
            observations[: args.minimum_proofs]
        )
    except (EthereumXoneEventError, Exception) as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": "rpc_corroboration_disagreement",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
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
                "identity": identity,
                "event_window": event_window,
                "observations": observations,
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
