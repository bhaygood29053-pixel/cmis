#!/usr/bin/env python3
"""Read-only CMIS v1.4.8 canonical vault-family qualification probe."""

from __future__ import annotations

import argparse
import json
import time

from liquidity_scout.providers.x1.canonical_vault_family_qualification import (
    qualify_canonical_vault_family,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Qualify one X1 pool's recurrent vault-pair family using direct "
            "jsonParsed token-account identity evidence."
        )
    )
    parser.add_argument("pool_address")
    parser.add_argument("asset_mint")
    parser.add_argument("--pair", default=None)
    parser.add_argument("--rpc-url", default=None)
    parser.add_argument("--end-epoch", type=float, default=None)
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-signatures", type=int, default=5000)
    args = parser.parse_args()

    result = qualify_canonical_vault_family(
        pool_address=args.pool_address,
        asset_mint=args.asset_mint,
        end_epoch=(time.time() if args.end_epoch is None else args.end_epoch),
        pair=args.pair,
        rpc_url=args.rpc_url,
        page_size=args.page_size,
        max_signatures=args.max_signatures,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
