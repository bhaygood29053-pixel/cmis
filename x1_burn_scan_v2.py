import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal, ROUND_HALF_UP

import x1_burn_scan as base

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

def open_db():
    db = base.open_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS scan_state (
            mint TEXT PRIMARY KEY,
            full_history_complete INTEGER NOT NULL DEFAULT 0,
            last_scan_time INTEGER
        )
    """)
    db.commit()
    return db


def history_complete(db, mint):
    row = db.execute(
        "SELECT full_history_complete FROM scan_state WHERE mint = ?",
        (mint,),
    ).fetchone()
    return bool(row and row[0])


def set_history_complete(db, mint, complete):
    db.execute(
        """
        INSERT INTO scan_state (mint, full_history_complete, last_scan_time)
        VALUES (?, ?, ?)
        ON CONFLICT(mint) DO UPDATE SET
            full_history_complete = excluded.full_history_complete,
            last_scan_time = excluded.last_scan_time
        """,
        (mint, 1 if complete else 0, int(time.time())),
    )
    db.commit()


def known_signatures(db, mint):
    return {
        row[0]
        for row in db.execute(
            "SELECT signature FROM processed WHERE mint = ?",
            (mint,),
        )
    }


def collect_signatures(mint, known, period, complete, max_signatures=None):
    cutoff = None if period == "lifetime" else (
        int(time.time()) - PERIOD_SECONDS[period]
    )
    stop_at_known = complete

    results = []
    before = None
    boundary_complete = False

    while True:
        limit = 1000
        if max_signatures is not None:
            remaining = max_signatures - len(results)
            if remaining <= 0:
                break
            limit = min(limit, remaining)

        options = {"limit": limit}
        if before:
            options["before"] = before

        batch = base.rpc(
            "getSignaturesForAddress",
            [mint, options],
        ) or []

        if not batch:
            boundary_complete = True
            break

        stop = False

        for item in batch:
            sig = item.get("signature")
            block_time = item.get("blockTime")

            if stop_at_known and sig in known:
                boundary_complete = True
                stop = True
                break

            if (
                cutoff is not None
                and block_time is not None
                and block_time < cutoff
            ):
                boundary_complete = True
                stop = True
                break

            if item.get("err") is None:
                results.append(item)

                if (
                    max_signatures is not None
                    and len(results) >= max_signatures
                ):
                    stop = True
                    break

        print(
            f"Successful signatures collected: {len(results):,}",
            flush=True,
        )

        if stop:
            break

        if len(batch) < limit:
            boundary_complete = True
            break

        before = batch[-1]["signature"]

    if max_signatures is not None:
        boundary_complete = False

    return results, boundary_complete


def fetch_transaction(signature, mint):
    tx = base.rpc(
        "getTransaction",
        [
            signature,
            {
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 0,
            },
        ],
    )
    if not tx:
        raise RuntimeError("transaction unavailable from RPC")
    return signature, base.extract_burns(tx, mint)


def inspect_transactions(db, mint, signatures, workers):
    known = known_signatures(db, mint)
    pending = [
        item["signature"]
        for item in signatures
        if item["signature"] not in known
    ]

    print(f"Cached transactions:  {len(known):,}")
    print(f"Need RPC inspection:  {len(pending):,}")
    print(f"Workers:              {workers}")
    print()

    completed = 0
    errors = 0

    for start in range(0, len(pending), 500):
        batch = pending[start:start + 500]

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(fetch_transaction, sig, mint): sig
                for sig in batch
            }

            for future in as_completed(futures):
                sig = futures[future]
                try:
                    signature, burns = future.result()
                    base.save_result(db, mint, signature, burns)
                    completed += 1
                except Exception as exc:
                    errors += 1
                    print(
                        f"RPC error {sig[:12]}...: {exc}",
                        flush=True,
                    )

                if completed and completed % 50 == 0:
                    db.commit()

                if completed and completed % 100 == 0:
                    print(
                        f"Processed this run: {completed:,}/{len(pending):,} "
                        f"| RPC errors: {errors:,}",
                        flush=True,
                    )

        db.commit()

    return errors


def print_summary(db, symbol, mint, decimals, period):
    where = "WHERE mint = ?"
    params = [mint]

    if period != "lifetime":
        cutoff = int(time.time()) - PERIOD_SECONDS[period]
        where += " AND block_time >= ?"
        params.append(cutoff)

    rows = db.execute(
        f"SELECT raw_amount FROM burns {where}",
        tuple(params),
    ).fetchall()

    burn_txs = db.execute(
        f"SELECT COUNT(DISTINCT signature) FROM burns {where}",
        tuple(params),
    ).fetchone()[0]

    total_raw = sum(
        (Decimal(row[0]) for row in rows),
        Decimal(0),
    )
    total = total_raw / (Decimal(10) ** decimals)

    label = {
        "24h": "Burned last 24h",
        "7d": "Burned last 7d",
        "30d": "Burned last 30d",
        "lifetime": "Lifetime burned",
    }[period]

    print()
    print("============================================")
    print(" VERIFIED X1 BURN SUMMARY")
    print("============================================")
    print(f"Token:             {symbol}")
    print(f"Period:            {period}")
    print(f"Burn txs:          {burn_txs:,}")
    print(f"Burn instructions: {len(rows):,}")
    print(f"{label}: {total:,.9f} {symbol}")
    print(f"Rounded burned:    {round_token_amount(total):,} {symbol}")
    print("============================================")


def run_scan(symbol, mint, decimals, period, workers, max_signatures):
    db = open_db()
    known = known_signatures(db, mint)
    complete = history_complete(db, mint)

    if complete:
        print("Historical cache: COMPLETE")
        print("Checking only for new X1 transactions.\n")
    elif period == "lifetime":
        print("Historical cache: NOT COMPLETE")
        print("Building full lifetime history.\n")
    else:
        print("Historical cache: NOT COMPLETE")
        print(f"Scanning only enough history to cover {period}.\n")

    signatures, boundary_complete = collect_signatures(
        mint,
        known,
        period,
        complete,
        max_signatures,
    )

    errors = inspect_transactions(
        db,
        mint,
        signatures,
        workers,
    )

    if (
        period == "lifetime"
        and not complete
        and boundary_complete
        and errors == 0
        and max_signatures is None
    ):
        set_history_complete(db, mint, True)
        print("\nHistorical cache is now COMPLETE.")

    print_summary(db, symbol, mint, decimals, period)

    if errors:
        print(
            f"\nWARNING: {errors:,} RPC transactions failed. "
            "Run the same command again to retry them."
        )

    if not boundary_complete:
        print(
            "\nNOTE: This was a limited/test scan; "
            "period coverage is not guaranteed complete."
        )

    db.close()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generic X1 burn scanner with 24h, 7d, 30d "
            "and lifetime reporting."
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
    )
    parser.add_argument(
        "--max-signatures",
        type=int,
        default=None,
        help="Testing only",
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

    run_scan(
        symbol,
        mint,
        info["decimals"],
        args.period,
        max(1, args.workers),
        args.max_signatures,
    )


if __name__ == "__main__":
    main()
