#!/usr/bin/env python3
"""Verify one X1.Ninja trade row through the CMIS trade service."""

import argparse
import json
from decimal import Decimal

from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("signature")
    parser.add_argument("--side", choices=("BUY", "SELL", "buy", "sell"), required=True)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--slot", type=int, required=True)
    parser.add_argument("--timestamp", required=True)
    parser.add_argument("--token-amount", required=True)
    parser.add_argument("--native-amount", required=True)
    args = parser.parse_args()

    event = {
        "type": args.side.lower(),
        "txHash": args.signature,
        "poolAddress": args.pool,
        "slot": args.slot,
        "timestamp": args.timestamp,
        "amountToken": args.token_amount,
        "amountNative": args.native_amount,
    }
    response = TradeAwareCMISGateway().dispatch({
        "service": "trade_verification",
        "chain": "x1",
        "asset": None,
        "params": {"event": event},
    })
    print(json.dumps(response, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
