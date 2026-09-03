#!/usr/bin/env python3
"""Run the bounded read-only Warp rare-account capture on Solana and X1."""

from __future__ import annotations

import argparse
import json

from liquidity_scout.providers.x1.warp_rare_account_capture import (
    SOLANA_RPC_URL,
    X1_RPC_URL,
    capture_warp_rare_both_chains,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solana-rpc-url", default=SOLANA_RPC_URL)
    parser.add_argument("--x1-rpc-url", default=X1_RPC_URL)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--include-raw-base64",
        action="store_true",
        help=(
            "Include full account base64 in this ephemeral process output. "
            "Do not commit the output as a source fixture."
        ),
    )
    args = parser.parse_args()

    result = capture_warp_rare_both_chains(
        solana_rpc_url=args.solana_rpc_url,
        x1_rpc_url=args.x1_rpc_url,
        timeout=args.timeout,
        include_raw_base64=args.include_raw_base64,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
