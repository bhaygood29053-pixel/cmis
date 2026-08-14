import argparse
import os
import sqlite3
import time
from decimal import Decimal, ROUND_HALF_UP
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv

load_dotenv()

RPC = os.getenv(
    "X1_RPC_URL",
    "https://rpc.mainnet.x1.xyz"
).strip()

DB_FILE = "x1_burn_scan.db"

BASE58 = set(
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    "abcdefghijkmnopqrstuvwxyz"
)


# ============================================================
# RPC
# ============================================================


def round_token_amount(value):
    """Round to nearest whole token; .5 and above rounds up."""
    return int(
        Decimal(str(value)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

def rpc(method, params, retries=5):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }

    for attempt in range(retries):
        try:
            r = requests.post(
                RPC,
                json=payload,
                timeout=30,
            )

            # Retry rate limits / temporary server errors.
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(0.75 * (2 ** attempt))
                continue

            r.raise_for_status()

            data = r.json()

            if "error" in data:
                raise RuntimeError(data["error"])

            return data.get("result")

        except Exception:
            if attempt == retries - 1:
                raise

            time.sleep(0.75 * (2 ** attempt))


# ============================================================
# TOKEN RESOLUTION
# ============================================================

def looks_like_mint(value):
    value = value.strip()

    return (
        32 <= len(value) <= 50
        and all(ch in BASE58 for ch in value)
    )


def resolve_token(value):
    """
    Accept either:
      AGI
      XENCAT
      <mint address>

    Returns:
      symbol, mint
    """

    value = value.strip()

    if looks_like_mint(value):
        return value[:8] + "...", value

    try:
        import moltgrid_signal_v12_ollama as scout
    except Exception as exc:
        raise RuntimeError(
            "Could not load Liquidity Scout for symbol resolution: "
            f"{exc}"
        )

    catalog = scout.XDEXCatalog()
    catalog.refresh()

    term, matches = scout.resolve_asset(
        value,
        catalog.pools,
    )

    if not matches:
        raise RuntimeError(
            f"Token '{value}' was not found in the XDEX catalog."
        )

    snap = scout.compact_asset_snapshot(
        term,
        matches,
        catalog,
    )

    mint = str(
        snap.get("token_address") or ""
    ).strip()

    symbol = str(
        snap.get("symbol") or value
    ).strip().upper()

    # Fallback if snapshot does not expose token_address.
    if not mint:
        try:
            _pool, _side, asset, _quality = matches[0]

            for key in (
                "address",
                "mint",
                "tokenAddress",
                "token_address",
            ):
                candidate = str(
                    asset.get(key) or ""
                ).strip()

                if candidate:
                    mint = candidate
                    break

        except Exception:
            pass

    if not mint:
        raise RuntimeError(
            f"Could not determine X1 mint address for {symbol}."
        )

    return symbol, mint


# ============================================================
# TOKEN INFORMATION
# ============================================================

def get_token_info(mint):
    result = rpc(
        "getAccountInfo",
        [
            mint,
            {"encoding": "jsonParsed"},
        ],
    )

    info = (
        (result or {})
        .get("value", {})
        .get("data", {})
        .get("parsed", {})
        .get("info", {})
    )

    if not info:
        raise RuntimeError(
            "Mint account could not be parsed."
        )

    return {
        "decimals": int(info.get("decimals") or 0),
        "supply": str(info.get("supply") or ""),
        "mint_authority": info.get("mintAuthority"),
        "freeze_authority": info.get("freezeAuthority"),
    }


# ============================================================
# SIGNATURE HISTORY
# ============================================================

def get_signatures(mint, max_signatures=None):
    results = []
    before = None

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

        batch = rpc(
            "getSignaturesForAddress",
            [mint, options],
        ) or []

        if not batch:
            break

        # Failed transactions cannot contain completed burns.
        successful = [
            item for item in batch
            if item.get("err") is None
        ]

        results.extend(successful)

        print(
            f"Successful signatures collected: "
            f"{len(results):,}",
            flush=True,
        )

        if len(batch) < limit:
            break

        before = batch[-1]["signature"]

    return results


# ============================================================
# BURN EXTRACTION
# ============================================================

def extract_burns(tx, mint):
    burns = []

    if not tx:
        return burns

    meta = tx.get("meta") or {}

    # Never count a failed transaction.
    if meta.get("err") is not None:
        return burns

    block_time = tx.get("blockTime")

    def inspect(ix, location):
        if not isinstance(ix, dict):
            return

        parsed = ix.get("parsed")

        if not isinstance(parsed, dict):
            return

        ix_type = str(
            parsed.get("type") or ""
        ).lower()

        if ix_type not in (
            "burn",
            "burnchecked",
        ):
            return

        info = parsed.get("info") or {}

        # Only count burns for the requested mint.
        if str(info.get("mint") or "") != mint:
            return

        token_amount = info.get("tokenAmount") or {}

        raw_amount = (
            token_amount.get("amount")
            or info.get("amount")
        )

        if raw_amount is None:
            return

        burns.append({
            "location": location,
            "type": ix_type,
            "raw_amount": str(raw_amount),
            "authority": str(
                info.get("authority") or ""
            ),
            "account": str(
                info.get("account") or ""
            ),
            "block_time": block_time,
        })

    message = (
        tx.get("transaction", {})
        .get("message", {})
    )

    # Top-level token instructions.
    for i, ix in enumerate(
        message.get("instructions") or []
    ):
        inspect(ix, f"top:{i}")

    # Inner CPI token instructions.
    for group_i, group in enumerate(
        meta.get("innerInstructions") or []
    ):
        for ix_i, ix in enumerate(
            group.get("instructions") or []
        ):
            inspect(
                ix,
                f"inner:{group_i}:{ix_i}",
            )

    return burns


def fetch_transaction(signature, mint):
    tx = rpc(
        "getTransaction",
        [
            signature,
            {
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 0,
            },
        ],
    )

    return signature, extract_burns(tx, mint)


# ============================================================
# DATABASE / CACHE
# ============================================================

def open_db():
    db = sqlite3.connect(DB_FILE)

    db.execute("""
        CREATE TABLE IF NOT EXISTS processed (
            mint TEXT NOT NULL,
            signature TEXT NOT NULL,
            PRIMARY KEY (mint, signature)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS burns (
            mint TEXT NOT NULL,
            burn_key TEXT NOT NULL,
            signature TEXT NOT NULL,
            instruction_type TEXT NOT NULL,
            raw_amount TEXT NOT NULL,
            authority TEXT,
            account TEXT,
            block_time INTEGER,
            PRIMARY KEY (mint, burn_key)
        )
    """)

    db.commit()

    return db


def save_result(
    db,
    mint,
    signature,
    burns,
):
    for burn in burns:
        burn_key = (
            f"{signature}:{burn['location']}"
        )

        db.execute(
            """
            INSERT OR IGNORE INTO burns (
                mint,
                burn_key,
                signature,
                instruction_type,
                raw_amount,
                authority,
                account,
                block_time
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mint,
                burn_key,
                signature,
                burn["type"],
                burn["raw_amount"],
                burn["authority"],
                burn["account"],
                burn["block_time"],
            ),
        )

    db.execute(
        """
        INSERT OR IGNORE INTO processed (
            mint,
            signature
        )
        VALUES (?, ?)
        """,
        (
            mint,
            signature,
        ),
    )


# ============================================================
# SUMMARY
# ============================================================

def print_summary(
    db,
    symbol,
    mint,
    decimals,
):
    rows = db.execute(
        """
        SELECT raw_amount
        FROM burns
        WHERE mint = ?
        """,
        (mint,),
    ).fetchall()

    total_raw = sum(
        (Decimal(row[0]) for row in rows),
        Decimal(0),
    )

    divisor = Decimal(10) ** decimals

    total = total_raw / divisor

    processed = db.execute(
        """
        SELECT COUNT(*)
        FROM processed
        WHERE mint = ?
        """,
        (mint,),
    ).fetchone()[0]

    print()
    print("============================================")
    print(" VERIFIED X1 BURN SUMMARY")
    print("============================================")
    print(f"Token:             {symbol}")
    print(f"Mint:              {mint}")
    print(f"Decimals:          {decimals}")
    print(f"Txs processed:     {processed:,}")
    print(f"Burn instructions: {len(rows):,}")
    print(f"Burned tokens:     {total:,.9f} {symbol}")
    print(f"Rounded burned:    {round_token_amount(total):,} {symbol}")
    print("============================================")


# ============================================================
# SCANNER
# ============================================================

def scan(
    symbol,
    mint,
    decimals,
    workers,
    max_signatures,
):
    signatures = get_signatures(
        mint,
        max_signatures=max_signatures,
    )

    db = open_db()

    already_done = {
        row[0]
        for row in db.execute(
            """
            SELECT signature
            FROM processed
            WHERE mint = ?
            """,
            (mint,),
        )
    }

    pending = [
        item["signature"]
        for item in signatures
        if item["signature"] not in already_done
    ]

    print()
    print(f"Token:              {symbol}")
    print(f"Mint:               {mint}")
    print(f"Successful history: {len(signatures):,}")
    print(f"Already cached:     {len(already_done):,}")
    print(f"Remaining:          {len(pending):,}")
    print(f"Workers:            {workers}")
    print()

    if not pending:
        print("No new transactions need scanning.")
        print_summary(
            db,
            symbol,
            mint,
            decimals,
        )
        db.close()
        return

    completed = 0
    errors = 0

    # Work in batches so we do not create tens of thousands
    # of futures in memory at once.
    batch_size = 500

    for start in range(
        0,
        len(pending),
        batch_size,
    ):
        batch = pending[
            start:start + batch_size
        ]

        with ThreadPoolExecutor(
            max_workers=workers
        ) as executor:

            futures = {
                executor.submit(
                    fetch_transaction,
                    signature,
                    mint,
                ): signature
                for signature in batch
            }

            for future in as_completed(futures):
                signature = futures[future]

                try:
                    sig, burns = future.result()

                    save_result(
                        db,
                        mint,
                        sig,
                        burns,
                    )

                    completed += 1

                except Exception as exc:
                    errors += 1

                    print(
                        f"RPC error "
                        f"{signature[:12]}...: "
                        f"{exc}",
                        flush=True,
                    )

                if completed % 50 == 0:
                    db.commit()

                if completed % 100 == 0:
                    print(
                        f"Processed this run: "
                        f"{completed:,}/"
                        f"{len(pending):,} "
                        f"| RPC errors: "
                        f"{errors:,}",
                        flush=True,
                    )

        db.commit()

    print_summary(
        db,
        symbol,
        mint,
        decimals,
    )

    if errors:
        print()
        print(
            f"{errors:,} RPC requests were not "
            "successfully retrieved."
        )
        print(
            "Run the same command again; "
            "cached transactions will be skipped "
            "and missing ones retried."
        )

    db.close()


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Scan verified standard token burns "
            "for any token on X1."
        )
    )

    parser.add_argument(
        "token",
        help=(
            "XDEX symbol such as AGI/XENCAT "
            "or an X1 mint address"
        ),
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Concurrent RPC workers (default: 6)",
    )

    parser.add_argument(
        "--max-signatures",
        type=int,
        default=None,
        help=(
            "Only inspect this many recent "
            "signatures; useful for testing"
        ),
    )

    args = parser.parse_args()

    symbol, mint = resolve_token(
        args.token
    )

    token_info = get_token_info(mint)

    decimals = token_info["decimals"]

    print()
    print("============================================")
    print(" X1 GENERIC BURN SCANNER")
    print("============================================")
    print(f"Token:            {symbol}")
    print(f"Mint:             {mint}")
    print(f"Decimals:         {decimals}")

    mint_authority = token_info[
        "mint_authority"
    ]

    print(
        "Mint authority:   "
        + (
            "REVOKED"
            if mint_authority is None
            else str(mint_authority)
        )
    )

    print("============================================")
    print()

    scan(
        symbol=symbol,
        mint=mint,
        decimals=decimals,
        workers=max(1, args.workers),
        max_signatures=args.max_signatures,
    )


if __name__ == "__main__":
    main()
