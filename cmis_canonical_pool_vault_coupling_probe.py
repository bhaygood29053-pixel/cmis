#!/usr/bin/env python3
"""Read-only CMIS v1.4.9 canonical pool-vault coupling probe."""

from __future__ import annotations

import argparse
import json
import time

from liquidity_scout.providers.x1.canonical_pool_vault_coupling import (
    prove_canonical_pool_vault_coupling,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Prove whether exactly one v1.4.8-qualified token-account family "
            "is structurally coupled to every recognized AMM instruction for "
            "the selected X1 pool across the 1h/6h/24h proof windows."
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

    result = prove_canonical_pool_vault_coupling(
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
