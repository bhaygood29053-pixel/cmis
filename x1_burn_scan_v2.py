"""Legacy period burn-report CLI backed by the X1 activity provider.

The original v2 scanner maintained a second RPC/history/cache implementation
and could mark a local cache as complete lifetime history. This compatibility
version delegates all X1 collection and persistence to the provider scanner and
never upgrades RPC-visible history into a verified chain-lifetime claim.
"""

import argparse
import time
from decimal import Decimal, ROUND_HALF_UP

import x1_burn_scan as base
from liquidity_scout.providers.x1.activity_scanner import (
    X1ActivityScanner,
    open_activity_db,
)
from liquidity_scout.providers.x1.rpc import X1RPCProvider


PERIOD_SECONDS = {
    "24h": 86400,
    "7d": 7 * 86400,
    "30d": 30 * 86400,
}


def round_token_amount(value):
    """Round to nearest whole token; .5 and above rounds up."""
    return int(
        Decimal(str(value)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def _period_burn_events(report, period, *, now=None):
    """Filter provider-observed burn events by their explicit block time."""
    events = [
        event
        for event in (report.get("events") or [])
        if isinstance(event, dict) and event.get("kind") == "burn"
    ]

    if period == "lifetime":
        return events, []

    cutoff = int(time.time() if now is None else now) - PERIOD_SECONDS[period]
    selected = []
    warnings = []

    for event in events:
        block_time = event.get("block_time")
        if isinstance(block_time, bool) or not isinstance(block_time, int):
            warnings.append(
                "One or more observed burn events lacked a verified block time "
                "and were excluded from the period total."
            )
            continue
        if block_time >= cutoff:
            selected.append(event)

    return selected, sorted(set(warnings))


def _sum_burn_tokens(events, decimals):
    raw_total = sum(
        (Decimal(str(event["raw_amount"])) for event in events),
        Decimal(0),
    )
    return raw_total / (Decimal(10) ** int(decimals))


def print_summary(report, symbol, mint, decimals, period):
    """Print a period view without claiming independent lifetime coverage."""
    events, warnings = _period_burn_events(report, period)
    total = _sum_burn_tokens(events, decimals)
    signatures = {event.get("signature") for event in events if event.get("signature")}

    label = {
        "24h": "Observed burned last 24h",
        "7d": "Observed burned last 7d",
        "30d": "Observed burned last 30d",
        "lifetime": "Observed burned in scanned history",
    }[period]

    print()
    print("============================================")
    print(" X1 BURN ACTIVITY SUMMARY")
    print("============================================")
    print(f"Token:             {symbol}")
    print(f"Mint:              {mint}")
    print(f"Period:            {period}")
    print(f"Burn txs observed: {len(signatures):,}")
    print(f"Burn instructions: {len(events):,}")
    print(f"{label}: {total:,.9f} {symbol}")
    print(f"Rounded burned:    {round_token_amount(total):,} {symbol}")
    print(f"Coverage scope:    {report.get('coverage_scope')}")
    print("Lifetime coverage: UNVERIFIED")
    print("============================================")

    for warning in warnings:
        print(f"WARNING: {warning}")

    if period == "lifetime":
        print(
            "NOTE: 'lifetime' is a compatibility label for the CLI request. "
            "RPC history exhaustion is not independent proof of complete "
            "chain-lifetime history."
        )
    elif report.get("coverage_scope") != "rpc_history_exhausted":
        print(
            "NOTE: Period totals are observations from the selected RPC-visible "
            "scan window and are not promoted to complete period coverage."
        )


def run_scan(symbol, mint, decimals, period, workers, max_signatures):
    """Run the X1 provider scanner and render the legacy period view."""
    _ = max(1, int(workers))  # compatibility option; provider owns retrieval.

    rpc_provider = X1RPCProvider(
        rpc_url=base.RPC,
        retries=5,
        timeout=30,
    )
    scanner = X1ActivityScanner(rpc_provider.request)
    db = open_activity_db(base.DB_FILE)
    try:
        report = scanner.scan(
            mint=mint,
            decimals=decimals,
            db=db,
            max_signatures=max_signatures,
        )
    finally:
        db.close()

    print_summary(report, symbol, mint, decimals, period)
    return report


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Provider-backed X1 burn activity report with 24h, 7d, 30d "
            "and compatibility lifetime views."
        )
    )
    parser.add_argument(
        "token",
        help="XDEX symbol such as AGI/XENCAT or an X1 mint address",
    )
    parser.add_argument(
        "--period",
        choices=("24h", "7d", "30d", "lifetime"),
        default="lifetime",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help=(
            "Compatibility option retained from the legacy scanner; "
            "provider retrieval is deterministic"
        ),
    )
    parser.add_argument(
        "--max-signatures",
        type=int,
        default=None,
        help="Optional bound on recent signature-history entries examined",
    )
    args = parser.parse_args()

    symbol, mint = base.resolve_token(args.token)
    info = base.get_token_info(mint)

    print()
    print("============================================")
    print(" X1 GENERIC BURN SCANNER V2")
    print("============================================")
    print(f"Token:            {symbol}")
    print(f"Mint:             {mint}")
    print(f"Decimals:         {info['decimals']}")
    print(f"Requested period: {args.period}")
    print("============================================")
    print()

    return run_scan(
        symbol,
        mint,
        info["decimals"],
        args.period,
        max(1, args.workers),
        args.max_signatures,
    )


if __name__ == "__main__":
    main()
