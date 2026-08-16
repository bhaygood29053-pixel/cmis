#!/usr/bin/env python3
import argparse
import json

from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("asset")
    parser.add_argument("--max-pools", type=int, default=5)
    parser.add_argument("--per-pool-limit", type=int, default=5)
    args = parser.parse_args()

    response = TradeAwareCMISGateway().dispatch({
        "service": "verified_asset_activity",
        "chain": "x1",
        "asset": args.asset,
        "params": {
            "max_pools": args.max_pools,
            "per_pool_limit": args.per_pool_limit,
        },
    })
    print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
