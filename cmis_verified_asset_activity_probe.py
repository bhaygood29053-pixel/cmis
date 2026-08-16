#!/usr/bin/env python3
import argparse
import json

from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("asset")
    parser.add_argument("--max-pools", type=int, default=5)
    parser.add_argument("--per-pool-limit", type=int, default=None)
    parser.add_argument(
        "--window",
        choices=("1h", "6h", "24h"),
        default=None,
        help="Attach an explicit verified activity window.",
    )
    args = parser.parse_args()

    params = {"max_pools": args.max_pools}
    if args.per_pool_limit is not None:
        params["per_pool_limit"] = args.per_pool_limit
    if args.window is not None:
        params["window"] = args.window

    response = TradeAwareCMISGateway().dispatch({
        "service": "verified_asset_activity",
        "chain": "x1",
        "asset": args.asset,
        "params": params,
    })
    print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
