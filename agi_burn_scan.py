import sqlite3
import time
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

RPC = "https://rpc.mainnet.x1.xyz"
AGI_MINT = "7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER"

WORKERS = 6
DB_FILE = "agi_burn_scan.db"


def rpc(method, params, retries=4):
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

            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(0.5 * (2 ** attempt))
                continue

            r.raise_for_status()
            data = r.json()

            if "error" in data:
                raise RuntimeError(data["error"])

            return data.get("result")

        except Exception:
            if attempt == retries - 1:
                raise

            time.sleep(0.5 * (2 ** attempt))


def get_decimals():
    result = rpc("getTokenSupply", [AGI_MINT])
    return int(result["value"]["decimals"])


def get_all_signatures():
    results = []
    before = None

    while True:
        options = {"limit": 1000}

        if before:
            options["before"] = before

        batch = rpc(
            "getSignaturesForAddress",
            [AGI_MINT, options],
        ) or []

        if not batch:
            break

        # Failed transactions cannot produce successful burns.
        successful = [
            item for item in batch
            if item.get("err") is None
        ]

        results.extend(successful)

        print(
            f"Successful signatures collected: {len(results):,}",
            flush=True,
        )

        if len(batch) < 1000:
            break

        before = batch[-1]["signature"]

    return results


def extract_burns(tx, signature):
    burns = []

    if not tx:
        return burns

    meta = tx.get("meta") or {}

    # Absolutely do not count failed transactions.
    if meta.get("err") is not None:
        return burns

    def inspect(ix, location):
        if not isinstance(ix, dict):
            return

        parsed = ix.get("parsed")

        if not isinstance(parsed, dict):
            return

        ix_type = str(parsed.get("type", "")).lower()

        if ix_type not in ("burn", "burnchecked"):
            return

        info = parsed.get("info") or {}

        if str(info.get("mint", "")) != AGI_MINT:
            return

        token_amount = info.get("tokenAmount") or {}

        raw = (
            token_amount.get("amount")
            or info.get("amount")
        )

        if raw is None:
            return

        burns.append({
            "key": f"{signature}:{location}",
            "signature": signature,
            "type": ix_type,
            "raw": str(raw),
            "authority": str(info.get("authority") or ""),
        })

    message = (
        tx.get("transaction", {})
        .get("message", {})
    )

    for i, ix in enumerate(message.get("instructions", [])):
        inspect(ix, f"top:{i}")

    for group_i, group in enumerate(meta.get("innerInstructions") or []):
        for ix_i, ix in enumerate(group.get("instructions", [])):
            inspect(ix, f"inner:{group_i}:{ix_i}")

    return burns


def fetch_transaction(signature):
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

    return signature, extract_burns(tx, signature)


def open_db():
    db = sqlite3.connect(DB_FILE)

    db.execute("""
        CREATE TABLE IF NOT EXISTS processed (
            signature TEXT PRIMARY KEY
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS burns (
            burn_key TEXT PRIMARY KEY,
            signature TEXT NOT NULL,
            type TEXT NOT NULL,
            raw_amount TEXT NOT NULL,
            authority TEXT
        )
    """)

    db.commit()
    return db


def save_result(db, signature, burns):
    for burn in burns:
        db.execute(
            """
            INSERT OR IGNORE INTO burns
            (burn_key, signature, type, raw_amount, authority)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                burn["key"],
                burn["signature"],
                burn["type"],
                burn["raw"],
                burn["authority"],
            ),
        )

    db.execute(
        "INSERT OR IGNORE INTO processed(signature) VALUES (?)",
        (signature,),
    )


def print_summary(db, decimals):
    rows = db.execute(
        "SELECT raw_amount FROM burns"
    ).fetchall()

    total_raw = sum(
        Decimal(row[0]) for row in rows
    )

    divisor = Decimal(10) ** decimals
    total = total_raw / divisor

    print()
    print("==========================================")
    print(" VERIFIED AGI BURN SUMMARY")
    print("==========================================")
    print(f"Burn instructions: {len(rows):,}")
    print(f"Lifetime burned:   {total:,.9f} AGI")
    print(f"Rounded burned:    {round(total):,} AGI")
    print("==========================================")


def main():
    decimals = get_decimals()

    print(f"AGI decimals: {decimals}")
    print("Collecting AGI transaction signatures...")

    signatures = get_all_signatures()

    db = open_db()

    already_done = {
        row[0]
        for row in db.execute(
            "SELECT signature FROM processed"
        )
    }

    pending = [
        item["signature"]
        for item in signatures
        if item["signature"] not in already_done
    ]

    print()
    print(f"Successful signatures: {len(signatures):,}")
    print(f"Already processed:     {len(already_done):,}")
    print(f"Remaining to inspect:  {len(pending):,}")
    print()

    completed = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(fetch_transaction, sig): sig
            for sig in pending
        }

        for future in as_completed(futures):
            sig = futures[future]

            try:
                signature, burns = future.result()
                save_result(db, signature, burns)
                completed += 1

            except Exception as exc:
                errors += 1
                print(
                    f"RPC error {sig[:12]}...: {exc}",
                    flush=True,
                )

            if completed % 50 == 0:
                db.commit()

            if completed % 100 == 0:
                print(
                    f"Processed this run: {completed:,}/{len(pending):,} "
                    f"| RPC errors: {errors:,}",
                    flush=True,
                )

    db.commit()

    print_summary(db, decimals)

    if errors:
        print()
        print(
            f"{errors:,} transactions could not be retrieved. "
            "Run this script again to retry them."
        )

    db.close()


if __name__ == "__main__":
    main()
