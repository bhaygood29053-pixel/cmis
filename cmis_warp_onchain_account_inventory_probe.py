#!/usr/bin/env python3
"""Run a read-only zero-byte Warp program account inventory on Solana and X1."""

from __future__ import annotations

import argparse
import json

from liquidity_scout.providers.x1.warp_onchain_inventory import (
    SOLANA_RPC_URL,
    X1_RPC_URL,
    inventory_warp_both_chains,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solana-rpc-url", default=SOLANA_RPC_URL)
    parser.add_argument("--x1-rpc-url", default=X1_RPC_URL)
    parser.add_argument(
        "--data-slice-length",
        type=int,
        default=0,
        help="Account bytes to request from offset 0 (0..256).",
    )
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    result = inventory_warp_both_chains(
        solana_rpc_url=args.solana_rpc_url,
        x1_rpc_url=args.x1_rpc_url,
        data_slice_length=args.data_slice_length,
        timeout=args.timeout,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
