#!/usr/bin/env python3
"""Read-only CMIS v1.4.10.3 exact pool-leg semantics + diagnosis probe."""

from __future__ import annotations

import argparse
import json
import time

from liquidity_scout.providers.x1.exact_pool_leg_semantics_v14103 import (
    prove_exact_pool_leg_semantics,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Prove exact BUY/SELL semantics from canonical pool vaults after "
            "deterministically classifying recognized AMM operations as swaps, "
            "liquidity additions/removals, or UNKNOWN across nested 1h/6h/24h "
            "windows. UNKNOWN operations remain fail-closed. When proof is not "
            "available, return a deterministic proof_diagnosis explaining the "
            "blocking stage from literal requested-window evidence."
        )
    )
    parser.add_argument("pool_address")
    parser.add_argument("asset_mint")
    parser.add_argument("--pair", default=None)
    parser.add_argument("--rpc-url", default=None)
    parser.add_argument("--end-epoch", type=float, default=None)
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-signatures", type=int, default=5000)
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args()

    result = prove_exact_pool_leg_semantics(
        pool_address=args.pool_address,
        asset_mint=args.asset_mint,
        end_epoch=(time.time() if args.end_epoch is None else args.end_epoch),
        pair=args.pair,
        rpc_url=args.rpc_url,
        page_size=args.page_size,
        max_signatures=args.max_signatures,
    )

    print(json.dumps(result, indent=args.indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
